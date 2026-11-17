from app.core.config import Settings
from app.services.url_safety import check_url_safety


def test_google_published_phishing_test_vector():
    settings = Settings(safe_browsing_api_key="", virustotal_api_key="")
    result = check_url_safety("https://testsafebrowsing.appspot.com/s/phishing.html", settings)
    assert result.verdict == "phishing"
    assert result.classification == "high"
    assert result.source == "google_published_test_vector"
    assert "SOCIAL_ENGINEERING" in result.threats
    assert any("Live Google Safe Browsing API was not called" in item for item in result.limitations)


def test_unknown_url_without_keys_is_unavailable_not_invented():
    settings = Settings(safe_browsing_api_key="", virustotal_api_key="")
    result = check_url_safety("https://example.com/maybe-bad", settings)
    assert result.verdict == "unavailable"
    assert result.classification == "inconclusive"
    assert result.threats == []


def test_phishing_url_creates_high_risk_report(client):
    token = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Safety Analyst",
            "email": "safety@example.com",
            "password": "correct-horse-battery",
            "accepted_terms": True,
        },
    ).json()["access_token"]
    response = client.post(
        "/api/v1/urls",
        headers={"Authorization": f"Bearer {token}"},
        json={"url": "https://testsafebrowsing.appspot.com/s/phishing.html"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["classification"] == "high"
    module = next(item for item in body["modules"] if item["module"] == "url_reputation")
    assert module["status"] == "completed"
    assert module["finding_label"] == "phishing"
    assert module["confidence"] is None
    assert any("published Safe Browsing test vector" in item for item in body["warnings"] + [body["summary"]])
