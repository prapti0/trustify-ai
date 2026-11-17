"""Lazy Hugging Face image classifiers. Missing packages/weights => unavailable."""

from __future__ import annotations

import io
import logging
from functools import lru_cache
from typing import Any

from app.core.config import Settings
from app.services.detectors.types import DetectorOutcome

logger = logging.getLogger(__name__)

_DEFAULT_LIMITATIONS = (
    "This is a model prediction, not proof. Compression, screenshots, and out-of-distribution "
    "media reduce reliability. Confidence values are not averaged with other modules."
)


def _packages_ready() -> tuple[bool, str | None]:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        from PIL import Image  # noqa: F401
    except Exception as exc:  # pragma: no cover - depends on optional install
        return False, f"ML packages are not installed ({exc.__class__.__name__})."
    return True, None


@lru_cache(maxsize=4)
def _load_pipeline(model_id: str) -> Any:
    from transformers import pipeline

    return pipeline(
        "image-classification",
        model=model_id,
        device=-1,
    )


def probe_image_classifier(model_id: str) -> tuple[bool, str]:
    ready, reason = _packages_ready()
    if not ready:
        return False, reason or "ML packages are not installed."
    try:
        _load_pipeline(model_id)
        return True, f"Loaded {model_id}."
    except Exception as exc:  # pragma: no cover - network/weights
        logger.info("detector_probe_failed model=%s err=%s", model_id, exc.__class__.__name__)
        return False, f"Model {model_id} could not be loaded ({exc.__class__.__name__})."


def classify_image_bytes(payload: bytes, model_id: str, module: str) -> DetectorOutcome:
    ready, reason = _packages_ready()
    if not ready:
        return DetectorOutcome(
            module=module,
            status="unavailable",
            limitations=reason or "ML packages are not installed.",
        )
    try:
        from PIL import Image
    except Exception as exc:  # pragma: no cover
        return DetectorOutcome(
            module=module,
            status="unavailable",
            limitations=f"Pillow is required ({exc.__class__.__name__}).",
        )
    try:
        image = Image.open(io.BytesIO(payload)).convert("RGB")
    except Exception:
        return DetectorOutcome(
            module=module,
            status="failed",
            limitations="Image bytes could not be decoded for the detector.",
        )
    try:
        classifier = _load_pipeline(model_id)
        raw = classifier(image)
    except Exception as exc:
        logger.info("detector_infer_failed model=%s err=%s", model_id, exc.__class__.__name__)
        return DetectorOutcome(
            module=module,
            status="unavailable",
            model_name=model_id,
            limitations=f"Detector inference failed ({exc.__class__.__name__}). No score was invented.",
        )
    if not isinstance(raw, list) or not raw:
        return DetectorOutcome(
            module=module,
            status="failed",
            model_name=model_id,
            limitations="Detector returned an empty prediction.",
        )
    top = max(raw, key=lambda item: float(item.get("score") or 0.0))
    label = str(top.get("label") or "").strip()
    score = float(top.get("score") or 0.0)
    if score < 0 or score > 1:
        return DetectorOutcome(
            module=module,
            status="failed",
            model_name=model_id,
            limitations="Detector returned a confidence outside 0–1. The value was discarded.",
        )
    finding = _normalize_label(label, module)
    return DetectorOutcome(
        module=module,
        status="completed",
        finding_label=finding,
        confidence=score,
        model_name=model_id,
        model_version="hf-revision:main",
        limitations=_DEFAULT_LIMITATIONS,
        details={
            "raw_label": label,
            "raw_scores": [
                {"label": str(item.get("label")), "score": float(item.get("score") or 0.0)}
                for item in raw
                if isinstance(item, dict)
            ],
        },
    )


def _normalize_label(label: str, module: str) -> str:
    lowered = label.lower().replace("_", " ").replace("-", " ")
    synthetic_tokens = ("artificial", "ai", "fake", "generated", "synthetic", "deepfake")
    real_tokens = ("real", "authentic", "human", "natural", "live")
    if module == "image_forensics" and any(
        token in lowered for token in ("fake", "deepfake", "synthetic", "generated", "artificial")
    ):
        return "deepfake"
    if any(token in lowered for token in synthetic_tokens):
        return "ai_generated"
    if any(token in lowered for token in real_tokens):
        return "real_predicted"
    return label.lower().replace(" ", "_")[:64] or "unlabeled"


def default_model_ids(settings: Settings) -> tuple[str, str]:
    return settings.ai_image_model_id, settings.deepfake_image_model_id
