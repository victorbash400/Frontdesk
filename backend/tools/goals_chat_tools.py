from google.adk.tools import ToolContext
from app.database import SessionLocal
from app.goals import list_goals


def list_goal_tasks(tool_context: ToolContext) -> dict[str, object]:
    """Read every goal and its authoritative task board across all clients."""
    with SessionLocal() as session:
        return {"goals": list_goals(session, _account_id(tool_context))}


async def revise_goal_plan(goal_id: str, instruction: str, tool_context: ToolContext) -> dict[str, object]:
    """Ask the goal planner to create, reuse, update, steer, or cancel tasks for one active goal."""
    from app.goal_tasks import goal_tasks

    try:
        return await goal_tasks.revise_goal(_account_id(tool_context), goal_id, instruction)
    except Exception as error:
        return {"status": "failed", "error": str(error).strip() or error.__class__.__name__}


def _account_id(tool_context: ToolContext) -> str:
    account_id = str(tool_context.state.get("account_id") or "")
    if not account_id:
        raise RuntimeError("The Goals chat account scope is missing.")
    return account_id
