import asyncio
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import httpx
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


def test_token_payload_accepts_github_json_response() -> None:
    response = httpx.Response(200, json={"access_token": "token", "scope": "repo"})
    assert mcp_oauth._token_payload(response)["access_token"] == "token"


def test_token_payload_accepts_github_form_response() -> None:
    response = httpx.Response(200, text="access_token=token&scope=repo%20read%3Auser&token_type=bearer")
    assert mcp_oauth._token_payload(response) == {
        "access_token": "token",
        "scope": "repo read:user",
        "token_type": "bearer",
    }


def test_token_payload_rejects_empty_response() -> None:
    with pytest.raises(RuntimeError, match="empty token response"):
        mcp_oauth._token_payload(httpx.Response(200, text=""))


def test_begin_connection_declares_offline_consent(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace(
        scalar=lambda statement: object(),
        execute=lambda statement: None,
        add=lambda value: None,
        commit=lambda: None,
    )
    monkeypatch.setattr(mcp_oauth, "connection_support", lambda: {"atlassian": (True, None)})
    monkeypatch.setattr(mcp_oauth, "_discover", lambda provider: _async_result({
        "authorization_endpoint": "https://auth.example/authorize",
        "token_endpoint": "https://auth.example/token",
        "registration_endpoint": "https://auth.example/register",
        "resource": provider.server_url,
    }))
    monkeypatch.setattr(mcp_oauth, "_client_information", lambda provider, discovery: _async_result({
        "client_id": "client-id",
        "token_endpoint_auth_method": "none",
    }))

    authorization_url = asyncio.run(mcp_oauth.begin_connection(session, "account", "atlassian"))
    parameters = parse_qs(urlparse(authorization_url).query)

    assert parameters["prompt"] == ["consent"]
    assert parameters["resource"] == [mcp_oauth.PROVIDERS["atlassian"].server_url]


def test_atlassian_uses_authv2_for_oauth_and_mcp_for_tools() -> None:
    provider = mcp_oauth.PROVIDERS["atlassian"]

    assert provider.oauth_server_url == "https://mcp.atlassian.com/v1/mcp/authv2"
    assert provider.server_url == "https://mcp.atlassian.com/v1/mcp"
    assert "read:account" in provider.scopes.split()
    assert "search:jira-work" in provider.scopes.split()
    assert "read:space:confluence" in provider.scopes.split()


def test_slack_requests_the_complete_mcp_scope_set() -> None:
    scopes = set(mcp_oauth.PROVIDERS["slack"].scopes.split())

    assert {"search:read.public", "chat:write", "channels:write", "canvases:write", "users:read.email"} <= scopes


def test_first_exception_unwraps_nested_task_groups() -> None:
    detail = RuntimeError("Slack rejected the MCP request")

    assert mcp_oauth._first_exception(ExceptionGroup("outer", [ExceptionGroup("inner", [detail])])) is detail


def test_first_atlassian_cloud_id_reads_resource_list() -> None:
    assert mcp_oauth._first_atlassian_cloud_id('[{"id":"cloud-id","url":"https://example.atlassian.net"}]') == "cloud-id"


def test_first_atlassian_cloud_id_requires_a_site() -> None:
    with pytest.raises(RuntimeError, match="accessible site"):
        mcp_oauth._first_atlassian_cloud_id("[]")


async def _async_result(value):
    return value
