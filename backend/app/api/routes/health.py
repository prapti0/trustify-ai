from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.database import database_reachable

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="trustify-ai")


@router.get("/ready")
def ready() -> JSONResponse:
    database_ok = database_reachable()
    return JSONResponse(
        status_code=200 if database_ok else 503,
        content={
            "status": "ready" if database_ok else "unavailable",
            "checks": {"database": "ok" if database_ok else "unavailable"},
        },
    )
