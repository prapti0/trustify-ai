from uuid import UUID

from celery import Celery

from app.core.config import get_settings


def make_celery() -> Celery:
    settings = get_settings()
    app = Celery("trustify", broker=settings.redis_url, backend=settings.redis_url)
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
    )
    return app


celery_app = make_celery()


@celery_app.task(name="trustify.ping")
def ping() -> dict[str, str]:
    return {"service": "trustify-worker", "status": "ok"}


@celery_app.task(name="trustify.analyze_job")
def analyze_job(job_id: str) -> dict[str, str]:
    from app.core.database import get_session_factory
    from app.services.analysis import process_job

    settings = get_settings()
    factory = get_session_factory()
    session = factory()
    try:
        job = process_job(session, settings, UUID(job_id))
        return {"job_id": str(job.id), "status": job.status.value}
    finally:
        session.close()
