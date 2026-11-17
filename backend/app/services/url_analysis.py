"""Public URL intake for permitted metadata only. No DRM or login bypass."""

from __future__ import annotations

import ipaddress
import json
import re
import socket
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx

from app.services.integrity import identify_signature

_MAX_THUMB_BYTES = 5_000_000
_TIMEOUT = httpx.Timeout(12.0, connect=5.0)
_USER_AGENT = "TRUSTIFY-AI/0.1 (+local forensic research; public-metadata-only)"

_SUPPORTED = (
    "YouTube / Shorts",
    "Vimeo",
    "Dailymotion",
    "TikTok",
    "Reddit video posts",
)

_LOGIN_WALLED = {
    "instagram.com",
    "www.instagram.com",
    "facebook.com",
    "www.facebook.com",
    "fb.watch",
    "m.facebook.com",
}


class UrlAnalysisError(Exception):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass(frozen=True)
class PublicUrlEvidence:
    provider_id: str
    canonical_url: str
    media_id: str
    title: str
    author_name: str
    author_url: str | None
    provider_name: str
    thumbnail_url: str | None
    thumbnail_bytes: bytes | None
    thumbnail_filename: str | None
    thumbnail_format: str | None
    limitations: list[str]


@dataclass(frozen=True)
class _Provider:
    provider_id: str
    display_name: str
    oembed_endpoint: str
    match: Callable[[str], bool]
    canonical: Callable[[str, str], str]
    media_id: Callable[[str], str | None]
    thumb_allowed: Callable[[str], bool]


def analyze_public_url(url: str) -> PublicUrlEvidence:
    normalized = _normalize_http_url(url)
    host = (urlparse(normalized).hostname or "").lower()
    if host in _LOGIN_WALLED or host.endswith(".instagram.com") or host.endswith(".facebook.com"):
        raise UrlAnalysisError(
            "url_login_walled",
            "Instagram and Facebook media sit behind login walls. "
            "TRUSTIFY does not bypass login, DRM, or encryption. Download the file yourself and upload it instead.",
            501,
        )
    provider = _match_provider(normalized)
    if provider is None:
        raise UrlAnalysisError(
            "url_provider_unsupported",
            "Supported public video URL providers: "
            + ", ".join(_SUPPORTED)
            + ". Other sites are not fetched, and login walls or DRM are never bypassed.",
            501,
        )
    media_id = provider.media_id(normalized)
    if not media_id:
        raise UrlAnalysisError(
            "invalid_media_url",
            f"Could not find a media id in that {provider.display_name} URL.",
        )
    canonical = provider.canonical(normalized, media_id)
    oembed = _fetch_oembed(provider.oembed_endpoint, canonical, provider.display_name)
    thumb_url = oembed.get("thumbnail_url") if isinstance(oembed.get("thumbnail_url"), str) else None
    thumb_bytes = None
    thumb_name = None
    thumb_format = None
    limitations = [
        f"{provider.display_name} video and audio bitstreams were not downloaded.",
        "DRM, age gates, private posts, and login walls are not bypassed.",
        "Title and author fields come from public oEmbed and are unverified claims until independently checked.",
        "AI deepfake and synthetic-media detectors did not run on the video frames.",
    ]
    if thumb_url:
        try:
            thumb_bytes, thumb_name, thumb_format = _fetch_thumbnail(
                thumb_url,
                provider.provider_id,
                media_id,
                provider.thumb_allowed,
            )
        except UrlAnalysisError as exc:
            limitations.append(f"Thumbnail fetch skipped: {exc.message}")
    else:
        limitations.append(f"{provider.display_name} oEmbed did not return a thumbnail URL.")
    return PublicUrlEvidence(
        provider_id=provider.provider_id,
        canonical_url=canonical,
        media_id=media_id,
        title=str(oembed.get("title") or "")[:500],
        author_name=str(oembed.get("author_name") or "")[:200],
        author_url=str(oembed["author_url"])[:2048] if isinstance(oembed.get("author_url"), str) else None,
        provider_name=str(oembed.get("provider_name") or provider.display_name)[:100],
        thumbnail_url=thumb_url,
        thumbnail_bytes=thumb_bytes,
        thumbnail_filename=thumb_name,
        thumbnail_format=thumb_format,
        limitations=limitations,
    )


def supported_providers() -> list[str]:
    return list(_SUPPORTED)


