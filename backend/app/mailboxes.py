import asyncio
import email
import imaplib
import json
import logging
import smtplib
import ssl
import threading
from dataclasses import dataclass
from email.header import decode_header
from email.message import EmailMessage, Message
from email.utils import getaddresses, make_msgid, parseaddr, parsedate_to_datetime
from typing import Any

from google.adk.tools import FunctionTool, ToolContext
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import SessionLocal
from .event_stream import account_events
from .goals import add_goal_activity
from .models import ClientEmailIdentity, EmailAgentActivity, EmailConversation, Goal, MailboxConnection, MailMessage, Node
from .secret_store import decrypt_secret, encrypt_secret


TITAN_IMAP_HOST = "imap.titan.email"
TITAN_IMAP_PORT = 993
TITAN_SMTP_HOST = "smtp.titan.email"
TITAN_SMTP_PORT = 465
logger = logging.getLogger(__name__)
_active_clients: dict[str, imaplib.IMAP4_SSL] = {}
_active_clients_lock = threading.Lock()


@dataclass(frozen=True)
class IncomingMessage:
    uid: int
    message_id: str
    in_reply_to: str
    references: str
    sender: str
    recipients: str
    subject: str
    body: str
    received_at: Any


def connect_titan_mailbox(session: Session, account_id: str, mailbox_email: str, password: str) -> dict[str, object]:
    address = mailbox_email.strip().casefold()
    logger.info("mailbox=titan email=%s connection=starting", address)
    client = _login(address, password)
    try:
        capabilities = _authenticated_capabilities(client)
        logger.info("mailbox=titan email=%s authentication=accepted capabilities=%s", address, ",".join(sorted(capabilities)))
        if "IDLE" not in capabilities:
            logger.error("mailbox=titan email=%s connection=rejected reason=idle_unavailable", address)
            raise RuntimeError("Titan authenticated successfully but this mailbox does not provide live inbox notifications.")
        status, _ = client.select("INBOX", readonly=True)
        if status != "OK":
            logger.error("mailbox=titan email=%s connection=rejected reason=inbox_unavailable status=%s", address, status)
            raise RuntimeError("Titan did not open the inbox.")
        uid_validity = _response_value(client, "UIDVALIDITY")
        uid_next = int(_response_value(client, "UIDNEXT") or "1")
    finally:
        try:
            client.logout()
        except Exception:
            pass
    connection = session.scalar(select(MailboxConnection).where(MailboxConnection.account_id == account_id, MailboxConnection.provider == "titan"))
    if connection:
        previous_validity = connection.uid_validity
        connection.email = address
        connection.encrypted_password = encrypt_secret(password)
        connection.uid_validity = uid_validity
        connection.last_uid = max(connection.last_uid, uid_next - 1) if previous_validity == uid_validity else uid_next - 1
        connection.state = "connected"
        connection.failure = ""
    else:
        connection = MailboxConnection(account_id=account_id, provider="titan", email=address, incoming_host=TITAN_IMAP_HOST, incoming_port=TITAN_IMAP_PORT, outgoing_host=TITAN_SMTP_HOST, outgoing_port=TITAN_SMTP_PORT, encrypted_password=encrypt_secret(password), uid_validity=uid_validity, last_uid=uid_next - 1, state="connected")
        session.add(connection)
    session.commit()
    session.refresh(connection)
    logger.info("mailbox=titan email=%s connection=connected uid_validity=%s last_uid=%s", address, uid_validity, connection.last_uid)
    _publish(connection)
    return mailbox_snapshot(connection)


def mailbox_status(session: Session, account_id: str) -> dict[str, object]:
    connection = session.scalar(select(MailboxConnection).where(MailboxConnection.account_id == account_id, MailboxConnection.provider == "titan"))
    return mailbox_snapshot(connection) if connection else {"connected": False, "provider": "titan", "email": None, "state": "disconnected", "failure": None, "lastUid": 0}


