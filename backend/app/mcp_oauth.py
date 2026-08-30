import base64
import hashlib
import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
import jwt
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import GitHubRepositoryAccess, PluginConnection, PluginInstallation, PluginOAuthAttempt
from .secret_store import encrypt_secret


def callback_uri() -> str:
    return get_settings().public_api_url.rstrip("/") + "/oauth/mcp/callback"


PROTOCOL_VERSION = "2025-06-18"
INITIALIZE_BODY = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {},
        "clientInfo": {"name": "Front Desk", "version": "0.1.0"},
    },
}


@dataclass(frozen=True)
class MCPProvider:
    id: str
    server_url: str
    scopes: str
    client_setting: str | None = None
    secret_setting: str | None = None
    setup_message: str | None = None
    oauth_server_url: str | None = None


PROVIDERS = {
    "notion": MCPProvider("notion", "https://mcp.notion.com/mcp", "default"),
    "linear": MCPProvider("linear", "https://mcp.linear.app/mcp", "read write"),
    "atlassian": MCPProvider(
        "atlassian",
        "https://mcp.atlassian.com/v1/mcp",
        " ".join((
            "read:me",
            "read:account",
            "offline_access",
            "read:jira-work",
            "write:jira-work",
            "search:jira-work",
            "search:confluence",
            "read:page:confluence",
            "write:page:confluence",
            "read:comment:confluence",
            "write:comment:confluence",
            "read:space:confluence",
            "read:hierarchical-content:confluence",
        )),
        oauth_server_url="https://mcp.atlassian.com/v1/mcp/authv2",
    ),
    "vercel": MCPProvider("vercel", "https://mcp.vercel.com", "openid"),
    "github": MCPProvider(
        "github",
        "https://api.githubcopilot.com/mcp/",
        "repo read:org read:user user:email",
        "github_client_id",
        "github_client_secret",
        "GitHub OAuth setup is required before this connection can be used.",
    ),
    "slack": MCPProvider(
        "slack",
        "https://mcp.slack.com/mcp",
        " ".join((
            "search:read.public",
            "search:read.private",
            "search:read.mpim",
            "search:read.im",
            "search:read.files",
            "search:read.users",
            "files:read",
            "emoji:read",
            "chat:write",
            "channels:history",
            "groups:history",
            "mpim:history",
            "im:history",
            "channels:write",
            "groups:write",
            "im:write",
            "mpim:write",
            "reactions:write",
            "canvases:read",
            "canvases:write",
            "users:read",
            "users:read.email",
            "channels:read",
            "groups:read",
            "mpim:read",
        )),
        "slack_client_id",
        "slack_client_secret",
        "A Slack workspace admin must approve Front Desk before connecting.",
    ),
}


def connection_support() -> dict[str, tuple[bool, str | None]]:
    settings = get_settings()
    result: dict[str, tuple[bool, str | None]] = {}
    for plugin_id, provider in PROVIDERS.items():
        configured = True
        if provider.client_setting:
            configured = bool(getattr(settings, provider.client_setting) and getattr(settings, provider.secret_setting or ""))
        result[plugin_id] = (configured, None if configured else provider.setup_message)
    store_configured = bool(
        getattr(settings, "aqualabs_store_mcp_url", "")
        and getattr(settings, "aqualabs_store_mcp_token", "")
    )
    result["aqualabs-store"] = (
        store_configured,
        None if store_configured else "Configure the Aqualabs Store MCP URL and token on the Front Desk backend.",
    )
    return result


