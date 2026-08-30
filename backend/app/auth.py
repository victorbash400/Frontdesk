import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_session
from .models import Account


def require_account_id(
    account_id: Annotated[str | None, Header(alias="X-Front-Desk-Account")] = None,
    internal_secret: Annotated[str | None, Header(alias="X-Front-Desk-Internal-Secret")] = None,
    session: Session = Depends(get_session, scope="function"),
) -> str:
    expected_secret = get_settings().internal_secret
    if not account_id or not internal_secret or not hmac.compare_digest(internal_secret, expected_secret):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication is required.")
    if not session.get(Account, account_id):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication is required.")
    return account_id


def require_scheduler(
    authorization: Annotated[str | None, Header()] = None,
    internal_secret: Annotated[str | None, Header(alias="X-Front-Desk-Internal-Secret")] = None,
) -> None:
    settings = get_settings()
    if internal_secret and hmac.compare_digest(internal_secret, settings.internal_secret):
        return
    if not authorization or not authorization.startswith("Bearer ") or not settings.scheduler_audience or not settings.scheduler_service_account:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication is required.")
    try:
        claims = id_token.verify_oauth2_token(authorization.removeprefix("Bearer "), GoogleAuthRequest(), settings.scheduler_audience)
    except ValueError as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication is required.") from error
    if claims.get("email") != settings.scheduler_service_account or not claims.get("email_verified"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication is required.")
