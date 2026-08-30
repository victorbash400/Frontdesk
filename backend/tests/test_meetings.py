import base64
import asyncio
import json
import inspect
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from agents.meet_agent import MEET_AGENT_INSTRUCTION, MeetAgentContext, live_config
from agents.goal_planner import GoalPlan, GoalTaskOperation
from app.database import SessionLocal
from app.goal_tasks import GoalTaskManager
from app.models import GoalAssignment, GoalNotification
from app.config import get_settings
from app.main import app
from meetings.agent_session import AgentIdentity, _bridge, _coordinator_notification, _pcm_peak, _register_bridge_and_wait_for_participant, _run_identity_bound_agent, create_agent_ticket, verify_agent_ticket
from meetings.browser_worker import join_meeting
from meetings.events import decode_pubsub_event
from meetings.coordinator_tools import execute_coordinator_tool
from meetings.models import Meeting, MeetingEvent
from meetings.service import create_instant_meeting, record_agent_tool
from meetings.sample import ensure_angeline_sample
from tools.supervisor_tools import execute_client_tool


def test_pcm_peak_distinguishes_silence_from_client_speech() -> None:
    assert _pcm_peak(b"\x00\x00" * 32) == 0
    assert _pcm_peak(b"\x00\x01\x00\xff") == 256


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


def test_create_instant_meeting_uses_meet_api_without_calendar() -> None:
    with TestClient(app) as client:
        account = _account(client, "instant-meet@example.com")
    calls: list[tuple[str, str, dict[str, object]]] = []

    async def google_request(_account_id: str, method: str, url: str, **kwargs: object) -> dict[str, object]:
        calls.append((method, url, kwargs))
        return {"name": "spaces/instant-space", "meetingUri": "https://meet.google.com/abc-defg-hij"}

    with SessionLocal() as session, patch("meetings.service.workspace_request", new=google_request):
        meeting = asyncio.run(create_instant_meeting(
            session,
            account["id"],
            client_id="client-instant",
            client_email="client@example.com",
            title="Immediate support call",
        ))

    assert meeting["state"] == "invited"
    assert meeting["calendarEventId"] is None
    assert meeting["meetUri"] == "https://meet.google.com/abc-defg-hij"
    assert calls == [("POST", "https://meet.googleapis.com/v2/spaces", {"json": {}})]


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
        client_name="Victor Bash",
        client_email="victor@example.com",
        client_profile="Prefers concise support calls.",
        title="Support call",
        purpose="Resolve login access.",
        goal={"id": "goal-1", "text": "Restore access", "status": "active", "situation": "Login blocked"},
        voice="Kore",
        language="English",
    ))
    declarations = [declaration.name for tool in config.tools or [] for declaration in tool.function_declarations or []]

    assert "Remain silent until the session reports that the client has arrived" in MEET_AGENT_INSTRUCTION
    assert "without making any startup tool calls" in MEET_AGENT_INSTRUCTION
    assert "Victor Bash" in str(config.system_instruction)
    assert "browser" not in " ".join(declarations)
    assert declarations == [
        "prepare_coordinator_action", "confirm_coordinator_action", "inspect_coordinator_task", "list_coordinator_tasks",
        "steer_coordinator_task", "cancel_coordinator_task", "answer_coordinator_question", "end_meeting",
    ]


def test_coordinator_tasks_are_bound_to_the_exact_meeting() -> None:
    with TestClient(app) as client:
        account = _account(client, "meet-coordinator-scope@example.com")
        with SessionLocal() as session:
            sample = ensure_angeline_sample(session, account["id"])
            meetings = [Meeting(
                account_id=account["id"], client_id=sample["clientId"], goal_id=sample["goalId"],
                client_email="client@example.com", title=f"Meeting {index}", state="agent_active",
                meet_uri=f"https://meet.google.com/scope-{index}", start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc) + timedelta(minutes=30),
            ) for index in range(2)]
            session.add_all(meetings)
            session.flush()
            task = GoalAssignment(
                goal_id=sample["goalId"], source_meeting_id=meetings[0].id,
                title="Check the account", instruction="Inspect the customer's account.",
            )
            session.add(task)
            session.commit()
            first_id, second_id, task_id = meetings[0].id, meetings[1].id, task.id

        allowed = asyncio.run(execute_coordinator_tool(
            account["id"], sample["clientId"], first_id, "inspect_coordinator_task", {"task_id": task_id},
        ))
        rejected = asyncio.run(execute_coordinator_tool(
            account["id"], sample["clientId"], second_id, "inspect_coordinator_task", {"task_id": task_id},
        ))

        assert allowed["status"] == "success"
        assert allowed["task"]["sourceMeetingId"] == first_id
        assert rejected == {"status": "failed", "error": "That coordinator task does not belong to this meeting."}


