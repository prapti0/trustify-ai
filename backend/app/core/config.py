from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        extra="ignore",
    )

    app_name: str = "TRUSTIFY AI"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://trustify:trustify@localhost:5432/trustify"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"

    storage_backend: str = "local"
    local_storage_dir: str = "./var/storage"
    s3_bucket: str = ""
    aws_region: str = "us-east-1"

    jwt_secret: str = ""
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174,"
        "http://localhost:5175,http://127.0.0.1:5175"
    )
    max_upload_bytes: int = Field(default=104_857_600, ge=1)
    # inline runs analysis in the API process. celery requires a worker and Redis.
    analysis_mode: str = "inline"

    gemini_api_key: str = ""
    virustotal_api_key: str = ""
    safe_browsing_api_key: str = ""

    # Phase 3 detectors. Ready only after packages + weights actually load.
    enable_ml_detectors: bool = True
    ai_image_model_id: str = "umm-maybe/AI-image-detector"
    deepfake_image_model_id: str = "prithivMLmods/Deep-Fake-Detector-v2-Model"
    video_detector_max_frames: int = Field(default=8, ge=1, le=32)

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def signing_key(self) -> str:
        secret = self.jwt_secret.strip()
        dev_key = "dev-only-trustify-signing-key"
        if self.environment == "production":
            if not secret or secret == dev_key:
                return ""
            return secret
        if secret:
            return secret
        if self.environment == "development":
            return dev_key
        return ""

    @property
    def auth_configured(self) -> bool:
        return bool(self.signing_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
