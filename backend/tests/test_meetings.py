import base64
import asyncio
import json
import inspect
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from agents.meet_agent import MEET_AGENT_INSTRUCTION, MeetAgentContext, live_config
from app.database import SessionLocal
from app.config import get_settings
from app.main import app
from meetings.agent_session import AgentIdentity, _bridge, _register_bridge_and_wait_for_participant, _run_identity_bound_agent, create_agent_ticket, verify_agent_ticket
from meetings.events import decode_pubsub_event
from meetings.models import Meeting, MeetingEvent
from meetings.service import record_agent_tool
from meetings.sample import ensure_angeline_sample
from tools.supervisor_tools import execute_client_tool


def test_create_meeting_invites_client_and_persists_space() -> None:
    with TestClient(app) as client:
        account = _account(client, "meet-create@example.com")
        suffix = uuid4().hex[:12]
        meeting_code = f"abc-{suffix[:4]}-{suffix[4:8]}"
        space_name = f"spaces/durable-{suffix}"
        event_id = f"calendar-{suffix}"
        calls: list[tuple[str, str, dict[str, object]]] = []

        async def google_request(_account_id: str, method: str, url: str, **kwargs: object) -> dict[str, object]:
            calls.append((method, url, kwargs))
            if url.endswith("/events"):
                return {"id": event_id, "hangoutLink": f"https://meet.google.com/{meeting_code}"}
            if url.endswith(f"/spaces/{meeting_code}"):
                return {"name": space_name, "meetingUri": f"https://meet.google.com/{meeting_code}"}
            raise AssertionError(f"Unexpected Google request: {method} {url}")

        with patch("meetings.service.workspace_request", new=google_request):
            response = client.post("/api/meetings", headers=_headers(account["id"]), json={
                "client_id": "client-acme",
                "client_email": "client@example.com",
                "title": "Resolve onboarding",
                "description": "Help the client finish onboarding.",
                "start_time": "2026-08-27T10:00:00+03:00",
                "end_time": "2026-08-27T10:30:00+03:00",
            })

        assert response.status_code == 201
        meeting = response.json()
        assert meeting["state"] == "invited"
        assert meeting["meetUri"] == f"https://meet.google.com/{meeting_code}"
        assert meeting["meetSpaceName"] == space_name
        calendar_body = calls[0][2]["json"]
        assert calendar_body["attendees"] == [{"email": "client@example.com"}]
        assert calendar_body["start"] == {"dateTime": "2026-08-27T07:00:00Z", "timeZone": "UTC"}
        assert calendar_body["end"] == {"dateTime": "2026-08-27T07:30:00Z", "timeZone": "UTC"}
        assert calendar_body["conferenceData"]["createRequest"]["conferenceSolutionKey"] == {"type": "hangoutsMeet"}
        assert calls[0][2]["params"] == {"conferenceDataVersion": 1, "sendUpdates": "all"}

        listed = client.get("/api/meetings", headers=_headers(account["id"]), params={"client_id": "client-acme"})
        assert listed.status_code == 200
        assert meeting["id"] in [item["id"] for item in listed.json()]


def test_workspace_participant_event_is_deduplicated_and_wakes_meeting() -> None:
    with TestClient(app) as client:
        account = _account(client, "meet-events@example.com")
        space_name = f"spaces/event-space-{uuid4()}"
        with SessionLocal() as session:
            meeting = Meeting(
                account_id=account["id"],
                client_id="client-events",
                client_email="client@example.com",
                title="Client check-in",
                state="waiting_for_client",
                meet_space_name=space_name,
                meet_uri="https://meet.google.com/aaa-bbbb-ccc",
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc) + timedelta(minutes=30),
            )
            session.add(meeting)
            session.commit()
            meeting_id = meeting.id

        envelope = _pubsub_envelope(
            event_id=f"event-{uuid4()}",
            event_type="google.workspace.meet.participant.v2.joined",
            subject=f"//meet.googleapis.com/{space_name}",
            data={"participantSession": {"name": "conferenceRecords/conference-1/participants/client/participantSessions/session-1"}},
        )
        headers = {"X-Front-Desk-Internal-Secret": get_settings().internal_secret}
        async def google_request(*_args: object, **_kwargs: object) -> dict[str, object]:
            return {"participants": [{"name": "agent"}, {"name": "client"}]}

        with patch("meetings.service.workspace_request", new=google_request):
            first = client.post("/internal/google-workspace-events", headers=headers, json=envelope)
            second = client.post("/internal/google-workspace-events", headers=headers, json=envelope)

        assert first.status_code == 204
        assert second.status_code == 204
        with SessionLocal() as session:
            updated = session.get(Meeting, meeting_id)
            assert updated and updated.state == "client_joined"
            assert updated.client_joined_at is not None
            assert updated.conference_record_name == "conferenceRecords/conference-1"
            assert session.query(MeetingEvent).filter_by(meeting_id=meeting_id).count() == 1


