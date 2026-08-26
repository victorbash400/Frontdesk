import json
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from sqlalchemy import select

from app.database import SessionLocal
from app.models import PluginConnection, PluginPermission
from app.secret_store import decrypt_secret, encrypt_secret


MCP_COMMAND_TIMEOUT_SECONDS = 10


async def connected_external_plugin_toolset(account_id: str, plugin_id: str) -> McpToolset:
    connection, credentials = await _connection_credentials(account_id, plugin_id)
    token = str(credentials["tokens"]["access_token"])
    toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=str(credentials["server_url"]),
            headers={"Authorization": f"Bearer {token}"},
            timeout=MCP_COMMAND_TIMEOUT_SECONDS,
        ),
        tool_filter=_permission_filter(account_id, plugin_id),
        use_mcp_resources=True,
    )
    try:
        tools = await toolset.get_tools()
    except Exception:
        await toolset.close()
        raise RuntimeError(f"{plugin_id.title()} is not connected or did not answer its MCP tool listing.") from None
    if not tools:
        await toolset.close()
        raise RuntimeError(f"{plugin_id.title()} connected without exposing enabled tools.")
    if connection.tool_count != len(tools):
        with SessionLocal() as session:
            row = session.get(PluginConnection, connection.id)
            if row:
                row.tool_count = len(tools)
                session.commit()
    return toolset


async def connected_external_plugin_access_token(account_id: str, plugin_id: str) -> str:
    _, credentials = await _connection_credentials(account_id, plugin_id)
    return str(credentials["tokens"]["access_token"])


async def _connection_credentials(account_id: str, plugin_id: str) -> tuple[PluginConnection, dict[str, Any]]:
    with SessionLocal() as session:
        connection = session.scalar(select(PluginConnection).where(
            PluginConnection.account_id == account_id,
            PluginConnection.plugin_id == plugin_id,
        ))
        if not connection:
            raise RuntimeError(f"{plugin_id.title()} is not connected.")
        session.expunge(connection)
    credentials = json.loads(decrypt_secret(connection.credentials))
    tokens = credentials.get("tokens", {})
    expires_in = int(tokens.get("expires_in") or 0)
    updated_at = connection.updated_at.replace(tzinfo=timezone.utc) if connection.updated_at.tzinfo is None else connection.updated_at
    if expires_in and updated_at + timedelta(seconds=max(0, expires_in - 60)) <= datetime.now(timezone.utc):
        credentials = await _refresh(account_id, connection.id, credentials)
    if not credentials.get("tokens", {}).get("access_token"):
        raise RuntimeError(f"{plugin_id.title()} connection has no access token.")
    return connection, credentials


async def _refresh(account_id: str, connection_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
    tokens = credentials["tokens"]
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise RuntimeError("The plugin connection expired and must be reconnected.")
    client = credentials["client"]
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client["client_id"],
        "resource": credentials.get("resource"),
    }
    if client.get("client_secret"):
        data["client_secret"] = client["client_secret"]
    async with httpx.AsyncClient(timeout=10) as http:
        response = await http.post(credentials["token_endpoint"], data=data, headers={"Accept": "application/json"})
    if response.is_error:
        raise RuntimeError("The plugin connection expired and could not be refreshed.")
    refreshed = response.json()
    refreshed.setdefault("refresh_token", refresh_token)
    credentials["tokens"] = {**tokens, **refreshed}
    with SessionLocal() as session:
        row = session.scalar(select(PluginConnection).where(
            PluginConnection.id == connection_id,
            PluginConnection.account_id == account_id,
        ))
        if row:
            row.credentials = encrypt_secret(json.dumps(credentials))
            row.updated_at = datetime.now(timezone.utc)
            session.commit()
    return credentials


def _permission_filter(account_id: str, plugin_id: str):
    with SessionLocal() as session:
        permissions = {
            row.permission_id: row.enabled
            for row in session.scalars(select(PluginPermission).where(PluginPermission.account_id == account_id))
        }

    def enabled(tool: Any, _: Any = None) -> bool:
        name = str(getattr(tool, "name", "")).casefold()
        if plugin_id == "atlassian":
            if "confluence" in name and not permissions.get("atlassian.confluence", True):
                return False
            if "jira" in name and not permissions.get("atlassian.jira", True):
                return False
        if plugin_id == "github":
            if "issue" in name and not permissions.get("github.issues", True):
                return False
            if any(word in name for word in ("pull", "merge")) and not permissions.get("github.pull-requests", True):
                return False
        if plugin_id == "slack":
            if "channel" in name and not permissions.get("slack.channels", True):
                return False
            if "message" in name and not permissions.get("slack.messages", True):
                return False
        return True

    return enabled