async def begin_connection(session: Session, account_id: str, plugin_id: str) -> str:
    provider = _provider(plugin_id)
    installation = session.scalar(select(PluginInstallation).where(
        PluginInstallation.account_id == account_id,
        PluginInstallation.plugin_id == plugin_id,
    ))
    if not installation:
        raise ValueError("Add this plugin before connecting it.")
    configured, setup_message = connection_support()[plugin_id]
    if not configured:
        raise RuntimeError(setup_message or "This plugin is not configured.")

    discovery = await _discover(provider)
    client_info = await _client_information(provider, discovery)
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    context = {
        "verifier": verifier,
        "client": client_info,
        "token_endpoint": discovery["token_endpoint"],
        "resource": discovery["resource"],
        "scope": provider.scopes,
    }
    session.execute(delete(PluginOAuthAttempt).where(PluginOAuthAttempt.expires_at < datetime.now(timezone.utc)))
    session.add(PluginOAuthAttempt(
        state=state,
        account_id=account_id,
        plugin_id=plugin_id,
        context=encrypt_secret(json.dumps(context)),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    ))
    session.commit()

    parameters = {
        "response_type": "code",
        "client_id": client_info["client_id"],
        "redirect_uri": callback_uri(),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "resource": discovery["resource"],
    }
    if provider.scopes:
        parameters["scope"] = provider.scopes
        if "offline_access" in provider.scopes.split():
            parameters["prompt"] = "consent"
    return discovery["authorization_endpoint"] + "?" + urlencode(parameters)


async def finish_connection(session: Session, state: str, code: str) -> tuple[str, str]:
    attempt = session.get(PluginOAuthAttempt, state)
    if not attempt or attempt.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise ValueError("The plugin connection request expired or is invalid.")
    from .secret_store import decrypt_secret

    context = json.loads(decrypt_secret(attempt.context))
    provider = _provider(attempt.plugin_id)
    client_info = context["client"]
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": callback_uri(),
        "client_id": client_info["client_id"],
        "code_verifier": context["verifier"],
        "resource": context["resource"],
    }
    token_method = client_info.get("token_endpoint_auth_method") or "none"
    request_auth = None
    client_secret = client_info.get("client_secret")
    if token_method == "client_secret_basic" and client_secret:
        request_auth = httpx.BasicAuth(client_info["client_id"], client_secret)
    elif token_method == "client_secret_post" and client_secret:
        token_data["client_secret"] = client_secret

    async with httpx.AsyncClient(timeout=25) as client:
        token_response = await client.post(
            context["token_endpoint"],
            data=token_data,
            auth=request_auth,
            headers={"Accept": "application/json"},
        )
        if token_response.is_error:
            raise RuntimeError(_oauth_error(token_response, "The plugin did not accept the connection."))
        tokens = _token_payload(token_response)
    access_token = tokens.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        detail = tokens.get("error_description") or tokens.get("error")
        raise RuntimeError(str(detail) if detail else "The plugin did not return an access token.")
    tool_count = await _verify_connection(provider, access_token)
    account_label = _account_label(provider, tokens)
    credentials = encrypt_secret(json.dumps({
        "tokens": tokens,
        "client": client_info,
        "token_endpoint": context["token_endpoint"],
        "resource": context["resource"],
        "server_url": provider.server_url,
    }))
    connection = session.scalar(select(PluginConnection).where(
        PluginConnection.account_id == attempt.account_id,
        PluginConnection.plugin_id == attempt.plugin_id,
    ))
    if connection:
        connection.account_label = account_label
        connection.credentials = credentials
        connection.scopes = str(tokens.get("scope") or context["scope"])
        connection.tool_count = tool_count
    else:
        session.add(PluginConnection(
            account_id=attempt.account_id,
            plugin_id=attempt.plugin_id,
            account_label=account_label,
            credentials=credentials,
            scopes=str(tokens.get("scope") or context["scope"]),
            tool_count=tool_count,
        ))
    plugin_id = attempt.plugin_id
    session.delete(attempt)
    session.commit()
    return plugin_id, account_label


def disconnect(session: Session, account_id: str, plugin_id: str) -> None:
    _provider(plugin_id)
    if plugin_id == "github":
        session.execute(delete(GitHubRepositoryAccess).where(GitHubRepositoryAccess.account_id == account_id))
    session.execute(delete(PluginConnection).where(
        PluginConnection.account_id == account_id,
        PluginConnection.plugin_id == plugin_id,
    ))
    session.execute(delete(PluginOAuthAttempt).where(
        PluginOAuthAttempt.account_id == account_id,
        PluginOAuthAttempt.plugin_id == plugin_id,
    ))
    session.commit()


