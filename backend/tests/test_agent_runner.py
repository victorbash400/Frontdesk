import asyncio

from google.adk.agents import Agent
from google.adk.events import Event, EventActions
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import ToolContext
from google.genai import types

from app.accounts import create_account
from app.agent_runner import AgentEngineRunner
from app.agent_tool_gateway import ToolRequest, agent_tool_gateway
from app.database import SessionLocal, initialize_database
from app.runtime_lock import runtime_lock


def test_cloud_runner_reuses_durable_remote_session_and_executes_real_tools() -> None:
    def remember(value: str, tool_context: ToolContext) -> dict:
        """Remember an observed test value."""
        tool_context.state["remembered"] = value
        return {"remembered": value}

    class RemoteRuntime:
        resource = "projects/test/locations/us-central1/reasoningEngines/test"
        created = 0
        calls = 0

        async def query(self, method, parameters):
            assert method == "async_create_session"
            self.created += 1
            return {"id": "remote-session"}

        async def stream(self, method, parameters):
            assert method == "async_stream_query"
            assert parameters["session_id"] == "remote-session"
            self.calls += 1
            state = parameters["state_delta"]
            if self.calls == 2:
                assert state["remembered"] == "value-1"
            run_id = state["temp:front_desk_run_id"]
            ticket = state["temp:front_desk_run_ticket"]
            account_id = agent_tool_gateway.authorize(run_id, "test-internal-secret", f"Bearer {ticket}")
            response = await agent_tool_gateway.dispatch(run_id, account_id, "call", ToolRequest(name="remember", call_id="call-1", args={"value": f"value-{self.calls}"}, state=state))
            yield Event(author="front_desk_runtime", invocation_id=run_id, actions=EventActions(state_delta=response["state_delta"]), content=types.Content(role="model", parts=[types.Part(function_response=types.FunctionResponse(name="remember", id="call-1", response=response["result"]))]))

    async def exercise():
        initialize_database()
        with SessionLocal() as database:
            account_id = create_account(database, "runner-test@example.test", "runner-test-password", "Runner").id
        sessions = InMemorySessionService()
        session = await sessions.create_session(app_name="runner_test", user_id=account_id, state={"account_id": account_id})
        local = Runner(app_name="runner_test", agent=Agent(name="runner_test", model="gemini-3-flash-preview", instruction="Remember the user's value.", tools=[remember]), session_service=sessions)
        remote = RemoteRuntime()
        runner = AgentEngineRunner(local, remote)
        for _ in range(2):
            events = [item async for item in runner.run_async(user_id=account_id, session_id=session.id, new_message=types.Content(role="user", parts=[types.Part(text="Remember it.")]))]
            assert events[-1].get_function_responses()[0].response["remembered"] == f"value-{remote.calls}"
        assert remote.created == 1
        assert remote.calls == 2
        saved = await sessions.get_session(app_name="runner_test", user_id=account_id, session_id=session.id)
        assert saved.state["remembered"] == "value-2"
        assert not agent_tool_gateway.bindings

    asyncio.run(exercise())


def test_runtime_lock_is_exclusive_and_releases_after_failure() -> None:
    with runtime_lock("test", "one") as first:
        assert first
        with runtime_lock("test", "one") as duplicate:
            assert not duplicate
        with runtime_lock("test", "two") as other:
            assert other
    try:
        with runtime_lock("test", "one"):
            raise ValueError("test failure")
    except ValueError:
        pass
    with runtime_lock("test", "one") as acquired:
        assert acquired
