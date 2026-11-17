from unittest.mock import MagicMock, patch

from app.services.url_analysis import UrlAnalysisError, analyze_public_url, _youtube_video_id, _vimeo_id


def test_provider_ids_parse():
    assert _youtube_video_id("https://www.youtube.com/shorts/7-4QEinx930") == "7-4QEinx930"
    assert _youtube_video_id("https://youtu.be/7-4QEinx930") == "7-4QEinx930"
    assert _vimeo_id("https://vimeo.com/123456789") == "123456789"


def test_non_supported_is_rejected():
    try:
        analyze_public_url("https://example.com/clip.mp4")
        assert False, "expected UrlAnalysisError"
    except UrlAnalysisError as exc:
        assert exc.code == "url_provider_unsupported"
        assert exc.status == 501
        assert "Vimeo" in exc.message


def test_instagram_is_login_walled():
    try:
        analyze_public_url("https://www.instagram.com/reel/AbCdEfGhIjK/")
        assert False, "expected UrlAnalysisError"
    except UrlAnalysisError as exc:
        assert exc.code == "url_login_walled"
        assert "login" in exc.message.lower()


def test_multi_provider_oembed_and_thumbnail(client):
    token = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "URL Analyst",
            "email": "url-analyst@example.com",
            "password": "correct-horse-battery",
            "accepted_terms": True,
        },
    ).json()["access_token"]
    png = (
        b"\x89PNG\r\n\x1a\n"
        + (13).to_bytes(4, "big")
        + b"IHDR"
        + (2).to_bytes(4, "big")
        + (2).to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
        + b"\x00\x00\x00\x00"
    )

    oembed_response = MagicMock()
    oembed_response.status_code = 200
    oembed_response.json.return_value = {
        "title": "Sample Clip",
        "author_name": "Sample Channel",
        "author_url": "https://vimeo.com/sample",
        "provider_name": "Vimeo",
        "thumbnail_url": "https://i.vimeocdn.com/video/123_200x150.jpg",
    }
    thumb_response = MagicMock()
    thumb_response.status_code = 200
    thumb_response.content = png

    def fake_get(url, **_kwargs):
        if "oembed" in url:
            return oembed_response
        return thumb_response

    with (
        patch("app.services.url_analysis.httpx.Client") as client_cls,
        patch("app.services.url_analysis._assert_public_hostname"),
    ):
        client_cls.return_value.__enter__.return_value.get.side_effect = fake_get
        response = client.post(
            "/api/v1/urls",
            headers={"Authorization": f"Bearer {token}"},
            json={"url": "https://vimeo.com/123456789"},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["classification"] == "inconclusive"
    assert body["metadata"]["width"] == 2
    assert any(module["module"] == "url_oembed" and module["status"] == "completed" for module in body["modules"])
    assert any(module["module"] == "video_forensics" and module["status"] == "unavailable" for module in body["modules"])
    assert any("bitstreams were not downloaded" in warning for warning in body["warnings"])
    assert any("Sample Clip" in claim for claim in body["unverified_claims"])
