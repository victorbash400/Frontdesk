"""Non-blocking runtime ownership: PostgreSQL advisory locks, released on disconnect."""

import hashlib
import logging
from contextlib import contextmanager
from threading import Lock

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.database import engine


logger = logging.getLogger(__name__)

_local_guard = Lock()
_local_owners: set[int] = set()

# Advisory locks are session scoped, so every lease must keep a connection open for as
# long as the work runs. Distinct keys can be held together on one session, so the whole
# process leases through a single connection outside the query pool. Long running
# ownership therefore never competes with request and tool traffic for pooled
# connections. See infra/README.md for the per-instance connection budget.
_lease_guard = Lock()
_lease_engine = None
_lease_connection = None


def _lease():
    global _lease_engine, _lease_connection
    if _lease_engine is None:
        _lease_engine = create_engine(get_settings().database_url, poolclass=NullPool)
    if _lease_connection is None or _lease_connection.closed:
        if _lease_connection is not None:
            logger.warning("runtime_lock lease=reconnected note=locks_held_elsewhere_may_be_reacquirable")
        _lease_connection = _lease_engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    return _lease_connection


def _discard_lease() -> None:
    global _lease_connection
    connection, _lease_connection = _lease_connection, None
    if connection is not None:
        try:
            connection.close()
        except Exception:
            pass


def _acquire(key: int) -> bool:
    with _lease_guard:
        for final in (False, True):
            try:
                return bool(_lease().scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}))
            except SQLAlchemyError:
                _discard_lease()
                if final:
                    raise
    return False


def _release(key: int) -> None:
    with _lease_guard:
        try:
            _lease().execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
        except SQLAlchemyError:
            logger.warning("runtime_lock key=%s release=failed lease=discarded", key)
            _discard_lease()


@contextmanager
def runtime_lock(namespace: str, identity: str):
    key = int.from_bytes(hashlib.sha256(f"{namespace}:{identity}".encode()).digest()[:8], "big", signed=True)
    dialect = engine.dialect.name
    if dialect not in ("postgresql", "sqlite"):
        raise RuntimeError("Runtime ownership requires PostgreSQL or local SQLite.")
    # The shared lease makes advisory locks reentrant within this process, so in-process
    # ownership is decided here and PostgreSQL only arbitrates between instances.
    with _local_guard:
        acquired = key not in _local_owners
        if acquired:
            _local_owners.add(key)
    if acquired and dialect == "postgresql":
        try:
            acquired = _acquire(key)
        except BaseException:
            with _local_guard:
                _local_owners.discard(key)
            raise
        if not acquired:
            with _local_guard:
                _local_owners.discard(key)
    try:
        yield acquired
    finally:
        if acquired:
            if dialect == "postgresql":
                _release(key)
            with _local_guard:
                _local_owners.discard(key)
