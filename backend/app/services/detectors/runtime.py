"""Visual detector orchestration for images and sampled video frames."""

from __future__ import annotations

from app.core.config import Settings
from app.services.detectors.frames import extract_jpeg_frames
from app.services.detectors.image_models import classify_image_bytes, default_model_ids, probe_image_classifier
from app.services.detectors.types import DetectorOutcome, VisualDetectionBundle

_IMAGE_FORMATS = {"png", "jpeg", "jpg", "webp", "gif"}
_VIDEO_FORMATS = {"iso_bmff", "mp4", "mov", "avi", "ebml", "mkv", "webm"}


def detector_runtime_status(settings: Settings) -> dict[str, dict]:
    ai_id, deepfake_id = default_model_ids(settings)
    ai_ok, ai_detail = probe_image_classifier(ai_id) if settings.enable_ml_detectors else (False, "ML detectors disabled.")
    df_ok, df_detail = (
        probe_image_classifier(deepfake_id) if settings.enable_ml_detectors else (False, "ML detectors disabled.")
    )
    try:
        import cv2  # noqa: F401

        cv2_present = True
    except Exception:
        cv2_present = False
    return {
        "image_forensics": {
            "ready": bool(settings.enable_ml_detectors and df_ok),
            "detail": df_detail if settings.enable_ml_detectors else "ENABLE_ML_DETECTORS is false.",
            "model_id": deepfake_id,
        },
        "ai_image": {
            "ready": bool(settings.enable_ml_detectors and ai_ok),
            "detail": ai_detail if settings.enable_ml_detectors else "ENABLE_ML_DETECTORS is false.",
            "model_id": ai_id,
        },
        "video_forensics": {
            "ready": bool(settings.enable_ml_detectors and cv2_present and (ai_ok or df_ok)),
            "detail": (
                "Frame sampling plus image detectors."
                if cv2_present and (ai_ok or df_ok)
                else "Needs OpenCV and at least one loaded image detector."
            ),
            "model_id": ai_id,
        },
    }


def run_visual_detectors(
    *,
    settings: Settings,
    payload: bytes,
    format_id: str,
    category: str,
) -> VisualDetectionBundle:
    if not settings.enable_ml_detectors:
        return _unavailable_bundle("ENABLE_ML_DETECTORS is false. No detector score was produced.")

    ai_id, deepfake_id = default_model_ids(settings)
    is_image = format_id in _IMAGE_FORMATS or category == "image"
    is_video = format_id in _VIDEO_FORMATS or category == "video"

    if is_image:
        return _run_image_bundle(payload, ai_id, deepfake_id)
    if is_video:
        return _run_video_bundle(payload, settings, ai_id, deepfake_id)
    return _unavailable_bundle("No visual detector applies to this file type.")


def _run_image_bundle(payload: bytes, ai_id: str, deepfake_id: str) -> VisualDetectionBundle:
    ai = classify_image_bytes(payload, ai_id, module="ai_image_detection")
    # Store under image_forensics for deepfake-oriented model.
    deepfake = classify_image_bytes(payload, deepfake_id, module="image_forensics")
    # Also expose ai module id used by reports as part of ai detection stage.
    outcomes = [
        DetectorOutcome(
            module="image_forensics",
            status=deepfake.status,
            finding_label=deepfake.finding_label,
            confidence=deepfake.confidence,
            model_name=deepfake.model_name,
            model_version=deepfake.model_version,
            limitations=deepfake.limitations or "Deepfake image model unavailable.",
            details=deepfake.details,
        ),
        DetectorOutcome(
            module="video_forensics",
            status="unavailable",
            limitations="Video frame pipeline was not used for a still image.",
        ),
        DetectorOutcome(
            module="ai_content_detection",
            status=ai.status,
            finding_label=ai.finding_label,
            confidence=ai.confidence,
            model_name=ai.model_name,
            model_version=ai.model_version,
            limitations=ai.limitations or "AI-image model unavailable.",
            details=ai.details,
        ),
    ]
    ai_section = _section_from_outcome(ai, kind="ai_generation")
    manip_section = _section_from_outcome(deepfake, kind="manipulation")
    hint = _classification_hint([ai, deepfake])
    ai_stage = (
        ("done", f"AI-image model {ai.model_name or ai_id}: {ai.finding_label} ({ai.confidence}).")
        if ai.status == "completed"
        else ("unavailable", ai.limitations or "AI-image detector did not run.")
    )
    forensics_stage = (
        ("done", f"Deepfake image model {deepfake.model_name or deepfake_id}: {deepfake.finding_label} ({deepfake.confidence}).")
        if deepfake.status == "completed"
        else ("unavailable", deepfake.limitations or "Deepfake image detector did not run.")
    )
    content_stage = ("done", "Still-image pixels were passed to registered detectors.")
    return VisualDetectionBundle(
        outcomes=outcomes,
        content_stage=content_stage,
        ai_stage=ai_stage,
        forensics_stage=forensics_stage,
        ai_generation=ai_section,
        manipulation=manip_section,
        classification_hint=hint,
    )


