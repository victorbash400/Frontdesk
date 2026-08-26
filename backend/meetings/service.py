import json
from datetime import datetime, timezone
from urllib.parse import quote, urlparse
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.event_stream import account_events
from app.models import Goal
from tools.workspace import workspace_request

from .models import Meeting, MeetingEvent, MeetingTurn


CALENDAR_EVENTS_API = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
MEET_API = "https://meet.googleapis.com/v2"
WORKSPACE_EVENTS_API = "https://workspaceevents.googleapis.com/v1/subscriptions"
MEET_EVENT_TYPES = (
    "google.workspace.meet.conference.v2.started",
    "google.workspace.meet.conference.v2.ended",
    "google.workspace.meet.participant.v2.joined",
    "google.workspace.meet.participant.v2.left",
)
EXPIRATION_REMINDER = "google.workspace.events.subscription.v1.expirationReminder"
SUBSCRIPTION_EXPIRED = "google.workspace.events.subscription.v1.expired"


async def create_meeting(
    session: Session,
    account_id: str,
    *,
    client_id: str,
    client_email: str,
    title: str,
    start_time: datetime,
    end_time: datetime,
    goal_id: str | None = None,
    description: str = "",
) -> dict[str, object]:
    start_time = _aware(start_time)
    end_time = _aware(end_time)
    if end_time <= start_time:
        raise ValueError("Meeting end time must be after its start time.")
    if goal_id and not session.scalar(select(Goal.id).where(Goal.id == goal_id, Goal.account_id == account_id)):
        raise ValueError("The meeting goal does not belong to this account.")

    meeting = Meeting(
        account_id=account_id,
        client_id=client_id,
        client_email=client_email.strip().lower(),
        title=title.strip(),
        description=description.strip(),
        goal_id=goal_id,
        start_time=start_time,
        end_time=end_time,
    )
    session.add(meeting)
    session.commit()
    session.refresh(meeting)
    meeting_id = meeting.id
    try:
        calendar_event = await workspace_request(
            account_id,
            "POST",
            CALENDAR_EVENTS_API,
            params={"conferenceDataVersion": 1, "sendUpdates": "all"},
            json={
                "summary": meeting.title,
                "description": meeting.description,
                "start": _calendar_time(meeting.start_time),
                "end": _calendar_time(meeting.end_time),
                "attendees": [{"email": meeting.client_email}],
                "conferenceData": {
                    "createRequest": {
                        "requestId": str(uuid4()),
                        "conferenceSolutionKey": {"type": "hangoutsMeet"},
                    }
                },
            },
        )
        meet_uri = str(calendar_event.get("hangoutLink") or _video_entry_point(calendar_event) or "")
        event_id = str(calendar_event.get("id") or "")
        if not meet_uri or not event_id:
            raise RuntimeError("Google Calendar created the event without a usable Meet link.")
        meeting_code = urlparse(meet_uri).path.strip("/")
        space = await workspace_request(account_id, "GET", f"{MEET_API}/spaces/{quote(meeting_code, safe='-')}")
        space_name = str(space.get("name") or "")
        if not space_name:
            raise RuntimeError("Google Meet did not return a durable meeting space identity.")
        meeting.calendar_event_id = event_id
        meeting.meet_uri = meet_uri
        meeting.meet_space_name = space_name
        meeting.state = "invited"
        topic = get_settings().google_workspace_events_topic.strip()
        if topic:
            await _subscribe(meeting)
        session.commit()
        session.refresh(meeting)
        _publish(meeting)
        return meeting_snapshot(meeting)
    except Exception as error:
        session.rollback()
        meeting = session.get(Meeting, meeting_id)
        if not meeting:
            raise
        meeting.state = "failed"
        meeting.failure = str(error).strip() or error.__class__.__name__
        session.commit()
        _publish(meeting)
        raise


def list_meetings(session: Session, account_id: str, client_id: str | None = None) -> list[dict[str, object]]:
    query = select(Meeting).where(Meeting.account_id == account_id).order_by(Meeting.created_at.desc())
    if client_id:
        query = query.where(Meeting.client_id == client_id)
    return [meeting_snapshot(meeting) for meeting in session.scalars(query)]


def require_meeting(session: Session, account_id: str, meeting_id: str) -> Meeting:
    meeting = session.scalar(select(Meeting).where(Meeting.id == meeting_id, Meeting.account_id == account_id))
    if not meeting:
        raise ValueError("Meeting not found.")
    return meeting


