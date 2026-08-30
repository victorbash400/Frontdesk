"""Non-blocking runtime ownership: PostgreSQL advisory locks, released on disconnect."""

import hashlib
from contextlib import contextmanager
from threading import Lock

from sqlalchemy import text

from app.database import engine


_local_guard = Lock()
_local_owners: set[int] = set()


@contextmanager
def runtime_lock(namespace: str, identity: str):
    key = int.from_bytes(hashlib.sha256(f"{namespace}:{identity}".encode()).digest()[:8], "big", signed=True)
    if engine.dialect.name == "postgresql":
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            acquired = bool(connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}))
            try:
                yield acquired
            finally:
                if acquired:
                    connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
        return
    if engine.dialect.name != "sqlite":
        raise RuntimeError("Runtime ownership requires PostgreSQL or local SQLite.")
    with _local_guard:
        acquired = key not in _local_owners
        if acquired:
            _local_owners.add(key)
    try:
        yield acquired
    finally:
        if acquired:
            with _local_guard:
                _local_owners.remove(key)
