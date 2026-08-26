from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.goals import create_goal
from app.models import DocumentContent, Goal, Node
from app.repository import require_workspace


SAMPLE_DOCUMENT = Path(__file__).resolve().parents[1] / "samples" / "clients" / "angeline-kamau" / "duplicate-charge-resolution.md"


def ensure_angeline_sample(session: Session, account_id: str) -> dict[str, str]:
    workspace = require_workspace(session, account_id)
    client = session.scalar(select(Node).where(
        Node.workspace_id == workspace.id,
        Node.parent_id.is_(None),
        Node.kind == "client",
        Node.name == "Angeline Kamau",
    ))
    if not client:
        client = Node(workspace_id=workspace.id, name="Angeline Kamau", kind="client")
        session.add(client)
        session.flush()

    document = session.scalar(select(Node).where(
        Node.workspace_id == workspace.id,
        Node.parent_id == client.id,
        Node.kind == "document",
        Node.name == "Duplicate charge resolution.md",
    ))
    if not document:
        document = Node(
            workspace_id=workspace.id,
            parent_id=client.id,
            name="Duplicate charge resolution.md",
            kind="document",
        )
        session.add(document)
        session.flush()

    content = session.scalar(select(DocumentContent).where(DocumentContent.node_id == document.id))
    text = SAMPLE_DOCUMENT.read_text()
    if content:
        content.content = text
    else:
        session.add(DocumentContent(node_id=document.id, content=text))
    session.commit()

    goal_text = "Resolve Angeline's apparent duplicate USD 149 annual-plan charge during the client meeting."
    goal = session.scalar(select(Goal).where(
        Goal.account_id == account_id,
        Goal.client_id == client.id,
        Goal.text == goal_text,
        Goal.status == "active",
    ))
    if goal:
        goal_id = goal.id
    else:
        goal_id = str(create_goal(session, account_id, client.id, goal_text, [], [])["id"])
    return {"clientId": client.id, "documentId": document.id, "goalId": goal_id}