def record_workspace_event(
    session: Session,
    external_id: str,
    event_type: str,
    payload: dict[str, object],
    *,
    source: str = "",
    subject: str = "",
) -> dict[str, object] | None:
    existing = session.scalar(select(MeetingEvent).where(
        MeetingEvent.source == "google_workspace",
        MeetingEvent.external_id == external_id,
    ))
    if existing:
        meeting = session.get(Meeting, existing.meeting_id)
        return meeting_snapshot(meeting) if meeting else None
    space_name = _space_from_subject(subject) or _space_name(payload)
    conference_name = _conference_name(payload)
    meeting = session.scalar(select(Meeting).where(Meeting.meet_space_name == space_name)) if space_name else None
    if not meeting and conference_name:
        meeting = session.scalar(select(Meeting).where(Meeting.conference_record_name == conference_name))
    if not meeting:
        return None
    session.add(MeetingEvent(
        meeting_id=meeting.id,
        source="google_workspace",
        external_id=external_id,
        event_type=event_type,
        payload=json.dumps(payload, default=str),
    ))
    if event_type.endswith("conference.v2.started"):
        meeting.state = "waiting_for_client"
        meeting.conference_record_name = conference_name or meeting.conference_record_name
    elif event_type.endswith("participant.v2.joined"):
        meeting.conference_record_name = conference_name or meeting.conference_record_name
    elif event_type.endswith("conference.v2.ended"):
        meeting.state = "completed"
        meeting.completed_at = datetime.now(timezone.utc)
    if source.startswith("//workspaceevents.googleapis.com/subscriptions/"):
        meeting.event_subscription_name = source.removeprefix("//workspaceevents.googleapis.com/")
    session.commit()
    session.refresh(meeting)
    _publish(meeting)
    return meeting_snapshot(meeting)


async def process_workspace_event(
    session: Session,
    account_id: str | None,
    external_id: str,
    event_type: str,
    payload: dict[str, object],
    *,
    source: str,
    subject: str,
) -> dict[str, object] | None:
    snapshot = record_workspace_event(session, external_id, event_type, payload, source=source, subject=subject)
    if not snapshot:
        return None
    meeting = session.get(Meeting, str(snapshot["id"]))
    if not meeting:
        return None
    if account_id and account_id != meeting.account_id:
        raise ValueError("Workspace event account does not own this meeting.")
    if event_type.endswith("participant.v2.joined") and meeting.conference_record_name:
        response = await workspace_request(
            meeting.account_id,
            "GET",
            f"{MEET_API}/{meeting.conference_record_name}/participants",
            params={"filter": "latestEndTime IS NULL", "pageSize": 100},
        )
        participants = response.get("participants")
        if isinstance(participants, list) and len(participants) >= 2:
            meeting.state = "client_joined"
            meeting.client_joined_at = meeting.client_joined_at or datetime.now(timezone.utc)
            session.commit()
            _publish(meeting)
    elif event_type == EXPIRATION_REMINDER and meeting.event_subscription_name:
        await _renew_subscription(meeting)
    elif event_type == SUBSCRIPTION_EXPIRED and meeting.meet_space_name:
        await _subscribe(meeting)
        session.commit()
    session.refresh(meeting)
    return meeting_snapshot(meeting)


def mark_agent_active(session: Session, meeting: Meeting) -> None:
    meeting.state = "agent_active"
    activated_at = datetime.now(timezone.utc)
    meeting.client_joined_at = meeting.client_joined_at or activated_at
    meeting.agent_started_at = activated_at
    session.commit()
    _publish(meeting)


def mark_meeting_state(session: Session, meeting: Meeting, state: str) -> None:
    if meeting.state in {"agent_active", "completed", "failed"} and state in {"browser_ready", "waiting_for_client"}:
        return
    meeting.state = state
    if state == "completed":
        meeting.completed_at = datetime.now(timezone.utc)
    session.commit()
    _publish(meeting)


def append_turn(session: Session, meeting_id: str, role: str, text: str) -> None:
    clean = text.strip()
    if clean:
        session.add(MeetingTurn(meeting_id=meeting_id, role=role, text=clean))
        session.commit()


def record_agent_tool(
    session: Session,
    meeting_id: str,
    call_id: str,
    name: str,
    arguments: dict[str, object],
    result: dict[str, object],
) -> None:
    session.add(MeetingEvent(
        meeting_id=meeting_id,
        source="meet_agent",
        external_id=call_id,
        event_type=f"tool.{name}",
        payload=json.dumps({"arguments": arguments, "result": result}, default=str),
    ))
    session.commit()


def record_meeting_diagnostic(session: Session, meeting_id: str, event_type: str, payload: dict[str, object]) -> None:
    session.add(MeetingEvent(
        meeting_id=meeting_id,
        source="meet_agent",
        external_id=f"{event_type}-{uuid4()}",
        event_type=event_type,
        payload=json.dumps(payload, default=str),
    ))
    session.commit()


