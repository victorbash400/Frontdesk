import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from google.adk.agents.run_config import RunConfig
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import PrivateAttr

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agent_runtime.agent import configure_model, create_agent
from agent_runtime.relay import MANIFEST_STATE, RunManifest, declarations
from agent_runtime import relay


def manifest(tools=None):
    return {
        "instruction": "Read the assigned client only. Use the available tools and stop after completion.",
        "model": "gemini-3-flash-preview",
        "generation_config": {"thinking_config": {"thinking_level": "LOW"}},
        "tools": tools or [{"name": "load_goal_tools", "description": "Load selected capabilities."}],
    }


def test_remote_runtime_refreshes_tools_and_preserves_completion_signal() -> None:
    class ScriptedModel(BaseLlm):
        _calls: int = PrivateAttr(default=0)

        async def generate_content_async(self, llm_request, stream=False):
            del stream
            self._calls += 1
            if self._calls == 1:
                assert set(llm_request.tools_dict) == {"load_goal_tools"}
                name = "load_goal_tools"
            else:
                assert self._calls == 2
                assert set(llm_request.tools_dict) == {"load_goal_tools", "complete_goal"}
                name = "complete_goal"
            yield LlmResponse(content=types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name=name, args={}, id=f"call-{self._calls}"))]))

    loaded_manifest = manifest([{"name": "load_goal_tools"}, {"name": "complete_goal"}])

    async def call(context, operation, payload):
        assert operation == "call"
        assert payload["state"]["account_id"] == "account-test"
        assert not any(key.startswith("temp:") for key in payload["state"])
        if payload["name"] == "load_goal_tools":
            return {"result": {"status": "loaded"}, "state_delta": {"loaded_goal_tool_ids": ["test-capability"]}, "manifest": loaded_manifest}
        assert payload["call_id"]
        return {"result": {"status": "completed"}, "end_of_agent": True}

    async def exercise() -> None:
        with patch.dict("os.environ", {"FRONT_DESK_CLOUD_PROJECT": "front-desk-20260824"}), patch("agent_runtime.agent.relay_request", new=AsyncMock(return_value=manifest())), patch("agent_runtime.relay.relay_request", side_effect=call):
            agent = create_agent()
            agent.model = ScriptedModel(model="test-scripted")
            sessions = InMemorySessionService()
            session = await sessions.create_session(app_name="front_desk_runtime", user_id="account-test", state={"account_id": "account-test"})
            runner = Runner(app_name="front_desk_runtime", agent=agent, session_service=sessions)
            events = [event async for event in runner.run_async(user_id="account-test", session_id=session.id, new_message=types.Content(role="user", parts=[types.Part(text="Complete the test.")]), run_config=RunConfig(max_llm_calls=3))]
            responses = [response.response for event in events for response in event.get_function_responses()]
            assert responses == [{"status": "loaded"}, {"status": "completed"}]
            assert any(event.actions.end_of_agent for event in events)
            assert agent.model._calls == 2
            saved = await sessions.get_session(app_name=runner.app_name, user_id="account-test", session_id=session.id)
            assert saved.state["loaded_goal_tool_ids"] == ["test-capability"]
            assert not any(key.startswith("temp:") for key in saved.state)

    asyncio.run(exercise())


def test_remote_manifest_rejects_duplicate_function_declarations() -> None:
    with pytest.raises(RuntimeError, match="duplicate"):
        declarations(RunManifest.model_validate(manifest([{"name": "load_mcp_resource"}, {"name": "load_mcp_resource"}])))


def test_planner_schema_and_configuration_survive_runtime_boundary() -> None:
    from google.adk.models.llm_request import LlmRequest
    schema = {"type": "object", "properties": {"operations": {"type": "array", "items": {"type": "string"}}}}
    spec = {**manifest(), "output_schema": schema}
    request = LlmRequest()
    configure_model(SimpleNamespace(state={MANIFEST_STATE: spec}), request)
    assert request.model == spec["model"]
    assert request.config.response_json_schema == schema
    assert request.config.response_mime_type == "application/json"
    assert request.config.thinking_config.thinking_level == types.ThinkingLevel.LOW


def test_agent_engine_application_can_be_serialized_without_backend_imports() -> None:
    import cloudpickle
    from vertexai import agent_engines

    with patch.dict("os.environ", {"FRONT_DESK_CLOUD_PROJECT": "front-desk-20260824"}):
        application = agent_engines.AdkApp(agent=create_agent(), app_name="front_desk_runtime", enable_tracing=True)
        packaged = cloudpickle.dumps(application)
        restored = cloudpickle.loads(packaged)
    assert isinstance(restored, agent_engines.AdkApp)
    assert len(packaged) < 100_000


def test_scoped_run_can_select_a_tagged_https_tool_relay() -> None:
    context = SimpleNamespace(state={
        "temp:front_desk_run_id": "run",
        "temp:front_desk_run_ticket": "ticket",
        "temp:front_desk_tool_relay_url": "https://candidate---front-desk-api.example.run.app",
    })
    response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"ok": True})
    client = AsyncMock()
    client.__aenter__.return_value.post.return_value = response
    with patch("agent_runtime.relay.httpx.AsyncClient", return_value=client):
        assert asyncio.run(relay.relay_request(context, "manifest", {})) == {"ok": True}
    assert client.__aenter__.return_value.post.await_args.args[0].startswith(
        "https://candidate---front-desk-api.example.run.app/internal/agent-runs/"
    )