def test_meeting_delegation_uses_the_persisted_goal_and_meeting_identity() -> None:
    with TestClient(app) as client:
        account = _account(client, "meet-coordinator-delegate@example.com")
        with SessionLocal() as session:
            sample = ensure_angeline_sample(session, account["id"])
            meeting = Meeting(
                account_id=account["id"], client_id=sample["clientId"], goal_id=sample["goalId"],
                client_email="client@example.com", title="Delegation", state="agent_active",
                meet_uri="https://meet.google.com/delegation-test", start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc) + timedelta(minutes=30),
            )
            session.add(meeting)
            session.commit()
            meeting_id = meeting.id

        delegate = AsyncMock(return_value={"status": "running", "task_ids": ["task-1"]})
        with patch("meetings.coordinator_tools.goal_tasks.delegate_from_meeting", new=delegate):
            prepared = asyncio.run(execute_coordinator_tool(
                account["id"], sample["clientId"], meeting_id, "prepare_coordinator_action",
                {
                    "instruction": "Check the exact payment record and report verified evidence.",
                    "question": "Would you like me to check that payment record now?",
                    "_client_turn_sequence": 1,
                },
            ))
            premature = asyncio.run(execute_coordinator_tool(
                account["id"], sample["clientId"], meeting_id, "confirm_coordinator_action",
                {"confirmation_id": prepared["confirmation_id"], "answer": "Yes, please check it now."},
            ))
            assert premature == {"status": "failed", "error": "Wait for the client to answer the confirmation question before starting work."}
            delegate.assert_not_awaited()
            result = asyncio.run(execute_coordinator_tool(
                account["id"], sample["clientId"], meeting_id, "confirm_coordinator_action",
                {
                    "confirmation_id": prepared["confirmation_id"],
                    "answer": "Yes, please check it now.",
                    "_client_turn_sequence": 2,
                    "_observed_client_answer": "Yes, please check it now.",
                },
            ))

        assert result == {"status": "running", "task_ids": ["task-1"]}
        delegated_instruction = delegate.await_args.args[3]
        assert "The client explicitly confirmed this action" in delegated_instruction
        assert "Check the exact payment record" in delegated_instruction


def test_meeting_delegation_persists_an_independent_auxiliary_task() -> None:
    with TestClient(app) as client:
        account = _account(client, "meet-coordinator-persistence@example.com")
        with SessionLocal() as session:
            sample = ensure_angeline_sample(session, account["id"])
            session.add(Meeting(
                id="meeting-persisted", account_id=account["id"],
                client_id=sample["clientId"], goal_id=sample["goalId"],
                client_email="client@example.com", title="Persisted submission",
                state="agent_active", start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc) + timedelta(minutes=30),
            ))
            session.commit()

        manager = GoalTaskManager()
        plan = GoalPlan(operations=[GoalTaskOperation(
            action="create",
            key="inspect_account",
            title="Inspect account assignment",
            instruction="Inspect the exact account assignment and return verified evidence.",
            expected_outputs=["Verified account assignment"],
        )])
        planner_started = asyncio.Event()
        release_planner = asyncio.Event()

        async def delayed_plan(*_: object, **__: object) -> GoalPlan:
            planner_started.set()
            await release_planner.wait()
            return plan

        async def exercise() -> dict[str, object]:
            result = await manager.delegate_from_meeting(
                account["id"], sample["goalId"], "meeting-persisted",
                "Inspect the exact account assignment.",
            )
            assert result["status"] == "accepted"
            await planner_started.wait()
            assert manager.meeting_submissions(account["id"], "meeting-persisted")[0]["status"] == "received"
            release_planner.set()
            await manager._meeting_submission_workers[str(result["submission_id"])]
            return result

        with (
            patch("meetings.coordinator_planner.plan_goal", new=delayed_plan),
            patch.object(manager, "_run_delegated_assignments", new=AsyncMock()),
        ):
            result = asyncio.run(exercise())

        assert result["status"] == "accepted"
        submission = manager.meeting_submissions(account["id"], "meeting-persisted")[0]
        assert submission["status"] == "planned"
        assert GoalTaskManager().meeting_submissions(account["id"], "meeting-persisted") == [submission]
        with SessionLocal() as session:
            task = session.get(GoalAssignment, submission["task_id"])
            assert task is not None
            assert task.auxiliary is True
            assert task.source_meeting_id == "meeting-persisted"
            assert task.goal_id == sample["goalId"]


