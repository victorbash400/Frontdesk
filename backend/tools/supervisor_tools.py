from google.adk.tools import ToolContext

from app.database import SessionLocal
from sqlalchemy import select

from app.goals import create_notification, list_goals, update_goal
from app.models import DocumentContent, Node
from app.repository import require_node, require_workspace


def get_client_goals(tool_context: ToolContext) -> dict[str, object]:
    """Read the authoritative goals and living board for the current client."""
    account_id, client_id = _scope(tool_context)
    return execute_client_tool(account_id, client_id, "get_client_goals", {})


def update_goal_board(goal_id: str, situation: str, expected_version: int, tool_context: ToolContext) -> dict[str, object]:
    """Update a goal's current situation after interpreting confirmed worker evidence."""
    account_id, _ = _scope(tool_context)
    return execute_client_tool(account_id, "", "update_goal_board", {"goal_id": goal_id, "situation": situation, "expected_version": expected_version})


def ask_user(goal_id: str, question: str, tool_context: ToolContext) -> dict[str, object]:
    """Send one necessary goal clarification to the user's Needs You inbox."""
    account_id, _ = _scope(tool_context)
    return execute_client_tool(account_id, "", "ask_user", {"goal_id": goal_id, "question": question})


def send_client_message(goal_id: str, message: str, tool_context: ToolContext) -> dict[str, object]:
    """Place a confirmed supervisor update in the current client's message inbox."""
    account_id, _ = _scope(tool_context)
    return execute_client_tool(account_id, "", "send_client_message", {"goal_id": goal_id, "message": message})


def execute_client_tool(account_id: str, client_id: str, name: str, args: dict[str, object]) -> dict[str, object]:
    """Execute the shared client-supervisor surface for chat and live agents."""
    with SessionLocal() as session:
        if name == "get_client_goals":
            return {"goals": list_goals(session, account_id, client_id)}
        if name == "get_client_documents":
            workspace = require_workspace(session, account_id)
            require_node(session, workspace.id, client_id)
            nodes = list(session.scalars(select(Node).where(Node.workspace_id == workspace.id, Node.trashed_at.is_(None))))
            container_ids = {client_id}
            while True:
                children = {node.id for node in nodes if node.parent_id in container_ids and node.kind == "folder"}
                additions = children - container_ids
                if not additions:
                    break
                container_ids.update(additions)
            documents = session.execute(
                select(Node, DocumentContent)
                .join(DocumentContent, DocumentContent.node_id == Node.id)
                .where(Node.workspace_id == workspace.id, Node.parent_id.in_(container_ids), Node.kind.in_(("document", "note")), Node.trashed_at.is_(None))
                .order_by(Node.name)
            ).all()
            return {"documents": [{"id": node.id, "name": node.name, "content": content.content} for node, content in documents]}
        if name == "update_goal_board":
            return update_goal(session, account_id, str(args["goal_id"]), situation=str(args["situation"]), expected_version=int(args["expected_version"]))
        if name == "ask_user":
            return create_notification(session, account_id, str(args["goal_id"]), "clarification", str(args["question"]))
        if name == "send_client_message":
            return create_notification(session, account_id, str(args["goal_id"]), "message", str(args["message"]))
    return {"status": "failed", "error": "Unsupported client tool."}


def _scope(tool_context: ToolContext) -> tuple[str, str]:
    account_id = str(tool_context.state.get("account_id") or "")
    client_id = str(tool_context.state.get("client_id") or "")
    if not account_id or not client_id:
        raise RuntimeError("The client supervisor scope is missing. Start a new client chat.")
    return account_id, client_id