async def _discover(provider: MCPProvider) -> dict[str, str]:
    headers = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": PROTOCOL_VERSION}
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        oauth_server_url = provider.oauth_server_url or provider.server_url
        challenge = await client.post(oauth_server_url, json=INITIALIZE_BODY, headers=headers)
        resource_metadata_url = _resource_metadata_url(challenge.headers.get("www-authenticate", ""))
        if not resource_metadata_url:
            parsed_server = urlparse(oauth_server_url)
            issuer = f"{parsed_server.scheme}://{parsed_server.netloc}"
            oauth_metadata = await _authorization_metadata(client, issuer)
            return {
                "resource": oauth_server_url,
                "authorization_endpoint": str(oauth_metadata["authorization_endpoint"]),
                "token_endpoint": str(oauth_metadata["token_endpoint"]),
                "registration_endpoint": str(oauth_metadata.get("registration_endpoint") or ""),
            }
        resource_response = await client.get(resource_metadata_url)
        resource_response.raise_for_status()
        resource_metadata = resource_response.json()
        authorization_servers = resource_metadata.get("authorization_servers")
        if not isinstance(authorization_servers, list) or not authorization_servers:
            raise RuntimeError(f"{provider.id.title()} did not advertise an authorization server.")
        issuer = str(authorization_servers[0]).rstrip("/")
        oauth_metadata = await _authorization_metadata(client, issuer)
    return {
        "resource": str(resource_metadata.get("resource") or oauth_server_url),
        "authorization_endpoint": str(oauth_metadata["authorization_endpoint"]),
        "token_endpoint": str(oauth_metadata["token_endpoint"]),
        "registration_endpoint": str(oauth_metadata.get("registration_endpoint") or ""),
    }


async def _authorization_metadata(client: httpx.AsyncClient, issuer: str) -> dict[str, object]:
    candidates = (
        f"{issuer}/.well-known/oauth-authorization-server",
        f"{issuer}/.well-known/openid-configuration",
    )
    for url in candidates:
        response = await client.get(url)
        if response.status_code == 200:
            metadata = response.json()
            if metadata.get("authorization_endpoint") and metadata.get("token_endpoint"):
                return metadata
    raise RuntimeError("The plugin authorization service could not be discovered.")


