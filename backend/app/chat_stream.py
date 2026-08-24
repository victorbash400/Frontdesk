import asyncio
import hashlib
import json
from collections.abc import AsyncIterator

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types

from agents.agents import create_front_desk_app, name_chat
from app.config import get_settings


sessions = DatabaseSessionService(get_settings().agent_session_database_url)
runner = Runner(app=create_front_desk_app(), session_service=sessions)
_session_locks: dict[str, asyncio.Lock] = {}


async def stream_agent_events(*, account_id: str, client_id: str, chat_id: str, message: str, create_title: bool) -> AsyncIterator[str]:
    session_id = session_key(account_id, client_id, chat_id)
    lock = _session_locks.setdefault(session_id, asyncio.Lock())
    async with lock:
        try:
            existing = await sessions.get_session(
                app_name=runner.app_name,
                user_id=account_id,
                session_id=session_id,
            )
            if not existing:
                await sessions.create_session(
                    app_name=runner.app_name,
                    user_id=account_id,
                    session_id=session_id,
                )

            assistant_text = ""
            event_stream = runner.run_async(
                user_id=account_id,
                session_id=session_id,
                new_message=types.Content(role="user", parts=[types.Part.from_text(text=message)]),
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            )
            async for event in event_stream:
                if event.error_message:
                    yield sse({"type": "error", "error": event.error_message})
                    continue
                if not event.partial or not event.content:
                    continue
                for part in event.content.parts or []:
                    if not part.text:
                        continue
                    if not part.thought:
                        assistant_text += part.text
                    yield sse({
                        "type": "reasoning" if part.thought else "content",
                        "content": part.text,
                    })

            if create_title and assistant_text.strip():
                yield sse({"type": "title", "title": await name_chat(message, assistant_text)})
            yield sse({"type": "done"})
        except Exception as error:
            yield sse({"type": "error", "error": str(error)})


def session_key(account_id: str, client_id: str, chat_id: str) -> str:
    return hashlib.sha256(f"{account_id}:{client_id}:{chat_id}".encode()).hexdigest()


def sse(event: dict[str, object]) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"
