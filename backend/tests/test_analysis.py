def _register(client, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Ada Lovelace",
            "email": email,
            "password": "correct-horse-battery",
            "accepted_terms": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _upload(client, token: str, name: str = "sample.png", payload: bytes | None = None):
    body = payload if payload is not None else b"\x89PNG\r\n\x1a\nrest"
    return client.post(
        "/api/v1/files",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (name, body, "application/octet-stream")},
    )


def test_register_and_reject_duplicate_email(client):
    first = _register(client, "ada@example.com")
    assert first["user"]["email"] == "ada@example.com"
    again = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
            "password": "correct-horse-battery",
            "accepted_terms": True,
        },
    )
    assert again.status_code == 409


def test_upload_stays_inconclusive_without_scores(client):
    token = _register(client, "analyst@example.com")["access_token"]
    # Valid PNG with IHDR so metadata extraction has real dimensions.
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + (13).to_bytes(4, "big")
        + b"IHDR"
        + (4).to_bytes(4, "big")
        + (4).to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
        + b"\x00\x00\x00\x00"
    )
    response = _upload(client, token, payload=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["classification"] == "inconclusive"
    assert "risk_score" not in body
    assert body["sha256"]
    assert body["metadata"]["width"] == 4
    assert body["metadata"]["height"] == 4
    assert all(module["confidence"] is None for module in body["modules"])
    malware = next(module for module in body["modules"] if module["module"] == "malware_scanner")
    assert malware["status"] == "unavailable"
    meta = next(module for module in body["modules"] if module["module"] == "container_metadata")
    assert meta["status"] == "completed"
    assert meta["confidence"] is None
    assert any(stage["id"] == "ai" and stage["state"] == "unavailable" for stage in body["stages"])
    assert any(stage["id"] == "metadata" and stage["state"] == "done" for stage in body["stages"])


def test_dashboard_counts_records(client):
    token = _register(client, "dash@example.com")["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    before = client.get("/api/v1/dashboard", headers=headers)
    assert before.status_code == 200
    assert before.json()["total_files"] == 0
    assert before.json()["recent"] == []
    uploaded = _upload(client, token)
    assert uploaded.status_code == 200
    after = client.get("/api/v1/dashboard", headers=headers).json()
    assert after["total_files"] == 1
    assert after["ai_generated_indicators"] == 0
    assert after["deepfake_indicators"] == 0
    assert after["security_threats"] == 0
    assert after["suspicious_files"] == 0
    assert after["completed_investigations"] == 1
    assert after["file_types"] == [{"label": "image", "count": 1}]
    assert after["risk_distribution"] == [{"label": "inconclusive", "count": 1}]


def test_unsupported_file_and_private_url(client):
    token = _register(client, "reject@example.com")["access_token"]
    rejected = _upload(client, token, "run.exe", b"MZ\x00\x00")
    assert rejected.status_code == 400
    assert rejected.json()["detail"]["error"] == "unsupported_format"
    url = client.post(
        "/api/v1/urls",
        headers={"Authorization": f"Bearer {token}"},
        json={"url": "https://example.com/video.mp4"},
    )
    assert url.status_code == 200, url.text
    body = url.json()
    assert body["classification"] == "inconclusive"
    reputation = next(module for module in body["modules"] if module["module"] == "url_reputation")
    assert reputation["status"] == "unavailable"
    assert reputation["finding_label"] == "unavailable"


def test_users_cannot_read_each_other(client):
    owner = _register(client, "owner@example.com")
    uploaded = _upload(client, owner["access_token"])
    job_id = uploaded.json()["job_id"]
    other = _register(client, "other@example.com")
    hidden = client.get(f"/api/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {other['access_token']}"})
    assert hidden.status_code == 404


def test_exact_duplicate_is_limited_to_the_account(client):
    token = _register(client, "dup@example.com")["access_token"]
    payload = b"\x89PNG\r\n\x1a\nsame"
    assert _upload(client, token, "one.png", payload).status_code == 200
    second = _upload(client, token, "two.png", payload)
    assert second.status_code == 200
    body = second.json()
    assert len(body["duplicates"]) == 1
    assert body["duplicates"][0]["match_kind"] == "exact_hash"
    assert body["duplicates"][0]["file_name"] == "two.png"
    pdf = client.get(
        f"/api/v1/reports/{body['job_id']}/pdf",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert pdf.status_code == 501