def _run_video_bundle(payload: bytes, settings: Settings, ai_id: str, deepfake_id: str) -> VisualDetectionBundle:
    frames, error = extract_jpeg_frames(payload, max_frames=settings.video_detector_max_frames)
    if error or not frames:
        unavailable = DetectorOutcome(
            module="video_forensics",
            status="unavailable",
            limitations=error or "No frames available.",
        )
        return VisualDetectionBundle(
            outcomes=[
                unavailable,
                DetectorOutcome(
                    module="image_forensics",
                    status="unavailable",
                    limitations="Video frame extraction did not produce images for the deepfake model.",
                ),
                DetectorOutcome(
                    module="ai_content_detection",
                    status="unavailable",
                    limitations="Video frame extraction did not produce images for the AI-image model.",
                ),
            ],
            content_stage=("unavailable", error or "No frames available."),
            ai_stage=("unavailable", "AI detection skipped because frames were unavailable."),
            forensics_stage=("unavailable", "Video forensics skipped because frames were unavailable."),
            ai_generation={"status": "unavailable", "evidence": [], "limitations": error or "No frames."},
            manipulation={"status": "unavailable", "evidence": [], "limitations": error or "No frames."},
            classification_hint=None,
        )

    ai_results = [classify_image_bytes(frame, ai_id, module="ai_image_detection") for frame in frames]
    df_results = [classify_image_bytes(frame, deepfake_id, module="image_forensics") for frame in frames]
    completed_ai = [item for item in ai_results if item.status == "completed" and item.confidence is not None]
    completed_df = [item for item in df_results if item.status == "completed" and item.confidence is not None]

    ai_flagged = [item for item in completed_ai if item.finding_label == "ai_generated"]
    df_flagged = [item for item in completed_df if item.finding_label in {"deepfake", "ai_generated"}]

    # Do not average confidences. Report counts and the max observed confidence separately.
    ai_max = max((item.confidence or 0.0) for item in ai_flagged) if ai_flagged else None
    df_max = max((item.confidence or 0.0) for item in df_flagged) if df_flagged else None

    video_outcome = DetectorOutcome(
        module="video_forensics",
        status="completed" if completed_ai or completed_df else "unavailable",
        finding_label=(
            "synthetic_indicators"
            if ai_flagged or df_flagged
            else "no_synthetic_indicators"
            if completed_ai or completed_df
            else None
        ),
        confidence=None,  # frame confidences stay in details; no fused video score
        model_name=ai_id,
        model_version="frame-sample",
        limitations=(
            "Video analysis sampled frames and ran image detectors. Lip-sync and temporal models are not integrated. "
            "Frame confidences are listed separately and are not averaged into one authenticity score."
        ),
        details={
            "frames_sampled": len(frames),
            "ai_model": ai_id,
            "deepfake_model": deepfake_id,
            "ai_flagged_frames": len(ai_flagged),
            "deepfake_flagged_frames": len(df_flagged),
            "ai_max_confidence_among_flagged": ai_max,
            "deepfake_max_confidence_among_flagged": df_max,
            "ai_frame_findings": [
                {"finding_label": item.finding_label, "confidence": item.confidence}
                for item in completed_ai
            ],
            "deepfake_frame_findings": [
                {"finding_label": item.finding_label, "confidence": item.confidence}
                for item in completed_df
            ],
        },
    )
    image_outcome = DetectorOutcome(
        module="image_forensics",
        status="completed" if completed_df else "unavailable",
        finding_label=("deepfake" if df_flagged else "real_predicted") if completed_df else None,
        confidence=df_max if df_flagged else (completed_df[0].confidence if completed_df else None),
        model_name=deepfake_id,
        model_version="frame-sample",
        limitations=(
            "Deepfake labels come from sampled video frames, not a dedicated temporal deepfake model."
            if completed_df
            else (df_results[0].limitations if df_results else "Deepfake model unavailable.")
        ),
        details={"frames_sampled": len(frames), "flagged_frames": len(df_flagged)},
    )
    ai_outcome = DetectorOutcome(
        module="ai_content_detection",
        status="completed" if completed_ai else "unavailable",
        finding_label=("ai_generated" if ai_flagged else "real_predicted") if completed_ai else None,
        confidence=ai_max if ai_flagged else (completed_ai[0].confidence if completed_ai else None),
        model_name=ai_id,
        model_version="frame-sample",
        limitations=(
            "AI-generation labels come from sampled frames. Confidences were not averaged across frames."
            if completed_ai
            else (ai_results[0].limitations if ai_results else "AI-image model unavailable.")
        ),
        details={"frames_sampled": len(frames), "flagged_frames": len(ai_flagged)},
    )

    hint = None
    if (ai_flagged or df_flagged) and ((ai_max or 0) >= 0.85 or (df_max or 0) >= 0.85):
        hint = "high"
    elif ai_flagged or df_flagged:
        hint = "medium"

    return VisualDetectionBundle(
        outcomes=[image_outcome, video_outcome, ai_outcome],
        content_stage=("done", f"Sampled {len(frames)} video frame(s) for detector input."),
        ai_stage=(
            ("done", f"AI-image detector flagged {len(ai_flagged)}/{len(frames)} frames.")
            if completed_ai
            else ("unavailable", ai_outcome.limitations)
        ),
        forensics_stage=(
            ("done", f"Deepfake detector flagged {len(df_flagged)}/{len(frames)} frames.")
            if completed_df
            else ("unavailable", image_outcome.limitations)
        ),
        ai_generation=_section_from_outcome(ai_outcome, kind="ai_generation"),
        manipulation=_section_from_outcome(image_outcome, kind="manipulation"),
        classification_hint=hint,
    )


