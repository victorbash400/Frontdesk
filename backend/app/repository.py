from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from .models import Node, Workspace
from .schemas import NodeCreate, NodeUpdate


def list_nodes(session: Session, account_id: str, parent_id: str | None, include_trashed: bool) -> list[Node]:
    workspace = require_workspace(session, account_id)
    query: Select[tuple[Node]] = select(Node).where(Node.workspace_id == workspace.id)
    query = query.where(Node.parent_id == parent_id)
    if not include_trashed:
        query = query.where(Node.trashed_at.is_(None))
    return list(session.scalars(query.order_by(Node.name.asc())))


def search_nodes(session: Session, account_id: str, query: str) -> list[Node]:
    workspace = require_workspace(session, account_id)
    statement = select(Node).where(
        Node.workspace_id == workspace.id,
        Node.trashed_at.is_(None),
        Node.name.ilike(f"%{query}%"),
    ).order_by(Node.updated_at.desc()).limit(100)
    return list(session.scalars(statement))


def create_node(session: Session, account_id: str, body: NodeCreate) -> Node:
    workspace = require_workspace(session, account_id)
    if body.parent_id:
        parent = require_node(session, workspace.id, body.parent_id)
        if parent.kind not in {"client", "folder"} or parent.trashed_at:
            raise HTTPException(status.HTTP_409_CONFLICT, "The selected parent cannot contain items.")
    elif body.kind != "client":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Only clients can exist at the root.")

    node = Node(workspace_id=workspace.id, **body.model_dump())
    session.add(node)
    session.commit()
    session.refresh(node)
    return node


def update_node(session: Session, account_id: str, node_id: str, body: NodeUpdate) -> Node:
    workspace = require_workspace(session, account_id)
    node = require_node(session, workspace.id, node_id)
    changes = body.model_dump(exclude_unset=True)
    if "parent_id" in changes:
        validate_parent(session, workspace.id, node, changes["parent_id"])
    for field, value in changes.items():
        setattr(node, field, value)
    session.commit()
    session.refresh(node)
    return node


def set_trashed(session: Session, account_id: str, node_id: str, trashed: bool) -> Node:
    workspace = require_workspace(session, account_id)
    node = require_node(session, workspace.id, node_id)
    affected = {node.id}
    while True:
        child_ids = set(session.scalars(select(Node.id).where(Node.workspace_id == workspace.id, Node.parent_id.in_(affected))))
        new_ids = child_ids - affected
        if not new_ids:
            break
        affected.update(new_ids)
    timestamp = datetime.now(timezone.utc) if trashed else None
    for affected_node in session.scalars(select(Node).where(Node.workspace_id == workspace.id, Node.id.in_(affected))):
        affected_node.trashed_at = timestamp
    session.commit()
    session.refresh(node)
    return node


def require_workspace(session: Session, account_id: str) -> Workspace:
    workspace = session.scalar(select(Workspace).where(Workspace.owner_id == account_id))
    if not workspace:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found.")
    return workspace


def require_node(session: Session, workspace_id: str, node_id: str) -> Node:
    node = session.get(Node, node_id)
    if not node or node.workspace_id != workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found.")
    return node


def validate_parent(session: Session, workspace_id: str, node: Node, parent_id: str | None) -> None:
    if parent_id is None:
        if node.kind != "client":
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Only clients can exist at the root.")
        return
    if parent_id == node.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "An item cannot contain itself.")
    parent = require_node(session, workspace_id, parent_id)
    if parent.kind not in {"client", "folder"} or parent.trashed_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "The selected parent cannot contain items.")

    current = parent
    while current.parent_id:
        if current.parent_id == node.id:
            raise HTTPException(status.HTTP_409_CONFLICT, "A folder cannot move inside itself.")
        current = require_node(session, workspace_id, current.parent_id)
