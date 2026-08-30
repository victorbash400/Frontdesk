import base64
import hashlib
import json
import secrets
from urllib.parse import urlencode, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import OAuthConnection, PluginPermission
from .secret_store import decrypt_secret, encrypt_secret
from .oauth_attempts import consume_google_attempt, store_google_attempt


AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
SCOPES = (
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.events.freebusy",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/forms.responses.readonly",
    "https://www.googleapis.com/auth/meetings.space.created",
    "https://www.googleapis.com/auth/meetings.space.readonly",
)
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.modify"
WORKSPACE_REQUIRED_SCOPES = frozenset(
    scope for scope in SCOPES
    if scope.startswith("https://www.googleapis.com/auth/") and scope != GMAIL_SCOPE
)
WORKSPACE_PERMISSIONS = (
    ("workspace.drive", "Google Drive", "Search, read, create, and organize Drive files"),
    ("workspace.docs", "Google Docs", "Read and update Google documents"),
    ("workspace.sheets", "Google Sheets", "Read and update spreadsheets"),
    ("workspace.slides", "Google Slides", "Read and update presentations"),
    ("workspace.gmail", "Gmail", "Read, send, draft, reply to, and organize email"),
    ("workspace.calendar", "Google Calendar", "Read and manage calendar events"),
    ("workspace.people", "Google Contacts", "Find people and contact details"),
    ("workspace.tasks", "Google Tasks", "Create and manage task lists and tasks"),
    ("workspace.forms", "Google Forms", "Create forms and read responses"),
    ("workspace.meet", "Google Meet", "Create meetings and read meeting details"),
)


def decrypt_refresh_token(connection: OAuthConnection) -> str:
    return decrypt_secret(connection.refresh_token)


def connection_status(session: Session, account_id: str) -> dict[str, object]:
    settings = get_settings()
    client_id, client_secret = settings.google_oauth_credentials
    connection = session.scalar(select(OAuthConnection).where(
        OAuthConnection.account_id == account_id,
        OAuthConnection.provider == "google_workspace",
    ))
    granted_scopes = set(connection.scopes.split()) if connection else set()
    unavailable_permissions = set(json.loads(connection.unavailable_permissions or "[]")) if connection else set()
    missing_scopes = sorted(WORKSPACE_REQUIRED_SCOPES - granted_scopes) if connection else []
    permission_rows = {
        permission.permission_id: permission.enabled
        for permission in session.scalars(select(PluginPermission).where(PluginPermission.account_id == account_id))
    }
    return {
        "configured": bool(client_id and client_secret),
        "connected": connection is not None and not missing_scopes,
        "needs_reconnect": connection is not None and bool(missing_scopes),
        "missing_scopes": missing_scopes,
        "email": connection.email if connection else None,
        "name": connection.profile_name if connection else None,
        "picture": f"/api/plugins/google/avatar?revision={_picture_revision(connection)}" if connection and connection.picture_url else None,
        "permissions": [
            {
                "id": permission_id,
                "name": name,
                "description": description,
                "enabled": permission_id not in unavailable_permissions and permission_rows.get(permission_id, True),
                "available": permission_id not in unavailable_permissions,
                "unavailable_reason": "Not included with this Google Workspace edition" if permission_id in unavailable_permissions else None,
            }
            for permission_id, name, description in WORKSPACE_PERMISSIONS
        ],
    }


def _picture_revision(connection: OAuthConnection) -> str:
    identity = f"{connection.email}\0{connection.picture_url}\0{connection.updated_at.isoformat()}"
    return hashlib.sha256(identity.encode()).hexdigest()[:16]


async def profile_photo(session: Session, account_id: str) -> tuple[bytes, str]:
    connection = session.scalar(select(OAuthConnection).where(
        OAuthConnection.account_id == account_id,
        OAuthConnection.provider == "google_workspace",
    ))
    picture = connection.picture_url if connection else None
    hostname = urlparse(picture).hostname if picture else None
    if not hostname or not hostname.endswith(".googleusercontent.com"):
        raise ValueError("Google profile photo is unavailable.")
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        response = await client.get(picture)
        response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if not content_type.startswith("image/"):
        raise ValueError("Google returned an invalid profile photo.")
    return response.content, content_type


def begin_connection(account_id: str) -> str:
    settings = get_settings()
    client_id, client_secret = settings.google_oauth_credentials
    if not client_id or not client_secret:
        raise RuntimeError("Google Workspace OAuth is not configured.")
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    store_google_attempt(state, account_id, verifier)
    return AUTH_URL + "?" + urlencode({
        "client_id": client_id,
        "redirect_uri": settings.public_api_url.rstrip("/") + "/oauth/google/callback",
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })


