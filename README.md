# TRUSTIFY AI

Universal content authenticity and digital forensics platform. The current build has accounts, local uploads, integrity checks, public URL intake, URL reputation checks, and optional Phase 3 image/video detectors.

Missing engines stay `not_integrated`. Confidence is stored only for a completed model result, and that rule is a database constraint. Module confidences are never averaged into one authenticity score.

## Architecture

The running system is a modular monolith plus a Celery worker process.

```
Browser → FastAPI → validation and storage → Redis queue → workers
                 → PostgreSQL evidence tables
                 → Qdrant (reserved for embeddings)
```

Logical services (authentication, upload, video, audio, image, document, security, detection, investigation, reporting) live in one codebase with separate modules. They are not separate deployable services yet.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/API.md](docs/API.md), and [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Current status

Implemented and covered by tests:

- Email registration, password login, profile updates, session revocation, and account deletion
- Local file upload, SHA-256, magic-byte identification, and exact in-account duplicate records
- Queued analysis jobs (`ANALYSIS_MODE=inline` or Celery) with real container metadata extraction
- Phase 3 visual detectors (Hugging Face AI-image + deepfake classifiers; OpenCV frame sampling for video) when `requirements-ml.txt` is installed and `ENABLE_ML_DETECTORS=true`
- Public video URL oEmbed + thumbnail intake; URL reputation / phishing checks
- Dashboard counts read from stored rows
- Forensic report pages that keep unavailable detectors marked unavailable
- `GET /api/v1/health`, `GET /api/v1/ready`, `GET /api/v1/platform`
- SQLAlchemy models and an Alembic migration for the forensic schema
- Celery application and a non-analytic `trustify.ping` task

Explicitly unavailable, and reported that way in the UI:

- Google sign-in, password-reset email, two-factor authentication, and PDF export
- Instagram/Facebook URL fetching and any platform video bitstream download (DRM/login bypass)
- Temporal/lip-sync video models, ClamAV/YARA scans, C2PA checks, and Qdrant search
- LangGraph agents, Gemini summaries, and S3 uploads
- A public website

## Run locally

API tests use SQLite and do not need Docker.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Web UI:

```bash
cd frontend
npm install
npm test
npm run dev
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` to `http://127.0.0.1:8000`. Set `VITE_API_PROXY` when the API is on another port. Interactive API docs are at `http://127.0.0.1:8000/docs`.

In development, an empty `JWT_SECRET` uses a local signing key. Production rejects that key. The browser end-to-end check is `npm run test:e2e` while the API and Vite server are already running. Set `PLAYWRIGHT_BASE_URL` when Vite is not on port 5173.

PostgreSQL, Redis, and Qdrant:

```bash
docker compose up --build
```

Then apply the schema:

```bash
cd backend
alembic upgrade head
```

`alembic upgrade head` expects `DATABASE_URL` to point at PostgreSQL. The Compose default is in `.env.example`.

Optional Celery worker (`ANALYSIS_MODE=celery`):

```bash
docker compose --profile workers up --build
```

Optional Phase 3 ML detectors (large download):

```bash
cd backend
pip install -r requirements-ml.txt
# ENABLE_ML_DETECTORS=true in .env
```

## Configuration

Copy `.env.example` to `.env`. Leave `GEMINI_API_KEY` empty unless investigating. Set `SAFE_BROWSING_API_KEY` or `VIRUSTOTAL_API_KEY` for live URL reputation. Set a long random `JWT_SECRET` before any shared deployment. An empty secret is accepted only when `ENVIRONMENT=development`. Do not commit `.env`.

`STORAGE_BACKEND=s3` fails closed. Local development uses `local`.

## Tests

- Backend: `pytest` in `backend/`
- Frontend: `npm test` in `frontend/`
- Browser: `npm run test:e2e` in `frontend/` against a running API and Vite server
- CI: `.github/workflows/ci.yml`

## Safety rules already enforced

- Uploaded bytes are data. Nothing in this repository executes them.
- URL intake uses public oEmbed/thumbnails and reputation APIs only. It does not bypass login, DRM, or encryption.
- Platform responses do not contain confidence scores.
- A detection row with status other than `completed` cannot store a confidence value.
- Detector confidences are never averaged into one authenticity score.