def list_mailbox_threads(session: Session, account_id: str) -> list[dict[str, object]]:
    connection = session.scalar(select(MailboxConnection).where(MailboxConnection.account_id == account_id, MailboxConnection.provider == "titan"))
    if not connection:
        return []
    messages = list(session.scalars(select(MailMessage).where(MailMessage.mailbox_id == connection.id).order_by(MailMessage.created_at)))
    grouped: dict[str, list[MailMessage]] = {}
    for message in messages:
        grouped.setdefault(message.conversation_id or message.id, []).append(message)
    threads: list[dict[str, object]] = []
    for thread_messages in grouped.values():
        latest = thread_messages[-1]
        inbound = next((message for message in thread_messages if message.direction == "inbound"), latest)
        goal = session.get(Goal, latest.goal_id) if latest.goal_id else None
        client_id = latest.client_id or (goal.client_id if goal else None)
        client = session.get(Node, client_id) if client_id else None
        activities = list(session.scalars(select(EmailAgentActivity).where(
            EmailAgentActivity.message_id.in_([message.id for message in thread_messages]),
        ).order_by(EmailAgentActivity.created_at)))
        sender_name, sender_address = parseaddr(inbound.sender)
        threads.append({
            "id": latest.conversation_id or latest.id,
            "clientName": client.name if client else sender_name.strip() or sender_address,
            "customerEmail": sender_address,
            "subject": inbound.subject,
            "preview": latest.body.strip(),
            "updatedAt": latest.received_at or latest.created_at,
            "goalId": latest.goal_id,
            "goalStatus": goal.status if goal else None,
            "clientId": client_id,
            "agentStatus": latest.agent_status,
            "agentAction": latest.agent_action or None,
            "agentSummary": latest.agent_summary or None,
            "attentionRequired": any(message.attention_required for message in thread_messages),
            "agentFailure": latest.agent_failure or None,
            "activities": [{"id": item.id, "kind": item.kind, "summary": item.summary, "createdAt": item.created_at} for item in activities],
            "messages": [{
                "id": message.id,
                "direction": message.direction,
                "sender": message.sender,
                "recipients": message.recipients,
                "body": message.body,
                "sentAt": message.received_at or message.created_at,
            } for message in thread_messages],
        })
    return sorted(threads, key=lambda thread: thread["updatedAt"], reverse=True)


def disconnect_mailbox(session: Session, account_id: str) -> None:
    connection = session.scalar(select(MailboxConnection).where(MailboxConnection.account_id == account_id, MailboxConnection.provider == "titan"))
    if connection:
        session.delete(connection)
        session.commit()
        account_events.publish(account_id, {"type": "mailbox_changed", "state": "disconnected"})


def titan_tools(account_id: str) -> list[FunctionTool]:
    with SessionLocal() as session:
        connected = session.scalar(select(MailboxConnection.id).where(MailboxConnection.account_id == account_id, MailboxConnection.provider == "titan")) is not None
    return [FunctionTool(titan_list_goal_messages), FunctionTool(titan_email_client), FunctionTool(titan_reply_to_customer)] if connected else []


async def titan_list_goal_messages(tool_context: ToolContext) -> dict[str, object]:
    """Read the inbound and outbound Titan email messages attached to the current goal."""
    goal_id = str(tool_context.state.get("goal_id") or "")
    with SessionLocal() as session:
        messages = list(session.scalars(select(MailMessage).where(MailMessage.goal_id == goal_id).order_by(MailMessage.created_at)))
        return {"messages": [{"direction": item.direction, "from": item.sender, "to": item.recipients, "subject": item.subject, "body": item.body, "message_id": item.message_id} for item in messages]}


async def titan_email_client(to: str, subject: str, body: str, tool_context: ToolContext) -> dict[str, object]:
    """Send a new email from Titan to the verified client email for the current goal."""
    account_id = str(tool_context.state.get("account_id") or "")
    goal_id = str(tool_context.state.get("goal_id") or "")
    client_id = str(tool_context.state.get("client_id") or "")
    recipient = parseaddr(to)[1].strip().lower()
    if not recipient or not subject.strip() or not body.strip():
        raise ValueError("A client email, subject, and body are required.")
    with SessionLocal() as session:
        verified = session.scalar(select(ClientEmailIdentity.email).where(
            ClientEmailIdentity.client_id == client_id,
            ClientEmailIdentity.email == recipient,
        ))
        if not verified:
            raise ValueError("The recipient is not a verified email for the current Front Desk client.")
        connection = session.scalar(select(MailboxConnection).where(MailboxConnection.account_id == account_id, MailboxConnection.provider == "titan"))
        if not connection:
            raise RuntimeError("Titan mail is not connected.")
        logger.info("mailbox=titan goal=%s client=%s send=started to=%s subject=%r", goal_id, client_id, recipient, subject.strip())
        message_id = make_msgid(domain=connection.email.split("@", 1)[-1])
        message = EmailMessage()
        message["From"] = connection.email
        message["To"] = recipient
        message["Subject"] = subject.strip()
        message["Message-ID"] = message_id
        message.set_content(body.strip())
        await asyncio.to_thread(_smtp_send, connection, decrypt_secret(connection.encrypted_password), message)
        record = MailMessage(mailbox_id=connection.id, client_id=client_id or None, goal_id=goal_id or None, direction="outbound", message_id=message_id, sender=connection.email, recipients=recipient, subject=subject.strip(), body=body.strip(), agent_status="completed", agent_action="outbound")
        session.add(record)
        session.commit()
        if goal_id:
            add_goal_activity(session, account_id, goal_id, "email_sent", f"Sent an email to {recipient}: {subject.strip()}")
        logger.info("mailbox=titan goal=%s client=%s send=completed to=%s message_id=%s", goal_id, client_id, recipient, message_id)
        return {"status": "sent", "message_id": message_id, "to": recipient, "subject": subject.strip()}


