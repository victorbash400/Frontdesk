import json
from email.utils import parseaddr

from google.adk.tools import ToolContext
from sqlalchemy import select

from app.database import SessionLocal
from app.event_stream import account_events
from app.goals import add_goal_activity, create_goal
from app.models import (
    ClientEmailIdentity,
    DocumentContent,
    EmailAgentActivity,
    EmailConversation,
    Goal,
    GoalAssignment,
    MailMessage,
    Node,
    PluginInstallation,
    Skill,
    Workspace,
)
from app.skills import seed_skills


def resolve_email_client(tool_context: ToolContext) -> dict[str, object]:
    """Resolve the sender to exactly one client, or create that client and its profile once."""
    account_id, message_id = _scope(tool_context)
    with SessionLocal() as session:
        message = _message(session, message_id)
        workspace = session.scalar(select(Workspace).where(Workspace.owner_id == account_id))
        if not workspace:
            return _failed("The mailbox owner does not have a Front Desk workspace.")
        sender_name, sender_email = parseaddr(message.sender)
        address = sender_email.strip().casefold()
        if not address or "@" not in address or address.startswith("@") or address.endswith("@"):
            return _failed("The email sender does not contain a usable address.")

        identity = session.scalar(select(ClientEmailIdentity).where(
            ClientEmailIdentity.workspace_id == workspace.id,
            ClientEmailIdentity.email == address,
        ))
        created = False
        if identity:
            client = session.get(Node, identity.client_id)
            if not client or client.trashed_at or client.kind != "client":
                return _failed("The sender identity points to an unavailable client.")
        else:
            client = _find_legacy_client(session, workspace.id, address)
            if not client:
                client = Node(workspace_id=workspace.id, parent_id=None, name=sender_name.strip() or address, kind="client")
                session.add(client)
                session.flush()
                profile = Node(workspace_id=workspace.id, parent_id=client.id, name="Client Profile", kind="profile")
                session.add(profile)
                session.flush()
                session.add(DocumentContent(node_id=profile.id, content=f"Email: {address}\n"))
                created = True
            session.add(ClientEmailIdentity(workspace_id=workspace.id, client_id=client.id, email=address))

        conversation = _conversation_for_message(session, message)
        conversation.client_id = client.id
        message.client_id = client.id
        message.conversation_id = conversation.id
        _ensure_email_file(session, client, message)
        _activity(session, message, "client_created" if created else "client_matched", f"{'Created' if created else 'Matched'} client {client.name} for {address}.", client.id)
        session.commit()
        _publish(account_id, message.id)
        return {"status": "created" if created else "matched", "client_id": client.id, "client_name": client.name, "email": address}


def read_email_context(tool_context: ToolContext) -> dict[str, object]:
    """Read the email, its client profile, conversation, documents, active goals, and waiting tasks."""
    account_id, message_id = _scope(tool_context)
    with SessionLocal() as session:
        message = _message(session, message_id)
        if not message.client_id:
            return _failed("Resolve the email client before reading client context.")
        client = session.get(Node, message.client_id)
        if not client:
            return _failed("The resolved client no longer exists.")
        profile = session.scalar(select(DocumentContent).join(Node).where(Node.parent_id == client.id, Node.kind == "profile"))
        documents = session.execute(
            select(Node, DocumentContent).join(DocumentContent, DocumentContent.node_id == Node.id).where(
                Node.parent_id == client.id,
                Node.kind.in_(("document", "note")),
                Node.trashed_at.is_(None),
            ).order_by(Node.name)
        ).all()
        conversation_messages = list(session.scalars(select(MailMessage).where(
            MailMessage.conversation_id == message.conversation_id,
        ).order_by(MailMessage.created_at))) if message.conversation_id else [message]
        goals = list(session.scalars(select(Goal).where(Goal.account_id == account_id, Goal.client_id == client.id).order_by(Goal.updated_at.desc()).limit(12)))
        goal_rows = []
        for goal in goals:
            assignments = list(session.scalars(select(GoalAssignment).where(GoalAssignment.goal_id == goal.id).order_by(GoalAssignment.created_at)))
            goal_rows.append({
                "id": goal.id,
                "text": goal.text,
                "situation": goal.situation,
                "status": goal.status,
                "tasks": [{"id": item.id, "title": item.title, "status": item.status, "current_step": item.current_step, "next_step": item.next_step} for item in assignments],
            })
        conversation = session.get(EmailConversation, message.conversation_id) if message.conversation_id else None
        _activity(session, message, "context_read", f"Read {client.name}'s profile, email history, documents, and goal board.", client.id)
        session.commit()
        _publish(account_id, message.id)
        return {
            "status": "completed",
            "email": {"from": message.sender, "to": message.recipients, "subject": message.subject, "body": message.body},
            "client": {"id": client.id, "name": client.name, "profile": profile.content if profile else ""},
            "conversation": {
                "goal_id": conversation.goal_id if conversation else None,
                "task_id": conversation.assignment_id if conversation else None,
                "messages": [{"direction": item.direction, "subject": item.subject, "body": item.body} for item in conversation_messages[-20:]],
            },
            "documents": [{"name": node.name, "content": content.content[:8_000]} for node, content in documents],
            "goals": goal_rows,
        }


