"""URL reputation checks. No invented phishing labels without a real source."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.core.config import Settings

_TIMEOUT = httpx.Timeout(12.0, connect=5.0)
_SAFE_BROWSING = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
_THREAT_TYPES = [
    "MALWARE",
    "SOCIAL_ENGINEERING",
    "UNWANTED_SOFTWARE",
    "POTENTIALLY_HARMFUL_APPLICATION",
]

# Google publishes these Safe Browsing test URLs for integration checks.
# Matching them is not a live Safe Browsing API call.
_GOOGLE_TEST_VECTORS = {
    "/s/phishing.html": ("phishing", "SOCIAL_ENGINEERING"),
    "/s/malware.html": ("malware", "MALWARE"),
    "/s/unwanted.html": ("unwanted", "UNWANTED_SOFTWARE"),
    "/s/spyware.html": ("malware", "MALWARE"),
}


class UrlSafetyError(Exception):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass(frozen=True)
class UrlSafetyResult:
    url: str
    verdict: str  # phishing | malware | unwanted | clean | unavailable
    source: str
    threats: list[str]
    evidence: list[str]
    limitations: list[str]
    classification: str  # high | medium | low | inconclusive


def check_url_safety(url: str, settings: Settings) -> UrlSafetyResult:
    normalized = _normalize(url)
    if settings.safe_browsing_api_key.strip():
        return _safe_browsing_lookup(normalized, settings.safe_browsing_api_key.strip())
    if settings.virustotal_api_key.strip():
        return _virustotal_lookup(normalized, settings.virustotal_api_key.strip())
    test = _published_google_test(normalized)
    if test is not None:
        return test
    return UrlSafetyResult(
        url=normalized,
        verdict="unavailable",
        source="not_configured",
        threats=[],
        evidence=[],
        limitations=[
            "Live URL reputation APIs are not configured.",
            "Set SAFE_BROWSING_API_KEY or VIRUSTOTAL_API_KEY to query a real reputation service.",
            "No phishing or malware label was invented for this URL.",
        ],
        classification="inconclusive",
    )


def _normalize(url: str) -> str:
    value = url.strip()
    parsed = urlparse(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise UrlSafetyError("invalid_url", "Enter an http or https URL.")
    if parsed.username or parsed.password:
        raise UrlSafetyError("invalid_url", "URLs with embedded credentials are not accepted.")
    return value


def _published_google_test(url: str) -> UrlSafetyResult | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host != "testsafebrowsing.appspot.com":
        return None
    path = parsed.path or ""
    for suffix, (verdict, threat) in _GOOGLE_TEST_VECTORS.items():
        if path == suffix or path.endswith(suffix):
            return UrlSafetyResult(
                url=url,
                verdict=verdict,
                source="google_published_test_vector",
                threats=[threat],
                evidence=[
                    f"URL path matches Google's published Safe Browsing test vector ({suffix}).",
                    "Google documents these URLs for Safe Browsing integration testing.",
                ],
                limitations=[
                    "Live Google Safe Browsing API was not called because SAFE_BROWSING_API_KEY is empty.",
                    "This match is only valid for Google's published test site, not for arbitrary websites.",
                ],
                classification="high",
            )
    return UrlSafetyResult(
        url=url,
        verdict="unavailable",
        source="google_test_host_unknown_path",
        threats=[],
        evidence=[f"Host is testsafebrowsing.appspot.com but path {path!r} is not a known published test vector."],
        limitations=[
            "Live Safe Browsing API was not called.",
            "Unknown paths on the test host are not labeled phishing or clean.",
        ],
        classification="inconclusive",
    )


def _safe_browsing_lookup(url: str, api_key: str) -> UrlSafetyResult:
    body = {
        "client": {"clientId": "trustify-ai", "clientVersion": "0.1.0"},
        "threatInfo": {
            "threatTypes": _THREAT_TYPES,
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.post(f"{_SAFE_BROWSING}?key={api_key}", json=body)
    except httpx.HTTPError as exc:
        raise UrlSafetyError(
            "url_unreachable",
            "Unable to reach Google Safe Browsing.",
            502,
        ) from exc
    if response.status_code >= 400:
        raise UrlSafetyError(
            "safe_browsing_error",
            "Google Safe Browsing returned an error for this request.",
            502,
        )
    payload = response.json() if response.content else {}
    matches = payload.get("matches") if isinstance(payload, dict) else None
    if not matches:
        return UrlSafetyResult(
            url=url,
            verdict="clean",
            source="safe_browsing_api",
            threats=[],
            evidence=["Google Safe Browsing returned no threat matches for this URL at query time."],
            limitations=[
                "No match is not a guarantee the URL is safe forever.",
                "Safe Browsing coverage is incomplete for brand-new or targeted phishing.",
            ],
            classification="low",
        )
    threats = sorted({str(item.get("threatType")) for item in matches if isinstance(item, dict) and item.get("threatType")})
    verdict = "phishing" if "SOCIAL_ENGINEERING" in threats else "malware" if "MALWARE" in threats else "unwanted"
    return UrlSafetyResult(
        url=url,
        verdict=verdict,
        source="safe_browsing_api",
        threats=threats,
        evidence=[f"Google Safe Browsing matched threat type(s): {', '.join(threats)}."],
        limitations=["This is a Safe Browsing reputation signal, not proof about a person or business identity."],
        classification="high",
    )


def _virustotal_lookup(url: str, api_key: str) -> UrlSafetyResult:
    import base64

    url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.get(
                f"https://www.virustotal.com/api/v3/urls/{url_id}",
                headers={"x-apikey": api_key},
            )
    except httpx.HTTPError as exc:
        raise UrlSafetyError("url_unreachable", "Unable to reach VirusTotal.", 502) from exc
    if response.status_code == 404:
        return UrlSafetyResult(
            url=url,
            verdict="unavailable",
            source="virustotal_api",
            threats=[],
            evidence=["VirusTotal has no report for this URL yet."],
            limitations=["Absence of a VirusTotal report is not a clean finding."],
            classification="inconclusive",
        )
    if response.status_code >= 400:
        raise UrlSafetyError("virustotal_error", "VirusTotal returned an error for this request.", 502)
    payload = response.json()
    stats = (
        payload.get("data", {})
        .get("attributes", {})
        .get("last_analysis_stats", {})
    )
    if not isinstance(stats, dict):
        return UrlSafetyResult(
            url=url,
            verdict="unavailable",
            source="virustotal_api",
            threats=[],
            evidence=[],
            limitations=["VirusTotal response did not include analysis stats."],
            classification="inconclusive",
        )
    malicious = int(stats.get("malicious") or 0)
    suspicious = int(stats.get("suspicious") or 0)
    if malicious > 0:
        return UrlSafetyResult(
            url=url,
            verdict="malware",
            source="virustotal_api",
            threats=["VT_MALICIOUS"],
            evidence=[f"VirusTotal last_analysis_stats.malicious={malicious}, suspicious={suspicious}."],
            limitations=["Vendor votes differ. This is not a person or business label."],
            classification="high",
        )
    if suspicious > 0:
        return UrlSafetyResult(
            url=url,
            verdict="unwanted",
            source="virustotal_api",
            threats=["VT_SUSPICIOUS"],
            evidence=[f"VirusTotal last_analysis_stats.suspicious={suspicious}."],
            limitations=["Suspicious votes are not a confirmed phishing verdict."],
            classification="medium",
        )
    return UrlSafetyResult(
        url=url,
        verdict="clean",
        source="virustotal_api",
        threats=[],
        evidence=[f"VirusTotal last_analysis_stats showed malicious=0 and suspicious=0 (harmless={stats.get('harmless', 0)})."],
        limitations=["Vendor coverage is incomplete. Clean votes are not a lifetime guarantee."],
        classification="low",
    )
