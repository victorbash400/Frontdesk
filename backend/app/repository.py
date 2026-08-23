from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from .models import Node, Workspace
from .schemas import NodeCreate, NodeUpdate


DEFAULT_WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"


def ensure_default_workspace(session: Session) -> None:
    if session.get(Workspace, DEFAULT_WORKSPACE_ID):
        return
    session.add(Workspace(id=DEFAULT_WORKSPACE_ID, name="Operator"))
    session.commit()


def list_nodes(session: Session, parent_id: str | None, include_trashed: bool) -> list[Node]:
    query: Select[tuple[Node]] = select(Node).where(Node.workspace_id == DEFAULT_WORKSPACE_ID)
    query = query.where(Node.parent_id == parent_id)
    if not include_trashed:
        query = query.where(Node.trashed_at.is_(None))
    return list(session.scalars(query.order_by(Node.name.asc())))


def search_nodes(session: Session, query: str) -> list[Node]:
    statement = select(Node).where(
        Node.workspace_id == DEFAULT_WORKSPACE_ID,
        Node.trashed_at.is_(None),
        Node.name.ilike(f"%{query}%"),
    ).order_by(Node.updated_at.desc()).limit(100)
    return list(session.scalars(statement))


def create_node(session: Session, body: NodeCreate) -> Node:
    if body.parent_id:
        parent = require_node(session, body.parent_id)
        if parent.kind not in {"client", "folder"} or parent.trashed_at:
            raise HTTPException(status.HTTP_409_CONFLICT, "The selected parent cannot contain items.")
    elif body.kind != "client":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Only clients can exist at the root.")

    node = Node(workspace_id=DEFAULT_WORKSPACE_ID, **body.model_dump())
    session.add(node)
    session.commit()
    session.refresh(node)
    return node


def update_node(session: Session, node_id: str, body: NodeUpdate) -> Node:
    node = require_node(session, node_id)
    changes = body.model_dump(exclude_unset=True)
    if "parent_id" in changes:
        validate_parent(session, node, changes["parent_id"])
    for field, value in changes.items():
        setattr(node, field, value)
    session.commit()
    session.refresh(node)
    return node


def set_trashed(session: Session, node_id: str, trashed: bool) -> Node:
    node = require_node(session, node_id)
    affected = {node.id}
    while True:
        child_ids = set(session.scalars(select(Node.id).where(Node.parent_id.in_(affected))))
        new_ids = child_ids - affected
        if not new_ids:
            break
        affected.update(new_ids)
    timestamp = datetime.now(timezone.utc) if trashed else None
    for affected_node in session.scalars(select(Node).where(Node.id.in_(affected))):
        affected_node.trashed_at = timestamp
    session.commit()
    session.refresh(node)
    return node


def require_node(session: Session, node_id: str) -> Node:
    node = session.get(Node, node_id)
    if not node or node.workspace_id != DEFAULT_WORKSPACE_ID:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found.")
    return node


def validate_parent(session: Session, node: Node, parent_id: str | None) -> None:
    if parent_id is None:
        if node.kind != "client":
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Only clients can exist at the root.")
        return
    if parent_id == node.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "An item cannot contain itself.")
    parent = require_node(session, parent_id)
    if parent.kind not in {"client", "folder"} or parent.trashed_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "The selected parent cannot contain items.")

    current = parent
    while current.parent_id:
        if current.parent_id == node.id:
            raise HTTPException(status.HTTP_409_CONFLICT, "A folder cannot move inside itself.")
        current = require_node(session, current.parent_id)
