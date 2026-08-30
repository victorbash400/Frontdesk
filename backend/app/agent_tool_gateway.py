"""A scoped, authenticated tool gateway with persistent duplicate-call detection."""

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from app.agent_tool_binding import AgentToolBinding
from app.agent_tool_channel import route_request, serve_requests
from app.agent_tool_runs import AgentToolCall, AgentToolRun
from app.config import get_settings
from app.database import SessionLocal
from app.event_stream import account_events


OWNER_ID = str(uuid4())
router = APIRouter()
logger = logging.getLogger("uvicorn.error")


class ToolRequest(BaseModel):
    name: str = ""
    call_id: str = ""
    args: dict[str, Any] = Field(default_factory=dict)
    state: dict[str, Any] = Field(default_factory=dict)


class AgentToolGateway:
    def __init__(self) -> None:
        self.bindings: dict[str, AgentToolBinding] = {}
        self.locks: dict[str, asyncio.Lock] = {}

    @asynccontextmanager
    async def bind(self, runner, session):
        run_id, ticket = str(uuid4()), secrets.token_urlsafe(32)
        binding = AgentToolBinding(runner, session, run_id)
        with SessionLocal() as database:
            database.add(AgentToolRun(
                id=run_id, account_id=session.user_id, owner_id=OWNER_ID,
                ticket_hash=hashlib.sha256(ticket.encode()).hexdigest(),
                state=json.dumps(session.state), expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            ))
            database.commit()
        self.bindings[run_id] = binding
        self.locks[run_id] = asyncio.Lock()
        ready = asyncio.Event()
        async def handle(operation, payload):
            return await self.dispatch(run_id, session.user_id, operation, ToolRequest.model_validate(payload))
        listener = asyncio.create_task(serve_requests(session.user_id, run_id, handle, ready))
        readiness = asyncio.create_task(ready.wait())
        try:
            async with asyncio.timeout(15):
                await asyncio.wait({listener, readiness}, return_when=asyncio.FIRST_COMPLETED)
                if listener.done():
                    listener.result()
                await readiness
            yield run_id, ticket
        finally:
            listener.cancel()
            readiness.cancel()
            await asyncio.gather(listener, readiness, return_exceptions=True)
            self.bindings.pop(run_id, None)
            self.locks.pop(run_id, None)
            with SessionLocal() as database:
                record = database.get(AgentToolRun, run_id)
                record.status = "closed"
                database.commit()
            account_events.publish(session.user_id, {"type": "agent_tool_run_closed", "run_id": run_id})
            logger.info("agent_run=%s account=%s gateway=closed", run_id, session.user_id)

    def authorize(self, run_id: str, secret: str | None, authorization: str | None) -> str:
        if not secret or not hmac.compare_digest(secret, get_settings().internal_secret) or not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Agent tool authentication is required.")
        with SessionLocal() as database:
            record = database.get(AgentToolRun, run_id)
            if not record or not hmac.compare_digest(record.ticket_hash, hashlib.sha256(authorization[7:].encode()).hexdigest()):
                raise HTTPException(401, "Invalid agent tool run.")
            if record.status != "active" or record.expires_at.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
                raise HTTPException(410, "The agent tool run has ended.")
            return record.account_id

    async def dispatch(self, run_id: str, account_id: str, operation: str, body: ToolRequest) -> dict[str, Any]:
        if run_id not in self.bindings:
            return await route_request(account_id, run_id, operation, body.model_dump())
        if operation == "manifest":
            return await self.bindings[run_id].manifest()
        return await self.call(run_id, body)

    async def call(self, run_id: str, body: ToolRequest) -> dict[str, Any]:
        binding = self.bindings[run_id]
        if not body.call_id or not body.name:
            raise HTTPException(422, "A tool name and function call ID are required.")
        if body.state.get("account_id") != binding.session.user_id:
            raise HTTPException(403, "Tool account identity does not match the run.")
        call_key = hashlib.sha256(f"{run_id}:{body.call_id}".encode()).hexdigest()
        fingerprint = hashlib.sha256(json.dumps([body.name, body.args], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        async with self.locks[run_id]:
            with SessionLocal() as database:
                run = database.get(AgentToolRun, run_id)
                if run.status != "active" or run.expires_at.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
                    raise HTTPException(410, "The agent tool run has ended.")
                database.add(AgentToolCall(id=call_key, run_id=run_id, fingerprint=fingerprint))
                try:
                    database.commit()
                except IntegrityError:
                    database.rollback()
                    existing = database.get(AgentToolCall, call_key)
                    if existing.fingerprint != fingerprint:
                        raise HTTPException(409, "The function call ID was reused for a different action.")
                    if existing.status != "completed":
                        raise HTTPException(409, "This call has already started; its outcome must be checked before retrying.")
                    return json.loads(existing.response)
            # A cancelled or interrupted call stays 'executing'; it is never replayed.
            logger.info("agent_run=%s call=%s tool=%s gateway=executing", run_id, body.call_id, body.name)
            response = await binding.call(body.name, body.args, body.call_id)
            with SessionLocal() as database:
                record = database.get(AgentToolCall, call_key)
                record.status, record.response = "completed", json.dumps(response)
                run = database.get(AgentToolRun, run_id)
                run.state = json.dumps(binding.session.state)
                if response.get("end_of_agent") and run.status == "active":
                    run.status = "finished"
                database.commit()
            logger.info("agent_run=%s call=%s tool=%s gateway=recorded", run_id, body.call_id, body.name)
            return response


agent_tool_gateway = AgentToolGateway()


@router.post("/internal/agent-runs/{run_id}/{operation}")
async def agent_tool_request(
    run_id: str, operation: Literal["manifest", "call"], body: ToolRequest,
    secret: str | None = Header(default=None, alias="X-Front-Desk-Agent-Secret"),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    account_id = agent_tool_gateway.authorize(run_id, secret, authorization)
    return await agent_tool_gateway.dispatch(run_id, account_id, operation, body)