def read_email_goal_skill(tool_context: ToolContext) -> dict[str, object]:
    """Read the organization's goal-handling skill before deciding whether email should create or resume work."""
    account_id, message_id = _scope(tool_context)
    with SessionLocal() as session:
        seed_skills(session, account_id)
        skill = session.scalar(select(Skill).where(Skill.account_id == account_id, Skill.slug == "email-goal-routing"))
        if not skill:
            return _failed("The Email Goal Routing skill is unavailable.")
        message = _message(session, message_id)
        _activity(session, message, "skill_read", "Read the Email Goal Routing skill.", message.client_id)
        session.commit()
        _publish(account_id, message.id)
        return {"status": "completed", "skill_id": skill.id, "name": skill.name, "instructions": skill.instructions}


def update_client_email_summary(summary: str, tool_context: ToolContext) -> dict[str, object]:
    """Update the resolved client's living profile with a concise evidence-based summary."""
    account_id, message_id = _scope(tool_context)
    clean_summary = summary.strip()
    if not clean_summary:
        return _failed("The client summary cannot be empty.")
    with SessionLocal() as session:
        message = _message(session, message_id)
        if not message.client_id:
            return _failed("Resolve the email client before updating its profile.")
        client = session.get(Node, message.client_id)
        profile_node = session.scalar(select(Node).where(Node.parent_id == message.client_id, Node.kind == "profile"))
        if not client or not profile_node:
            return _failed("The resolved client profile is unavailable.")
        profile = session.scalar(select(DocumentContent).where(DocumentContent.node_id == profile_node.id))
        if not profile:
            return _failed("The resolved client profile has no content record.")
        _, sender_email = parseaddr(message.sender)
        profile.content = _updated_profile(profile.content, sender_email.strip().casefold(), clean_summary)
        message.agent_summary = clean_summary
        _activity(session, message, "profile_updated", f"Updated {client.name}'s living client summary.", client.id)
        session.commit()
        _publish(account_id, message.id)
        return {"status": "updated", "client_id": client.id}


def decide_email_action(
    action: str,
    reason: str,
    tool_context: ToolContext,
    goal_id: str = "",
    task_id: str = "",
    goal_objective: str = "",
) -> dict[str, object]:
    """Record the Email Agent's final action: record_only, resume_goal, create_goal, or request_attention."""
    account_id, message_id = _scope(tool_context)
    if action not in {"record_only", "resume_goal", "create_goal", "request_attention"}:
        return _failed("Unknown email action.")
    clean_reason = reason.strip()
    if not clean_reason:
        return _failed("The email action needs an evidence-based reason.")
    with SessionLocal() as session:
        message = _message(session, message_id)
        if not message.client_id or not message.conversation_id:
            return _failed("Resolve the client before deciding the email action.")
        client = session.get(Node, message.client_id)
        conversation = session.get(EmailConversation, message.conversation_id)
        if not client or not conversation:
            return _failed("The email context is unavailable.")

        dispatch_goal_id = ""
        dispatch_instruction = ""
        if action == "resume_goal":
            goal = session.scalar(select(Goal).where(Goal.id == goal_id, Goal.account_id == account_id, Goal.client_id == client.id))
            if not goal or goal.status != "active":
                return _failed("The selected active goal does not belong to this client.")
            assignment = session.scalar(select(GoalAssignment).where(GoalAssignment.id == task_id, GoalAssignment.goal_id == goal.id)) if task_id else None
            conversation.goal_id = goal.id
            conversation.assignment_id = assignment.id if assignment else None
            message.goal_id = goal.id
            message.assignment_id = assignment.id if assignment else None
            add_goal_activity(session, account_id, goal.id, "email_received", f"Email Agent attached customer email: {message.subject}")
            dispatch_goal_id = goal.id
            dispatch_instruction = _resume_instruction(message, assignment)
        elif action == "create_goal":
            objective = goal_objective.strip()
            if not objective:
                return _failed("A new goal requires a concrete customer outcome.")
            skill = session.scalar(select(Skill).where(Skill.account_id == account_id, Skill.slug == "aqualabs-customer-resolution"))
            installed = set(session.scalars(select(PluginInstallation.plugin_id).where(PluginInstallation.account_id == account_id)))
            plugin_ids = sorted(installed & {"aqualabs-store", "atlassian", "browser-use", "github", "google-workspace", "slack"})
            snapshot = create_goal(session, account_id, client.id, objective, [skill.id] if skill else [], plugin_ids)
            dispatch_goal_id = str(snapshot["id"])
            conversation.goal_id = dispatch_goal_id
            message.goal_id = dispatch_goal_id
            add_goal_activity(session, account_id, dispatch_goal_id, "email_received", f"Email Agent created this goal from: {message.subject}")
        elif action == "request_attention":
            client.needs_attention = True
            message.attention_required = True

        message.agent_status = "completed"
        message.agent_action = action
        message.agent_failure = ""
        _activity(session, message, "decision", clean_reason, client.id)
        session.commit()
        _publish(account_id, message.id)
        return {"status": "completed", "action": action, "goal_id": dispatch_goal_id, "instruction": dispatch_instruction}


