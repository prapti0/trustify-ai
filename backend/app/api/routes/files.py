import json
from collections import Counter
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user
from app.api.schemas import (
    ActivityPoint,
    CountPoint,
    DashboardResponse,
    DuplicatePublic,
    EvidencePublic,
    JobSummary,
    MetadataPublic,
    ModulePublic,
    ReportResponse,
    ScamBody,
    StagePublic,
    UrlBody,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.domain.enums import DetectionStatus, RiskClassification
from app.models import (
    AnalysisJob,
    DetectionResult,
    DuplicateMatch,
    FileMetadata,
    ForensicEvidence,
    InvestigationReport,
    SecurityScanResult,
    UploadedFile,
    User,
)
from app.services.storage import LocalObjectStorage
from app.services.uploads import UploadRejected, category_for, clean_filename, extension_of, store_upload

router = APIRouter()

_NOTES = {
    "ai_generated_indicators": (
        "Completed model findings labeled as AI-generated. "
        "Zero means no completed AI-generated label was stored — not that files are human-made."
    ),
    "suspicious_files": "Reports classified high or critical. Inconclusive reports are not counted as suspicious.",
    "deepfake_indicators": (
        "Completed findings labeled as deepfake. "
        "Zero means no completed deepfake label was stored — not that media is authentic."
    ),
    "security_threats": "Completed scans with a malicious finding. A scan that did not run is not counted as clean.",
}


def _owned_job(db: Session, user: User, job_id: UUID) -> AnalysisJob:
    job = db.get(AnalysisJob, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Analysis not found."})
    return job


def _summary(db: Session, job: AnalysisJob) -> JobSummary:
    uploaded = db.get(UploadedFile, job.file_id)
    report = db.scalar(select(InvestigationReport).where(InvestigationReport.job_id == job.id))
    metadata = db.scalar(select(FileMetadata).where(FileMetadata.file_id == job.file_id)) if uploaded else None
    category = "unknown"
    if metadata and isinstance(metadata.extra, dict) and metadata.extra.get("category"):
        category = str(metadata.extra["category"])
    elif uploaded:
        category = category_for(uploaded.detected_format, extension_of(uploaded.original_filename))
    classification = report.overall_classification.value if report and report.overall_classification else None
    return JobSummary(
        job_id=job.id,
        file_id=job.file_id,
        file_name=uploaded.original_filename if uploaded else "Removed file",
        file_type=uploaded.detected_format if uploaded and uploaded.detected_format else "unknown",
        category=category,
        size_bytes=uploaded.size_bytes if uploaded else 0,
        sha256=uploaded.sha256 if uploaded else "",
        created_at=job.created_at,
        status=job.status.value,
        classification=classification,
    )


@router.post("/files", response_model=ReportResponse)
async def upload_file(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportResponse:
    settings = get_settings()
    payload = await _read_limited(file, settings.max_upload_bytes)
    try:
        job = store_upload(db, settings, user, file.filename or "upload", payload)
    except UploadRejected as exc:
        raise HTTPException(status_code=exc.status, detail={"error": exc.code, "message": exc.message}) from exc
    return _report_payload(db, user, job.id)


@router.post("/urls", response_model=ReportResponse)
def analyze_url(
    body: UrlBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportResponse:
    from app.domain.enums import FileSource
    from app.services.url_analysis import UrlAnalysisError, analyze_public_url
    from app.services.url_safety import UrlSafetyError, check_url_safety

    settings = get_settings()
    try:
        evidence = analyze_public_url(body.url)
    except UrlAnalysisError as exc:
        if exc.code == "url_login_walled":
            raise HTTPException(status_code=exc.status, detail={"error": exc.code, "message": exc.message}) from exc
        if exc.code != "url_provider_unsupported":
            raise HTTPException(status_code=exc.status, detail={"error": exc.code, "message": exc.message}) from exc
        try:
            safety = check_url_safety(body.url, settings)
        except UrlSafetyError as safety_exc:
            raise HTTPException(
                status_code=safety_exc.status,
                detail={"error": safety_exc.code, "message": safety_exc.message},
            ) from safety_exc
        payload = json.dumps(
            {
                "kind": "url_safety",
                "url": safety.url,
                "verdict": safety.verdict,
                "source": safety.source,
                "threats": safety.threats,
                "evidence": safety.evidence,
                "limitations": safety.limitations,
                "classification": safety.classification,
            },
            indent=2,
        ).encode("utf-8")
        try:
            job = store_upload(
                db,
                settings,
                user,
                "url-safety-report.json",
                payload,
                source=FileSource.URL,
                source_url=safety.url,
                metadata_extra={
                    "url_safety": {
                        "url": safety.url,
                        "verdict": safety.verdict,
                        "source": safety.source,
                        "threats": safety.threats,
                        "evidence": safety.evidence,
                        "limitations": safety.limitations,
                        "classification": safety.classification,
                    },
                    "intake_limitations": safety.limitations,
                },
            )
        except UploadRejected as upload_exc:
            raise HTTPException(
                status_code=upload_exc.status,
                detail={"error": upload_exc.code, "message": upload_exc.message},
            ) from upload_exc
        return _report_payload(db, user, job.id)

    url_meta = {
        "provider_id": evidence.provider_id,
        "canonical_url": evidence.canonical_url,
        "media_id": evidence.media_id,
        "title": evidence.title,
        "author_name": evidence.author_name,
        "author_url": evidence.author_url,
        "provider_name": evidence.provider_name,
        "thumbnail_url": evidence.thumbnail_url,
        "limitations": evidence.limitations,
        "submitted_url": body.url.strip(),
    }
    if evidence.thumbnail_bytes and evidence.thumbnail_filename:
        payload = evidence.thumbnail_bytes
        filename = evidence.thumbnail_filename
    else:
        # Keep an analyzable artifact without claiming the video was downloaded.
        payload = json.dumps(
            {
                "provider": f"{evidence.provider_id}_oembed",
                "canonical_url": evidence.canonical_url,
                "media_id": evidence.media_id,
                "title": evidence.title,
                "author_name": evidence.author_name,
                "note": "Thumbnail bytes were unavailable. Video bitstream was not downloaded.",
            },
            indent=2,
        ).encode("utf-8")
        filename = f"{evidence.provider_id}-{evidence.media_id}-oembed.json"

    try:
        job = store_upload(
            db,
            settings,
            user,
            filename,
            payload,
            source=FileSource.URL,
            source_url=evidence.canonical_url,
            metadata_extra={"url_source": url_meta, "intake_limitations": evidence.limitations},
        )
    except UploadRejected as exc:
        raise HTTPException(status_code=exc.status, detail={"error": exc.code, "message": exc.message}) from exc
    return _report_payload(db, user, job.id)


@router.get("/jobs", response_model=list[JobSummary])
def list_jobs(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[JobSummary]:
    jobs = db.scalars(
        select(AnalysisJob).where(AnalysisJob.user_id == user.id).order_by(AnalysisJob.created_at.desc())
    ).all()
    return [_summary(db, job) for job in jobs]


@router.get("/jobs/{job_id}", response_model=ReportResponse)
def get_job(job_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ReportResponse:
    _owned_job(db, user, job_id)
    return _report_payload(db, user, job_id)


@router.delete("/jobs/{job_id}")
def delete_job(job_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    job = _owned_job(db, user, job_id)
    uploaded = db.get(UploadedFile, job.file_id)
    if uploaded is not None:
        try:
            LocalObjectStorage(Path(get_settings().local_storage_dir)).delete(uploaded.stored_key)
        except Exception:
            pass
        db.delete(uploaded)
    else:
        db.delete(job)
    db.commit()
    return {"status": "deleted"}


@router.get("/files/{file_id}/content")
def file_content(file_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    uploaded = db.get(UploadedFile, file_id)
    if uploaded is None or uploaded.user_id != user.id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "File not found."})
    payload = LocalObjectStorage(Path(get_settings().local_storage_dir)).read(uploaded.stored_key)
    media = _media_type(uploaded.detected_format)
    return Response(
        content=payload,
        media_type=media,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'inline; filename="{clean_filename(uploaded.original_filename)}"',
        },
    )


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DashboardResponse:
    jobs = db.scalars(select(AnalysisJob).where(AnalysisJob.user_id == user.id)).all()
    files = db.scalars(select(UploadedFile).where(UploadedFile.user_id == user.id)).all()
    reports = []
    for job in jobs:
        report = db.scalar(select(InvestigationReport).where(InvestigationReport.job_id == job.id))
        if report:
            reports.append(report)
    results = []
    scans = []
    for job in jobs:
        results.extend(db.scalars(select(DetectionResult).where(DetectionResult.job_id == job.id)).all())
        scans.extend(db.scalars(select(SecurityScanResult).where(SecurityScanResult.job_id == job.id)).all())
    ai_labels = {"ai_generated", "synthetic"}
    deepfake_labels = {"deepfake", "face_swap"}
    ai_count = sum(
        1
        for row in results
        if row.status == DetectionStatus.COMPLETED and (row.finding_label or "") in ai_labels
    )
    deepfake_count = sum(
        1
        for row in results
        if row.status == DetectionStatus.COMPLETED and (row.finding_label or "") in deepfake_labels
    )
    suspicious = sum(
        1
        for report in reports
        if report.overall_classification in {RiskClassification.HIGH, RiskClassification.CRITICAL}
    )
    threats = sum(1 for scan in scans if _scan_is_malicious(scan))
    type_counts: Counter[str] = Counter()
    for uploaded in files:
        metadata = db.scalar(select(FileMetadata).where(FileMetadata.file_id == uploaded.id))
        if metadata and isinstance(metadata.extra, dict) and metadata.extra.get("category"):
            type_counts[str(metadata.extra["category"])] += 1
        else:
            type_counts[uploaded.detected_format or "unknown"] += 1
    risk_counts: Counter[str] = Counter()
    for report in reports:
        label = report.overall_classification.value if report.overall_classification else "inconclusive"
        risk_counts[label] += 1
    detection_counts: Counter[str] = Counter(row.status.value for row in results)
    activity: Counter[str] = Counter(job.created_at.date().isoformat() for job in jobs if job.created_at)
    recent = sorted(jobs, key=lambda job: job.created_at or "", reverse=True)[:8]
    return DashboardResponse(
        total_files=len(files),
        ai_generated_indicators=ai_count,
        suspicious_files=suspicious,
        deepfake_indicators=deepfake_count,
        security_threats=threats,
        completed_investigations=sum(1 for job in jobs if job.status.value == "completed"),
        notes=_NOTES,
        recent=[_summary(db, job) for job in recent],
        file_types=[CountPoint(label=label, count=count) for label, count in sorted(type_counts.items())],
        risk_distribution=[CountPoint(label=label, count=count) for label, count in sorted(risk_counts.items())],
        detection_results=[CountPoint(label=label, count=count) for label, count in sorted(detection_counts.items())],
        activity=[ActivityPoint(date=day, count=activity[day]) for day in sorted(activity)],
    )


@router.get("/duplicates", response_model=list[DuplicatePublic])
def duplicates(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[DuplicatePublic]:
    file_ids = list(db.scalars(select(UploadedFile.id).where(UploadedFile.user_id == user.id)).all())
    rows = (
        db.scalars(select(DuplicateMatch).where(DuplicateMatch.file_id.in_(file_ids))).all() if file_ids else []
    )
    payload = []
    for row in rows:
        matched = db.get(UploadedFile, row.matched_file_id)
        if matched is None or matched.user_id != user.id:
            continue
        original = db.get(UploadedFile, row.file_id)
        payload.append(
            DuplicatePublic(
                file_id=row.file_id,
                file_name=original.original_filename if original else "Removed file",
                matched_file_id=matched.id,
                matched_file_name=matched.original_filename,
                match_kind=row.match_kind.value,
                distance=row.distance,
            )
        )
    return payload


@router.post("/investigations/scam")
def scam_investigation(body: ScamBody, _: User = Depends(get_current_user)) -> dict:
    return {
        "status": "unavailable",
        "summary": (
            "The scam investigation model is not integrated. "
            "This response is not a finding about any person or business."
        ),
        "unverified_input": body.content.strip()[:500],
        "evidence": [],
        "risk_indicators": [],
        "recommended_steps": [
            "Do not treat this submission as verified.",
            "Keep the original message and headers if you need a later review.",
        ],
    }


@router.get("/reports/{job_id}/pdf")
def report_pdf(job_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    _owned_job(db, user, job_id)
    raise HTTPException(
        status_code=501,
        detail={"error": "pdf_unavailable", "message": "PDF report export is not implemented."},
    )


def _report_payload(db: Session, user: User, job_id: UUID) -> ReportResponse:
    job = _owned_job(db, user, job_id)
    summary = _summary(db, job)
    report = db.scalar(select(InvestigationReport).where(InvestigationReport.job_id == job.id))
    modules = db.scalars(select(DetectionResult).where(DetectionResult.job_id == job.id)).all()
    evidence = db.scalars(select(ForensicEvidence).where(ForensicEvidence.job_id == job.id)).all()
    matches = db.scalars(select(DuplicateMatch).where(DuplicateMatch.file_id == job.file_id)).all()
    duplicates = []
    for row in matches:
        matched = db.get(UploadedFile, row.matched_file_id)
        if matched and matched.user_id == user.id:
            duplicates.append(
                DuplicatePublic(
                    file_id=job.file_id,
                    file_name=summary.file_name,
                    matched_file_id=matched.id,
                    matched_file_name=matched.original_filename,
                    match_kind=row.match_kind.value,
                    distance=row.distance,
                )
            )
    stages = []
    if isinstance(job.modules, list):
        for stage in job.modules:
            if isinstance(stage, dict):
                stages.append(
                    StagePublic(
                        id=str(stage.get("id", "")),
                        label=str(stage.get("label", "")),
                        state=str(stage.get("state", "")),
                        detail=str(stage.get("detail", "")),
                    )
                )
    sections = {}
    if report:
        sections = {
            "ai_generation": report.ai_generation,
            "manipulation": report.manipulation,
            "malware": report.malware,
            "provenance": report.provenance,
            "similarity": report.similarity,
            "scam": report.scam,
        }
    metadata_row = db.scalar(select(FileMetadata).where(FileMetadata.file_id == job.file_id))
    metadata = None
    if metadata_row and (
        metadata_row.container
        or metadata_row.width
        or metadata_row.duration_seconds is not None
        or metadata_row.extra
    ):
        metadata = MetadataPublic(
            container=metadata_row.container,
            codec=metadata_row.codec,
            duration_seconds=metadata_row.duration_seconds,
            width=metadata_row.width,
            height=metadata_row.height,
            exif=metadata_row.exif,
            extra=metadata_row.extra if isinstance(metadata_row.extra, dict) else None,
        )
    warnings = []
    unverified_claims: list[str] = []
    steps = [
        "Treat this classification as inconclusive.",
        "Do not describe the file as authentic, synthetic, malicious, or clean from this report alone.",
    ]
    if summary.status == "completed":
        warnings.append(
            "AI detection, malware scanning, provenance checks, and perceptual similarity did not run."
        )
        meta_extra = metadata.extra if metadata and isinstance(metadata.extra, dict) else {}
        if isinstance(meta_extra.get("intake_limitations"), list):
            warnings.extend(str(item) for item in meta_extra["intake_limitations"])
        if report and isinstance(report.scam, dict):
            claims = report.scam.get("unverified_claims")
            if isinstance(claims, list):
                unverified_claims = [str(item) for item in claims]
    elif summary.status in {"queued", "processing"}:
        warnings.append("Analysis is still running. Module findings are incomplete until the job finishes.")
        steps = ["Wait for processing to finish before treating any module as final."]
    elif summary.status == "failed":
        warnings.append("Analysis failed. Incomplete stages are not clean findings.")
        steps = ["Retry the upload or inspect the processing stages for the failure detail."]
    return ReportResponse(
        job_id=summary.job_id,
        file_id=summary.file_id,
        file_name=summary.file_name,
        file_type=summary.file_type,
        category=summary.category,
        size_bytes=summary.size_bytes,
        sha256=summary.sha256,
        created_at=summary.created_at,
        status=summary.status,
        classification=summary.classification,
        summary=report.summary if report else None,
        limitations=report.limitations if report else "No report was stored yet.",
        metadata=metadata,
        stages=stages,
        modules=[
            ModulePublic(
                module=row.module,
                status=row.status.value,
                finding_label=row.finding_label,
                confidence=row.confidence,
                limitations=row.limitations,
                details=row.details,
            )
            for row in modules
        ],
        evidence=[
            EvidencePublic(
                category=row.category,
                observation=row.observation,
                severity=row.severity,
                source_module=row.source_module,
            )
            for row in evidence
        ],
        sections=sections,
        duplicates=duplicates,
        warnings=warnings,
        unverified_claims=unverified_claims,
        recommended_steps=steps,
    )


async def _read_limited(upload: UploadFile, limit: int) -> bytes:
    if upload.size is not None and upload.size > limit:
        raise HTTPException(
            status_code=413,
            detail={"error": "file_too_large", "message": "File size exceeds the configured limit."},
        )
    await upload.seek(0)
    payload = await run_in_threadpool(upload.file.read)
    if len(payload) > limit:
        raise HTTPException(
            status_code=413,
            detail={"error": "file_too_large", "message": "File size exceeds the configured limit."},
        )
    if not payload:
        raise HTTPException(status_code=400, detail={"error": "empty_file", "message": "The file is empty."})
    return payload


def _media_type(format_id: str | None) -> str:
    return {
        "png": "image/png",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
        "pdf": "application/pdf",
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "flac": "audio/flac",
        "aac": "audio/aac",
        "mp4": "video/mp4",
        "iso_bmff": "video/mp4",
        "avi": "video/x-msvideo",
        "ebml": "video/webm",
        "txt": "text/plain; charset=utf-8",
        "csv": "text/plain; charset=utf-8",
        "json": "text/plain; charset=utf-8",
        "xml": "text/plain; charset=utf-8",
    }.get(format_id or "", "application/octet-stream")


def _scan_is_malicious(scan: SecurityScanResult) -> bool:
    if scan.status != DetectionStatus.COMPLETED or not isinstance(scan.findings, dict):
        return False
    verdict = str(scan.findings.get("verdict", "")).lower()
    return verdict == "malicious"
