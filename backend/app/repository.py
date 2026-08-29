from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from .models import DocumentContent, Node, Workspace
from .schemas import FileSystemNodeSync, NodeCreate, NodeUpdate


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


def filesystem_snapshot(session: Session, account_id: str) -> list[dict[str, object]]:
    workspace = require_workspace(session, account_id)
    rows = session.execute(
        select(Node, DocumentContent)
        .outerjoin(DocumentContent, DocumentContent.node_id == Node.id)
        .where(Node.workspace_id == workspace.id)
        .order_by(Node.created_at)
    ).all()
    return [{
        "id": node.id,
        "parentId": node.parent_id,
        "name": node.name,
        "kind": node.kind,
        "createdAt": node.created_at,
        "updatedAt": node.updated_at,
        "shared": node.shared,
        "needsAttention": node.needs_attention,
        "trashedAt": node.trashed_at,
        "content": content.content if content else None,
    } for node, content in rows]


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


def sync_nodes(session: Session, account_id: str, nodes: list[FileSystemNodeSync]) -> dict[str, int]:
    workspace = require_workspace(session, account_id)
    incoming_ids = {item.id for item in nodes}
    for item in nodes:
        existing = session.get(Node, item.id)
        if existing and existing.workspace_id != workspace.id:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Item {item.id} belongs to another workspace.")
        if item.parent_id and item.parent_id not in incoming_ids:
            parent = session.get(Node, item.parent_id)
            if not parent or parent.workspace_id != workspace.id:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Parent {item.parent_id} is missing.")

    pending = list(nodes)
    synced = 0
    while pending:
        progressed = False
        for item in pending[:]:
            if item.parent_id and not session.get(Node, item.parent_id):
                continue
            node = session.get(Node, item.id)
            if not node:
                node = Node(id=item.id, workspace_id=workspace.id, parent_id=item.parent_id, name=item.name, kind=item.kind)
                session.add(node)
            node.parent_id = item.parent_id
            node.name = item.name
            node.kind = item.kind
            node.shared = item.shared
            node.needs_attention = item.needs_attention
            node.trashed_at = item.trashed_at
            session.flush()
            if item.kind in {"document", "note"} and item.content is not None:
                content = session.scalar(select(DocumentContent).where(DocumentContent.node_id == node.id))
                if content:
                    content.content = item.content
                else:
                    session.add(DocumentContent(node_id=node.id, content=item.content))
            pending.remove(item)
            synced += 1
            progressed = True
        if not progressed:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The filesystem contains a parent cycle.")
    session.commit()
    return {"synced": synced}


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
