import json

import pytest

from app.config import Settings
from tools.browser_use.playwright import BROWSER_COMMAND_TIMEOUT_SECONDS, PLAYWRIGHT_ALLOWED_TOOLS


def test_google_oauth_credentials_load_from_downloaded_file(tmp_path) -> None:
    credentials_file = tmp_path / "client_secret.json"
    credentials_file.write_text(json.dumps({
        "web": {
            "client_id": "front-desk.apps.googleusercontent.com",
            "client_secret": "local-test-secret",
        },
    }))

    settings = Settings(_env_file=None, google_client_credentials_file=str(credentials_file))

    assert settings.google_oauth_credentials == (
        "front-desk.apps.googleusercontent.com",
        "local-test-secret",
    )


def test_google_oauth_credentials_reject_invalid_file(tmp_path) -> None:
    credentials_file = tmp_path / "client_secret.json"
    credentials_file.write_text('{"web": {}}')
    settings = Settings(_env_file=None, google_client_credentials_file=str(credentials_file))

    with pytest.raises(RuntimeError, match="could not be loaded"):
        settings.google_oauth_credentials


def test_browser_use_does_not_expose_unsafe_code_runner() -> None:
    assert "browser_run_code_unsafe" not in PLAYWRIGHT_ALLOWED_TOOLS


def test_browser_use_allows_normal_long_running_actions() -> None:
    assert BROWSER_COMMAND_TIMEOUT_SECONDS >= 30