def test_coordinator_notification_contains_only_persisted_task_state() -> None:
    message = _coordinator_notification([{
        "meeting_id": "meeting-1", "task_id": "task-1", "status": "completed",
        "summary": "Verified the account assignment.", "evidence": {"record": "account-7"},
    }])

    assert "trusted application context" in message
    assert "Verified the account assignment." in message
    assert "account-7" in message


def test_client_answer_resumes_only_the_question_from_this_meeting_task() -> None:
    with TestClient(app) as client:
        account = _account(client, "meet-coordinator-answer@example.com")
        with SessionLocal() as session:
            sample = ensure_angeline_sample(session, account["id"])
            meeting = Meeting(
                account_id=account["id"], client_id=sample["clientId"], goal_id=sample["goalId"],
                client_email="client@example.com", title="Answer routing", state="agent_active",
                meet_uri="https://meet.google.com/answer-routing", start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc) + timedelta(minutes=30),
            )
            session.add(meeting)
            session.flush()
            task = GoalAssignment(
                goal_id=sample["goalId"], source_meeting_id=meeting.id, auxiliary=True,
                title="Check order", instruction="Check the exact order.", status="blocked", phase="blocked",
            )
            session.add(task)
            session.flush()
            matching = GoalNotification(
                goal_id=sample["goalId"], assignment_id=task.id, client_id=sample["clientId"],
                kind="clarification", message="What is the order number?",
            )
            unrelated = GoalNotification(
                goal_id=sample["goalId"], client_id=sample["clientId"],
                kind="clarification", message="Unrelated owner question",
            )
            session.add_all([matching, unrelated])
            session.commit()
            meeting_id, task_id, matching_id, unrelated_id = meeting.id, task.id, matching.id, unrelated.id

        steer = AsyncMock(return_value={"status": "steered", "task_id": task_id})
        with patch("meetings.coordinator_tools.goal_tasks.steer_task", new=steer):
            result = asyncio.run(execute_coordinator_tool(
                account["id"], sample["clientId"], meeting_id, "answer_coordinator_question",
                {"task_id": task_id, "answer": "AQL-2048"},
            ))

        assert result["status"] == "answered"
        with SessionLocal() as session:
            assert session.get(GoalNotification, matching_id).status == "answered"
            assert session.get(GoalNotification, unrelated_id).status == "open"
        steer.assert_awaited_once()


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


def test_agent_ticket_supersedes_every_other_active_meeting() -> None:
    with TestClient(app) as client:
        account = _account(client, "exclusive-meeting@example.com")
        start = datetime.now(timezone.utc)
        with SessionLocal() as session:
            older = Meeting(
                account_id=account["id"], client_id="potato", client_email="client@example.com",
                title="Older", state="agent_active", meet_uri="https://meet.google.com/old-meeting",
                start_time=start, end_time=start + timedelta(minutes=30), active_runtime_id="old-runtime",
            )
            current = Meeting(
                account_id=account["id"], client_id="potato", client_email="client@example.com",
                title="Current", state="invited", meet_uri="https://meet.google.com/new-meeting",
                start_time=start, end_time=start + timedelta(minutes=30),
            )
            session.add_all([older, current])
            session.commit()
            older_id, current_id = older.id, current.id

        create_agent_ticket(account["id"], current_id, runtime_id="current-runtime", bridge_id="current-bridge")

        with SessionLocal() as session:
            replaced = session.get(Meeting, older_id)
            launched = session.get(Meeting, current_id)
            assert replaced and replaced.state == "superseded"
            assert replaced.active_runtime_id is None
            assert launched and launched.state == "launching"
            assert launched.active_runtime_id == "current-runtime"


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


def test_browser_opener_does_not_compete_with_meet_worker_controls() -> None:
    source = inspect.getsource(join_meeting)
    assert "browser_navigate" in source
    assert "browser_snapshot" in source
    assert "browser_click" not in source
    assert "Join now" not in source
    assert "Turn on microphone" not in source


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
