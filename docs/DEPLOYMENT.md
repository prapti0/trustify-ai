# Deployment

The application runs locally and in Docker Compose. It is not deployed to a public URL. Do not describe a domain as live until the health endpoint answers on that domain. Set a real `JWT_SECRET` before sharing a host. The Compose database password is for local development only.

## Local containers

From the repository root:

```bash
docker compose up --build
```

This starts PostgreSQL 16, Redis 7, Qdrant 1.12.5, and the API on port 8000. The API image installs `backend/requirements.txt` only. PyTorch and the other packages in `requirements-ml.txt` are intentionally absent, so detectors cannot pretend to run inside that image.

Apply migrations against the Compose database:

```bash
cd backend
DATABASE_URL=postgresql+psycopg://trustify:trustify@localhost:5432/trustify alembic upgrade head
```

The worker profile starts Celery. Its only task is `trustify.ping`.

```bash
docker compose --profile workers up --build
```

The development database password in Compose is `trustify`. Replace it before any shared or public host.

## Frontend

Development: `npm run dev` in `frontend/`, with the Vite proxy.

A production build is `npm run build`. Static files are in `frontend/dist`. Set `VITE_API_BASE_URL` at build time when the API is on another origin. Leave it empty when a reverse proxy serves the UI and `/api` on one origin.

## Production target

| Piece | Target |
| --- | --- |
| Web | Vercel, or static files behind Nginx |
| API and workers | Container host on AWS or equivalent |
| Database | Managed PostgreSQL |
| Objects | S3, after the storage client exists |
| Queue | Redis |
| Vectors | Qdrant |
| CI | GitHub Actions, already in `.github/workflows/ci.yml` |

Required before a public release:

- HTTPS
- a real `JWT_SECRET` and authentication
- private S3 bucket and short-lived credentials, not keys in the frontend
- upload size limits, malware scanning, and a non-root processing container
- removal of the Compose database password
- error monitoring that does not record file contents or secrets
- a domain check that `GET /api/v1/health` and the UI both load

## Secrets

`.env.example` lists every variable. Real values stay in the host secret store. The repository `.gitignore` excludes `.env`.
