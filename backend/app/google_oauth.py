import secrets
import base64
import hashlib
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import OAuthConnection


REDIRECT_URI = "http://127.0.0.1:8000/oauth/google/callback"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
SCOPES = (
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/tasks",
)


@dataclass
class PendingConnection:
    account_id: str


pending_connections: dict[str, PendingConnection] = {}


def _token_cipher() -> Fernet:
    secret = get_settings().internal_secret.encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def decrypt_refresh_token(connection: OAuthConnection) -> str:
    return _token_cipher().decrypt(connection.refresh_token.encode()).decode()


def connection_status(session: Session, account_id: str) -> dict[str, object]:
    settings = get_settings()
    connection = session.scalar(select(OAuthConnection).where(
        OAuthConnection.account_id == account_id,
        OAuthConnection.provider == "google_workspace",
    ))
    return {
        "configured": bool(settings.google_client_id and settings.google_client_secret),
        "connected": connection is not None,
        "email": connection.email if connection else None,
    }


def begin_connection(account_id: str) -> str:
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise RuntimeError("Google Workspace OAuth is not configured.")
    state = secrets.token_urlsafe(32)
    pending_connections[state] = PendingConnection(account_id=account_id)
    return AUTH_URL + "?" + urlencode({
        "client_id": settings.google_client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    })


async def finish_connection(session: Session, state: str, code: str) -> str:
    pending = pending_connections.pop(state, None)
    if not pending:
        raise ValueError("The Google connection request expired or is invalid.")
    settings = get_settings()
    async with httpx.AsyncClient(timeout=20) as client:
        token_response = await client.post(TOKEN_URL, data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        })
        token_response.raise_for_status()
        tokens = token_response.json()
        refresh_token = tokens.get("refresh_token")
        access_token = tokens.get("access_token")
        if not refresh_token or not access_token:
            raise RuntimeError("Google did not return an offline account token.")
        user_response = await client.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
        user_response.raise_for_status()
        email = str(user_response.json().get("email") or "")
    connection = session.scalar(select(OAuthConnection).where(
        OAuthConnection.account_id == pending.account_id,
        OAuthConnection.provider == "google_workspace",
    ))
    if connection:
        connection.email = email
        connection.refresh_token = _token_cipher().encrypt(refresh_token.encode()).decode()
        connection.scopes = str(tokens.get("scope") or "")
    else:
        session.add(OAuthConnection(
            account_id=pending.account_id,
            provider="google_workspace",
            email=email,
            refresh_token=_token_cipher().encrypt(refresh_token.encode()).decode(),
            scopes=str(tokens.get("scope") or ""),
        ))
    session.commit()
    return email


def disconnect(session: Session, account_id: str) -> None:
    connection = session.scalar(select(OAuthConnection).where(
        OAuthConnection.account_id == account_id,
        OAuthConnection.provider == "google_workspace",
    ))
    if connection:
        session.delete(connection)
        session.commit()
