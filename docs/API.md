# API

Base path: `/api/v1`. Interactive docs: `/docs` when the API process is running.

Authenticated routes expect `Authorization: Bearer <access token>`. The access token lasts 12 hours. A missing signing key returns 503. A bad token returns 401.

## Operations

### GET /api/v1/health

Liveness. Does not check PostgreSQL.

```json
{"status": "ok", "service": "trustify-ai"}
```

### GET /api/v1/ready

Readiness. Runs `SELECT 1`.

- `200` when the database accepts the query: `{"status":"ready","checks":{"database":"ok"}}`
- `503` when it does not: `{"status":"unavailable","checks":{"database":"unavailable"}}`

### GET /api/v1/platform

Live description of this build. Engine `status` is `ready` or `not_integrated`. Image/video forensics become `ready` only when `ENABLE_ML_DETECTORS=true` and the ML packages from `requirements-ml.txt` are importable. A failed weight download at inference still returns `unavailable`, not a simulated score.

`auth_configured` is true when the process has a signing key. In development, an empty `JWT_SECRET` still produces the local development key. Production requires a real secret and rejects the known development key.

Responses do not include a confidence field.

## Accounts

| Method | Path | Result |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | Creates an account and session |
| POST | `/api/v1/auth/login` | Returns an access token. A bad email or password uses the same 401 message |
| POST | `/api/v1/auth/logout` | Revokes the current session |
| GET, PATCH | `/api/v1/auth/me` | Reads or updates the profile |
| POST | `/api/v1/auth/password` | Changes the password |
| GET | `/api/v1/auth/sessions` | Lists sessions |
| DELETE | `/api/v1/auth/sessions/{id}` | Revokes one session |
| DELETE | `/api/v1/account/files` | Deletes uploaded objects for the account |
| DELETE | `/api/v1/account` | Deletes the account |

`POST /api/v1/auth/google` and `POST /api/v1/auth/forgot-password` return 501. They are not configured.

Passwords are hashed with PBKDF2-HMAC-SHA256 and must be at least 12 characters.

## Analysis

| Method | Path | Result |
| --- | --- | --- |
| POST | `/api/v1/files` | Stores one uploaded file, queues analysis, extracts container metadata, and writes an inconclusive report |
| GET | `/api/v1/jobs` | Lists the signed-in user's jobs |
| GET | `/api/v1/jobs/{id}` | Returns the report for one owned job |
| DELETE | `/api/v1/jobs/{id}` | Deletes one owned analysis |
| GET | `/api/v1/files/{id}/content` | Returns the stored bytes for preview. HTML is not served as `text/html` |
| GET | `/api/v1/dashboard` | Returns counts from stored rows |
| GET | `/api/v1/duplicates` | Returns exact SHA-256 matches inside the same account |
| POST | `/api/v1/investigations/scam` | Stores the submission as unverified input and returns no person or business label |

`POST /api/v1/urls` accepts:
- public video URLs from YouTube/Shorts, Vimeo, Dailymotion, TikTok, and Reddit (oEmbed + thumbnail; no DRM bypass)
- other http(s) URLs for reputation checks (Google Safe Browsing or VirusTotal when configured; otherwise only Google's published `testsafebrowsing.appspot.com` test vectors are recognized)

Instagram and Facebook media URLs return 501. Arbitrary sites are not labeled phishing without a configured reputation API or a published test-vector match.

`GET /api/v1/reports/{job_id}/pdf` returns 501.

Jobs belonging to another user return 404. Completed integrity checks store a null confidence. The report has no authenticity score and no fused risk score.

## Errors

Unhandled exceptions return:

```json
{"error": "internal_error", "message": "The request could not be completed."}
```

`X-Request-ID` is echoed when it is 1–64 characters of letters, digits, `_`, or `-`. Any other value is replaced.
