"""Account-scoped public transport for Playwright's private extension socket."""

import asyncio
import hashlib
import logging
import re
import secrets
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import DateTime, ForeignKey, String, Text, update
from sqlalchemy.orm import Mapped, mapped_column
from websockets.asyncio.client import connect

from app.auth import require_account_id
from app.config import get_settings
from app.database import Base, SessionLocal
from app.event_stream import account_events


INSTANCE_ID = str(uuid4())
logger = logging.getLogger("uvicorn.error")
router = APIRouter()


class BrowserRelayConnection(Base):
    __tablename__ = "browser_relay_connections"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    instance_id: Mapped[str] = mapped_column(String(36))
    local_endpoint: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(24), default="pending")


class ConnectionRequest(BaseModel):
    endpoint: str


def validate_endpoint(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    if (
        parsed.scheme != "ws" or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}
        or not parsed.port or parsed.username or parsed.password or parsed.query or parsed.fragment
        or not re.fullmatch(r"/extension/[0-9a-f-]{36}", parsed.path)
    ):
        raise ValueError("Invalid private Playwright relay endpoint.")
    return endpoint


@router.post("/internal/browser/connections")
async def register_connection(body: ConnectionRequest, account_id: str = Depends(require_account_id)) -> dict[str, str]:
    try:
        endpoint = validate_endpoint(body.endpoint)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    ticket = secrets.token_urlsafe(32)
    connection_id = hashlib.sha256(ticket.encode()).hexdigest()
    with SessionLocal() as session:
        session.add(BrowserRelayConnection(
            id=connection_id, account_id=account_id, instance_id=INSTANCE_ID,
            local_endpoint=endpoint, expires_at=datetime.now(timezone.utc) + timedelta(minutes=2),
        ))
        session.commit()
    origin = get_settings().public_api_url.rstrip("/").replace("https://", "wss://").replace("http://", "ws://")
    url = f"{origin}/api/browser/relay/{ticket}"
    account_events.publish(account_id, {"type": "browser_connection_requested", "relay_url": url})
    logger.info("browser=%s account=%s connection=requested instance=%s", connection_id, account_id, INSTANCE_ID)
    return {"status": "requested"}


@router.websocket("/api/browser/relay/{ticket}")
async def relay_socket(socket: WebSocket, ticket: str) -> None:
    connection_id = hashlib.sha256(ticket.encode()).hexdigest()
    with SessionLocal() as session:
        endpoint = session.execute(update(BrowserRelayConnection).where(
            BrowserRelayConnection.id == connection_id,
            BrowserRelayConnection.instance_id == INSTANCE_ID,
            BrowserRelayConnection.state == "pending",
            BrowserRelayConnection.expires_at > datetime.now(timezone.utc),
        ).values(state="connected").returning(BrowserRelayConnection.local_endpoint)).scalar_one_or_none()
        session.commit()
    if not endpoint:
        await socket.close(code=1008, reason="Browser connection expired, already used, or belongs to another runtime.")
        return
    await socket.accept()
    logger.info("browser=%s connection=connected", connection_id)
    try:
        async with connect(endpoint, max_size=32 * 1024 * 1024, open_timeout=10) as upstream:
            async def to_playwright() -> None:
                while True:
                    await upstream.send(await socket.receive_text())

            async def to_extension() -> None:
                async for message in upstream:
                    await socket.send_text(message.decode() if isinstance(message, bytes) else message)

            tasks = {asyncio.create_task(to_playwright()), asyncio.create_task(to_extension())}
            try:
                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    task.result()
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("browser=%s connection=failed", connection_id)
    finally:
        with SessionLocal() as session:
            session.execute(update(BrowserRelayConnection).where(BrowserRelayConnection.id == connection_id).values(state="closed"))
            session.commit()
        with suppress(RuntimeError):
            await socket.close()
        logger.info("browser=%s connection=closed", connection_id)
