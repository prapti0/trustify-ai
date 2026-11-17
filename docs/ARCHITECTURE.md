# Architecture

TRUSTIFY AI is a content authenticity and digital forensics product. Accounts, local uploads, integrity reports, URL intake, and optional pretrained visual detectors exist. Further detectors must keep the same evidence model.

## Shape

Start as a modular monolith. Keep background work in a separate process so video and malware jobs can scale without scaling the API.

| Process | Responsibility now | Scales independently |
| --- | --- | --- |
| FastAPI | Accounts, uploads, integrity reports, capability catalog | Yes, later |
| Celery worker | Job analysis when `ANALYSIS_MODE=celery`, including optional ML detectors | Yes |
| PostgreSQL | System of record for users, files, jobs, evidence, reports | Managed service in production |
| Redis | Celery broker and result backend | Yes |
| Qdrant | Reserved for embeddings. No client calls yet | Yes |
| Object storage | Local filesystem in development. S3 is rejected until implemented | Yes |

The browser never receives model credentials. `GEMINI_API_KEY` and `VIRUSTOTAL_API_KEY` are server environment variables and are unused in this phase.

## Request path

1. The React app registers or signs in, then calls account and analysis routes with a bearer token.
2. FastAPI validates the file, stores the bytes locally, and records the hash and signature.
3. The upload creates a queued analysis job. `ANALYSIS_MODE=inline` finishes in the API process; `celery` dispatches `trustify.analyze_job`.
4. The job extracts container metadata, records integrity evidence, and runs visual detectors when packages and weights load.
5. Image jobs call Hugging Face classifiers. Video jobs sample frames with OpenCV and reuse those classifiers. Public URL jobs may score the thumbnail only — not the remote bitstream.
6. Each pipeline writes a `detection_results` row. If the model is absent or fails to load, status is `unavailable` and confidence is null. Confidences are never averaged across modules or frames into one authenticity score.
7. A report keeps six separate finding objects: AI generation, manipulation, malware, provenance, similarity, and scam. `overall_classification` is optional and is never a substitute for those objects.

There is no LangGraph graph yet. The agent list (file, video, image, audio, document, malware, duplicate, provenance, scam, report) maps to future modules behind the same result tables. Gemini, when added, summarizes evidence. It is not the detector.

## Modules

```
backend/app/api            HTTP
backend/app/core           settings, database, passwords, errors
backend/app/domain         enums
backend/app/models         SQLAlchemy tables
backend/app/platform       capability catalog
backend/app/services       hashing, signatures, storage, metadata, URL intake, detectors, analysis jobs
backend/app/workers        Celery application (`ping`, `analyze_job`)
frontend/src               React UI
```

New file formats land in `identify_signature` and a pipeline registry. New models land as a versioned row in `model_versions` plus a wrapper that returns a real `DetectionResult`. A wrapper that cannot load its weights must return `unavailable`.

## Data model

Thirteen tables: `users`, `user_sessions`, `uploaded_files`, `file_metadata`, `analysis_jobs`, `detection_results`, `forensic_evidence`, `security_scan_results`, `duplicate_matches`, `investigation_reports`, `model_versions`, `api_keys`, `audit_logs`.

Files are owned by a user. Jobs are owned by a user. Query paths filter on `user_id`. Large bytes go to object storage; the database stores the key, hash, and metadata.

`detection_results` rejects a confidence value unless `status = completed`, and a completed confidence must be between 0 and 1. That is the mechanical version of “no simulated scores.”

Reports have no `authenticity_score` column.

SHA-256 matches are exact duplicates inside a user-authorized corpus. They are not a search of the public internet. Embedding search will use Qdrant after a model exists.

## Detection policy

- Pretrained weights only, after the license is recorded on `model_versions`.
- No foundation-model training.
- No fusion by averaging. A fusion model needs a labeled evaluation set and its own version row.
- Metrics to record later: precision, recall, F1, ROC-AUC, false positives, false negatives.
- The UI shows model name, version, confidence, and limitations together. A bare percentage is not a result.

## Security boundaries

- Email login issues a 12-hour JWT. The hasher is PBKDF2-HMAC-SHA256 with 200,000 iterations. Sessions store a hash of the refresh token, not the token. Google sign-in and password reset return 501.
- CORS origins come from configuration. Credentials are not combined with `*`.
- Request IDs are accepted only when they match `[A-Za-z0-9_-]{1,64}`.
- Unhandled errors return a generic message. Database exceptions are not logged with their text, because that text can contain the connection URL.
- Storage keys cannot contain `..` or escape the storage root.
- Malware scanning, when added, runs in a container without a route that executes the sample or document macros.
- URL analysis, when added, uses permitted APIs. It does not log into platforms or strip DRM.

## Job states

`uploaded`, `queued`, `processing`, `completed`, `failed`. Uploads start as `queued`, move to `processing`, then `completed` or `failed`. Metadata extraction is real. Detector stages that cannot run are marked unavailable. There is no estimated time.

## What stays out of the API on purpose

PDF export, Google sign-in, and password-reset email return 501. Login-walled / DRM video bitstream download is refused. A handler that would have to invent a forensic finding is not mounted.