async def titan_reply_to_customer(body: str, tool_context: ToolContext) -> dict[str, object]:
    """Reply from the connected Titan support mailbox in the current goal's customer email thread."""
    account_id = str(tool_context.state.get("account_id") or "")
    goal_id = str(tool_context.state.get("goal_id") or "")
    with SessionLocal() as session:
        connection = session.scalar(select(MailboxConnection).where(MailboxConnection.account_id == account_id, MailboxConnection.provider == "titan"))
        latest = session.scalar(select(MailMessage).where(MailMessage.goal_id == goal_id, MailMessage.direction == "inbound").order_by(MailMessage.created_at.desc()))
        if not connection or not latest:
            raise RuntimeError("The current goal does not have a connected Titan customer email thread.")
        recipient = parseaddr(latest.sender)[1]
        if not recipient:
            raise RuntimeError("The customer email has no reply address.")
        subject = latest.subject if latest.subject.casefold().startswith("re:") else f"Re: {latest.subject}"
        message_id = make_msgid(domain=connection.email.split("@", 1)[-1])
        message = EmailMessage()
        message["From"] = connection.email
        message["To"] = recipient
        message["Subject"] = subject
        message["Message-ID"] = message_id
        message["In-Reply-To"] = latest.message_id
        references = " ".join(filter(None, (latest.references, latest.message_id)))
        message["References"] = references
        message.set_content(body.strip())
        password = decrypt_secret(connection.encrypted_password)
        await asyncio.to_thread(_smtp_send, connection, password, message)
        record = MailMessage(mailbox_id=connection.id, client_id=latest.client_id, conversation_id=latest.conversation_id, goal_id=goal_id, assignment_id=latest.assignment_id, uid=None, direction="outbound", message_id=message_id, in_reply_to=latest.message_id, references=references, sender=connection.email, recipients=recipient, subject=subject, body=body.strip(), agent_status="completed", agent_action="outbound")
        session.add(record)
        session.commit()
        add_goal_activity(session, account_id, goal_id, "email_sent", f"Sent a reply to {recipient}: {subject}")
        return {"status": "sent", "message_id": message_id, "to": recipient, "subject": subject}


class MailboxManager:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}

    async def recover(self) -> None:
        with SessionLocal() as session:
            ids = list(session.scalars(select(MailboxConnection.id)))
        for mailbox_id in ids:
            await self.start(mailbox_id)

    async def start(self, mailbox_id: str) -> None:
        current = self._tasks.get(mailbox_id)
        if current and not current.done():
            return
        task = asyncio.create_task(self._run(mailbox_id), name=f"mailbox-{mailbox_id}")
        self._tasks[mailbox_id] = task
        task.add_done_callback(lambda done: self._tasks.pop(mailbox_id, None) if self._tasks.get(mailbox_id) is done else None)

    async def stop(self, mailbox_id: str) -> None:
        task = self._tasks.pop(mailbox_id, None)
        if task:
            await asyncio.to_thread(_interrupt_mailbox, mailbox_id)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def close(self) -> None:
        tasks = list(self._tasks.values())
        mailbox_ids = list(self._tasks)
        self._tasks.clear()
        await asyncio.gather(*(asyncio.to_thread(_interrupt_mailbox, mailbox_id) for mailbox_id in mailbox_ids))
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run(self, mailbox_id: str) -> None:
        delay = 1
        logger.info("mailbox=%s listener=started", mailbox_id)
        while True:
            try:
                messages = await asyncio.to_thread(_wait_for_mail, mailbox_id)
                delay = 1
                logger.info("mailbox=%s listener=fetched count=%s", mailbox_id, len(messages))
                for message in messages:
                    message_id = _record_incoming(mailbox_id, message)
                    logger.info("mailbox=%s message=stored uid=%s subject=%r stored=%s", mailbox_id, message.uid, message.subject, message_id is not None)
                    if message_id:
                        from .email_agent import email_agent
                        await email_agent.start(message_id)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                if _expected_socket_shutdown(error):
                    logger.info("mailbox=%s listener=interrupted reason=socket_closed", mailbox_id)
                else:
                    _set_failure(mailbox_id, str(error).strip() or error.__class__.__name__)
                    logger.warning("mailbox=%s listener=failed error=%s", mailbox_id, error)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)