def test_meet_agent_is_conversation_only_and_ticket_is_meeting_scoped() -> None:
    config = live_config(MeetAgentContext(
        meeting_id="meeting-1",
        client_id="client-1",
        title="Support call",
        purpose="Resolve login access.",
        goals=[],
        documents=[],
        voice="Kore",
        language="English",
    ))
    declarations = [declaration.name for tool in config.tools or [] for declaration in tool.function_declarations or []]

    assert "Remain silent until the session reports that the client has arrived" in MEET_AGENT_INSTRUCTION
    assert "browser" not in " ".join(declarations)
    assert declarations == ["get_client_goals", "get_client_documents", "update_goal_board", "ask_user", "send_client_message", "end_meeting"]

def test_replacement_meeting_ticket_revokes_previous_ticket() -> None:
    with TestClient(app) as client:
        account = _account(client, "meet-ticket-lease@example.com")
        with SessionLocal() as session:
            meeting = Meeting(
                account_id=account["id"], client_id="client-ticket", client_email="client@example.com",
                title="Ticket lease", state="waiting_for_client", meet_uri="https://meet.google.com/ticket-test",
                start_time=datetime.now(timezone.utc), end_time=datetime.now(timezone.utc) + timedelta(minutes=30),
            )
            session.add(meeting)
            session.commit()
            meeting_id = meeting.id

        first = create_agent_ticket(account["id"], meeting_id, runtime_id="runtime-1", bridge_id="bridge-1")
        second = create_agent_ticket(account["id"], meeting_id, runtime_id="runtime-2", bridge_id="bridge-2")
        identity = verify_agent_ticket(second, meeting_id)
        assert identity.account_id == account["id"]
        assert identity.runtime_id == "runtime-2"
        assert identity.bridge_id == "bridge-2"
        with SessionLocal() as session:
            meeting = session.get(Meeting, meeting_id)
            assert meeting and meeting.active_tab_id is None
        try:
            verify_agent_ticket(first, meeting_id)
        except ValueError as error:
            assert "authentication expired" in str(error)
        else:
            raise AssertionError("A replacement meeting ticket must revoke the previous ticket.")


def test_bridge_requires_exact_identity_and_persists_tab() -> None:
    with TestClient(app) as client:
        account = _account(client, "meet-bridge-identity@example.com")
        with SessionLocal() as session:
            meeting = Meeting(
                account_id=account["id"], client_id="client-bridge", client_email="client@example.com",
                title="Identity", state="browser_opened", meet_uri="https://meet.google.com/identity-test",
                active_runtime_id="runtime-exact", active_bridge_id="bridge-exact",
                start_time=datetime.now(timezone.utc), end_time=datetime.now(timezone.utc) + timedelta(minutes=30),
            )
            session.add(meeting)
            session.commit()
            meeting_id = meeting.id

        identity = AgentIdentity(account["id"], meeting_id, "runtime-exact", "bridge-exact", "ticket-exact")

        class Socket:
            def __init__(self) -> None:
                self.messages = iter([
                    {"text": json.dumps({"type": "bridge_registered", "meetingId": meeting_id, "runtimeId": "runtime-exact", "bridgeId": "bridge-exact", "tabId": "417"})},
                    {"text": json.dumps({"type": "participant_arrived"})},
                ])

            async def receive(self) -> dict[str, str]:
                return next(self.messages)

            async def send_json(self, _message: object) -> None:
                return None

        assert asyncio.run(_register_bridge_and_wait_for_participant(Socket(), identity)) == "417"  # type: ignore[arg-type]
        with SessionLocal() as session:
            meeting = session.get(Meeting, meeting_id)
            assert meeting and meeting.active_tab_id == "417"


