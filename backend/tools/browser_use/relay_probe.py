"""One-shot, two-process cloud relay check without customer data or browser tabs."""

import asyncio
import sys
from uuid import uuid4

from sqlalchemy import select

from app.database import SessionLocal, engine
from .relay_channel import BrowserRelayFrame, RelayChannel, until_disconnected


async def worker(identity: str):
    channel = RelayChannel(identity, "owner")
    async with channel.open() as consumer:
        print("ready", flush=True)

        async def echo():
            for _ in range(3):
                await channel.send(await channel.receive())

        await until_disconnected(consumer, echo())


async def check():
    if engine.dialect.name != "postgresql":
        raise RuntimeError("The two-process relay check requires PostgreSQL.")
    BrowserRelayFrame.__table__.create(engine, checkfirst=True)
    identity = uuid4().hex
    channel = RelayChannel(identity, "extension")
    async with channel.open() as consumer:
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "tools.browser_use.relay_probe", identity,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            async with asyncio.timeout(90):
                assert await process.stdout.readline() == b"ready\n", "Relay subprocess failed to start."
                for payload in ['{"method":"initialize"}', "browser-frame" * 100000, "final"]:
                    await channel.send(payload)
                    received = asyncio.create_task(channel.receive())
                    done, _ = await asyncio.wait({consumer, received}, return_when=asyncio.FIRST_COMPLETED)
                    if consumer in done and received not in done:
                        consumer.result()
                    assert await received == payload
                await process.wait()
                assert process.returncode == 0, (await process.stderr.read()).decode()
        finally:
            if process.returncode is None:
                process.terminate()
                await process.wait()
    with SessionLocal() as database:
        assert not database.scalars(select(BrowserRelayFrame).where(BrowserRelayFrame.connection_id == identity)).all()
    return "verified"


if __name__ == "__main__":
    asyncio.run(worker(sys.argv[1]))