mailboxes = MailboxManager()


def _wait_for_mail(mailbox_id: str) -> list[IncomingMessage]:
    with SessionLocal() as session:
        connection = session.get(MailboxConnection, mailbox_id)
        if not connection:
            return []
        address = connection.email
        password = decrypt_secret(connection.encrypted_password)
        last_uid = connection.last_uid
        expected_validity = connection.uid_validity
    client = _login(address, password)
    with _active_clients_lock:
        _active_clients[mailbox_id] = client
    try:
        if "IDLE" not in _authenticated_capabilities(client):
            raise RuntimeError("Titan stopped providing live inbox notifications.")
        if client.select("INBOX", readonly=True)[0] != "OK":
            raise RuntimeError("Titan did not open the inbox.")
        validity = _response_value(client, "UIDVALIDITY")
        if validity != expected_validity:
            raise RuntimeError("Titan changed the inbox identity. Reconnect the mailbox before processing mail.")
        _set_connected(mailbox_id)
        messages = _fetch_after(client, last_uid)
        if messages:
            return messages
        logger.info("mailbox=%s listener=idle last_uid=%s", mailbox_id, last_uid)
        with client.idle(duration=29 * 60) as idler:
            for response in idler:
                if response and _imap_event_name(response[0]) == "EXISTS":
                    logger.info("mailbox=%s listener=notified event=EXISTS", mailbox_id)
                    break
        return _fetch_after(client, last_uid)
    finally:
        with _active_clients_lock:
            if _active_clients.get(mailbox_id) is client:
                _active_clients.pop(mailbox_id, None)
        try:
            client.logout()
        except Exception:
            pass


def _fetch_after(client: imaplib.IMAP4_SSL, last_uid: int) -> list[IncomingMessage]:
    status, data = client.uid("search", None, f"UID {last_uid + 1}:*")
    if status != "OK" or not data or not data[0]:
        return []
    results: list[IncomingMessage] = []
    for raw_uid in data[0].split():
        uid = int(raw_uid)
        if uid <= last_uid:
            continue
        status, payload = client.uid("fetch", raw_uid, "(RFC822)")
        if status != "OK" or not payload or not isinstance(payload[0], tuple):
            raise RuntimeError(f"Titan could not fetch inbox message UID {uid}.")
        results.append(_parse_message(uid, payload[0][1]))
    return results


def _parse_message(uid: int, raw: bytes) -> IncomingMessage:
    message = email.message_from_bytes(raw)
    message_id = str(message.get("Message-ID") or make_msgid(domain="titan.local")).strip()
    received_at = parsedate_to_datetime(str(message.get("Date"))) if message.get("Date") else None
    return IncomingMessage(uid, message_id, str(message.get("In-Reply-To") or "").strip(), str(message.get("References") or "").strip(), str(message.get("From") or ""), ", ".join(address for _, address in getaddresses(message.get_all("To", []))), _decoded_header(message.get("Subject")), _message_body(message), received_at)


def _record_incoming(mailbox_id: str, incoming: IncomingMessage) -> str | None:
    with SessionLocal() as session:
        connection = session.get(MailboxConnection, mailbox_id)
        if not connection:
            return None
        existing = session.scalar(select(MailMessage).where(MailMessage.mailbox_id == mailbox_id, MailMessage.message_id == incoming.message_id))
        if existing:
            if incoming.uid > connection.last_uid:
                connection.last_uid = incoming.uid
                session.commit()
            return None
        record = MailMessage(mailbox_id=mailbox_id, uid=incoming.uid, direction="inbound", message_id=incoming.message_id, in_reply_to=incoming.in_reply_to, references=incoming.references, sender=incoming.sender, recipients=incoming.recipients, subject=incoming.subject, body=incoming.body, received_at=incoming.received_at, agent_status="queued")
        session.add(record)
        connection.last_uid = max(connection.last_uid, incoming.uid)
        connection.state = "connected"
        connection.failure = ""
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            return None
        session.commit()
        _publish(connection)
        return record.id


