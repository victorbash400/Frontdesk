from datetime import datetime
import logging

from google.adk.tools import ToolContext

from app.database import SessionLocal

from .service import create_instant_meeting, create_meeting, require_meeting


logger = logging.getLogger("uvicorn.error")


async def create_client_meeting(
    client_email: str,
    title: str,
    start_time: str,
    end_time: str,
    tool_context: ToolContext,
    description: str = "",
    goal_id: str | None = None,
) -> dict[str, object]:
    """Create a Google Meet calendar invitation for the current client."""
    _reject_nested_meeting_action(tool_context)
    account_id = str(tool_context.state.get("account_id") or "")
    client_id = str(tool_context.state.get("client_id") or "")
    if not account_id or not client_id:
        raise RuntimeError("The meeting worker account and client scope are missing.")
    try:
        start = datetime.fromisoformat(start_time)
        end = datetime.fromisoformat(end_time)
    except ValueError as error:
        raise ValueError("Meeting times must be ISO 8601 values with timezone offsets.") from error
    with SessionLocal() as session:
        return await create_meeting(
            session,
            account_id,
            client_id=client_id,
            client_email=client_email,
            title=title,
            start_time=start,
            end_time=end,
            goal_id=goal_id or str(tool_context.state.get("goal_id") or "") or None,
            description=description,
        )


async def create_instant_client_meeting(
    client_email: str,
    title: str,
    tool_context: ToolContext,
    description: str = "",
) -> dict[str, object]:
    """Create an immediate 30-minute Google Meet space without a Calendar event."""
    _reject_nested_meeting_action(tool_context)
    account_id = str(tool_context.state.get("account_id") or "")
    client_id = str(tool_context.state.get("client_id") or "")
    goal_id = str(tool_context.state.get("goal_id") or "") or None
    if not account_id or not client_id:
        raise RuntimeError("The meeting worker account and client scope are missing.")
    logger.info("goal=%s meeting=create_instant status=started client=%s email=%s", goal_id, client_id, client_email)
    with SessionLocal() as session:
        result = await create_instant_meeting(
            session,
            account_id,
            client_id=client_id,
            client_email=client_email,
            title=title,
            goal_id=goal_id,
            description=description,
        )
    logger.info("goal=%s meeting=%s create_instant status=completed uri=%s", goal_id, result.get("id"), result.get("meetUri"))
    return result


async def join_client_meeting(meeting_id: str, tool_context: ToolContext) -> dict[str, str]:
    """Join the exact Front Desk meeting through its dedicated media worker."""
    from .browser_worker import join_meeting

    account_id = str(tool_context.state.get("account_id") or "")
    logger.info("meeting=%s worker=join status=started", meeting_id)
    with SessionLocal() as session:
        meeting = require_meeting(session, account_id, meeting_id)
        expected_goal = str(tool_context.state.get("goal_id") or "")
        if expected_goal and meeting.goal_id != expected_goal:
            raise ValueError("The meeting does not belong to the current goal.")
        result = await join_meeting(meeting)
    logger.info("meeting=%s worker=join status=completed runtime=%s", meeting_id, result.get("runtimeId"))
    return result


def wait_for_client_in_meeting(meeting_id: str, tool_context: ToolContext) -> dict[str, str]:
    """End the goal-worker run while the dedicated meeting worker waits for the client."""
    account_id = str(tool_context.state.get("account_id") or "")
    expected_goal = str(tool_context.state.get("goal_id") or "")
    with SessionLocal() as session:
        meeting = require_meeting(session, account_id, meeting_id)
        if expected_goal and meeting.goal_id != expected_goal:
            raise ValueError("The meeting does not belong to the current goal.")
        if meeting.state not in {"browser_opened", "browser_ready", "waiting_for_client"}:
            raise ValueError(f"The meeting worker is not waiting for the client; current state is {meeting.state}.")
    logger.info("meeting=%s goal_worker=external_wait state=%s", meeting_id, meeting.state)
    return {"status": "waiting", "meeting_id": meeting_id, "reason": "Waiting for the client to join the emailed Meet link."}


def _reject_nested_meeting_action(tool_context: ToolContext) -> None:
    source_meeting_id = str(tool_context.state.get("source_meeting_id") or "")
    if source_meeting_id:
        raise RuntimeError(
            f"This task belongs to active meeting {source_meeting_id}; creating another meeting is prohibited."
        )
