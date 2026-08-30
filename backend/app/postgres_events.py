"""One PostgreSQL LISTEN connection per event loop, shared by all subscribers."""

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import psycopg
from psycopg import sql


@dataclass
class Listener:
    ready: asyncio.Future
    subscribers: dict[asyncio.Queue, str] = field(default_factory=dict)
    task: asyncio.Task | None = None
    error: Exception | None = None


class PostgresEvents:
    def __init__(self, channel: str):
        self.channel = channel
        self.listeners: dict[asyncio.AbstractEventLoop, Listener] = {}

    async def events(self, url: str, account_id: str, ready: asyncio.Event | None) -> AsyncIterator[dict]:
        loop = asyncio.get_running_loop()
        listener = self.listeners.get(loop)
        if listener is None:
            listener = Listener(loop.create_future())
            self.listeners[loop] = listener
            listener.task = loop.create_task(self._listen(url, listener))
        queue: asyncio.Queue = asyncio.Queue()
        listener.subscribers[queue] = account_id
        try:
            await asyncio.shield(listener.ready)
            if listener.error is not None:
                raise listener.error
            if ready is not None:
                ready.set()
            while True:
                event = await queue.get()
                if isinstance(event, Exception):
                    raise event
                yield event
        finally:
            listener.subscribers.pop(queue, None)
            if not listener.subscribers:
                if self.listeners.get(loop) is listener:
                    self.listeners.pop(loop)
                listener.task.cancel()
                await asyncio.gather(listener.task, return_exceptions=True)

    async def _listen(self, url: str, listener: Listener) -> None:
        connection = None
        try:
            connection = await psycopg.AsyncConnection.connect(url, autocommit=True)
            await connection.execute(sql.SQL("LISTEN {}").format(sql.Identifier(self.channel)))
            listener.ready.set_result(None)
            async for notification in connection.notifies():
                payload = json.loads(notification.payload)
                if not isinstance(payload.get("event"), dict):
                    continue
                for queue, account_id in tuple(listener.subscribers.items()):
                    if account_id == payload.get("account_id"):
                        queue.put_nowait(payload["event"])
            raise ConnectionError("PostgreSQL event listener ended unexpectedly.")
        except Exception as error:
            listener.error = error
            if not listener.ready.done():
                listener.ready.set_exception(error)
            for queue in tuple(listener.subscribers):
                queue.put_nowait(error)
        finally:
            if connection is not None:
                await connection.close()
