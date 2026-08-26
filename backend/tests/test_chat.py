import asyncio
import json
from types import SimpleNamespace

import pytest

from app import chat_stream, goals_chat_stream
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


def test_goals_chat_emits_final_multi_part_answer_without_duplicate_text(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeSessions:
        async def get_session(self, **_: object):
            return object()

    class FakeRunner:
        app_name = "front_desk_goals_chat"

        def run_async(self, **_: object):
            async def events():
                yield SimpleNamespace(error_message=None, partial=True, content=SimpleNamespace(parts=[SimpleNamespace(text="No active", thought=False)]))
                yield SimpleNamespace(error_message=None, partial=False, content=SimpleNamespace(parts=[
                    SimpleNamespace(text="Checked every task.", thought=True),
                    SimpleNamespace(text="No active tasks remain.", thought=False),
                ]))
            return events()

    monkeypatch.setattr(goals_chat_stream, "sessions", FakeSessions())
    monkeypatch.setattr(goals_chat_stream, "runner", FakeRunner())

    async def collect() -> list[str]:
        return [frame async for frame in goals_chat_stream.stream_goals_chat(
            account_id="account-1",
            chat_id="goals-chat-1",
            create_title=False,
            message="What is active?",
        )]

    events = [json.loads(frame.removeprefix("data: ")) for frame in asyncio.run(collect())]
    assert [event["type"] for event in events] == ["content", "reasoning", "content", "done"]
    assert "".join(event["content"] for event in events if event["type"] == "content") == "No active tasks remain."


def test_goals_chat_deduplicates_streamed_tool_events(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeSessions:
        async def get_session(self, **_: object):
            return object()

    call = SimpleNamespace(id="call-1", name="list_goal_tasks", args={})
    response = SimpleNamespace(id="call-1", name="list_goal_tasks", response={"goals": []})

    class Event:
        error_message = None
        partial = False
        content = SimpleNamespace(parts=[SimpleNamespace(text="No active goals.", thought=False)])

        def get_function_calls(self):
            return [call]

        def get_function_responses(self):
            return [response]

    class FakeRunner:
        app_name = "front_desk_goals_chat"

        def run_async(self, **_: object):
            async def events():
                yield Event()
                yield Event()
            return events()

    monkeypatch.setattr(goals_chat_stream, "sessions", FakeSessions())
    monkeypatch.setattr(goals_chat_stream, "runner", FakeRunner())

    async def collect() -> list[str]:
        return [frame async for frame in goals_chat_stream.stream_goals_chat(
            account_id="account-1",
            chat_id="goals-chat-1",
            create_title=False,
            message="What is active?",
        )]

    events = [json.loads(frame.removeprefix("data: ")) for frame in asyncio.run(collect())]
    assert [event["type"] for event in events] == ["tool_call", "tool_response", "content", "done"]