async def finish_connection(session: Session, state: str, code: str) -> str:
    account_id, verifier = consume_google_attempt(session, state)
    settings = get_settings()
    client_id, client_secret = settings.google_oauth_credentials
    async with httpx.AsyncClient(timeout=20) as client:
        token_response = await client.post(TOKEN_URL, data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "code_verifier": verifier,
            "grant_type": "authorization_code",
            "redirect_uri": settings.public_api_url.rstrip("/") + "/oauth/google/callback",
        })
        token_response.raise_for_status()
        tokens = token_response.json()
        refresh_token = tokens.get("refresh_token")
        access_token = tokens.get("access_token")
        if not refresh_token or not access_token:
            raise RuntimeError("Google did not return an offline account token.")
        user_response = await client.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
        user_response.raise_for_status()
        user = user_response.json()
        email = str(user.get("email") or "")
        name = str(user.get("name") or "")
        picture = str(user.get("picture") or "")
        granted_scopes = set(str(tokens.get("scope") or " ".join(SCOPES)).split())
        missing_scopes = WORKSPACE_REQUIRED_SCOPES - granted_scopes
        if missing_scopes:
            raise RuntimeError("Google Workspace did not grant every required permission. Reconnect and approve all requested access.")
        unavailable_permissions = {"workspace.gmail"} if GMAIL_SCOPE not in granted_scopes else set()
        unavailable_permissions.update(await _validate_workspace_token(client, access_token, check_gmail=GMAIL_SCOPE in granted_scopes))
    connection = session.scalar(select(OAuthConnection).where(
        OAuthConnection.account_id == account_id,
        OAuthConnection.provider == "google_workspace",
    ))
    if connection:
        connection.email = email
        connection.profile_name = name
        connection.picture_url = picture
        connection.refresh_token = encrypt_secret(refresh_token)
        connection.scopes = str(tokens.get("scope") or "")
        connection.unavailable_permissions = json.dumps(sorted(unavailable_permissions))
    else:
        session.add(OAuthConnection(
            account_id=account_id,
            provider="google_workspace",
            email=email,
            profile_name=name,
            picture_url=picture,
            refresh_token=encrypt_secret(refresh_token),
            scopes=str(tokens.get("scope") or ""),
            unavailable_permissions=json.dumps(sorted(unavailable_permissions)),
        ))
    for permission_id in unavailable_permissions:
        permission = session.scalar(select(PluginPermission).where(
            PluginPermission.account_id == account_id,
            PluginPermission.permission_id == permission_id,
        ))
        if permission:
            permission.enabled = False
        else:
            session.add(PluginPermission(account_id=account_id, permission_id=permission_id, enabled=False))
    session.commit()
    return email


def set_workspace_permission(session: Session, account_id: str, permission_id: str, enabled: bool) -> None:
    valid_ids = {item[0] for item in WORKSPACE_PERMISSIONS}
    if permission_id not in valid_ids:
        raise ValueError("Unknown Google Workspace permission.")
    connection = session.scalar(select(OAuthConnection).where(
        OAuthConnection.account_id == account_id,
        OAuthConnection.provider == "google_workspace",
    ))
    unavailable_permissions = set(json.loads(connection.unavailable_permissions or "[]")) if connection else set()
    if enabled and permission_id in unavailable_permissions:
        raise ValueError("This service is not included with the connected Google Workspace edition.")
    permission = session.scalar(select(PluginPermission).where(
        PluginPermission.account_id == account_id,
        PluginPermission.permission_id == permission_id,
    ))
    if permission:
        permission.enabled = enabled
    else:
        session.add(PluginPermission(account_id=account_id, permission_id=permission_id, enabled=enabled))
    session.commit()


async def _validate_workspace_token(client: httpx.AsyncClient, access_token: str, *, check_gmail: bool = True) -> set[str]:
    headers = {"Authorization": f"Bearer {access_token}"}
    checks = (
        ("workspace.gmail", "Gmail", "https://gmail.googleapis.com/gmail/v1/users/me/profile", False),
        ("workspace.drive", "Google Drive", "https://www.googleapis.com/drive/v3/files?pageSize=1&fields=files(id)", True),
    )
    unavailable_permissions: set[str] = set()
    for permission_id, product, url, required in checks:
        if permission_id == "workspace.gmail" and not check_gmail:
            unavailable_permissions.add(permission_id)
            continue
        response = await client.get(url, headers=headers)
        if response.is_success:
            continue
        try:
            detail = response.json().get("error", {}).get("message")
        except ValueError:
            detail = response.text[:300]
        if not required and "service not enabled" in str(detail or "").casefold():
            unavailable_permissions.add(permission_id)
            continue
        raise RuntimeError(f"{product} authorization failed: {detail or response.reason_phrase}. Reconnect and approve the requested access.")
    return unavailable_permissions


def disconnect(session: Session, account_id: str) -> None:
    connection = session.scalar(select(OAuthConnection).where(
        OAuthConnection.account_id == account_id,
        OAuthConnection.provider == "google_workspace",
    ))
    if connection:
        session.delete(connection)
        session.commit()
