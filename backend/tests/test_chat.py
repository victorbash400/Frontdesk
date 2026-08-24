import asyncio
import json
from types import SimpleNamespace

import pytest

from app import chat_stream
from tools.time_tool import get_current_time


def test_time_tool_returns_requested_timezone() -> None:
    result = get_current_time(timezone="Africa/Nairobi")
    assert result["timezone"] == "Africa/Nairobi"
    assert result["iso"].endswith("+03:00")
    assert result["display"].endswith("EAT")


def test_stream_translates_adk_reasoning_and_content(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeSessions:
        async def get_session(self, **_: object):
            return None

        async def create_session(self, **_: object):
            return object()

    class FakeRunner:
        app_name = "front_desk"

        def run_async(self, **_: object):
            async def events():
                yield SimpleNamespace(
                    error_message=None,
                    partial=True,
                    content=SimpleNamespace(parts=[SimpleNamespace(text="I will answer directly.", thought=True)]),
                )
                yield SimpleNamespace(
                    error_message=None,
                    partial=True,
                    content=SimpleNamespace(parts=[SimpleNamespace(text="Hello **there**.", thought=False)]),
                )
            return events()

    async def fake_name_chat(_user: str, _assistant: str) -> str:
        return "Friendly Greeting"

    monkeypatch.setattr(chat_stream, "sessions", FakeSessions())
    monkeypatch.setattr(chat_stream, "runner", FakeRunner())
    monkeypatch.setattr(chat_stream, "name_chat", fake_name_chat)

    async def collect() -> list[str]:
        return [frame async for frame in chat_stream.stream_agent_events(
            account_id="account-1",
            chat_id="chat-1",
            client_id="client-1",
            create_title=True,
            message="Hello",
        )]

    frames = asyncio.run(collect())
    events = [json.loads(frame.removeprefix("data: ")) for frame in frames]
    assert [event["type"] for event in events] == ["reasoning", "content", "title", "done"]
    assert events[1]["content"] == "Hello **there**."
