import asyncio
import hashlib
import json
from collections.abc import AsyncIterator

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.genai import types

from agents.agents import name_chat
from agents.goals_chat_agent import create_goals_chat_app
from app.chat_stream import sessions


runner = Runner(app=create_goals_chat_app(), session_service=sessions)
_session_locks: dict[str, asyncio.Lock] = {}


async def stream_goals_chat(*, account_id: str, chat_id: str, message: str, create_title: bool) -> AsyncIterator[str]:
    session_id = hashlib.sha256(f"{account_id}:goals-chat:{chat_id}".encode()).hexdigest()
    lock = _session_locks.setdefault(session_id, asyncio.Lock())
    async with lock:
        existing = await sessions.get_session(app_name=runner.app_name, user_id=account_id, session_id=session_id)
        if not existing:
            await sessions.create_session(app_name=runner.app_name, user_id=account_id, session_id=session_id, state={"account_id": account_id})
        assistant_text = ""
        reasoning_text = ""
        seen_calls: set[str] = set()
        seen_responses: set[str] = set()
        try:
            async for event in runner.run_async(user_id=account_id, session_id=session_id, new_message=types.Content(role="user", parts=[types.Part.from_text(text=message)]), run_config=RunConfig(streaming_mode=StreamingMode.SSE)):
                if event.error_message:
                    yield _sse({"type": "error", "error": event.error_message})
                    continue
                for call in event.get_function_calls() if hasattr(event, "get_function_calls") else []:
                    call_id = call.id or call.name
                    if call_id in seen_calls:
                        continue
                    seen_calls.add(call_id)
                    yield _sse({"type": "tool_call", "id": call_id, "name": call.name, "args": call.args or {}})
                for response in event.get_function_responses() if hasattr(event, "get_function_responses") else []:
                    response_id = response.id or response.name
                    if response_id in seen_responses:
                        continue
                    seen_responses.add(response_id)
                    result = dict(response.response or {})
                    yield _sse({"type": "tool_response", "id": response_id, "name": response.name, "status": "error" if result.get("error") or result.get("status") == "failed" else "done"})
                if event.content:
                    for part in event.content.parts or []:
                        if not part.text:
                            continue
                        if part.thought:
                            delta = _text_delta(reasoning_text, part.text, bool(event.partial))
                            reasoning_text += delta
                            if delta:
                                yield _sse({"type": "reasoning", "content": delta})
                            continue
                        delta = _text_delta(assistant_text, part.text, bool(event.partial))
                        assistant_text += delta
                        if delta:
                            yield _sse({"type": "content", "content": delta})
            if not assistant_text.strip():
                yield _sse({"type": "error", "error": "The Goals supervisor returned no answer."})
                return
            if create_title and assistant_text.strip():
                yield _sse({"type": "title", "title": await name_chat(message, assistant_text)})
            yield _sse({"type": "done"})
        except Exception as error:
            yield _sse({"type": "error", "error": str(error)})


def _sse(event: dict[str, object]) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


def _text_delta(accumulated: str, incoming: str, partial: bool) -> str:
    if partial:
        return incoming
    if incoming.startswith(accumulated):
        return incoming[len(accumulated):]
    if accumulated.endswith(incoming):
        return ""
    return incoming
