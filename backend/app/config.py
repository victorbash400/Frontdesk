from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'backend' / 'operator.db'}"
    s3_bucket: str = ""
    aws_region: str = "af-south-1"
    strands_region: str = "us-west-2"
    strands_model_id: str = "global.anthropic.claude-sonnet-4-6"
    cors_origins: str = "http://localhost:3000"
    internal_secret: str = "operator-local-development-secret"

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / "backend" / ".env",
        env_prefix="OPERATOR_",
        extra="ignore",
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
