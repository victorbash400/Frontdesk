import base64
import hashlib

from cryptography.fernet import Fernet

from .config import get_settings


def encrypt_secret(value: str) -> str:
    return _cipher().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    return _cipher().decrypt(value.encode()).decode()


def _cipher() -> Fernet:
    secret = get_settings().internal_secret.encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)
