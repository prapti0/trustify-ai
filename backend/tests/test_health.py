def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "trustify-ai"}


def test_ready_uses_database(client):
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json()["checks"]["database"] == "ok"


def test_request_id_is_sanitized(client):
    response = client.get("/api/v1/health", headers={"X-Request-ID": "bad id"})
    assert response.status_code == 200
    request_id = response.headers["X-Request-ID"]
    assert " " not in request_id
    assert len(request_id) > 8


def test_request_id_is_preserved_when_safe(client):
    response = client.get("/api/v1/health", headers={"X-Request-ID": "job-123"})
    assert response.headers["X-Request-ID"] == "job-123"


def test_unknown_route_is_not_a_server_error(client):
    response = client.get("/api/v1/uploads")
    assert response.status_code == 404


def test_analysis_requires_sign_in(client):
    response = client.get("/api/v1/dashboard")
    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "unauthorized"
