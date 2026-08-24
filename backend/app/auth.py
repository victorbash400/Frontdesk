import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_session
from .models import Account


def require_account_id(
    account_id: Annotated[str | None, Header(alias="X-Front-Desk-Account")] = None,
    internal_secret: Annotated[str | None, Header(alias="X-Front-Desk-Internal-Secret")] = None,
    session: Session = Depends(get_session),
) -> str:
    expected_secret = get_settings().internal_secret
    if not account_id or not internal_secret or not hmac.compare_digest(internal_secret, expected_secret):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication is required.")
    if not session.get(Account, account_id):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication is required.")
    return account_id
