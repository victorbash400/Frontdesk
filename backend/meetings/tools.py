from datetime import datetime

from google.adk.tools import ToolContext

from app.database import SessionLocal

from .service import create_meeting


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
