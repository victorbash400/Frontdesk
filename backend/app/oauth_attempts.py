"""Single-use OAuth handshakes shared by all API instances."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import PluginOAuthAttempt
from .secret_store import decrypt_secret, encrypt_secret


def store_google_attempt(state: str, account_id: str, verifier: str) -> None:
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        session.execute(delete(PluginOAuthAttempt).where(PluginOAuthAttempt.expires_at < now))
        session.add(PluginOAuthAttempt(
            state=state,
            account_id=account_id,
            plugin_id="google_workspace",
            context=encrypt_secret(verifier),
            expires_at=now + timedelta(minutes=10),
        ))
        session.commit()


def consume_google_attempt(session: Session, state: str) -> tuple[str, str]:
    row = session.execute(
        delete(PluginOAuthAttempt).where(
            PluginOAuthAttempt.state == state,
            PluginOAuthAttempt.plugin_id == "google_workspace",
            PluginOAuthAttempt.expires_at > datetime.now(timezone.utc),
        ).returning(PluginOAuthAttempt.account_id, PluginOAuthAttempt.context)
    ).first()
    session.commit()
    if row is None:
        raise ValueError("The Google connection request expired or is invalid.")
    return row.account_id, decrypt_secret(row.context)
