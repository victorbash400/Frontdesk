"""Own the private Playwright socket for one explicitly identified connection."""

import asyncio
import logging

from websockets.asyncio.client import connect

from .relay_channel import MAX_FRAME_BYTES, RelayChannel, until_disconnected


logger = logging.getLogger("uvicorn.error")


class BrowserRelayWorkers:
    def __init__(self):
        self.tasks: dict[str, asyncio.Task] = {}

    async def start(self, connection_id: str, endpoint: str, finish) -> None:
        ready = asyncio.Event()

        async def run():
            try:
                channel = RelayChannel(connection_id, "owner")
                async with channel.open() as consumer:
                    ready.set()

                    async def bridge():
                        async with asyncio.timeout(120):
                            await channel.connected.wait()
                        async with connect(endpoint, max_size=MAX_FRAME_BYTES, open_timeout=10) as upstream:
                            channel.announce_connected()

                            async def to_playwright():
                                while True:
                                    await upstream.send(await channel.receive())

                            async def to_extension():
                                async for message in upstream:
                                    await channel.send(message.decode() if isinstance(message, bytes) else message)

                            await until_disconnected(to_playwright(), to_extension())

                    await until_disconnected(consumer, bridge())
            except ConnectionError as error:
                logger.info("browser=%s owner=disconnected detail=%s", connection_id, error)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("browser=%s owner=failed", connection_id)
            finally:
                finish(connection_id)

        task = asyncio.create_task(run())
        self.tasks[connection_id] = task
        task.add_done_callback(lambda _: self.tasks.pop(connection_id, None))
        readiness = asyncio.create_task(ready.wait())
        try:
            async with asyncio.timeout(15):
                await asyncio.wait({task, readiness}, return_when=asyncio.FIRST_COMPLETED)
                if task.done():
                    raise RuntimeError("Browser relay owner could not initialize.")
                await readiness
        except BaseException:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise
        finally:
            readiness.cancel()
            await asyncio.gather(readiness, return_exceptions=True)

    async def close(self):
        tasks = tuple(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


browser_relay_workers = BrowserRelayWorkers()
