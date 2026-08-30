import asyncio
import logging
from contextlib import ExitStack
from uuid import uuid4

from google.genai import types

from agents.email_agent import create_email_agent_runner
from app.database import SessionLocal
from app.event_stream import account_events
from app.models import EmailAgentActivity, MailMessage
from app.runtime_lock import runtime_lock
from app.session_store import sessions


logger = logging.getLogger(__name__)
runner = create_email_agent_runner(sessions)


class EmailAgentManager:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}

    async def recover(self) -> None:
        with SessionLocal() as session:
            pending = session.query(MailMessage).filter(MailMessage.direction == "inbound", MailMessage.agent_status.in_(("queued", "processing"))).all()
            message_ids = [item.id for item in pending]
        for message_id in message_ids:
            await self.start(message_id)

    async def start(self, message_id: str, instruction: str = "Process the newly received email now.", fresh_session: bool = False) -> bool:
        current = self._tasks.get(message_id)
        if current and not current.done():
            return False
        lease = ExitStack()
        if not lease.enter_context(runtime_lock("email-message", message_id)):
            lease.close()
            return False
        try:
            task = asyncio.create_task(self._run(message_id, instruction, fresh_session), name=f"email-agent-{message_id}")
        except BaseException:
            lease.close()
            raise
        self._tasks[message_id] = task
        def finished(done):
            lease.close()
            if self._tasks.get(message_id) is done:
                self._tasks.pop(message_id, None)
        task.add_done_callback(finished)
        return True

    async def retry(self, account_id: str, message_id: str) -> dict[str, str]:
        current = self._tasks.get(message_id)
        if current and not current.done():
            return {"status": "processing", "message_id": message_id}
        with SessionLocal() as session:
            message = session.get(MailMessage, message_id)
            if not message or message.direction != "inbound":
                raise RuntimeError("The customer email was not found.")
            from app.models import MailboxConnection
            mailbox = session.get(MailboxConnection, message.mailbox_id)
            if not mailbox or mailbox.account_id != account_id:
                raise RuntimeError("The customer email was not found.")
            message.agent_status = "queued"
            message.agent_action = ""
            message.agent_failure = ""
            message.attention_required = False
            session.commit()
            account_events.publish(account_id, {"type": "mailbox_changed", "message_id": message.id})
        await self.start(message_id, "Re-read this email and its current persisted context. Check how far the linked customer work has progressed, correct any failed or incomplete routing decision, and continue the same case without duplicating its client or goal.", fresh_session=True)
        return {"status": "queued", "message_id": message_id}

    async def close(self) -> None:
        tasks = list(self._tasks.values())
        self._tasks.clear()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run(self, message_id: str, instruction: str, fresh_session: bool) -> None:
        account_id = self._begin(message_id)
        if not account_id:
            return
        session_id = f"email-{message_id}-{uuid4().hex}" if fresh_session else f"email-{message_id}"
        try:
            existing = await sessions.get_session(app_name=runner.app_name, user_id=account_id, session_id=session_id)
            if not existing:
                await sessions.create_session(app_name=runner.app_name, user_id=account_id, session_id=session_id, state={"account_id": account_id, "email_message_id": message_id})
            async for event in runner.run_async(
                user_id=account_id,
                session_id=session_id,
                new_message=types.Content(role="user", parts=[types.Part.from_text(text=instruction)]),
            ):
                if event.error_message:
                    raise RuntimeError(event.error_message)
            await self._dispatch(message_id, account_id)
            self._ensure_completed(message_id, account_id)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._fail(message_id, account_id, str(error).strip() or type(error).__name__)
            logger.exception("email_agent message=%s status=failed", message_id)

    def _begin(self, message_id: str) -> str:
        with SessionLocal() as session:
            message = session.get(MailMessage, message_id)
            if not message or message.direction != "inbound" or message.agent_status == "completed":
                return ""
            from app.models import MailboxConnection
            mailbox = session.get(MailboxConnection, message.mailbox_id)
            account_id = mailbox.account_id if mailbox else ""
            if not account_id:
                return ""
            message.agent_status = "processing"
            message.agent_failure = ""
            session.add(EmailAgentActivity(mailbox_id=message.mailbox_id, message_id=message.id, kind="started", summary="Email Agent started reading the message."))
            session.commit()
            account_events.publish(account_id, {"type": "mailbox_changed", "message_id": message.id})
            return account_id

    async def _dispatch(self, message_id: str, account_id: str) -> None:
        with SessionLocal() as session:
            message = session.get(MailMessage, message_id)
            if not message or message.agent_status != "completed" or not message.goal_id or message.agent_action not in {"resume_goal", "create_goal"}:
                return
            instruction = ""
            if message.agent_action == "resume_goal":
                assignment_title = ""
                if message.assignment_id:
                    from app.models import GoalAssignment
                    assignment = session.get(GoalAssignment, message.assignment_id)
                    assignment_title = f" Continue task {assignment.id}: {assignment.title}." if assignment else ""
                instruction = f"Resume this customer case using the newly received email.{assignment_title}\nFrom: {message.sender}\nSubject: {message.subject}\nMessage:\n{message.body}"
            goal_id = message.goal_id
        from app.goal_tasks import goal_tasks
        await goal_tasks.start(account_id, goal_id, instruction or None)

    def _ensure_completed(self, message_id: str, account_id: str) -> None:
        with SessionLocal() as session:
            message = session.get(MailMessage, message_id)
            if not message or message.agent_status == "completed":
                return
            self._fail(message_id, account_id, "The Email Agent finished without recording an action.")

    def _fail(self, message_id: str, account_id: str, error: str) -> None:
        with SessionLocal() as session:
            message = session.get(MailMessage, message_id)
            if not message:
                return
            message.agent_status = "failed"
            message.agent_failure = error
            message.attention_required = True
            if message.client_id:
                from app.models import Node
                client = session.get(Node, message.client_id)
                if client:
                    client.needs_attention = True
            session.add(EmailAgentActivity(mailbox_id=message.mailbox_id, message_id=message.id, client_id=message.client_id, kind="failed", summary=f"Email Agent needs attention: {error}"))
            session.commit()
            account_events.publish(account_id, {"type": "mailbox_changed", "message_id": message.id})


email_agent = EmailAgentManager()
