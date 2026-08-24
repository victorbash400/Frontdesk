from types import SimpleNamespace

import pytest

from app import mcp_oauth


def test_resource_metadata_url_is_read_from_bearer_challenge() -> None:
    header = 'Bearer realm="OAuth", resource_metadata="https://mcp.example/.well-known/oauth-protected-resource", error="invalid_token"'
    assert mcp_oauth._resource_metadata_url(header) == "https://mcp.example/.well-known/oauth-protected-resource"


def test_connection_support_surfaces_static_provider_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mcp_oauth, "get_settings", lambda: SimpleNamespace(
        github_client_id="",
        github_client_secret="",
        slack_client_id="",
        slack_client_secret="",
    ))
    support = mcp_oauth.connection_support()
    assert support["notion"] == (True, None)
    assert support["linear"] == (True, None)
    assert support["github"][0] is False
    assert support["github"][1]
