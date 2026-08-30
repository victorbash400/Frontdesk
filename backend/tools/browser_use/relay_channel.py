"""Bounded, event-driven browser frames between Cloud Run instances."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import DateTime, String, Text, delete
from sqlalchemy.orm import Mapped, mapped_column

from app.agent_tool_channel import ready_events
from app.database import Base, SessionLocal
from app.event_stream import account_events


MAX_FRAME_BYTES = 32 * 1024 * 1024


class BrowserRelayFrame(Base):
    __tablename__ = "browser_relay_frames"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    connection_id: Mapped[str] = mapped_column(String(64), index=True)
    recipient: Mapped[str] = mapped_column(String(16))
    payload: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, default=lambda: datetime.now(timezone.utc) + timedelta(minutes=2))


class RelayChannel:
    def __init__(self, connection_id: str, side: str):
        if side not in {"owner", "extension"}:
            raise ValueError("Unknown browser relay side.")
        self.connection_id = connection_id
        self.side = side
        self.peer = "extension" if side == "owner" else "owner"
        self.incoming = asyncio.Queue(maxsize=1)
        self.acknowledgements: dict[str, asyncio.Future] = {}
        self.connected = asyncio.Event()
        self._sending = asyncio.Lock()

    def _publish(self, event: dict) -> None:
        account_events.publish(f"browser:{self.connection_id}:{self.peer}", event)

    async def send(self, payload: str) -> None:
        if len(payload.encode()) > MAX_FRAME_BYTES:
            raise ValueError("Browser relay frame exceeds 32 MiB.")
        async with self._sending:
            identity = str(uuid4())
            acknowledgement = asyncio.get_running_loop().create_future()
            self.acknowledgements[identity] = acknowledgement
            try:
                with SessionLocal() as database:
                    database.add(BrowserRelayFrame(id=identity, connection_id=self.connection_id, recipient=self.peer, payload=payload))
                    database.commit()
                self._publish({"type": "frame", "id": identity})
                async with asyncio.timeout(30):
                    await acknowledgement
            finally:
                self.acknowledgements.pop(identity, None)
                with SessionLocal() as database:
                    database.execute(delete(BrowserRelayFrame).where(BrowserRelayFrame.id == identity))
                    database.commit()

    async def receive(self) -> str:
        return await self.incoming.get()

    async def _consume(self, events, first) -> None:
        pending = first
        try:
            while True:
                async with asyncio.timeout(45 if self.connected.is_set() else 120):
                    event = await pending
                kind = event.get("type")
                if kind == "close":
                    raise ConnectionError("The browser relay peer closed.")
                if kind == "connected":
                    self.connected.set()
                elif kind == "ack":
                    future = self.acknowledgements.get(event.get("id"))
                    if future is not None and not future.done():
                        future.set_result(None)
                elif kind == "frame":
                    with SessionLocal() as database:
                        payload = database.execute(delete(BrowserRelayFrame).where(
                            BrowserRelayFrame.id == event.get("id"),
                            BrowserRelayFrame.connection_id == self.connection_id,
                            BrowserRelayFrame.recipient == self.side,
                        ).returning(BrowserRelayFrame.payload)).scalar_one_or_none()
                        database.commit()
                    if payload is None:
                        raise ConnectionError("Browser relay frame is missing or already consumed.")
                    await self.incoming.put(payload)
                    self._publish({"type": "ack", "id": event["id"]})
                pending = asyncio.create_task(anext(events))
        finally:
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)

    async def _heartbeat(self) -> None:
        while True:
            await asyncio.sleep(15)
            self._publish({"type": "heartbeat"})

    @asynccontextmanager
    async def open(self):
        key = f"browser:{self.connection_id}:{self.side}"
        with SessionLocal() as database:
            database.execute(delete(BrowserRelayFrame).where(BrowserRelayFrame.expires_at < datetime.now(timezone.utc)))
            database.commit()
        async with ready_events(key) as (events, first):
            consumer = asyncio.create_task(self._consume(events, first))
            heartbeat = asyncio.create_task(self._heartbeat())
            try:
                yield consumer
            finally:
                try:
                    self._publish({"type": "close"})
                finally:
                    consumer.cancel()
                    heartbeat.cancel()
                    await asyncio.gather(consumer, heartbeat, return_exceptions=True)
                    with SessionLocal() as database:
                        database.execute(delete(BrowserRelayFrame).where(
                            BrowserRelayFrame.connection_id == self.connection_id,
                            BrowserRelayFrame.recipient == self.side,
                        ))
                        database.commit()

    def announce_connected(self) -> None:
        self._publish({"type": "connected"})


async def until_disconnected(*awaitables) -> None:
    tasks = {asyncio.ensure_future(awaitable) for awaitable in awaitables}
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
