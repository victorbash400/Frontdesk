import asyncio
import threading
from unittest.mock import patch
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from websockets.sync.server import serve

from app.main import app
from app.database import SessionLocal
from tools.browser_use.cloud_relay import BrowserRelayConnection, validate_endpoint
from tools.browser_use.playwright import create_playwright_toolset


@pytest.mark.parametrize("url", [
    "ws://example.com:1234/extension/11111111-1111-1111-1111-111111111111",
    "http://127.0.0.1:1234/extension/11111111-1111-1111-1111-111111111111",
    "ws://127.0.0.1:1234/admin",
    "ws://user@127.0.0.1:1234/extension/11111111-1111-1111-1111-111111111111",
])
def test_private_endpoint_rejects_unrelated_services(url: str) -> None:
    with pytest.raises(ValueError):
        validate_endpoint(url)


def test_cloud_browser_registration_is_authenticated_and_account_scoped() -> None:
    with TestClient(app) as client:
        account = client.post("/accounts", json={"name": "Cloud Browser", "email": "cloud-browser@example.test", "password": "browser-test-password"}).json()
        body = {"endpoint": "ws://127.0.0.1:45678/extension/11111111-1111-1111-1111-111111111111"}
        assert client.post("/internal/browser/connections", json=body).status_code == 401
        with patch("tools.browser_use.cloud_relay.account_events.publish") as publish:
            response = client.post("/internal/browser/connections", json=body, headers={
                "X-Front-Desk-Account": account["id"], "X-Front-Desk-Internal-Secret": "test-internal-secret",
            })
        assert response.status_code == 200
        assert publish.call_args.args[0] == account["id"]
        event = publish.call_args.args[1]
        assert event["type"] == "browser_connection_requested"
        assert "/api/browser/relay/" in event["relay_url"]
        with SessionLocal() as session:
            record = session.query(BrowserRelayConnection).filter_by(account_id=account["id"]).one()
            assert record.local_endpoint == body["endpoint"]
            assert record.id not in event["relay_url"]


def test_cloud_browser_does_not_require_local_chrome_profile_or_token() -> None:
    from app.config import Settings
    settings = Settings(browser_cloud_relay=True, playwright_extension_token="", playwright_profile_directory="")
    with patch("tools.browser_use.playwright.get_settings", return_value=settings):
        with pytest.raises(RuntimeError, match="account identity"):
            create_playwright_toolset()
        toolset = create_playwright_toolset("test-account")
        assert toolset is not None
        asyncio.run(toolset.close())


@pytest.mark.parametrize("other_instance", [False, True])
def test_cloud_relay_transports_messages_and_rejects_reused_ticket(other_instance) -> None:
    def echo(connection):
        for message in connection:
            connection.send(message)

    with serve(echo, "127.0.0.1", 0) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with TestClient(app) as client:
                account = client.post("/accounts", json={"name": "Relay Transport", "email": f"transport-{other_instance}@example.test", "password": "browser-test-password"}).json()
                port = server.socket.getsockname()[1]
                with patch("tools.browser_use.cloud_relay.account_events.publish") as publish:
                    response = client.post("/internal/browser/connections", json={
                        "endpoint": f"ws://127.0.0.1:{port}/extension/11111111-1111-1111-1111-111111111111",
                    }, headers={"X-Front-Desk-Account": account["id"], "X-Front-Desk-Internal-Secret": "test-internal-secret"})
                assert response.status_code == 200
                path = urlparse(publish.call_args.args[1]["relay_url"]).path
                from tools.browser_use.cloud_relay import INSTANCE_ID
                with patch("tools.browser_use.cloud_relay.INSTANCE_ID", "different-ingress" if other_instance else INSTANCE_ID):
                    with client.websocket_connect(path) as socket:
                        for message in ['{"id":1,"method":"extension.initialized","params":[]}', "large frame " * 10000]:
                            socket.send_text(message)
                            assert socket.receive_text() == message
                with pytest.raises(WebSocketDisconnect):
                    with client.websocket_connect(path):
                        pass
        finally:
            server.shutdown()
            thread.join(timeout=5)
