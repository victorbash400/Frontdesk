from fastapi import APIRouter, Body, Depends, HTTPException, WebSocket
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.auth import require_account_id, require_scheduler
from app.database import get_session
from app.schemas import MeetingAgentTicketRequest, MeetingCreate

from .agent_session import create_agent_ticket, run_meet_agent
from .browser_worker import join_meeting
from .events import decode_pubsub_event
from .service import create_meeting, list_meetings, process_workspace_event, require_meeting


router = APIRouter()


@router.get("/api/meetings")
def get_meetings(client_id: str | None = None, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> list[dict[str, object]]:
    return list_meetings(session, account_id, client_id)


@router.post("/api/meetings", status_code=201)
async def post_meeting(body: MeetingCreate, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        return await create_meeting(session, account_id, **body.model_dump())
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except RuntimeError as error:
        raise HTTPException(502, str(error)) from error


@router.post("/api/meetings/{meeting_id}/agent-ticket")
def post_meeting_agent_ticket(meeting_id: str, body: MeetingAgentTicketRequest, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, str]:
    try:
        require_meeting(session, account_id, meeting_id)
    except ValueError as error:
        raise HTTPException(404, str(error)) from error
    return {
        "ticket": create_agent_ticket(account_id, meeting_id),
        "voice": body.voice,
        "language": body.language,
    }


@router.post("/api/meetings/{meeting_id}/join")
async def post_join_meeting(meeting_id: str, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, str]:
    try:
        meeting = require_meeting(session, account_id, meeting_id)
        return await join_meeting(meeting)
    except ValueError as error:
        raise HTTPException(404, str(error)) from error
    except RuntimeError as error:
        raise HTTPException(503, str(error)) from error


@router.websocket("/api/meetings/{meeting_id}/agent")
async def meeting_agent_socket(websocket: WebSocket, meeting_id: str, ticket: str, voice: str = "Kore", language: str = "en") -> None:
    await run_meet_agent(websocket, meeting_id, ticket, voice, language)


@router.post("/internal/google-workspace-events", status_code=204)
async def post_google_workspace_event(
    envelope: dict[str, object] = Body(...),
    _: None = Depends(require_scheduler),
    session: Session = Depends(get_session),
) -> Response:
    try:
        event = decode_pubsub_event(envelope)
        await process_workspace_event(session, None, event.id, event.type, event.data, source=event.source, subject=event.subject)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    return Response(status_code=204)
