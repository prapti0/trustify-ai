"""Job pipeline for integrity, metadata, and optional visual detectors."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domain.enums import DetectionStatus, JobStatus, RiskClassification
from app.models import (
    AnalysisJob,
    DetectionResult,
    DuplicateMatch,
    FileMetadata,
    ForensicEvidence,
    InvestigationReport,
    ModelVersion,
    SecurityScanResult,
    UploadedFile,
)
from app.services.detectors import run_visual_detectors
from app.services.detectors.types import VisualDetectionBundle
from app.services.metadata import extract_metadata
from app.services.storage import LocalObjectStorage

_UNAVAILABLE = (
    ("audio_forensics", "No voice or synthetic-speech model is registered."),
    ("document_forensics", "Document structure and macro inspection are not implemented."),
    ("malware_scanner", "ClamAV and YARA were not invoked. This is not a clean scan."),
    ("duplicate_perceptual", "Perceptual and embedding search are not implemented."),
    ("provenance", "C2PA, signature, and watermark verification are not implemented."),
    ("scam_investigation", "Scam investigation was not requested, and Gemini is not called."),
    ("fusion", "Findings are not fused into a score."),
)


def initial_stages(format_id: str, note: str | None) -> list[dict]:
    signature_detail = f"Identified format: {format_id}."
    if note:
        signature_detail = f"{signature_detail} {note}"
    return [
        {"id": "validation", "label": "File Validation", "state": "done", "detail": signature_detail},
        {
            "id": "metadata",
            "label": "Metadata Extraction",
            "state": "pending",
            "detail": "Waiting for the analysis worker.",
        },
        {
            "id": "content",
            "label": "Content Processing",
            "state": "pending",
            "detail": "Waiting for the analysis worker.",
        },
        {
            "id": "ai",
            "label": "AI Detection",
            "state": "pending",
            "detail": "Waiting for the analysis worker.",
        },
        {
            "id": "forensics",
            "label": "Forensic Analysis",
            "state": "pending",
            "detail": "Waiting for the analysis worker.",
        },
        {
            "id": "security",
            "label": "Security Scanning",
            "state": "pending",
            "detail": "Waiting for the analysis worker.",
        },
        {
            "id": "correlation",
            "label": "Evidence Correlation",
            "state": "pending",
            "detail": "Waiting for the analysis worker.",
        },
        {
            "id": "report",
            "label": "Report Generation",
            "state": "pending",
            "detail": "Waiting for the analysis worker.",
        },
    ]


def process_job(session: Session, settings: Settings, job_id: UUID) -> AnalysisJob:
    job = session.get(AnalysisJob, job_id)
    if job is None:
        raise ValueError("job_not_found")
    if job.status == JobStatus.COMPLETED:
        return job
    uploaded = session.get(UploadedFile, job.file_id)
    if uploaded is None:
        job.status = JobStatus.FAILED
        job.error_message = "The uploaded file record is missing."
        job.finished_at = datetime.now(timezone.utc)
        session.commit()
        return job

    job.status = JobStatus.PROCESSING
    job.started_at = datetime.now(timezone.utc)
    job.error_message = None
    _set_stage(job, "metadata", "processing", "Extracting container metadata.")
    session.commit()

    try:
        storage = LocalObjectStorage(Path(settings.local_storage_dir))
        payload = storage.read(uploaded.stored_key)
    except Exception:
        job.status = JobStatus.FAILED
        job.error_message = "Stored file bytes could not be read."
        job.finished_at = datetime.now(timezone.utc)
        _set_stage(job, "metadata", "failed", "Stored file bytes could not be read.")
        session.commit()
        return job

    metadata_row = session.scalar(select(FileMetadata).where(FileMetadata.file_id == uploaded.id))
    extra = dict(metadata_row.extra) if metadata_row and isinstance(metadata_row.extra, dict) else {}
    extension = str(extra.get("extension") or Path(uploaded.original_filename).suffix.lstrip("."))
    format_id = uploaded.detected_format or extension
    extracted = extract_metadata(payload, format_id, extension)

    if metadata_row is None:
        metadata_row = FileMetadata(file_id=uploaded.id, extra=extra)
        session.add(metadata_row)
    metadata_row.container = extracted.container
    metadata_row.codec = extracted.codec
    metadata_row.duration_seconds = extracted.duration_seconds
    metadata_row.width = extracted.width
    metadata_row.height = extracted.height
    metadata_row.exif = extracted.exif
    merged = {**extra, **extracted.extra, "extraction_notes": extracted.notes}
    metadata_row.extra = merged
    metadata_row.extracted_at = datetime.now(timezone.utc)

    meta_detail = _metadata_detail(extracted)
    url_source = extra.get("url_source") if isinstance(extra.get("url_source"), dict) else None
    url_safety = extra.get("url_safety") if isinstance(extra.get("url_safety"), dict) else None
    if url_source is None and isinstance(extra.get("youtube"), dict):
        # Backward-compatible key from the first YouTube-only intake.
        url_source = {"provider_id": "youtube", **extra["youtube"]}
    if url_source:
        provider = str(url_source.get("provider_name") or url_source.get("provider_id") or "URL")
        meta_detail = f"{provider} oEmbed title/author recorded. Thumbnail container: {meta_detail}"
    elif url_safety:
        meta_detail = f"URL reputation check recorded via {url_safety.get('source')}."
    _set_stage(job, "metadata", "done", meta_detail)
    visual: VisualDetectionBundle | None = None
    category = str(extra.get("category") or "")
    if url_safety and not url_source:
        _set_stage(
            job,
            "content",
            "done",
            "No media file was downloaded. This job is a URL reputation investigation.",
        )
        _set_stage(job, "ai", "unavailable", "URL reputation jobs do not run visual detectors.")
        _set_stage(job, "forensics", "done", "Signature and hash checks finished.")
    else:
        # Uploaded media, or public URL thumbnail bytes (not the remote video stream).
        visual = run_visual_detectors(
            settings=settings,
            payload=payload,
            format_id=format_id,
            category=category or ("image" if url_source else ""),
        )
        if url_source:
            _set_stage(
                job,
                "content",
                "done" if visual.content_stage[0] == "done" else "unavailable",
                (
                    "Remote video frames were not downloaded. Detectors ran on the public thumbnail only. "
                    f"{visual.content_stage[1]}"
                ),
            )
        else:
            _set_stage(job, "content", visual.content_stage[0], visual.content_stage[1])
        _set_stage(job, "ai", visual.ai_stage[0], visual.ai_stage[1])
        forensics_detail = visual.forensics_stage[1]
        if visual.forensics_stage[0] != "done":
            forensics_detail = f"Signature and hash checks finished. {forensics_detail}"
        _set_stage(
            job,
            "forensics",
            "done" if visual.forensics_stage[0] in {"done", "unavailable"} else visual.forensics_stage[0],
            forensics_detail,
        )
    if url_safety and url_safety.get("verdict") not in {None, "unavailable"}:
        _set_stage(
            job,
            "security",
            "done",
            f"URL reputation verdict: {url_safety.get('verdict')} (source: {url_safety.get('source')}).",
        )
    else:
        _set_stage(
            job,
            "security",
            "unavailable",
            "Malware scanners were not invoked. This is not a clean result."
            if not url_safety
            else "URL reputation could not produce a live verdict. This is not a clean finding.",
        )

    duplicates = session.scalars(
        select(DuplicateMatch).where(DuplicateMatch.file_id == uploaded.id)
    ).all()
    _set_stage(
        job,
        "correlation",
        "done",
        f"Exact hash matches in this account: {len(duplicates)}. Separate findings were not averaged.",
    )
    _set_stage(job, "report", "processing", "Writing detection rows and investigation summary.")

    session.execute(delete(DetectionResult).where(DetectionResult.job_id == job.id))
    session.execute(delete(SecurityScanResult).where(SecurityScanResult.job_id == job.id))
    session.execute(delete(ForensicEvidence).where(ForensicEvidence.job_id == job.id))
    session.execute(delete(InvestigationReport).where(InvestigationReport.job_id == job.id))

    note = extra.get("signature_note")
    note_text = str(note) if note else None
    report_status = _write_results(
        session,
        job.id,
        format_id,
        uploaded.sha256,
        note_text,
        extracted,
        url_source=url_source,
        url_safety=url_safety,
        source_url=uploaded.source_url,
        visual=visual,
    )
    _write_report(
        session,
        job.id,
        uploaded.original_filename,
        format_id,
        uploaded.sha256,
        len(duplicates),
        extracted,
        url_source=url_source,
        url_safety=url_safety,
        source_url=uploaded.source_url,
        category=str(extra.get("category") or ""),
        visual=visual,
    )
    if report_status == "completed_with_detectors":
        _set_stage(
            job,
            "report",
            "done",
            "Report includes model predictions where detectors ran. Confidences were not fused into one authenticity score.",
        )
    elif url_safety and url_safety.get("verdict") not in {None, "unavailable"}:
        _set_stage(job, "report", "done", "Report includes URL reputation evidence.")
    else:
        _set_stage(
            job,
            "report",
            "done",
            "The classification remains limited because required detectors did not fully run.",
        )

    job.status = JobStatus.COMPLETED
    job.finished_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(job)
    return job


def enqueue_or_run(session: Session, settings: Settings, job_id: UUID) -> AnalysisJob:
    if settings.analysis_mode == "celery":
        from app.workers.celery_app import analyze_job

        analyze_job.delay(str(job_id))
        job = session.get(AnalysisJob, job_id)
        assert job is not None
        return job
    return process_job(session, settings, job_id)


def _set_stage(job: AnalysisJob, stage_id: str, state: str, detail: str) -> None:
    stages = list(job.modules) if isinstance(job.modules, list) else []
    updated = []
    found = False
    for stage in stages:
        if isinstance(stage, dict) and stage.get("id") == stage_id:
            updated.append({**stage, "state": state, "detail": detail})
            found = True
        else:
            updated.append(stage)
    if not found:
        updated.append({"id": stage_id, "label": stage_id, "state": state, "detail": detail})
    job.modules = updated


def _metadata_detail(extracted) -> str:
    parts = []
    if extracted.width and extracted.height:
        parts.append(f"Dimensions {extracted.width}x{extracted.height}.")
    if extracted.duration_seconds is not None:
        parts.append(f"Duration {extracted.duration_seconds}s.")
    if extracted.container:
        parts.append(f"Container {extracted.container}.")
    if extracted.codec:
        parts.append(f"Codec/brand {extracted.codec}.")
    if extracted.extra.get("member_count") is not None:
        parts.append(f"Archive members listed: {extracted.extra['member_count']}.")
    if extracted.extra.get("page_object_count") is not None:
        parts.append(f"PDF page object markers: {extracted.extra['page_object_count']}.")
    if extracted.extra.get("line_count") is not None:
        parts.append(f"Text lines: {extracted.extra['line_count']}.")
    parts.extend(extracted.notes)
    if not parts:
        return "Metadata extraction finished with no container fields."
    return " ".join(parts)


def _write_results(
    session: Session,
    job_id: UUID,
    format_id: str,
    digest: str,
    note: str | None,
    extracted,
    *,
    url_source: dict | None = None,
    url_safety: dict | None = None,
    source_url: str | None = None,
    visual: VisualDetectionBundle | None = None,
) -> str:
    session.add(
        DetectionResult(
            job_id=job_id,
            module="file_signature",
            status=DetectionStatus.COMPLETED,
            finding_label=format_id,
            confidence=None,
            limitations="Magic-byte identification does not judge whether content is synthetic.",
            details={"note": note} if note else {},
        )
    )
    session.add(
        DetectionResult(
            job_id=job_id,
            module="sha256",
            status=DetectionStatus.COMPLETED,
            finding_label="hash_recorded",
            confidence=None,
            limitations="A hash confirms integrity against a known value. It is not an authenticity score.",
            details={"sha256": digest},
        )
    )
    session.add(
        DetectionResult(
            job_id=job_id,
            module="container_metadata",
            status=DetectionStatus.COMPLETED,
            finding_label="metadata_recorded",
            confidence=None,
            limitations=(
                "Container metadata describes structure. Missing fields are inconclusive and are not "
                "treated as proof of synthetic media."
            ),
            details={
                "container": extracted.container,
                "codec": extracted.codec,
                "width": extracted.width,
                "height": extracted.height,
                "duration_seconds": extracted.duration_seconds,
                "extra": extracted.extra,
                "notes": extracted.notes,
            },
        )
    )
    if url_source:
        provider = str(url_source.get("provider_name") or url_source.get("provider_id") or "URL")
        media_id = url_source.get("media_id") or url_source.get("video_id")
        session.add(
            DetectionResult(
                job_id=job_id,
                module="url_oembed",
                status=DetectionStatus.COMPLETED,
                finding_label="public_metadata_recorded",
                confidence=None,
                limitations=(
                    "oEmbed metadata is public page data. It is not a deepfake verdict and does not "
                    "prove authenticity of the video."
                ),
                details={
                    "source_url": source_url,
                    "provider_id": url_source.get("provider_id"),
                    "canonical_url": url_source.get("canonical_url"),
                    "media_id": media_id,
                    "title": url_source.get("title"),
                    "author_name": url_source.get("author_name"),
                    "thumbnail_url": url_source.get("thumbnail_url"),
                    "limitations": url_source.get("limitations") or [],
                },
            )
        )
        session.add(
            ForensicEvidence(
                job_id=job_id,
                category="url",
                observation=(
                    f"Public {provider} metadata recorded for media id {media_id}. "
                    "The video bitstream was not fetched."
                ),
                severity="info",
                source_module="url_oembed",
            )
        )
    if url_safety:
        verdict = str(url_safety.get("verdict") or "unavailable")
        status = DetectionStatus.COMPLETED if verdict != "unavailable" else DetectionStatus.UNAVAILABLE
        session.add(
            DetectionResult(
                job_id=job_id,
                module="url_reputation",
                status=status,
                finding_label=verdict,
                confidence=None,
                limitations="; ".join(str(item) for item in (url_safety.get("limitations") or [])),
                details={
                    "source_url": source_url or url_safety.get("url"),
                    "source": url_safety.get("source"),
                    "threats": url_safety.get("threats") or [],
                    "evidence": url_safety.get("evidence") or [],
                },
            )
        )
        for item in url_safety.get("evidence") or []:
            session.add(
                ForensicEvidence(
                    job_id=job_id,
                    category="url_reputation",
                    observation=str(item),
                    severity="warning" if verdict in {"phishing", "malware", "unwanted"} else "info",
                    source_module="url_reputation",
                )
            )

    detectors_completed = False
    if visual is not None:
        for outcome in visual.outcomes:
            status = {
                "completed": DetectionStatus.COMPLETED,
                "failed": DetectionStatus.FAILED,
            }.get(outcome.status, DetectionStatus.UNAVAILABLE)
            confidence = outcome.confidence if status == DetectionStatus.COMPLETED else None
            session.add(
                DetectionResult(
                    job_id=job_id,
                    module=outcome.module,
                    status=status,
                    finding_label=outcome.finding_label,
                    confidence=confidence,
                    model_name=outcome.model_name,
                    model_version=outcome.model_version,
                    limitations=outcome.limitations or "No limitation text provided.",
                    details=outcome.details,
                )
            )
            if status == DetectionStatus.COMPLETED:
                detectors_completed = True
                if outcome.model_name:
                    existing = session.scalar(
                        select(ModelVersion).where(
                            ModelVersion.name == outcome.model_name,
                            ModelVersion.version == (outcome.model_version or "unknown"),
                        )
                    )
                    if existing is None:
                        session.add(
                            ModelVersion(
                                name=outcome.model_name,
                                version=outcome.model_version or "unknown",
                                task=outcome.module,
                                license_name="See model card on Hugging Face",
                                artifact_uri=f"https://huggingface.co/{outcome.model_name}",
                                metrics={"registered_by": "detector_runtime"},
                                is_active=True,
                            )
                        )
                session.add(
                    ForensicEvidence(
                        job_id=job_id,
                        category="model_prediction",
                        observation=(
                            f"{outcome.module} predicted {outcome.finding_label} "
                            f"with confidence {outcome.confidence}."
                        ),
                        severity="warning"
                        if outcome.finding_label in {"ai_generated", "deepfake", "synthetic_indicators"}
                        else "info",
                        source_module=outcome.module,
                    )
                )
    else:
        for module, limitation in (
            ("image_forensics", "No image or deepfake model ran for this job."),
            ("video_forensics", "No video frame detector ran for this job."),
        ):
            session.add(
                DetectionResult(
                    job_id=job_id,
                    module=module,
                    status=DetectionStatus.UNAVAILABLE,
                    confidence=None,
                    limitations=limitation,
                )
            )

    for module, limitation in _UNAVAILABLE:
        session.add(
            DetectionResult(
                job_id=job_id,
                module=module,
                status=DetectionStatus.UNAVAILABLE,
                confidence=None,
                limitations=limitation,
            )
        )
    if url_safety and url_safety.get("verdict") not in {None, "unavailable"}:
        session.add(
            SecurityScanResult(
                job_id=job_id,
                engine=str(url_safety.get("source") or "url_reputation"),
                status=DetectionStatus.COMPLETED,
                findings={
                    "verdict": url_safety.get("verdict"),
                    "threats": url_safety.get("threats") or [],
                    "evidence": url_safety.get("evidence") or [],
                },
            )
        )
    else:
        session.add(
            SecurityScanResult(
                job_id=job_id,
                engine="clamav",
                status=DetectionStatus.UNAVAILABLE,
                findings={"evidence": [], "reason": "ClamAV was not invoked."},
            )
        )
    session.add(
        ForensicEvidence(
            job_id=job_id,
            category="integrity",
            observation=f"SHA-256 is {digest}. Detected format is {format_id}.",
            severity="info",
            source_module="sha256",
        )
    )
    if extracted.width and extracted.height:
        session.add(
            ForensicEvidence(
                job_id=job_id,
                category="metadata",
                observation=f"Recorded dimensions {extracted.width}x{extracted.height}.",
                severity="info",
                source_module="container_metadata",
            )
        )
    if extracted.duration_seconds is not None:
        session.add(
            ForensicEvidence(
                job_id=job_id,
                category="metadata",
                observation=f"Recorded duration {extracted.duration_seconds} seconds.",
                severity="info",
                source_module="container_metadata",
            )
        )
    for note in extracted.notes:
        session.add(
            ForensicEvidence(
                job_id=job_id,
                category="metadata",
                observation=note,
                severity="info",
                source_module="container_metadata",
            )
        )
    if detectors_completed:
        session.add(
            ForensicEvidence(
                job_id=job_id,
                category="coverage",
                observation=(
                    "Visual detectors produced model predictions. Malware scanning, provenance, "
                    "and perceptual similarity remain unavailable. Confidences were not fused."
                ),
                severity="info",
                source_module="orchestrator",
            )
        )
    else:
        session.add(
            ForensicEvidence(
                job_id=job_id,
                category="coverage",
                observation="AI detection, malware scanning, provenance, and perceptual similarity did not run.",
                severity="warning",
                source_module="orchestrator",
            )
        )
    return "completed_with_detectors" if detectors_completed else "completed"


def _write_report(
    session: Session,
    job_id: UUID,
    filename: str,
    format_id: str,
    digest: str,
    duplicates: int,
    extracted,
    *,
    url_source: dict | None = None,
    url_safety: dict | None = None,
    source_url: str | None = None,
    category: str = "",
    visual: VisualDetectionBundle | None = None,
) -> None:
    unavailable = {
        "status": "unavailable",
        "evidence": [],
        "limitations": "This module did not run. Absence of a result is not a clean finding.",
    }
    meta_bits = []
    if extracted.width and extracted.height:
        meta_bits.append(f"{extracted.width}x{extracted.height}")
    if extracted.duration_seconds is not None:
        meta_bits.append(f"{extracted.duration_seconds}s")
    meta_sentence = f" Extracted metadata: {', '.join(meta_bits)}." if meta_bits else ""
    classification = RiskClassification.INCONCLUSIVE
    malware_section = unavailable
    ai_section = unavailable
    manipulation_section = unavailable
    if url_source:
        provider = str(url_source.get("provider_name") or url_source.get("provider_id") or "URL")
        summary = (
            f"{provider} URL {source_url or url_source.get('canonical_url')} was analyzed with public oEmbed "
            f"and the published thumbnail ({filename}, {format_id}). "
            f"Reported title: {url_source.get('title')!r}. Author: {url_source.get('author_name')!r}. "
            f"Thumbnail SHA-256 is {digest}. Exact hash matches in this account: {duplicates}."
            f"{meta_sentence} "
            "The remote video stream was not downloaded, so no frame-level deepfake verdict exists."
        )
        limitations = (
            f"This report is inconclusive for video authenticity. {provider} DRM and login walls are not bypassed. "
            "oEmbed title and author fields are unverified claims. "
            "Missing metadata is not proof of synthetic content."
        )
        scam = {
            "status": "not_requested",
            "evidence": [],
            "unverified_claims": [
                f"Title from oEmbed: {url_source.get('title')}",
                f"Author from oEmbed: {url_source.get('author_name')}",
                f"Provider: {provider}",
            ],
            "limitations": "No person or business was labeled a scammer.",
        }
    elif url_safety:
        verdict = str(url_safety.get("verdict") or "unavailable")
        class_name = str(url_safety.get("classification") or "inconclusive")
        classification = {
            "high": RiskClassification.HIGH,
            "medium": RiskClassification.MEDIUM,
            "low": RiskClassification.LOW,
            "critical": RiskClassification.CRITICAL,
        }.get(class_name, RiskClassification.INCONCLUSIVE)
        summary = (
            f"URL {source_url or url_safety.get('url')} reputation check finished with verdict {verdict!r} "
            f"from source {url_safety.get('source')!r}. "
            f"Evidence: {' '.join(str(item) for item in (url_safety.get('evidence') or [])) or 'none recorded.'}"
        )
        limitations = " ".join(str(item) for item in (url_safety.get("limitations") or []))
        malware_section = {
            "status": "completed" if verdict != "unavailable" else "unavailable",
            "verdict": verdict,
            "threats": url_safety.get("threats") or [],
            "evidence": url_safety.get("evidence") or [],
            "limitations": limitations,
        }
        scam = {
            "status": "completed" if verdict in {"phishing", "malware", "unwanted"} else "partial",
            "evidence": url_safety.get("evidence") or [],
            "risk_indicators": url_safety.get("threats") or [],
            "unverified_claims": [f"Submitted URL: {source_url or url_safety.get('url')}"],
            "limitations": "This is a URL reputation signal. No person or business was labeled a scammer.",
        }
    else:
        summary = (
            f"{filename} was stored and identified as {format_id}. "
            f"SHA-256 is {digest}. Exact hash matches already in this account: {duplicates}."
            f"{meta_sentence} "
            "No completed visual-detector prediction was stored for this job."
        )
        limitations = (
            "This report is inconclusive when detectors do not complete. "
            "It must not be read as proof that the file is authentic, synthetic, malicious, or clean. "
            "Missing metadata is not proof of synthetic content."
        )
        scam = {
            "status": "not_requested",
            "evidence": [],
            "limitations": "No claim about a person or business was assessed.",
        }
    if visual is not None:
        ai_section = visual.ai_generation
        manipulation_section = visual.manipulation
        if visual.classification_hint in {"high", "medium", "low"} and classification == RiskClassification.INCONCLUSIVE:
            classification = {
                "high": RiskClassification.HIGH,
                "medium": RiskClassification.MEDIUM,
                "low": RiskClassification.LOW,
            }[visual.classification_hint]
        completed_bits = []
        for outcome in visual.outcomes:
            if outcome.status == "completed":
                completed_bits.append(
                    f"{outcome.module}={outcome.finding_label}"
                    + (f"({outcome.confidence})" if outcome.confidence is not None else "")
                )
        if completed_bits and not url_safety:
            detector_clause = (
                f" Detector outputs: {', '.join(completed_bits)}. "
                "These are model predictions with limitations, not fused authenticity proof."
            )
            if url_source:
                summary = f"{summary.rstrip()}{detector_clause}"
                limitations = (
                    f"{limitations} Detector confidences were not averaged into one authenticity score. "
                    "A real_predicted label is not proof the media is authentic. "
                    "The remote video stream was still not downloaded."
                )
            else:
                summary = (
                    f"{filename} was stored and identified as {format_id}."
                    f"{meta_sentence} "
                    f"SHA-256 is {digest}. Exact hash matches in this account: {duplicates}."
                    f"{detector_clause}"
                )
                limitations = (
                    "Detector confidences were not averaged into one authenticity score. "
                    "A real_predicted label is not proof the media is authentic. "
                    "Missing malware/provenance checks remain unavailable."
                )
    session.add(
        InvestigationReport(
            job_id=job_id,
            overall_classification=classification,
            summary=summary,
            ai_generation=ai_section,
            manipulation=manipulation_section,
            malware=malware_section,
            provenance=unavailable,
            similarity={
                "status": "partial",
                "exact_hash_matches": duplicates,
                "limitations": "Only SHA-256 matches inside this account were compared.",
            },
            scam=scam,
            limitations=limitations,
        )
    )
