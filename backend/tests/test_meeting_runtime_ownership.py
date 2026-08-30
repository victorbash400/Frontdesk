import asyncio
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

from meetings.agent_session import AgentIdentity, run_meet_agent


def test_another_instance_cannot_start_an_overlapping_meeting_agent():
    @contextmanager
    def occupied(namespace, identity):
        assert (namespace, identity) == ("meeting-agent", "meeting-test")
        yield False

    socket = AsyncMock()
    identity = AgentIdentity("account", "meeting-test", "runtime", "bridge", "ticket")
    with patch("meetings.agent_session.verify_agent_ticket", return_value=identity), patch(
        "meetings.agent_session.runtime_lock", occupied,
    ), patch("meetings.agent_session._run_identity_bound_agent", new_callable=AsyncMock) as run:
        asyncio.run(run_meet_agent(socket, "meeting-test", "ticket", "Kore", "en"))
    run.assert_not_awaited()
    socket.close.assert_awaited_once_with(code=1008)
    assert "already has an active agent" in socket.send_json.await_args.args[0]["error"]


def test_meeting_ownership_is_held_until_the_agent_stops():
    held = False

    @contextmanager
    def ownership(namespace, identity):
        nonlocal held
        assert (namespace, identity) == ("meeting-agent", "meeting-test")
        held = True
        try:
            yield True
        finally:
            held = False

    async def run(*args):
        assert held

    socket = AsyncMock()
    identity = AgentIdentity("account", "meeting-test", "runtime", "bridge", "ticket")
    with patch("meetings.agent_session.verify_agent_ticket", return_value=identity), patch(
        "meetings.agent_session.runtime_lock", ownership,
    ), patch("meetings.agent_session._run_identity_bound_agent", side_effect=run) as agent:
        asyncio.run(run_meet_agent(socket, "meeting-test", "ticket", "Kore", "en"))
    agent.assert_awaited_once()
    assert not held