def _normalize_http_url(url: str) -> str:
    value = url.strip()
    parsed = urlparse(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise UrlAnalysisError("invalid_url", "Enter an http or https URL.")
    if parsed.username or parsed.password:
        raise UrlAnalysisError("invalid_url", "URLs with embedded credentials are not accepted.")
    return value


def _looks_like_id(value: str, minimum: int = 6, maximum: int = 64) -> bool:
    return bool(re.fullmatch(rf"[A-Za-z0-9_-]{{{minimum},{maximum}}}", value))


def _youtube_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path or ""
    if host in {"youtu.be", "www.youtu.be"}:
        candidate = path.strip("/").split("/")[0]
        return candidate if _looks_like_id(candidate, 6, 20) else None
    shorts = re.match(r"^/shorts/([A-Za-z0-9_-]{6,})", path)
    if shorts:
        return shorts.group(1)
    embed = re.match(r"^/embed/([A-Za-z0-9_-]{6,})", path)
    if embed:
        return embed.group(1)
    query = parse_qs(parsed.query)
    if "v" in query and query["v"]:
        candidate = query["v"][0]
        return candidate if _looks_like_id(candidate, 6, 20) else None
    return None


def _vimeo_id(url: str) -> str | None:
    path = urlparse(url).path or ""
    match = re.search(r"/(\d{6,12})(?:/|$)", path)
    return match.group(1) if match else None


def _dailymotion_id(url: str) -> str | None:
    path = urlparse(url).path or ""
    match = re.search(r"/(?:video/)?([A-Za-z0-9]+)(?:_|$|/)", path)
    if not match:
        return None
    return match.group(1)


def _tiktok_id(url: str) -> str | None:
    path = urlparse(url).path or ""
    match = re.search(r"/video/(\d{8,})", path)
    if match:
        return match.group(1)
    # short links like /t/ZTxxxx leave the path token as id surrogate
    short = re.match(r"^/t/([A-Za-z0-9]+)/?$", path)
    return short.group(1) if short else None


def _reddit_id(url: str) -> str | None:
    path = urlparse(url).path or ""
    match = re.search(r"/comments/([A-Za-z0-9]+)/", path)
    return match.group(1) if match else None


def _host_endswith(host: str, suffixes: tuple[str, ...]) -> bool:
    return any(host == item or host.endswith(item) for item in suffixes)


def _providers() -> list[_Provider]:
    return [
        _Provider(
            provider_id="youtube",
            display_name="YouTube",
            oembed_endpoint="https://www.youtube.com/oembed",
            match=lambda url: _host_endswith(
                (urlparse(url).hostname or "").lower(),
                ("youtube.com", "youtu.be", "www.youtu.be"),
            ),
            canonical=lambda _url, media_id: f"https://www.youtube.com/watch?v={media_id}",
            media_id=_youtube_video_id,
            thumb_allowed=lambda host: _host_endswith(host, (".ytimg.com", ".ggpht.com", "img.youtube.com")),
        ),
        _Provider(
            provider_id="vimeo",
            display_name="Vimeo",
            oembed_endpoint="https://vimeo.com/api/oembed.json",
            match=lambda url: _host_endswith((urlparse(url).hostname or "").lower(), ("vimeo.com", "player.vimeo.com")),
            canonical=lambda _url, media_id: f"https://vimeo.com/{media_id}",
            media_id=_vimeo_id,
            thumb_allowed=lambda host: _host_endswith(host, ("vimeocdn.com", ".vimeocdn.com", "i.vimeocdn.com")),
        ),
        _Provider(
            provider_id="dailymotion",
            display_name="Dailymotion",
            oembed_endpoint="https://www.dailymotion.com/services/oembed",
            match=lambda url: _host_endswith(
                (urlparse(url).hostname or "").lower(),
                ("dailymotion.com", "dai.ly", "www.dai.ly"),
            ),
            canonical=lambda _url, media_id: f"https://www.dailymotion.com/video/{media_id}",
            media_id=_dailymotion_id,
            thumb_allowed=lambda host: _host_endswith(host, ("dmcdn.net", ".dmcdn.net", "dailymotion.com")),
        ),
        _Provider(
            provider_id="tiktok",
            display_name="TikTok",
            oembed_endpoint="https://www.tiktok.com/oembed",
            match=lambda url: _host_endswith(
                (urlparse(url).hostname or "").lower(),
                ("tiktok.com", "www.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"),
            ),
            canonical=lambda url, _media_id: url.split("?")[0],
            media_id=_tiktok_id,
            thumb_allowed=lambda host: _host_endswith(
                host,
                (
                    "tiktokcdn.com",
                    ".tiktokcdn.com",
                    "tiktokcdn-us.com",
                    ".tiktokcdn-us.com",
                    "musical.ly",
                    ".musical.ly",
                    "tiktok.com",
                ),
            ),
        ),
        _Provider(
            provider_id="reddit",
            display_name="Reddit",
            oembed_endpoint="https://www.reddit.com/oembed",
            match=lambda url: _host_endswith(
                (urlparse(url).hostname or "").lower(),
                ("reddit.com", "www.reddit.com", "old.reddit.com", "v.redd.it"),
            ),
            canonical=lambda url, _media_id: url.split("?")[0],
            media_id=_reddit_id,
            thumb_allowed=lambda host: _host_endswith(
                host,
                (
                    "redd.it",
                    ".redd.it",
                    "redditmedia.com",
                    ".redditmedia.com",
                    "redditstatic.com",
                    ".redditstatic.com",
                ),
            ),
        ),
    ]


def _match_provider(url: str) -> _Provider | None:
    for provider in _providers():
        if provider.match(url):
            return provider
    return None


def _fetch_oembed(endpoint: str, canonical_url: str, display_name: str) -> dict:
    params = urlencode({"url": canonical_url, "format": "json"})
    separator = "&" if "?" in endpoint else "?"
    request_url = f"{endpoint}{separator}{params}"
    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=False) as client:
            response = client.get(request_url, headers={"User-Agent": _USER_AGENT})
    except httpx.HTTPError as exc:
        raise UrlAnalysisError(
            "url_unreachable",
            f"Unable to access the submitted URL. {display_name} oEmbed could not be reached.",
            502,
        ) from exc
    if response.status_code in {401, 403}:
        raise UrlAnalysisError(
            "url_forbidden",
            f"{display_name} refused public metadata for this URL. Private or restricted media is not analyzed.",
            403,
        )
    if response.status_code == 404:
        raise UrlAnalysisError(
            "url_not_found",
            f"{display_name} oEmbed did not find that media. It may be private, deleted, or invalid.",
            404,
        )
    if response.status_code >= 400:
        raise UrlAnalysisError(
            "url_unreachable",
            f"Unable to access the submitted URL. {display_name} oEmbed returned an error.",
            502,
        )
    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise UrlAnalysisError(
            "url_unreachable",
            f"{display_name} oEmbed returned an invalid response.",
            502,
        ) from exc
    if not isinstance(payload, dict):
        raise UrlAnalysisError(
            "url_unreachable",
            f"{display_name} oEmbed returned an invalid response.",
            502,
        )
    return payload


