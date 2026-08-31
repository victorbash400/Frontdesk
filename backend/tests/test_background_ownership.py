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


def test_mailbox_listener_has_one_owner_and_hands_over_after_cancel():
    async def exercise():
        listening: list[str] = []

        async def stalled(mailbox_id):
            listening.append(mailbox_id)
            try:
                await asyncio.Event().wait()
            finally:
                listening.remove(mailbox_id)

        first, second = MailboxManager(), MailboxManager()
        with patch.object(first, "_listen", side_effect=stalled), patch.object(second, "_listen", side_effect=stalled):
            with patch("app.mailboxes.OWNERSHIP_RETRY_SECONDS", 0.01):
                assert await first.start("mailbox-owner-test")
                assert await second.start("mailbox-owner-test")
                await asyncio.sleep(0.05)
                # Both listeners are scheduled, but only the owner reaches the mailbox.
                assert listening == ["mailbox-owner-test"]
                await first.close()
                # The standby reclaims ownership instead of leaving the mailbox unattended.
                await asyncio.sleep(0.05)
                assert listening == ["mailbox-owner-test"]
                await second.close()
        assert listening == []
    asyncio.run(exercise())
