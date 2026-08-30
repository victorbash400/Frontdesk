import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.database import SessionLocal, initialize_database
from tools.browser_use.relay_channel import BrowserRelayFrame, RelayChannel, until_disconnected


def test_bidirectional_frames_are_ordered_isolated_and_removed():
    initialize_database()

    async def exercise():
        identity = uuid4().hex
        left, right = RelayChannel(identity, "owner"), RelayChannel(identity, "extension")
        unrelated = RelayChannel(uuid4().hex, "owner")
        async with left.open(), right.open(), unrelated.open():
            for index in range(4):
                one, two = f"first-{index}", f"second-{index}"
                await asyncio.gather(left.send(one), right.send(two))
                assert await right.receive() == one
                assert await left.receive() == two
                assert unrelated.incoming.empty()
            with SessionLocal() as database:
                assert not database.scalars(select(BrowserRelayFrame).where(BrowserRelayFrame.connection_id == identity)).all()

    asyncio.run(exercise())


def test_peer_close_ends_pending_receive_and_cleans_expired_frames():
    initialize_database()
    expired_id = str(uuid4())
    with SessionLocal() as database:
        database.add(BrowserRelayFrame(id=expired_id, connection_id="expired", recipient="owner", payload="old", expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
        database.commit()

    async def exercise():
        identity = uuid4().hex
        left, right = RelayChannel(identity, "owner"), RelayChannel(identity, "extension")
        async with left.open() as consumer:
            async with right.open():
                pass
            with pytest.raises(ConnectionError, match="closed"):
                await until_disconnected(consumer, left.receive())
        with SessionLocal() as database:
            assert database.get(BrowserRelayFrame, expired_id) is None

    asyncio.run(exercise())
