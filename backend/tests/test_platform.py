BASE_READY = {"file_signature", "sha256", "container_metadata", "url_oembed", "url_reputation"}


def test_platform_does_not_invent_detection(client):
    response = client.get("/api/v1/platform")
    assert response.status_code == 200
    body = response.json()
    assert body["phase"] == 3
    assert body["auth_configured"] is True
    assert "Detection scores are not simulated." in body["guarantees"]

    ready = {engine["id"] for engine in body["engines"] if engine["status"] == "ready"}
    assert BASE_READY.issubset(ready)
    for engine in body["engines"]:
        assert "confidence" not in engine
        assert engine["detail"]
        if engine["id"] == "scam_investigation":
            assert "Gemini is not called" in engine["detail"]
        if engine["id"] in {"image_forensics", "video_forensics"} and engine["status"] == "ready":
            assert "not fused" in engine["detail"].lower() or "No fused" in engine["detail"]


def test_services_match_the_phase_plan(client):
    body = client.get("/api/v1/platform").json()
    by_id = {service["id"]: service for service in body["services"]}
    assert by_id["authentication"]["state"] == "implemented"
    assert by_id["file_upload"]["state"] == "implemented"
    assert by_id["metadata_extraction"]["state"] == "implemented"
    assert by_id["analysis_jobs"]["state"] == "implemented"
    assert by_id["url_intake"]["state"] == "implemented"
    assert by_id["ai_detection"]["state"] in {"foundation", "implemented"}
    assert by_id["image_processing"]["state"] in {"foundation", "implemented"}
    assert by_id["video_processing"]["state"] in {"foundation", "implemented"}
    assert by_id["reporting"]["state"] == "foundation"
    assert len(by_id) == 13
