import asyncio
from unittest.mock import patch

import httpx
import pytest
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool, ToolContext
from google.adk.tools.base_toolset import BaseToolset

from app.accounts import create_account
from app.agent_tool_gateway import AgentToolGateway, agent_tool_gateway
from app.database import SessionLocal, initialize_database
from app.main import app


@pytest.mark.parametrize("different_runtime", [False, True])
def test_gateway_preserves_dynamic_tools_and_does_not_repeat_actions(different_runtime: bool) -> None:
    effects = []

    def increment(amount: int, tool_context: ToolContext) -> dict:
        """Increment the test counter."""
        effects.append(amount)
        assert tool_context.state["goal_id"] == "assigned-goal"
        return {"count": sum(effects)}

    def load_tools(tool_context: ToolContext) -> dict:
        """Load the counter tool."""
        tool_context.state["counter_loaded"] = True
        return {"status": "loaded"}

    def broken_tool() -> dict:
        """Report a tool error."""
        raise ValueError("Counter is unavailable")

    class CounterTools(BaseToolset):
        def __init__(self):
            super().__init__()
            self._use_invocation_cache = False

        async def get_tools(self, readonly_context=None):
            return [FunctionTool(increment)] if readonly_context.state.get("counter_loaded") else []

        async def close(self):
            pass

    async def exercise() -> None:
        initialize_database()
        with SessionLocal() as database:
            account = create_account(database, f"gateway-test-{different_runtime}@example.test", "gateway-test-password", "Gateway")
            account_id = account.id
        sessions = InMemorySessionService()
        session = await sessions.create_session(app_name="gateway_test", user_id=account_id, state={"account_id": account_id, "goal_id": "assigned-goal"})
        runner = Runner(app_name="gateway_test", session_service=sessions, agent=Agent(name="gateway_test", model="gemini-3.6-flash", instruction="Use the assigned goal.", tools=[load_tools, broken_tool, CounterTools()]))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            async with agent_tool_gateway.bind(runner, session) as (run_id, ticket):
                path = f"/internal/agent-runs/{run_id}"
                headers = {"X-Front-Desk-Agent-Secret": "test-internal-secret", "Authorization": f"Bearer {ticket}"}
                assert (await client.post(path + "/manifest", json={})).status_code == 401
                bad_headers = {**headers, "Authorization": "Bearer unrelated-ticket"}
                assert (await client.post(path + "/manifest", headers=bad_headers, json={})).status_code == 401
                initial = await client.post(path + "/manifest", headers=headers, json={})
                assert {tool["name"] for tool in initial.json()["tools"]} == {"load_tools", "broken_tool"}
                load = await client.post(path + "/call", headers=headers, json={"name": "load_tools", "call_id": "load-1", "state": {"account_id": account_id}})
                assert load.status_code == 200, load.text
                assert load.json()["result"] == {"status": "loaded"}
                assert "increment" in {tool["name"] for tool in load.json()["manifest"]["tools"]}
                body = {"name": "increment", "call_id": "increment-1", "args": {"amount": 3}, "state": {"account_id": account_id, "goal_id": "forged-goal"}}
                assert (await client.post(path + "/call", headers=headers, json={**body, "state": {"account_id": "other-account"}})).status_code == 403
                results = await asyncio.gather(*[client.post(path + "/call", headers=headers, json=body) for _ in range(2)])
                assert [result.status_code for result in results] == [200, 200]
                assert results[0].json() == results[1].json()
                assert effects == [3]
                assert (await client.post(path + "/call", headers=headers, json={**body, "args": {"amount": 6}})).status_code == 409
                failure = await client.post(path + "/call", headers=headers, json={"name": "broken_tool", "call_id": "broken-1", "state": {"account_id": account_id}})
                assert failure.status_code == 200
                assert failure.json()["result"]["status"] == "failed"
                assert "Counter is unavailable" in failure.json()["result"]["error"]
                assert (await client.post(path + "/call", headers=headers, json={**body, "call_id": "increment-2"})).status_code == 200
                assert effects == [3, 3]
            assert (await client.post(path + "/manifest", headers=headers, json={})).status_code == 410

    receiver = AgentToolGateway() if different_runtime else agent_tool_gateway
    with patch("app.agent_tool_gateway.agent_tool_gateway", receiver):
        asyncio.run(exercise())
