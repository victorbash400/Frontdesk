"""Choose local ADK or Agent Engine explicitly, preserving the same agent and tools."""

import hashlib
from collections.abc import AsyncIterator

from google.adk.events import Event
from google.adk.runners import Runner

from app.agent_engine_client import AgentEngineClient
from app.agent_tool_gateway import agent_tool_gateway
from app.agent_tool_runs import AgentSessionLink
from app.config import get_settings
from app.database import SessionLocal
from app.runtime_lock import runtime_lock


def create_runner(*, app, session_service):
    runner = Runner(app=app, session_service=session_service)
    resource = get_settings().agent_engine_resource
    return AgentEngineRunner(runner, AgentEngineClient(resource)) if resource else runner


class AgentEngineRunner:
    def __init__(self, local: Runner, remote: AgentEngineClient) -> None:
        self.local = local
        self.remote = remote
        self.agent = local.agent
        self.app_name = local.app_name
        self.session_service = local.session_service

    async def _remote_session(self, session) -> str:
        key = hashlib.sha256(f"{self.remote.resource}:{self.app_name}:{session.user_id}:{session.id}".encode()).hexdigest()
        with SessionLocal() as database:
            link = database.get(AgentSessionLink, key)
            if link:
                return link.remote_id
        if session.events:
            raise RuntimeError("This chat contains local agent history. Start a new chat for Agent Engine; existing history has not been migrated.")
        created = await self.remote.query("async_create_session", {"user_id": session.user_id, "state": session.state})
        remote_id = created.get("id")
        if not isinstance(remote_id, str) or not remote_id:
            raise RuntimeError("Agent Engine did not return the new session identity.")
        with SessionLocal() as database:
            database.add(AgentSessionLink(id=key, remote_id=remote_id))
            database.commit()
        return remote_id

    async def run_async(self, *, user_id, session_id, new_message, run_config=None) -> AsyncIterator[Event]:
        identity = f"{self.app_name}:{user_id}:{session_id}"
        with runtime_lock("agent-session", identity) as acquired:
            if not acquired:
                raise RuntimeError("This agent session is already running in another request.")
            session = await self.session_service.get_session(app_name=self.app_name, user_id=user_id, session_id=session_id)
            if session is None or session.state.get("account_id", user_id) != user_id:
                raise RuntimeError("The scoped Front Desk agent session is missing.")
            session.state["account_id"] = user_id
            remote_id = await self._remote_session(session)
            async with agent_tool_gateway.bind(self.local, session) as (run_id, ticket):
                await self.session_service.append_event(session, Event(author="user", invocation_id=run_id, content=new_message))
                parameters = {
                    "user_id": user_id, "session_id": remote_id,
                    "message": new_message.model_dump(mode="json", exclude_none=True),
                    "state_delta": {
                        **session.state,
                        "temp:front_desk_run_id": run_id,
                        "temp:front_desk_run_ticket": ticket,
                        "temp:front_desk_tool_relay_url": get_settings().public_api_url.rstrip("/"),
                    },
                }
                if run_config is not None:
                    parameters["run_config"] = run_config.model_dump(mode="json", exclude_none=True)
                async for event in self.remote.stream("async_stream_query", parameters):
                    await self.session_service.append_event(session, event)
                    yield event
