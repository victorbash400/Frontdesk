from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import ClientEmailIdentity, DocumentContent, EmailAgentActivity, EmailConversation, Goal, MailboxConnection, MailMessage, Node, PluginInstallation
from app import mailboxes
from tools.email_agent_tools import decide_email_action, read_email_context, read_email_goal_skill, resolve_email_client, update_client_email_summary
from tests.test_api import account_headers, create_account


def test_email_agent_tools_create_one_client_record_only_and_preserve_profile() -> None:
    with TestClient(app) as client:
        account = create_account(client, "email-agent-record@example.com", "Email Agent Record")
        message_id = _incoming(account["id"], "Pat Potato <pat@example.com>", "Hello", "Just saying hello.")
        context = _context(account["id"], message_id)

        resolved = resolve_email_client(context)
        repeated = resolve_email_client(context)
        assert resolved["status"] == "created"
        assert repeated["status"] == "matched"
        assert read_email_context(context)["email"]["body"] == "Just saying hello."
        assert read_email_goal_skill(context)["name"] == "Email Goal Routing"
        assert update_client_email_summary("Latest interaction: Pat sent a greeting. No action is required.", context)["status"] == "updated"
        decision = decide_email_action("record_only", "The email is a greeting and requests no work.", context)
        assert decision == {"status": "completed", "action": "record_only", "goal_id": "", "instruction": ""}
        snapshot = client.get("/api/filesystem/snapshot", headers=account_headers(account["id"]))
        assert snapshot.status_code == 200
        assert {item["kind"] for item in snapshot.json()} >= {"client", "profile", "email"}

        with SessionLocal() as session:
            message = session.get(MailMessage, message_id)
            assert message and message.goal_id is None and message.agent_status == "completed"
            assert session.query(ClientEmailIdentity).filter_by(email="pat@example.com").count() == 1
            assert session.get(Node, message.client_id).name == "Pat Potato"
            assert session.query(Node).filter_by(kind="email", parent_id=message.client_id).count() == 1
            profile_node = session.query(Node).filter_by(kind="profile", parent_id=message.client_id).one()
            profile = session.query(DocumentContent).filter_by(node_id=profile_node.id).one()
            assert "Email: pat@example.com" in profile.content
            assert "## Email Agent Summary" in profile.content
            assert session.query(EmailAgentActivity).filter_by(message_id=message_id).count() >= 6


def test_email_agent_tools_bind_reply_to_exact_existing_goal() -> None:
    with TestClient(app) as client:
        account = create_account(client, "email-agent-resume@example.com", "Email Agent Resume")
        first_id = _incoming(account["id"], "Pat Potato <pat@example.com>", "Order AQ-1042", "My payment is missing.")
        first_context = _context(account["id"], first_id)
        client_id = str(resolve_email_client(first_context)["client_id"])
        with SessionLocal() as session:
            session.add(PluginInstallation(account_id=account["id"], plugin_id="aqualabs-store"))
            session.commit()
        update_client_email_summary("Current problem: Order AQ-1042 payment is missing.", first_context)
        created = decide_email_action("create_goal", "This is a concrete new order problem.", first_context, goal_objective="Correct the missing payment on order AQ-1042 and confirm the outcome with Pat.")
        goal_id = str(created["goal_id"])

        with SessionLocal() as session:
            goal = session.get(Goal, goal_id)
            assert goal and "aqualabs-store" in goal.plugin_ids
            first = session.get(MailMessage, first_id)
            connection = session.get(MailboxConnection, first.mailbox_id)
            outbound = MailMessage(mailbox_id=connection.id, client_id=client_id, conversation_id=first.conversation_id, goal_id=goal_id, direction="outbound", message_id="<question@example.com>", in_reply_to=first.message_id, references=first.message_id, sender=connection.email, recipients="pat@example.com", subject="Re: Order AQ-1042", body="Can you confirm the charge time?", agent_status="completed", agent_action="outbound")
            session.add(outbound)
            session.commit()

        reply = mailboxes.IncomingMessage(2, "<answer@example.com>", "<question@example.com>", "<first@example.com> <question@example.com>", "pat@example.com", "support@aqualabs.tech", "Re: Order AQ-1042", "The charge was at 10:15.", datetime.now(timezone.utc))
        mailbox_id = _mailbox_id(account["id"])
        reply_id = mailboxes._record_incoming(mailbox_id, reply)
        reply_context = _context(account["id"], str(reply_id))
        assert resolve_email_client(reply_context)["client_id"] == client_id
        context_payload = read_email_context(reply_context)
        assert context_payload["conversation"]["goal_id"] == goal_id
        resumed = decide_email_action("resume_goal", "This answers the active case's outstanding question.", reply_context, goal_id=goal_id)
        assert resumed["goal_id"] == goal_id

        with SessionLocal() as session:
            assert session.query(ClientEmailIdentity).filter_by(email="pat@example.com", client_id=client_id).count() == 1
            assert session.query(Goal).filter_by(account_id=account["id"]).count() == 1
            reply_record = session.get(MailMessage, reply_id)
            assert reply_record and reply_record.goal_id == goal_id
            conversation = session.get(EmailConversation, reply_record.conversation_id)
            assert conversation and conversation.goal_id == goal_id


def test_email_agent_tool_failures_are_results() -> None:
    with TestClient(app) as client:
        account = create_account(client, "email-agent-failure@example.com", "Email Agent Failure")
        message_id = _incoming(account["id"], "No Address", "Unknown", "Help")
        result = resolve_email_client(_context(account["id"], message_id))
        assert result["status"] == "failed"
        assert "usable address" in str(result["error"])


def _incoming(account_id: str, sender: str, subject: str, body: str) -> str:
    mailbox_id = _mailbox_id(account_id, create=True)
    incoming = mailboxes.IncomingMessage(1, f"<{subject.casefold().replace(' ', '-')}@example.com>", "", "", sender, "support@aqualabs.tech", subject, body, datetime.now(timezone.utc))
    message_id = mailboxes._record_incoming(mailbox_id, incoming)
    assert message_id
    return message_id


def _mailbox_id(account_id: str, create: bool = False) -> str:
    with SessionLocal() as session:
        connection = session.query(MailboxConnection).filter_by(account_id=account_id).one_or_none()
        if not connection and create:
            connection = MailboxConnection(account_id=account_id, provider="titan", email="support@aqualabs.tech", incoming_host="imap.titan.email", incoming_port=993, outgoing_host="smtp.titan.email", outgoing_port=465, encrypted_password="encrypted", uid_validity="1", last_uid=0, state="connected")
            session.add(connection)
            session.commit()
        assert connection
        return connection.id


def _context(account_id: str, message_id: str) -> SimpleNamespace:
    return SimpleNamespace(state={"account_id": account_id, "email_message_id": message_id})
