import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.postgres_events import PostgresEvents


def test_subscribers_share_connection_and_remain_account_scoped():
    async def exercise():
        incoming = asyncio.Queue()

        async def notifications():
            while True:
                yield await incoming.get()

        connection = SimpleNamespace(execute=AsyncMock(), close=AsyncMock(), notifies=notifications)
        broker = PostgresEvents("front_desk_events")
        ready_events = [asyncio.Event() for _ in range(3)]
        streams = [broker.events("postgresql://test", account, ready) for account, ready in zip(["a", "a", "b"], ready_events)]
        with patch("app.postgres_events.psycopg.AsyncConnection.connect", new=AsyncMock(return_value=connection)) as connect:
            tasks = [asyncio.create_task(anext(stream)) for stream in streams]
            await asyncio.gather(*(ready.wait() for ready in ready_events))
            connect.assert_awaited_once()
            incoming.put_nowait(SimpleNamespace(payload=json.dumps({"account_id": "a", "event": {"type": "changed"}})))
            assert await tasks[0] == await tasks[1] == {"type": "changed"}
            assert not tasks[2].done()
            await streams[0].aclose()
            connection.close.assert_not_awaited()
            await streams[1].aclose()
            tasks[2].cancel()
            await asyncio.gather(tasks[2], return_exceptions=True)
            await streams[2].aclose()
            connection.close.assert_awaited_once()
            assert not broker.listeners

    asyncio.run(exercise())


def test_listener_failure_reaches_every_subscriber():
    async def exercise():
        broker = PostgresEvents("front_desk_events")
        with patch("app.postgres_events.psycopg.AsyncConnection.connect", new=AsyncMock(side_effect=ConnectionError("database unavailable"))):
            streams = [broker.events("postgresql://test", "a", None) for _ in range(2)]
            results = await asyncio.gather(*(anext(stream) for stream in streams), return_exceptions=True)
            assert all(isinstance(result, ConnectionError) for result in results)
            assert not broker.listeners

    asyncio.run(exercise())


def test_late_subscriber_receives_failed_listener_error():
    async def exercise():
        incoming = asyncio.Queue()
        disconnect = asyncio.Event()

        async def notifications():
            yield await incoming.get()
            await disconnect.wait()
            raise ConnectionError("listener disconnected")

        connection = SimpleNamespace(execute=AsyncMock(), close=AsyncMock(), notifies=notifications)
        broker = PostgresEvents("front_desk_events")
        with patch("app.postgres_events.psycopg.AsyncConnection.connect", new=AsyncMock(return_value=connection)):
            stream = broker.events("postgresql://test", "a", None)
            pending = asyncio.create_task(anext(stream))
            incoming.put_nowait(SimpleNamespace(payload=json.dumps({"account_id": "a", "event": {"type": "changed"}})))
            assert await pending == {"type": "changed"}
            disconnect.set()
            await broker.listeners[asyncio.get_running_loop()].task
            late = broker.events("postgresql://test", "a", None)
            result = await asyncio.gather(anext(late), return_exceptions=True)
            assert isinstance(result[0], ConnectionError)
            await stream.aclose()
            assert not broker.listeners

    asyncio.run(exercise())