def meeting_snapshot(meeting: Meeting) -> dict[str, object]:
    return {
        "id": meeting.id,
        "clientId": meeting.client_id,
        "goalId": meeting.goal_id,
        "clientEmail": meeting.client_email,
        "title": meeting.title,
        "description": meeting.description,
        "state": meeting.state,
        "calendarEventId": meeting.calendar_event_id,
        "meetSpaceName": meeting.meet_space_name,
        "meetUri": meeting.meet_uri,
        "eventSubscriptionName": meeting.event_subscription_name,
        "eventSubscriptionOperation": meeting.event_subscription_operation,
        "activeRuntimeId": meeting.active_runtime_id,
        "activeBridgeId": meeting.active_bridge_id,
        "activeTabId": meeting.active_tab_id,
        "failure": meeting.failure or None,
        "startTime": meeting.start_time.isoformat(),
        "endTime": meeting.end_time.isoformat(),
        "clientJoinedAt": meeting.client_joined_at.isoformat() if meeting.client_joined_at else None,
        "agentStartedAt": meeting.agent_started_at.isoformat() if meeting.agent_started_at else None,
        "completedAt": meeting.completed_at.isoformat() if meeting.completed_at else None,
        "createdAt": meeting.created_at.isoformat(),
        "updatedAt": meeting.updated_at.isoformat(),
    }


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Meeting times must include a timezone offset.")
    return value


def _calendar_time(value: datetime) -> dict[str, str]:
    utc_value = value.astimezone(timezone.utc)
    return {"dateTime": utc_value.isoformat().replace("+00:00", "Z"), "timeZone": "UTC"}


def _video_entry_point(event: dict[str, object]) -> str:
    conference = event.get("conferenceData")
    if not isinstance(conference, dict):
        return ""
    entries = conference.get("entryPoints")
    if not isinstance(entries, list):
        return ""
    return next((str(item.get("uri") or "") for item in entries if isinstance(item, dict) and item.get("entryPointType") == "video"), "")


def _subscription_name(operation: dict[str, object]) -> str | None:
    response = operation.get("response")
    if isinstance(response, dict) and response.get("name"):
        return str(response["name"])
    metadata = operation.get("metadata")
    if isinstance(metadata, dict):
        subscription = str(metadata.get("subscription") or "")
        if subscription:
            return subscription
    return None


async def _subscribe(meeting: Meeting) -> None:
    topic = get_settings().google_workspace_events_topic.strip()
    if not topic or not meeting.meet_space_name:
        return
    operation = await workspace_request(meeting.account_id, "POST", WORKSPACE_EVENTS_API, json={
        "targetResource": f"//meet.googleapis.com/{meeting.meet_space_name}",
        "eventTypes": list(MEET_EVENT_TYPES),
        "notificationEndpoint": {"pubsubTopic": topic},
        "ttl": "604800s",
    })
    meeting.event_subscription_name = _subscription_name(operation)
    meeting.event_subscription_operation = None if meeting.event_subscription_name else str(operation.get("name") or "") or None


async def _renew_subscription(meeting: Meeting) -> None:
    name = meeting.event_subscription_name
    if not name:
        return
    await workspace_request(
        meeting.account_id,
        "PATCH",
        f"{WORKSPACE_EVENTS_API}/{quote(name, safe='/')}",
        params={"updateMask": "ttl"},
        json={"ttl": "604800s"},
    )


def _space_name(payload: dict[str, object]) -> str:
    resource = payload.get("space")
    if isinstance(resource, dict):
        return str(resource.get("name") or "")
    conference = payload.get("conferenceRecord")
    if isinstance(conference, dict):
        return str(conference.get("space") or "")
    return ""


def _conference_name(payload: dict[str, object]) -> str:
    conference = payload.get("conferenceRecord")
    if isinstance(conference, dict):
        return str(conference.get("name") or "")
    participant = payload.get("participantSession")
    if isinstance(participant, dict):
        name = str(participant.get("name") or "")
        return name.split("/participants/", 1)[0]
    return ""


def _space_from_subject(subject: str) -> str:
    prefix = "//meet.googleapis.com/"
    return subject.removeprefix(prefix) if subject.startswith(prefix) else ""


def _publish(meeting: Meeting) -> None:
    account_events.publish(meeting.account_id, {
        "type": "meeting_changed",
        "meeting_id": meeting.id,
        "client_id": meeting.client_id,
        "state": meeting.state,
    })
