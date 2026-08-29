import json
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'backend' / 'front-desk.db'}"
    agent_session_database_url: str = f"sqlite+aiosqlite:///{PROJECT_ROOT / 'backend' / 'front-desk-sessions.db'}"
    google_cloud_project: str = "front-desk-20260824"
    google_cloud_location: str = "global"
    gemini_model: str = "gemini-3-flash-preview"
    gemini_title_model: str = "gemini-3-flash-preview"
    gemini_voice_model: str = "gemini-3.1-flash-live-preview"
    gemini_api_key: str = ""
    google_client_credentials_file: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    slack_client_id: str = ""
    slack_client_secret: str = ""
    aqualabs_store_mcp_url: str = ""
    aqualabs_store_mcp_token: str = ""
    gcs_bucket: str = ""
    cors_origins: str = "http://localhost:3000"
    internal_secret: str = "front-desk-local-development-secret"
    scheduler_audience: str = ""
    scheduler_service_account: str = ""
    playwright_extension_token: str = ""
    google_workspace_events_topic: str = ""
    public_api_url: str = "http://127.0.0.1:8000"

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / "backend" / ".env",
        env_prefix="FRONT_DESK_",
        extra="ignore",
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def google_oauth_credentials(self) -> tuple[str, str]:
        if self.google_client_credentials_file:
            credentials_path = Path(self.google_client_credentials_file).expanduser()
            try:
                payload = json.loads(credentials_path.read_text())
                web_credentials = payload["web"]
                client_id = web_credentials["client_id"]
                client_secret = web_credentials["client_secret"]
                if not isinstance(client_id, str) or not client_id or not isinstance(client_secret, str) or not client_secret:
                    raise ValueError("Google OAuth credentials are empty.")
                return client_id, client_secret
            except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
                raise RuntimeError(
                    f"Google OAuth credentials could not be loaded from {credentials_path}."
                ) from error
        return self.google_client_id, self.google_client_secret


@lru_cache
def get_settings() -> Settings:
    return Settings()
