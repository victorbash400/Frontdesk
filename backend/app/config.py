from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'backend' / 'front-desk.db'}"
    google_cloud_project: str = "front-desk-20260824"
    google_cloud_location: str = "global"
    gemini_model: str = "gemini-3.1-pro-preview"
    gemini_title_model: str = "gemini-3-flash-preview"
    google_client_id: str = ""
    google_client_secret: str = ""
    gcs_bucket: str = ""
    cors_origins: str = "http://localhost:3000"
    internal_secret: str = "front-desk-local-development-secret"

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / "backend" / ".env",
        env_prefix="FRONT_DESK_",
        extra="ignore",
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
