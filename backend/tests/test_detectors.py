from app.core.config import Settings
from app.services.detectors.image_models import _normalize_label
from app.services.detectors.runtime import run_visual_detectors
from app.services.detectors.types import DetectorOutcome, VisualDetectionBundle


def test_normalize_label_maps_common_tokens():
    assert _normalize_label("Fake", "image_forensics") == "deepfake"
    assert _normalize_label("artificial", "ai_image_detection") == "ai_generated"
    assert _normalize_label("Real", "ai_image_detection") == "real_predicted"


def test_run_visual_detectors_respects_disable_flag():
    settings = Settings(enable_ml_detectors=False)
    bundle = run_visual_detectors(
        settings=settings,
        payload=b"\x89PNG\r\n\x1a\n",
        format_id="png",
        category="image",
    )
    assert all(item.status == "unavailable" for item in bundle.outcomes)
    assert bundle.classification_hint is None
    assert bundle.ai_generation["status"] == "unavailable"


def test_run_visual_detectors_image_with_mocked_classifiers(monkeypatch):
    settings = Settings(enable_ml_detectors=True)

    def fake_classify(payload, model_id, module):
        if "Deep-Fake" in model_id or module == "image_forensics":
            return DetectorOutcome(
                module=module,
                status="completed",
                finding_label="deepfake",
                confidence=0.91,
                model_name=model_id,
                model_version="test",
                limitations="mock",
            )
        return DetectorOutcome(
            module=module,
            status="completed",
            finding_label="ai_generated",
            confidence=0.88,
            model_name=model_id,
            model_version="test",
            limitations="mock",
        )

    monkeypatch.setattr(
        "app.services.detectors.runtime.classify_image_bytes",
        fake_classify,
    )
    bundle = run_visual_detectors(
        settings=settings,
        payload=b"fake-image-bytes",
        format_id="png",
        category="image",
    )
    assert isinstance(bundle, VisualDetectionBundle)
    assert bundle.classification_hint == "high"
    assert bundle.ai_generation["status"] == "completed"
    assert bundle.manipulation["status"] == "completed"
    assert bundle.ai_stage[0] == "done"
    completed = [item for item in bundle.outcomes if item.status == "completed"]
    assert {item.module for item in completed} == {"image_forensics", "ai_content_detection"}


def test_upload_stores_mocked_detector_results(client, monkeypatch):
    def fake_run_visual_detectors(*, settings, payload, format_id, category):
        return VisualDetectionBundle(
            outcomes=[
                DetectorOutcome(
                    module="image_forensics",
                    status="completed",
                    finding_label="real_predicted",
                    confidence=0.77,
                    model_name="mock/deepfake",
                    model_version="t1",
                    limitations="mock deepfake model",
                ),
                DetectorOutcome(
                    module="video_forensics",
                    status="unavailable",
                    limitations="Still image.",
                ),
                DetectorOutcome(
                    module="ai_content_detection",
                    status="completed",
                    finding_label="real_predicted",
                    confidence=0.66,
                    model_name="mock/ai",
                    model_version="t1",
                    limitations="mock ai model",
                ),
            ],
            content_stage=("done", "Mocked detectors ran."),
            ai_stage=("done", "Mock AI model completed."),
            forensics_stage=("done", "Mock deepfake model completed."),
            ai_generation={
                "status": "completed",
                "finding_label": "real_predicted",
                "confidence": 0.66,
                "evidence": ["mock"],
                "limitations": "mock",
            },
            manipulation={
                "status": "completed",
                "finding_label": "real_predicted",
                "confidence": 0.77,
                "evidence": ["mock"],
                "limitations": "mock",
            },
            classification_hint=None,
        )

    monkeypatch.setattr(
        "app.services.analysis.run_visual_detectors",
        fake_run_visual_detectors,
    )
    token = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Detector Tester",
            "email": "detectors@example.com",
            "password": "correct-horse-battery",
            "accepted_terms": True,
        },
    ).json()["access_token"]
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + (13).to_bytes(4, "big")
        + b"IHDR"
        + (4).to_bytes(4, "big")
        + (4).to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
        + b"\x00\x00\x00\x00"
    )
    response = client.post(
        "/api/v1/files",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("sample.png", payload, "image/png")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["classification"] == "inconclusive"
    by_module = {item["module"]: item for item in body["modules"]}
    assert by_module["image_forensics"]["status"] == "completed"
    assert by_module["image_forensics"]["confidence"] == 0.77
    assert by_module["ai_content_detection"]["status"] == "completed"
    assert by_module["ai_content_detection"]["confidence"] == 0.66
    assert any(stage["id"] == "ai" and stage["state"] == "done" for stage in body["stages"])
