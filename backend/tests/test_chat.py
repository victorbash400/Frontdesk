import asyncio
import json
from types import SimpleNamespace

import pytest

from agents.agents import ToolEventRecorder
from app import chat_stream
from tools.time_tool import get_current_time


def test_time_tool_returns_requested_timezone() -> None:
    result = get_current_time(timezone="Africa/Nairobi")
    assert result["timezone"] == "Africa/Nairobi"
    assert result["iso"].endswith("+03:00")
    assert result["display"].endswith("EAT")


def test_tool_event_recorder_reports_completion() -> None:
    recorder = ToolEventRecorder()
    recorder.after_tool_call(SimpleNamespace(
        exception=None,
        result={"status": "success"},
        tool_use={"toolUseId": "time-1", "name": "get_current_time"},
    ))
    assert recorder.drain() == [{"id": "time-1", "name": "get_current_time", "status": "done"}]
    assert recorder.drain() == []


def test_stream_translates_strands_events(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAgent:
        def __init__(self, recorder: ToolEventRecorder) -> None:
            self.recorder = recorder

        async def stream_async(self, _: str):
            yield {"current_tool_use": {"toolUseId": "time-1", "name": "get_current_time", "input": {"timezone": "Africa/Nairobi"}}}
            self.recorder.after_tool_call(SimpleNamespace(
                exception=None,
                result={"status": "success"},
                tool_use={"toolUseId": "time-1", "name": "get_current_time"},
            ))
            yield {"start_event_loop": True}
            yield {"data": "It is midnight."}

    monkeypatch.setattr(chat_stream, "create_operator_agent", lambda _session_id, recorder: FakeAgent(recorder))

    async def fake_name_chat(_user: str, _assistant: str) -> str:
        return "Current Nairobi Time"

    monkeypatch.setattr(chat_stream, "name_chat", fake_name_chat)
    async def collect() -> list[str]:
        return [frame async for frame in chat_stream.stream_agent_events(
            account_id="account-1",
            chat_id="chat-1",
            client_id="client-1",
            create_title=True,
            message="What time is it?",
        )]

    frames = asyncio.run(collect())
    events = [json.loads(frame.removeprefix("data: ")) for frame in frames]
    assert [event["type"] for event in events] == ["tool_call", "tool_response", "content", "title", "done"]
    assert events[1]["status"] == "done"
