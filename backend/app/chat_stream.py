import asyncio
import hashlib
import json
from collections.abc import AsyncIterator

from agents.agents import ToolEventRecorder, create_operator_agent, name_chat


_session_locks: dict[str, asyncio.Lock] = {}


async def stream_agent_events(*, account_id: str, client_id: str, chat_id: str, message: str, create_title: bool) -> AsyncIterator[str]:
    session_id = session_key(account_id, client_id, chat_id)
    lock = _session_locks.setdefault(session_id, asyncio.Lock())
    async with lock:
        tool_events = ToolEventRecorder()
        agent = create_operator_agent(session_id, tool_events)
        assistant_text = ""
        tool_names: dict[str, str] = {}
        try:
            async for event in agent.stream_async(message):
                for completed in tool_events.drain():
                    yield sse({"type": "tool_response", **completed})
                content = event.get("data")
                if isinstance(content, str) and content:
                    assistant_text += content
                    yield sse({"type": "content", "content": content})

                tool_use = event.get("current_tool_use")
                if isinstance(tool_use, dict):
                    tool_id = str(tool_use.get("toolUseId") or "")
                    tool_name = str(tool_use.get("name") or "")
                    if tool_id and tool_name and tool_id not in tool_names:
                        tool_names[tool_id] = tool_name
                        tool_input = tool_use.get("input")
                        yield sse({
                            "type": "tool_call",
                            "id": tool_id,
                            "name": tool_name,
                            "args": tool_input if isinstance(tool_input, dict) else {},
                        })

            for completed in tool_events.drain():
                yield sse({"type": "tool_response", **completed})
            if create_title and assistant_text.strip():
                yield sse({"type": "title", "title": await name_chat(message, assistant_text)})
            yield sse({"type": "done"})
        except Exception as error:
            yield sse({"type": "error", "error": str(error)})


def session_key(account_id: str, client_id: str, chat_id: str) -> str:
    value = f"{account_id}:{client_id}:{chat_id}".encode()
    return hashlib.sha256(value).hexdigest()


def sse(event: dict[str, object]) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"
