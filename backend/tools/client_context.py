from google.adk.tools import ToolContext
from sqlalchemy import select

from app.database import SessionLocal
from app.models import ClientEmailIdentity, DocumentContent, Goal, Node, Workspace


def list_clients(tool_context: ToolContext) -> dict[str, object]:
    """List the canonical Front Desk clients available to this account."""
    account_id = _account_id(tool_context)
    with SessionLocal() as session:
        workspace = session.scalar(select(Workspace).where(Workspace.owner_id == account_id))
        if not workspace:
            return {"status": "failed", "error": "This account does not have a Front Desk workspace."}
        clients = list(session.scalars(select(Node).where(
            Node.workspace_id == workspace.id,
            Node.kind == "client",
            Node.trashed_at.is_(None),
        ).order_by(Node.name)))
        return {
            "status": "completed",
            "clients": [{"id": client.id, "name": client.name} for client in clients],
        }


def read_client_profile(tool_context: ToolContext, client_id: str = "") -> dict[str, object]:
    """Read the assigned client profile, or one canonical client by exact client ID."""
    account_id = _account_id(tool_context)
    resolved_client_id = client_id.strip() or str(tool_context.state.get("client_id") or "")
    if not resolved_client_id:
        return {"status": "failed", "error": "No assigned or selected Front Desk client is available."}
    with SessionLocal() as session:
        workspace = session.scalar(select(Workspace).where(Workspace.owner_id == account_id))
        if not workspace:
            return {"status": "failed", "error": "This account does not have a Front Desk workspace."}
        client = session.scalar(select(Node).where(
            Node.id == resolved_client_id,
            Node.workspace_id == workspace.id,
            Node.kind == "client",
            Node.trashed_at.is_(None),
        ))
        if not client:
            return {"status": "not_found", "error": "That client is not in the Front Desk client list."}
        profile = session.execute(
            select(Node, DocumentContent)
            .join(DocumentContent, DocumentContent.node_id == Node.id)
            .where(Node.parent_id == client.id, Node.kind == "profile", Node.trashed_at.is_(None))
        ).first()
        emails = list(session.scalars(select(ClientEmailIdentity.email).where(
            ClientEmailIdentity.workspace_id == workspace.id,
            ClientEmailIdentity.client_id == client.id,
        ).order_by(ClientEmailIdentity.email)))
        goals = list(session.scalars(select(Goal).where(
            Goal.account_id == account_id,
            Goal.client_id == client.id,
        ).order_by(Goal.updated_at.desc()).limit(10)))
        return {
            "status": "completed",
            "client": {
                "id": client.id,
                "name": client.name,
                "profile": profile[1].content if profile else "",
                "emails": emails,
                "goals": [
                    {
                        "id": goal.id,
                        "text": goal.text,
                        "status": goal.status,
                        "situation": goal.situation,
                    }
                    for goal in goals
                ],
            },
        }


def _account_id(tool_context: ToolContext) -> str:
    account_id = str(tool_context.state.get("account_id") or "")
    if not account_id:
        raise RuntimeError("The client-directory tool is missing its account scope.")
    return account_id