def _fetch_thumbnail(
    thumb_url: str,
    provider_id: str,
    media_id: str,
    allowed,
) -> tuple[bytes, str, str]:
    parsed = urlparse(thumb_url.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise UrlAnalysisError("thumbnail_blocked", "Thumbnail URL must be https.")
    host = parsed.hostname.lower()
    if not allowed(host):
        raise UrlAnalysisError(
            "thumbnail_blocked",
            f"Thumbnail host is not on the {provider_id} allowlist.",
        )
    _assert_public_hostname(host)
    safe_url = urlunparse(("https", host, parsed.path, "", parsed.query, ""))
    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=False) as client:
            response = client.get(safe_url, headers={"User-Agent": _USER_AGENT})
    except httpx.HTTPError as exc:
        raise UrlAnalysisError("thumbnail_unreachable", "The public thumbnail could not be downloaded.", 502) from exc
    if response.status_code >= 400:
        raise UrlAnalysisError("thumbnail_unreachable", "The public thumbnail could not be downloaded.", 502)
    payload = response.content
    if not payload:
        raise UrlAnalysisError("thumbnail_unreachable", "The public thumbnail was empty.", 502)
    if len(payload) > _MAX_THUMB_BYTES:
        raise UrlAnalysisError("file_too_large", "Thumbnail exceeds the configured limit.", 413)
    signature = identify_signature(payload)
    if signature is None or signature.format_id not in {"jpeg", "png", "webp", "gif"}:
        raise UrlAnalysisError(
            "unsupported_format",
            "Thumbnail bytes were not a supported image type.",
        )
    extension = {"jpeg": "jpg", "png": "png", "webp": "webp", "gif": "gif"}[signature.format_id]
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", media_id)[:40]
    return payload, f"{provider_id}-{safe_id}-thumbnail.{extension}", signature.format_id


def _assert_public_hostname(host: str) -> None:
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UrlAnalysisError("thumbnail_blocked", "Thumbnail host could not be resolved.", 502) from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise UrlAnalysisError("thumbnail_blocked", "Thumbnail host resolved to a non-public address.")
