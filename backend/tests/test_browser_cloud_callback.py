"""Exercise the packaged MCP binary, not a mocked Playwright connection."""

import asyncio
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from tools.browser_use.cloud_relay import validate_endpoint


def test_packaged_mcp_uses_cloud_callback_without_launching_chrome() -> None:
    requests = []

    class Callback(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append({
                "account": self.headers.get("X-Front-Desk-Account"),
                "secret": self.headers.get("X-Front-Desk-Internal-Secret"),
                "body": json.loads(self.rfile.read(int(self.headers["Content-Length"]))),
            })
            # Stop before opening any browser or live extension session.
            self.send_response(409)
            self.end_headers()
            self.wfile.write(b"Cloud callback test rejected the connection intentionally.")

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Callback)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    root = Path(__file__).resolve().parents[2]
    binary = os.environ.get("FRONT_DESK_TEST_PLAYWRIGHT_BINARY", str(root / "node_modules/.bin/playwright-mcp"))
    environment = dict(os.environ)
    environment.update({
        "FRONT_DESK_BROWSER_CONNECT_URL": f"http://127.0.0.1:{server.server_port}/connect",
        "FRONT_DESK_BROWSER_ACCOUNT_ID": "cloud-callback-test-account",
        "FRONT_DESK_INTERNAL_SECRET": "cloud-callback-test-secret",
    })

    async def exercise() -> None:
        async with stdio_client(StdioServerParameters(command=binary, args=["--extension"], env=environment)) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                result = await session.call_tool("browser_tabs", {"action": "list"})
                assert result.isError
                assert "Cloud browser connection rejected: 409" in " ".join(getattr(item, "text", "") for item in result.content)

    try:
        asyncio.run(asyncio.wait_for(exercise(), timeout=20))
        assert len(requests) == 1
        assert requests[0]["account"] == "cloud-callback-test-account"
        assert requests[0]["secret"] == "cloud-callback-test-secret"
        validate_endpoint(requests[0]["body"]["endpoint"])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
