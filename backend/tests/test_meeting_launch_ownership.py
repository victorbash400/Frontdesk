import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from meetings import browser_worker


def test_meeting_launch_has_one_runtime_owner_and_releases():
    async def exercise():
        meeting = SimpleNamespace(id="meeting-ownership-test")
        entered = asyncio.Event()
        release = asyncio.Event()

        async def launch(*_, **__):
            entered.set()
            await release.wait()
            return {"state": "browser_opened"}

        with patch.object(browser_worker, "_join_meeting", side_effect=launch):
            first = asyncio.create_task(browser_worker.join_meeting(meeting))
            await entered.wait()
            try:
                await browser_worker.join_meeting(meeting)
            except ValueError as error:
                assert str(error) == "This meeting is already being launched."
            else:
                raise AssertionError("A duplicate meeting launch was accepted.")
            release.set()
            assert await first == {"state": "browser_opened"}
            release.clear()
            second = asyncio.create_task(browser_worker.join_meeting(meeting))
            await entered.wait()
            release.set()
            assert await second == {"state": "browser_opened"}

    asyncio.run(exercise())
