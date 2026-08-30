import asyncio
import hashlib
import json
from collections.abc import AsyncIterator

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.sessions import DatabaseSessionService
from google.genai import types

from agents.agents import create_front_desk_app, name_chat
from app.config import get_settings
from app.database import SessionLocal
from app.goals import client_goal_context
from app.agent_runner import create_runner


sessions = DatabaseSessionService(get_settings().agent_session_database_url)
runner = create_runner(app=create_front_desk_app(), session_service=sessions)
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
                    state={"account_id": account_id, "client_id": client_id},
                )

            with SessionLocal() as database:
                goal_context = client_goal_context(database, account_id, client_id)
            assistant_text = ""
            event_stream = runner.run_async(
                user_id=account_id,
                session_id=session_id,
                new_message=types.Content(role="user", parts=[types.Part.from_text(text=(
                    "Authoritative active goal board for this client:\n"
                    f"{goal_context}\n\n"
                    "Answer the user's message as this client's supervisor. Do not expose this context wrapper.\n\n"
                    f"User message:\n{message}"
                ))]),
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            )
            async for event in event_stream:
                if event.error_message:
                    yield sse({"type": "error", "error": event.error_message})
                    continue
                function_calls = event.get_function_calls() if hasattr(event, "get_function_calls") else []
                for call in function_calls:
                    yield sse({"type": "tool_call", "id": call.id or call.name, "name": call.name, "args": call.args or {}})
                function_responses = event.get_function_responses() if hasattr(event, "get_function_responses") else []
                for response in function_responses:
                    result = response.response or {}
                    yield sse({"type": "tool_response", "id": response.id or response.name, "name": response.name, "status": "error" if isinstance(result, dict) and result.get("error") else "done"})
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
