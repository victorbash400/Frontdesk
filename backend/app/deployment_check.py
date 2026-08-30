"""One-shot cloud preflight. Does not create accounts, goals, or other user records."""

import asyncio
import json
from uuid import uuid4

from sqlalchemy import text

from app.database import engine
from app.event_stream import AccountEventBroker
from app.runtime_lock import runtime_lock
from tools.browser_use.relay_probe import check as check_browser_relay


async def check() -> dict[str, str]:
    if engine.dialect.name != "postgresql":
        raise RuntimeError("Cloud deployment requires PostgreSQL, not a local database.")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT 1")) == 1
    identity = str(uuid4())
    with runtime_lock("deployment-preflight", identity) as owned:
        assert owned, "Could not acquire the runtime lock."
        with runtime_lock("deployment-preflight", identity) as duplicate:
            assert not duplicate, "Two database connections acquired the same runtime identity."
    with runtime_lock("deployment-preflight", identity) as released:
        assert released, "Runtime ownership was not released."
    receiver, sender = AccountEventBroker(), AccountEventBroker()
    ready = asyncio.Event()
    events = receiver.events(identity, ready).__aiter__()
    incoming = asyncio.create_task(anext(events))
    try:
        async with asyncio.timeout(15):
            await ready.wait()
            sender.publish(identity, {"type": "deployment_probe", "nonce": identity})
            assert await incoming == {"type": "deployment_probe", "nonce": identity}
    finally:
        incoming.cancel()
        await asyncio.gather(incoming, return_exceptions=True)
        await events.aclose()
    browser_relay = await check_browser_relay()
    return {"database": "connected", "exclusive_ownership": "verified", "cross_connection_notifications": "verified", "two_process_browser_relay": browser_relay}


if __name__ == "__main__":
    print(json.dumps(asyncio.run(check())))
