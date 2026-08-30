import asyncio
from unittest.mock import patch

from app.email_agent import EmailAgentManager
from app.mailboxes import MailboxManager


def test_email_worker_has_one_owner_and_releases_after_cancel():
    async def exercise():
        async def stalled(*_):
            await asyncio.Event().wait()
        first, second = EmailAgentManager(), EmailAgentManager()
        with patch.object(first, "_run", side_effect=stalled):
            assert await first.start("email-owner-test")
            assert not await second.start("email-owner-test")
            await first.close()
        with patch.object(second, "_run", side_effect=stalled):
            assert await second.start("email-owner-test")
            await second.close()
    asyncio.run(exercise())


def test_mailbox_listener_has_one_owner_and_releases_after_cancel():
    async def exercise():
        async def stalled(*_):
            await asyncio.Event().wait()
        first, second = MailboxManager(), MailboxManager()
        with patch.object(first, "_run", side_effect=stalled):
            assert await first.start("mailbox-owner-test")
            assert not await second.start("mailbox-owner-test")
            await first.close()
        with patch.object(second, "_run", side_effect=stalled):
            assert await second.start("mailbox-owner-test")
            await second.close()
    asyncio.run(exercise())