def test_media_bridge_awaits_cancelled_live_receiver() -> None:
    live_receiver_closed = asyncio.Event()

    class Socket:
        async def receive(self) -> dict[str, str]:
            await asyncio.sleep(0)
            return {"type": "websocket.disconnect"}

    class Live:
        async def receive(self):
            try:
                while True:
                    await asyncio.sleep(60)
                    yield None
            finally:
                live_receiver_closed.set()

    async def exercise() -> None:
        try:
            await _bridge(Socket(), Live(), "account", "client", "meeting", {})  # type: ignore[arg-type]
        except Exception as error:
            assert error.__class__.__name__ == "WebSocketDisconnect"
        assert live_receiver_closed.is_set()

    asyncio.run(exercise())


def test_agent_does_not_generate_synthetic_client_speech() -> None:
    source = inspect.getsource(_run_identity_bound_agent)
    assert "send_realtime_input(text=" not in source
    assert "ready_waiting_for_speech" in source


def test_meet_agent_tool_calls_are_persisted() -> None:
    with TestClient(app) as client:
        account = _account(client, "meet-tool-event@example.com")
        with SessionLocal() as session:
            meeting = Meeting(
                account_id=account["id"], client_id="client-tools", client_email="client@example.com",
                title="Tool persistence", state="agent_active", meet_uri="https://meet.google.com/tool-test",
                start_time=datetime.now(timezone.utc), end_time=datetime.now(timezone.utc) + timedelta(minutes=30),
            )
            session.add(meeting)
            session.commit()
            meeting_id = meeting.id
            record_agent_tool(session, meeting_id, "call-1", "get_client_documents", {}, {"documents": [{"name": "Resolution"}]})

        with SessionLocal() as session:
            event = session.query(MeetingEvent).filter_by(meeting_id=meeting_id, source="meet_agent").one()
            assert event.event_type == "tool.get_client_documents"
            assert json.loads(event.payload)["result"]["documents"][0]["name"] == "Resolution"


def test_pubsub_decoder_rejects_incomplete_events() -> None:
    try:
        decode_pubsub_event({"message": {"attributes": {}}})
    except ValueError as error:
        assert "incomplete" in str(error)
    else:
        raise AssertionError("Incomplete CloudEvents must be rejected.")


def test_sample_client_document_is_available_to_meet_agent_tools() -> None:
    with TestClient(app) as client:
        account = _account(client, "meet-sample@example.com")
        with SessionLocal() as session:
            sample = ensure_angeline_sample(session, account["id"])

        result = execute_client_tool(account["id"], sample["clientId"], "get_client_documents", {})

        assert result["documents"][0]["name"] == "Duplicate charge resolution.md"
        assert "AUTH-88421" in result["documents"][0]["content"]


def _account(client: TestClient, email: str) -> dict[str, str]:
    credentials = {"email": email, "password": "password-123"}
    response = client.post("/accounts", json={**credentials, "name": "Meet Test"})
    if response.status_code == 409:
        response = client.post("/accounts/authenticate", json=credentials)
    assert response.status_code in {200, 201}
    return response.json()


def _headers(account_id: str) -> dict[str, str]:
    return {"X-Front-Desk-Account": account_id, "X-Front-Desk-Internal-Secret": get_settings().internal_secret}


def _pubsub_envelope(*, event_id: str, event_type: str, subject: str, data: dict[str, object]) -> dict[str, object]:
    return {"message": {
        "attributes": {
            "ce-id": event_id,
            "ce-type": event_type,
            "ce-source": f"//workspaceevents.googleapis.com/subscriptions/{uuid4()}",
            "ce-subject": subject,
        },
        "data": base64.b64encode(json.dumps(data).encode()).decode(),
    }}