def _scope(tool_context: ToolContext) -> tuple[str, str]:
    account_id = str(tool_context.state.get("account_id") or "")
    message_id = str(tool_context.state.get("email_message_id") or "")
    if not account_id or not message_id:
        raise RuntimeError("The Email Agent scope is missing.")
    return account_id, message_id


def _message(session, message_id: str) -> MailMessage:
    message = session.get(MailMessage, message_id)
    if not message:
        raise RuntimeError("The incoming email no longer exists.")
    return message


def _find_legacy_client(session, workspace_id: str, address: str) -> Node | None:
    profiles = session.execute(select(Node, DocumentContent).join(DocumentContent, DocumentContent.node_id == Node.id).where(
        Node.workspace_id == workspace_id,
        Node.kind == "profile",
        Node.trashed_at.is_(None),
    )).all()
    for profile, content in profiles:
        known = {line.split(":", 1)[1].strip().casefold() for line in content.content.splitlines() if line.casefold().startswith("email:") and ":" in line}
        if address in known and profile.parent_id:
            client = session.get(Node, profile.parent_id)
            if client and client.kind == "client" and not client.trashed_at:
                return client
    return None


def _conversation_for_message(session, message: MailMessage) -> EmailConversation:
    if message.conversation_id:
        existing = session.get(EmailConversation, message.conversation_id)
        if existing:
            return existing
    identities = set(message.references.split())
    if message.in_reply_to:
        identities.add(message.in_reply_to)
    related = session.scalar(select(MailMessage).where(
        MailMessage.mailbox_id == message.mailbox_id,
        MailMessage.message_id.in_(identities),
        MailMessage.conversation_id.is_not(None),
    ).order_by(MailMessage.created_at.desc())) if identities else None
    if related and related.conversation_id:
        conversation = session.get(EmailConversation, related.conversation_id)
        if conversation:
            return conversation
    conversation = EmailConversation(mailbox_id=message.mailbox_id, provider_thread_id=message.message_id)
    session.add(conversation)
    session.flush()
    return conversation


def _ensure_email_file(session, client: Node, message: MailMessage) -> None:
    name = f"Email - {(message.subject.strip() or 'No subject')[:180]} - {message.id[:8]}"
    existing = session.scalar(select(Node).where(Node.workspace_id == client.workspace_id, Node.parent_id == client.id, Node.name == name, Node.kind == "email"))
    if existing:
        return
    node = Node(workspace_id=client.workspace_id, parent_id=client.id, name=name, kind="email")
    session.add(node)
    session.flush()
    session.add(DocumentContent(node_id=node.id, content=json.dumps({
        "from": message.sender,
        "to": message.recipients,
        "subject": message.subject,
        "body": message.body,
        "received_at": message.received_at.isoformat() if message.received_at else None,
    }, ensure_ascii=False)))


def _activity(session, message: MailMessage, kind: str, summary: str, client_id: str | None) -> None:
    session.add(EmailAgentActivity(mailbox_id=message.mailbox_id, message_id=message.id, client_id=client_id, kind=kind, summary=summary.strip()))


def _resume_instruction(message: MailMessage, assignment: GoalAssignment | None) -> str:
    target = f" Continue task {assignment.id}: {assignment.title}." if assignment else ""
    return f"Resume this customer case using the newly received email.{target}\nFrom: {message.sender}\nSubject: {message.subject}\nMessage:\n{message.body}"


def _updated_profile(existing: str, address: str, summary: str) -> str:
    marker = "## Email Agent Summary"
    base = existing.split(marker, 1)[0].rstrip()
    email_line = f"Email: {address}"
    if not any(line.strip().casefold() == email_line.casefold() for line in base.splitlines()):
        base = f"{base}\n{email_line}".strip()
    return f"{base}\n\n{marker}\n{summary}\n"


def _publish(account_id: str, message_id: str) -> None:
    account_events.publish(account_id, {"type": "mailbox_changed", "message_id": message_id})


def _failed(error: str) -> dict[str, str]:
    return {"status": "failed", "error": error}
