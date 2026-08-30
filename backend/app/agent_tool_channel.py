"""Event-driven routing to the instance that owns a tool run. No polling."""

import asyncio
import json
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import update

from app.agent_tool_runs import AgentToolRequest
from app.database import SessionLocal
from app.event_stream import account_events


@asynccontextmanager
async def ready_events(account_id: str):
    ready = asyncio.Event()
    events = account_events.events(account_id, ready).__aiter__()
    first = asyncio.create_task(anext(events))
    ready_task = asyncio.create_task(ready.wait())
    try:
        async with asyncio.timeout(15):
            await asyncio.wait({first, ready_task}, return_when=asyncio.FIRST_COMPLETED)
            if first.done():
                first.result()
            await ready_task
        yield events, first
    finally:
        first.cancel()
        ready_task.cancel()
        await asyncio.gather(first, ready_task, return_exceptions=True)
        await events.aclose()


async def route_request(account_id: str, run_id: str, operation: str, payload: dict) -> dict:
    request_id = str(uuid4())
    async with ready_events(account_id) as (events, first):
        with SessionLocal() as database:
            database.add(AgentToolRequest(id=request_id, run_id=run_id, operation=operation, payload=json.dumps(payload)))
            database.commit()
        account_events.publish(account_id, {"type": "agent_tool_request", "run_id": run_id, "request_id": request_id})
        try:
            async with asyncio.timeout(180):
                event = await first
                while True:
                    if event.get("type") == "agent_tool_run_closed" and event.get("run_id") == run_id:
                        raise HTTPException(503, "The owning tool runtime disconnected.")
                    if event.get("type") == "agent_tool_response" and event.get("request_id") == request_id:
                        with SessionLocal() as database:
                            record = database.get(AgentToolRequest, request_id)
                            response = json.loads(record.response)
                            database.delete(record)
                            database.commit()
                        if "http_error" in response:
                            raise HTTPException(response["http_error"], response["detail"])
                        return response["result"]
                    event = await anext(events)
        except TimeoutError as error:
            raise HTTPException(504, "The owning tool runtime did not respond; the call was not retried.") from error
        finally:
            with SessionLocal() as database:
                database.execute(update(AgentToolRequest).where(AgentToolRequest.id == request_id, AgentToolRequest.status == "pending").values(status="abandoned"))
                database.commit()


async def serve_requests(account_id: str, run_id: str, handler, ready: asyncio.Event) -> None:
    async with ready_events(account_id) as (events, first):
        ready.set()
        event = await first
        while True:
            if event.get("type") == "agent_tool_request" and event.get("run_id") == run_id:
                request_id = event["request_id"]
                with SessionLocal() as database:
                    record = database.execute(update(AgentToolRequest).where(
                        AgentToolRequest.id == request_id, AgentToolRequest.run_id == run_id, AgentToolRequest.status == "pending",
                    ).values(status="processing").returning(AgentToolRequest.operation, AgentToolRequest.payload)).first()
                    database.commit()
                if record:
                    try:
                        response = {"result": await handler(record.operation, json.loads(record.payload))}
                    except HTTPException as error:
                        response = {"http_error": error.status_code, "detail": error.detail}
                    except Exception as error:
                        response = {"http_error": 500, "detail": str(error).strip() or type(error).__name__}
                    with SessionLocal() as database:
                        database.execute(update(AgentToolRequest).where(AgentToolRequest.id == request_id).values(status="completed", response=json.dumps(response)))
                        database.commit()
                    account_events.publish(account_id, {"type": "agent_tool_response", "request_id": request_id})
            event = await anext(events)