def _login(address: str, password: str) -> imaplib.IMAP4_SSL:
    try:
        client = imaplib.IMAP4_SSL(TITAN_IMAP_HOST, TITAN_IMAP_PORT, ssl_context=ssl.create_default_context())
    except (OSError, ssl.SSLError) as error:
        logger.exception("mailbox=titan email=%s connection=failed stage=tls", address)
        raise RuntimeError(f"Titan IMAP could not be reached: {_safe_imap_error(error)}") from None
    try:
        client.login(address, password)
        return client
    except imaplib.IMAP4.error as error:
        detail = _safe_imap_error(error)
        logger.error("mailbox=titan email=%s connection=failed stage=authentication detail=%s", address, detail)
        try:
            client.logout()
        except Exception:
            pass
        raise RuntimeError(f"Titan rejected the mailbox login: {detail}") from None
    except (OSError, ssl.SSLError) as error:
        detail = _safe_imap_error(error)
        logger.exception("mailbox=titan email=%s connection=failed stage=authentication_transport", address)
        try:
            client.shutdown()
        except Exception:
            pass
        raise RuntimeError(f"Titan closed the IMAP connection during login: {detail}") from None


def _safe_imap_error(error: BaseException) -> str:
    detail = str(error).strip().replace("\r", " ").replace("\n", " ")
    return detail[:300] or type(error).__name__


def _expected_socket_shutdown(error: BaseException) -> bool:
    detail = str(error).casefold()
    return isinstance(error, OSError) and error.errno == 9 or "bad file descriptor" in detail or "socket error: eof" in detail


def _imap_event_name(value: bytes | str) -> str:
    return value.decode("ascii", errors="replace").upper() if isinstance(value, bytes) else value.upper()


def _authenticated_capabilities(client: imaplib.IMAP4_SSL) -> set[str]:
    status, values = client.capability()
    if status != "OK":
        raise RuntimeError("Titan authenticated successfully but did not return its mailbox capabilities.")
    capabilities: set[str] = set()
    for value in values:
        text = value.decode("ascii", errors="replace") if isinstance(value, bytes) else value
        capabilities.update(text.upper().split())
    client.capabilities = tuple(sorted(capabilities))
    return capabilities


def _smtp_send(connection: MailboxConnection, password: str, message: EmailMessage) -> None:
    with smtplib.SMTP_SSL(connection.outgoing_host, connection.outgoing_port, context=ssl.create_default_context()) as client:
        client.login(connection.email, password)
        client.send_message(message)


def _interrupt_mailbox(mailbox_id: str) -> None:
    with _active_clients_lock:
        client = _active_clients.pop(mailbox_id, None)
    if client:
        try:
            client.shutdown()
        except Exception:
            pass


def _response_value(client: imaplib.IMAP4_SSL, name: str) -> str:
    _, values = client.response(name)
    if not values or not values[0]:
        return ""
    value = values[0].decode() if isinstance(values[0], bytes) else str(values[0])
    return value.split()[-1]


def _decoded_header(value: str | None) -> str:
    return "".join(part.decode(charset or "utf-8", errors="replace") if isinstance(part, bytes) else part for part, charset in decode_header(value or ""))


def _message_body(message: Message) -> str:
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition") or "").casefold():
                return _decoded_payload(part)
        return ""
    return _decoded_payload(message)


def _decoded_payload(message: Message) -> str:
    payload = message.get_payload(decode=True)
    if not isinstance(payload, bytes):
        return str(payload or "")
    return payload.decode(message.get_content_charset() or "utf-8", errors="replace").strip()


def _set_failure(mailbox_id: str, message: str) -> None:
    with SessionLocal() as session:
        connection = session.get(MailboxConnection, mailbox_id)
        if connection:
            connection.state = "failed"
            connection.failure = message
            session.commit()
            _publish(connection)


def _set_connected(mailbox_id: str) -> None:
    with SessionLocal() as session:
        connection = session.get(MailboxConnection, mailbox_id)
        if connection and (connection.state != "connected" or connection.failure):
            connection.state = "connected"
            connection.failure = ""
            session.commit()
            _publish(connection)


def _publish(connection: MailboxConnection) -> None:
    account_events.publish(connection.account_id, {"type": "mailbox_changed", "state": connection.state})


def mailbox_snapshot(connection: MailboxConnection) -> dict[str, object]:
    return {"connected": True, "provider": connection.provider, "email": connection.email, "state": connection.state, "failure": connection.failure or None, "lastUid": connection.last_uid}
