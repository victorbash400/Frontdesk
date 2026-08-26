import asyncio
import json
from collections.abc import AsyncIterator
from threading import Lock

import psycopg

from .config import get_settings


EVENT_CHANNEL = "front_desk_events"
KEEPALIVE_SECONDS = 15


class AccountEventBroker:
    def __init__(self) -> None:
        self._lock = Lock()
        self._subscribers: dict[str, set[tuple[asyncio.AbstractEventLoop, asyncio.Queue[dict[str, object]]]]] = {}

    async def subscribe(self, account_id: str) -> AsyncIterator[str]:
        if _postgres_url():
            async for event in self._subscribe_postgres(account_id):
                yield event
            return
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
        subscriber = (loop, queue)
        with self._lock:
            self._subscribers.setdefault(account_id, set()).add(subscriber)
        try:
            yield frame({"type": "ready"})
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SECONDS)
                except TimeoutError:
                    yield keepalive()
                    continue
                yield frame(event)
        finally:
            with self._lock:
                subscribers = self._subscribers.get(account_id)
                if subscribers:
                    subscribers.discard(subscriber)
                    if not subscribers:
                        self._subscribers.pop(account_id, None)

    def publish(self, account_id: str, event: dict[str, object]) -> None:
        postgres_url = _postgres_url()
        if postgres_url:
            payload = json.dumps({"account_id": account_id, "event": event}, default=str)
            with psycopg.connect(postgres_url, autocommit=True) as connection:
                connection.execute("SELECT pg_notify(%s, %s)", (EVENT_CHANNEL, payload))
            return
        with self._lock:
            subscribers = tuple(self._subscribers.get(account_id, ()))
        for loop, queue in subscribers:
            loop.call_soon_threadsafe(queue.put_nowait, event)

    async def _subscribe_postgres(self, account_id: str) -> AsyncIterator[str]:
        postgres_url = _postgres_url()
        if not postgres_url:
            return
        connection = await psycopg.AsyncConnection.connect(postgres_url, autocommit=True)
        try:
            await connection.execute(f"LISTEN {EVENT_CHANNEL}")
            yield frame({"type": "ready"})
            notifications = connection.notifies().__aiter__()
            next_notification = asyncio.create_task(anext(notifications))
            while True:
                done, _ = await asyncio.wait({next_notification}, timeout=KEEPALIVE_SECONDS)
                if not done:
                    yield keepalive()
                    continue
                notification = next_notification.result()
                next_notification = asyncio.create_task(anext(notifications))
                payload = json.loads(notification.payload)
                if payload.get("account_id") == account_id and isinstance(payload.get("event"), dict):
                    yield frame(payload["event"])
        finally:
            if "next_notification" in locals():
                next_notification.cancel()
                await asyncio.gather(next_notification, return_exceptions=True)
            await connection.close()


def frame(event: dict[str, object]) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


def keepalive() -> str:
    return ": keepalive\n\n"


account_events = AccountEventBroker()


def _postgres_url() -> str | None:
    database_url = get_settings().database_url
    if not database_url.startswith("postgresql"):
        return None
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)
