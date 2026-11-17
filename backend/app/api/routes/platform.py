from fastapi import APIRouter

from app.core.config import get_settings
from app.platform.catalog import PlatformStatus, build_platform_status

router = APIRouter()


@router.get("/platform", response_model=PlatformStatus)
def platform() -> PlatformStatus:
    return build_platform_status(get_settings())
