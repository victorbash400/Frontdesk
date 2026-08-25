from google.adk.tools import ToolContext

from app.database import SessionLocal
from app.goals import create_notification, list_goals, update_goal


def get_client_goals(tool_context: ToolContext) -> dict[str, object]:
    """Read the authoritative goals and living board for the current client."""
    account_id, client_id = _scope(tool_context)
    with SessionLocal() as session:
        return {"goals": list_goals(session, account_id, client_id)}


def update_goal_board(goal_id: str, situation: str, expected_version: int, tool_context: ToolContext) -> dict[str, object]:
    """Update a goal's current situation after interpreting confirmed worker evidence."""
    account_id, _ = _scope(tool_context)
    with SessionLocal() as session:
        return update_goal(session, account_id, goal_id, situation=situation, expected_version=expected_version)


def ask_user(goal_id: str, question: str, tool_context: ToolContext) -> dict[str, object]:
    """Send one necessary goal clarification to the user's Needs You inbox."""
    account_id, _ = _scope(tool_context)
    with SessionLocal() as session:
        return create_notification(session, account_id, goal_id, "clarification", question)


def send_client_message(goal_id: str, message: str, tool_context: ToolContext) -> dict[str, object]:
    """Place a confirmed supervisor update in the current client's message inbox."""
    account_id, _ = _scope(tool_context)
    with SessionLocal() as session:
        return create_notification(session, account_id, goal_id, "message", message)


def _scope(tool_context: ToolContext) -> tuple[str, str]:
    account_id = str(tool_context.state.get("account_id") or "")
    client_id = str(tool_context.state.get("client_id") or "")
    if not account_id or not client_id:
        raise RuntimeError("The client supervisor scope is missing. Start a new client chat.")
    return account_id, client_id
