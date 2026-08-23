import hashlib
import hmac
import os
import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Account, Workspace


DEMO_EMAIL = "demo@operator.local"
DEMO_PASSWORD = "operator-demo"
EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def create_account(session: Session, email_input: str, password: str, name_input: str) -> Account:
    email = normalize_email(email_input)
    name = name_input.strip()
    validate_account(email, password, name)
    if account_by_email(session, email):
        raise ValueError("An account with this email already exists")
    salt = os.urandom(16).hex()
    account = Account(email=email, name=name, salt=salt, password_hash=hash_password(password, salt))
    session.add(account)
    try:
        session.flush()
        session.add(Workspace(owner_id=account.id, name="Operator"))
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ValueError("An account with this email already exists") from error
    session.refresh(account)
    return account


def authenticate_account(session: Session, email_input: str, password: str) -> Account | None:
    email = normalize_email(email_input)
    if email == DEMO_EMAIL:
        ensure_demo_account(session)
    account = account_by_email(session, email)
    if not account or not hmac.compare_digest(hash_password(password, account.salt), account.password_hash):
        return None
    return account


def ensure_demo_account(session: Session) -> Account:
    account = account_by_email(session, DEMO_EMAIL)
    return account or create_account(session, DEMO_EMAIL, DEMO_PASSWORD, "Demo")


def account_by_email(session: Session, email: str) -> Account | None:
    return session.scalar(select(Account).where(Account.email == normalize_email(email)))


def hash_password(password: str, salt: str) -> str:
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1, dklen=64).hex()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_account(email: str, password: str, name: str) -> None:
    if not EMAIL.fullmatch(email):
        raise ValueError("Enter a valid email address")
    if not name:
        raise ValueError("Enter your name")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
