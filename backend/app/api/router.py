from fastapi import APIRouter

from app.api.routes import auth, files, health, platform

api_router = APIRouter()
api_router.include_router(health.router, tags=["operations"])
api_router.include_router(platform.router, tags=["platform"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(auth.account_router, tags=["account"])
api_router.include_router(files.router, tags=["analysis"])