async def _client_information(provider: MCPProvider, discovery: dict[str, str]) -> dict[str, object]:
    settings = get_settings()
    if provider.client_setting:
        return {
            "client_id": getattr(settings, provider.client_setting),
            "client_secret": getattr(settings, provider.secret_setting or ""),
            "token_endpoint_auth_method": "client_secret_post",
        }
    registration_endpoint = discovery["registration_endpoint"]
    if not registration_endpoint:
        raise RuntimeError(f"{provider.id.title()} requires a registered OAuth client.")
    payload = {
        "client_name": "Front Desk",
        "redirect_uris": [callback_uri()],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        "application_type": "native",
        "scope": provider.scopes,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(registration_endpoint, json=payload)
        if response.is_error:
            raise RuntimeError(_oauth_error(response, f"{provider.id.title()} could not register Front Desk."))
        information = response.json()
    if not information.get("client_id"):
        raise RuntimeError(f"{provider.id.title()} did not return a client registration.")
    return information


async def _verify_connection(provider: MCPProvider, access_token: str) -> int:
    try:
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {access_token}"}, timeout=25) as client:
            async with streamable_http_client(provider.server_url, http_client=client) as streams:
                read_stream, write_stream, _ = streams
                async with ClientSession(read_stream, write_stream) as mcp_session:
                    await mcp_session.initialize()
                    tools = await mcp_session.list_tools()
                    if provider.id == "atlassian":
                        await _verify_atlassian_tools(mcp_session, {tool.name for tool in tools.tools})
                    return len(tools.tools)
    except BaseExceptionGroup as error:
        detail = _first_exception(error)
        message = str(detail) or repr(detail)
        raise RuntimeError(f"{provider.id.title()} MCP verification failed ({type(detail).__name__}): {message}") from detail


def _first_exception(error: BaseExceptionGroup) -> Exception:
    detail: BaseException = error
    while isinstance(detail, BaseExceptionGroup):
        detail = detail.exceptions[0]
    return detail if isinstance(detail, Exception) else RuntimeError(str(detail))


async def _verify_atlassian_tools(mcp_session: ClientSession, tool_names: set[str]) -> None:
    required = {
        "getAccessibleAtlassianResources",
        "getVisibleJiraProjects",
        "searchJiraIssuesUsingJql",
    }
    missing = required - tool_names
    if missing:
        raise RuntimeError(f"Atlassian did not provide required tools: {', '.join(sorted(missing))}.")

    resources = await mcp_session.call_tool("getAccessibleAtlassianResources", {})
    cloud_id = _first_atlassian_cloud_id(_tool_text(resources))
    projects = await mcp_session.call_tool("getVisibleJiraProjects", {
        "cloudId": cloud_id,
        "maxResults": 1,
    })
    if projects.is_error:
        raise RuntimeError(_tool_text(projects) or "Atlassian could not list Jira projects.")
    search = await mcp_session.call_tool("searchJiraIssuesUsingJql", {
        "cloudId": cloud_id,
        "jql": "ORDER BY created DESC",
        "maxResults": 1,
    })
    if search.is_error:
        raise RuntimeError(_tool_text(search) or "Atlassian could not search Jira.")


def _tool_text(result: object) -> str:
    content = getattr(result, "content", [])
    return "\n".join(item.text for item in content if getattr(item, "type", None) == "text")


def _first_atlassian_cloud_id(value: str) -> str:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as error:
        raise RuntimeError("Atlassian returned an invalid site list.") from error
    sites = payload if isinstance(payload, list) else payload.get("resources", payload.get("sites", []))
    if not isinstance(sites, list) or not sites or not isinstance(sites[0], dict):
        raise RuntimeError("Atlassian did not return an accessible site.")
    cloud_id = sites[0].get("id") or sites[0].get("cloudId") or sites[0].get("url")
    if not isinstance(cloud_id, str) or not cloud_id:
        raise RuntimeError("Atlassian did not return a site identifier.")
    return cloud_id


def _resource_metadata_url(header: str) -> str | None:
    match = re.search(r'resource_metadata="([^"]+)"', header)
    return match.group(1) if match else None


def _provider(plugin_id: str) -> MCPProvider:
    provider = PROVIDERS.get(plugin_id)
    if not provider:
        raise ValueError("This plugin does not use an external account connection.")
    return provider


def _account_label(provider: MCPProvider, tokens: dict[str, object]) -> str:
    for key in ("workspace_name", "team_name", "organization_name"):
        value = tokens.get(key)
        if isinstance(value, str) and value:
            return value
    id_token = tokens.get("id_token")
    if isinstance(id_token, str):
        try:
            claims = jwt.decode(id_token, options={"verify_signature": False, "verify_aud": False})
            for key in ("email", "name", "preferred_username"):
                value = claims.get(key)
                if isinstance(value, str) and value:
                    return value
        except jwt.PyJWTError:
            pass
    return f"{provider.id.title()} account"


def _oauth_error(response: httpx.Response, fallback: str) -> str:
    try:
        payload = response.json()
    except ValueError:
        return fallback
    detail = payload.get("error_description") or payload.get("error") or payload.get("message")
    return str(detail) if detail else fallback


def _token_payload(response: httpx.Response) -> dict[str, object]:
    try:
        payload = response.json()
    except ValueError:
        values = parse_qs(response.text, keep_blank_values=True)
        payload = {key: items[-1] for key, items in values.items() if items}
    if not isinstance(payload, dict) or not payload:
        raise RuntimeError("The plugin returned an empty token response.")
    return payload