def _section_from_outcome(outcome: DetectorOutcome, *, kind: str) -> dict:
    if outcome.status != "completed":
        return {
            "status": "unavailable",
            "evidence": [],
            "limitations": outcome.limitations or "Detector did not run.",
        }
    return {
        "status": "completed",
        "finding_label": outcome.finding_label,
        "confidence": outcome.confidence,
        "model_name": outcome.model_name,
        "model_version": outcome.model_version,
        "evidence": [
            f"{kind} model prediction: {outcome.finding_label} "
            f"(confidence={outcome.confidence})."
        ],
        "limitations": outcome.limitations,
        "details": outcome.details,
    }


def _classification_hint(outcomes: list[DetectorOutcome]) -> str | None:
    synthetic = [
        item
        for item in outcomes
        if item.status == "completed"
        and item.finding_label in {"ai_generated", "deepfake"}
        and item.confidence is not None
    ]
    if not synthetic:
        return None
    peak = max(item.confidence or 0.0 for item in synthetic)
    if peak >= 0.85:
        return "high"
    if peak >= 0.65:
        return "medium"
    return "inconclusive"


def _unavailable_bundle(reason: str) -> VisualDetectionBundle:
    return VisualDetectionBundle(
        outcomes=[
            DetectorOutcome(module="image_forensics", status="unavailable", limitations=reason),
            DetectorOutcome(module="video_forensics", status="unavailable", limitations=reason),
            DetectorOutcome(module="ai_content_detection", status="unavailable", limitations=reason),
        ],
        content_stage=("unavailable", reason),
        ai_stage=("unavailable", reason),
        forensics_stage=("unavailable", reason),
        ai_generation={"status": "unavailable", "evidence": [], "limitations": reason},
        manipulation={"status": "unavailable", "evidence": [], "limitations": reason},
        classification_hint=None,
    )
