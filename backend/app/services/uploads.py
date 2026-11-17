import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import StorageNotConfigured
from app.domain.enums import FileSource, JobStatus, MatchKind
from app.models import (
    AnalysisJob,
    DuplicateMatch,
    FileMetadata,
    UploadedFile,
    User,
)
from app.services.analysis import enqueue_or_run, initial_stages
from app.services.integrity import identify_signature, sha256_hex
from app.services.storage import LocalObjectStorage, assert_storage_available

_TEXT_EXTENSIONS = {"txt", "csv", "json", "xml"}
_ACCEPT = {
    "mp4": {"category": "video", "signatures": {"iso_bmff"}},
    "mov": {"category": "video", "signatures": {"iso_bmff"}},
    "avi": {"category": "video", "signatures": {"avi"}},
    "mkv": {"category": "video", "signatures": {"ebml"}},
    "webm": {"category": "video", "signatures": {"ebml"}},
    "jpg": {"category": "image", "signatures": {"jpeg"}},
    "jpeg": {"category": "image", "signatures": {"jpeg"}},
    "png": {"category": "image", "signatures": {"png"}},
    "webp": {"category": "image", "signatures": {"webp"}},
    "gif": {"category": "image", "signatures": {"gif"}},
    "mp3": {"category": "audio", "signatures": {"mp3"}},
    "wav": {"category": "audio", "signatures": {"wav"}},
    "flac": {"category": "audio", "signatures": {"flac"}},
    "aac": {"category": "audio", "signatures": set()},
    "pdf": {"category": "document", "signatures": {"pdf"}},
    "docx": {"category": "document", "signatures": {"docx"}},
    "doc": {"category": "document", "signatures": {"ole_compound"}},
    "txt": {"category": "document", "signatures": set()},
    "csv": {"category": "data", "signatures": set()},
    "xlsx": {"category": "data", "signatures": {"xlsx"}},
    "json": {"category": "data", "signatures": set()},
    "xml": {"category": "data", "signatures": set()},
    "zip": {"category": "archive", "signatures": {"zip", "docx", "xlsx"}},
    "7z": {"category": "archive", "signatures": {"7z"}},
    "tar": {"category": "archive", "signatures": {"tar"}},
    "gz": {"category": "archive", "signatures": {"gzip"}},
}


class UploadRejected(Exception):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def extension_of(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def category_for(format_id: str | None, extension: str) -> str:
    if extension in _ACCEPT:
        return str(_ACCEPT[extension]["category"])
    return "unknown"


def validate_payload(filename: str, payload: bytes) -> tuple[str, str, str | None]:
    extension = extension_of(filename)
    rule = _ACCEPT.get(extension)
    if rule is None:
        raise UploadRejected("unsupported_format", "Unsupported file format.")
    if not payload:
        raise UploadRejected("empty_file", "The file is empty.")
    signature = identify_signature(payload)
    format_id = signature.format_id if signature else extension
    allowed = rule["signatures"]
    if extension in _TEXT_EXTENSIONS:
        if signature is not None:
            raise UploadRejected(
                "signature_mismatch",
                "File content does not match the extension.",
            )
        if b"\x00" in payload:
            raise UploadRejected("unsupported_format", "Unsupported file format.")
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise UploadRejected("unsupported_format", "Text files must be UTF-8.") from exc
        if extension == "json":
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                raise UploadRejected("invalid_json", "JSON file could not be parsed.") from exc
        if extension == "xml":
            stripped = text.lstrip()
            if not stripped.startswith("<") or "<!DOCTYPE" in stripped.upper():
                raise UploadRejected("unsupported_format", "XML file could not be accepted.")
        return extension, str(rule["category"]), None
    if extension == "aac":
        if signature is not None and signature.format_id not in {"aac"}:
            raise UploadRejected("signature_mismatch", "File content does not match the extension.")
        return "aac", "audio", "AAC was accepted from the extension. No frame signature was verified."
    if signature is None or signature.format_id not in allowed:
        raise UploadRejected("signature_mismatch", "File content does not match the extension.")
    note = None
    if extension == "zip" and signature.format_id in {"docx", "xlsx"}:
        note = "The archive signature matches an Office package."
        format_id = signature.format_id
    return format_id, str(rule["category"]), note


def store_upload(
    session: Session,
    settings: Settings,
    user: User,
    filename: str,
    payload: bytes,
    *,
    source: FileSource = FileSource.UPLOAD,
    source_url: str | None = None,
    metadata_extra: dict | None = None,
) -> AnalysisJob:
    if len(payload) > settings.max_upload_bytes:
        raise UploadRejected("file_too_large", "File size exceeds the configured limit.", 413)
    try:
        assert_storage_available(settings.storage_backend)
    except StorageNotConfigured as exc:
        raise UploadRejected("storage_unavailable", exc.message, 503) from exc
    format_id, category, note = validate_payload(filename, payload)
    digest = sha256_hex(payload)
    storage = LocalObjectStorage(Path(settings.local_storage_dir))
    key = f"{user.id}/{uuid4().hex}"
    storage.put(key, payload)
    safe_name = Path(filename).name[:512] or "upload"
    uploaded = UploadedFile(
        user_id=user.id,
        original_filename=safe_name,
        stored_key=key,
        mime_type=None,
        detected_format=format_id,
        size_bytes=len(payload),
        sha256=digest,
        source=source,
        source_url=source_url,
    )
    session.add(uploaded)
    session.flush()
    extra = {"category": category, "extension": extension_of(safe_name), "signature_note": note}
    if metadata_extra:
        extra.update(metadata_extra)
    session.add(
        FileMetadata(
            file_id=uploaded.id,
            extra=extra,
        )
    )
    prior = session.scalars(
        select(UploadedFile).where(
            UploadedFile.user_id == user.id,
            UploadedFile.sha256 == digest,
            UploadedFile.id != uploaded.id,
        )
    ).all()
    for match in prior:
        session.add(
            DuplicateMatch(
                file_id=uploaded.id,
                matched_file_id=match.id,
                match_kind=MatchKind.EXACT_HASH,
                distance=0,
            )
        )
    job = AnalysisJob(
        file_id=uploaded.id,
        user_id=user.id,
        status=JobStatus.QUEUED,
        modules=initial_stages(format_id, note),
        started_at=None,
        finished_at=None,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return enqueue_or_run(session, settings, job.id)


def session_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=14)


def clean_filename(value: str) -> str:
    name = Path(value).name.replace('"', "")
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip() or "download"
    return name[:180]
