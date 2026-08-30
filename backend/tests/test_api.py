import asyncio
import base64
import json
from email import message_from_bytes
from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.event_stream import AccountEventBroker
from app.goal_tasks import GoalTaskManager, WORKER_INSTRUCTION
from app.goals import create_notification
from app.models import GitHubRepositoryAccess, Goal, GoalAssignment, GoalAutomation, GoalBrowserPreview, MailboxConnection, MailMessage, OAuthConnection, PluginInstallation
from app.google_oauth import connection_status
from app.skills import list_skills
from agents.goal_planner import GoalPlan, GoalTaskOperation, PLANNER_INSTRUCTION
from agents.goals_chat_agent import create_goals_chat_app
from app import google_oauth
from app import email_agent as email_agent_service
from app import mailboxes as mailbox_service
from app.voice import VOICE_MODEL, VOICE_TOOLS, verify_voice_ticket
from tools import workspace
from tools.browser_use import playwright as playwright_browser
from tools.goal_control import complete_goal
from tools.client_context import list_clients, read_client_profile
from tools.goal_tool_registry import GoalToolRegistry
from tools.tool_failures import begin_single_tool, finish_single_tool
from tools.supervisor_tools import execute_client_tool


def create_test_assignment(goal_id: str, instruction: str) -> str:
    with SessionLocal() as session:
        assignment = GoalAssignment(goal_id=goal_id, instruction=instruction, status="queued")
        session.add(assignment)
        session.commit()
        return assignment.id


def test_google_oauth_attempt_survives_sessions_and_is_single_use() -> None:
    from app.oauth_attempts import consume_google_attempt, store_google_attempt
    with TestClient(app) as client:
        account = create_account(client, "cloud-oauth@example.com", "Cloud OAuth")
        store_google_attempt("cloud-oauth-state", account["id"], "verifier")
        with SessionLocal() as database:
            assert consume_google_attempt(database, "cloud-oauth-state") == (account["id"], "verifier")
        with SessionLocal() as database:
            try:
                consume_google_attempt(database, "cloud-oauth-state")
            except ValueError as error:
                assert "expired or is invalid" in str(error)
            else:
                raise AssertionError("OAuth state was consumed twice")


def test_google_oauth_uses_public_api_origin() -> None:
    from urllib.parse import parse_qs, urlparse
    from app.config import Settings
    from app import mcp_oauth
    configured = Settings(google_client_id="cloud-client", google_client_secret="cloud-secret", google_client_credentials_file="", public_api_url="https://api.example.test/")
    with TestClient(app) as client:
        account = create_account(client, "cloud-callback@example.com", "Cloud Callback")
        with patch.object(google_oauth, "get_settings", return_value=configured):
            query = parse_qs(urlparse(google_oauth.begin_connection(account["id"])).query)
            assert query["redirect_uri"] == ["https://api.example.test/oauth/google/callback"]
        with patch.object(mcp_oauth, "get_settings", return_value=configured):
            assert mcp_oauth.callback_uri() == "https://api.example.test/oauth/mcp/callback"


def test_client_folder_lifecycle() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}

        account = create_account(client, "aster@example.com", "Aster")
        headers = account_headers(account["id"])
        created = client.post("/api/nodes", headers=headers, json={"name": "Aster Bakery", "kind": "client"})
        assert created.status_code == 201
        client_id = created.json()["id"]

        folder = client.post("/api/nodes", headers=headers, json={"name": "Calls", "kind": "folder", "parent_id": client_id})
        assert folder.status_code == 201

        listed = client.get("/api/nodes", headers=headers, params={"parent_id": client_id})
        assert [item["name"] for item in listed.json()] == ["Calls"]

        renamed = client.patch(f"/api/nodes/{client_id}", headers=headers, json={"name": "Aster"})
        assert renamed.status_code == 200
        assert renamed.json()["name"] == "Aster"

        trashed = client.post(f"/api/nodes/{client_id}/trash", headers=headers)
        assert trashed.status_code == 200
        assert trashed.json()["trashed_at"] is not None


def test_filesystem_sync_exposes_nested_documents_and_respects_trash() -> None:
    with TestClient(app) as client:
        account = create_account(client, "potato-sync@example.com", "Potato Sync")
        headers = account_headers(account["id"])
        client_id = "potato-client"
        folder_id = "potato-runbooks"
        document_id = "potato-access"
        payload = {"nodes": [
            {"id": client_id, "parent_id": None, "name": "Potato", "kind": "client"},
            {"id": folder_id, "parent_id": client_id, "name": "Runbooks", "kind": "folder"},
            {"id": document_id, "parent_id": folder_id, "name": "Portal recovery.md", "kind": "document", "content": "Use incident PT-ACCESS-204."},
        ]}
        response = client.put("/api/filesystem/sync", headers=headers, json=payload)
        assert response.status_code == 200
        assert response.json() == {"synced": 3}
        documents = execute_client_tool(account["id"], client_id, "get_client_documents", {})["documents"]
        assert documents == [{"id": document_id, "name": "Portal recovery.md", "content": "Use incident PT-ACCESS-204."}]

        payload["nodes"][2]["trashed_at"] = datetime.now(timezone.utc).isoformat()
        assert client.put("/api/filesystem/sync", headers=headers, json=payload).status_code == 200
        assert execute_client_tool(account["id"], client_id, "get_client_documents", {}) == {"documents": []}


def test_accounts_and_workspaces_are_isolated() -> None:
    with TestClient(app) as client:
        first = create_account(client, "first@example.com", "First")
        second = create_account(client, "second@example.com", "Second")
        first_headers = account_headers(first["id"])
        second_headers = account_headers(second["id"])

        created = client.post("/api/nodes", headers=first_headers, json={"name": "Private Client", "kind": "client"})
        assert created.status_code == 201
        assert client.get("/api/nodes", headers=second_headers).json() == []
        assert client.get("/api/nodes").status_code == 401

        authenticated = client.post("/accounts/authenticate", json={"email": "FIRST@example.com", "password": "password-123"})
        assert authenticated.status_code == 200
        assert authenticated.json()["id"] == first["id"]
        assert client.post("/accounts/authenticate", json={"email": "first@example.com", "password": "wrong-password"}).status_code == 401


def test_demo_account_is_available() -> None:
    with TestClient(app) as client:
        response = client.post("/accounts/authenticate", json={"email": "demo@front-desk.local", "password": "front-desk-demo"})
        assert response.status_code == 200
        assert response.json()["name"] == "Demo"


def test_plugin_installations_are_account_scoped() -> None:
    with TestClient(app) as client:
        first = create_account(client, "plugins-first@example.com", "Plugins First")
        second = create_account(client, "plugins-second@example.com", "Plugins Second")
        first_headers = account_headers(first["id"])
        second_headers = account_headers(second["id"])

        initial = client.get("/api/plugins", headers=first_headers)
        assert initial.status_code == 200
        initial_states = {plugin["id"]: plugin for plugin in initial.json()["plugins"]}
        assert all(plugin["installed"] is False for plugin in initial_states.values())
        assert "code" not in initial_states
        assert "web-search" not in initial_states
        assert initial_states["google-workspace"]["installed"] is False

        installed = client.post("/api/plugins/notion", headers=first_headers)
        assert installed.status_code == 201
        assert {plugin["id"]: plugin for plugin in installed.json()["plugins"]}["notion"]["installed"] is True
        second_states = {plugin["id"]: plugin for plugin in client.get("/api/plugins", headers=second_headers).json()["plugins"]}
        assert second_states["notion"]["installed"] is False

        workspace = client.post("/api/plugins/google-workspace", headers=first_headers)
        assert workspace.status_code == 201
        assert {plugin["id"]: plugin for plugin in workspace.json()["plugins"]}["google-workspace"]["installed"] is True

        removed = client.delete("/api/plugins/notion", headers=first_headers)
        assert removed.status_code == 200
        assert {plugin["id"]: plugin for plugin in removed.json()["plugins"]}["notion"]["installed"] is False

        removed_workspace = client.delete("/api/plugins/google-workspace", headers=first_headers)
        assert removed_workspace.status_code == 200
        assert {plugin["id"]: plugin for plugin in removed_workspace.json()["plugins"]}["google-workspace"]["installed"] is False


def test_workspace_permissions_are_account_scoped() -> None:
    with TestClient(app) as client:
        first = create_account(client, "workspace-first@example.com", "Workspace First")
        second = create_account(client, "workspace-second@example.com", "Workspace Second")
        first_headers = account_headers(first["id"])
        second_headers = account_headers(second["id"])

        updated = client.put("/api/plugins/google/permissions/workspace.gmail", headers=first_headers, json={"enabled": False})
        assert updated.status_code == 200
        first_permissions = {permission["id"]: permission["enabled"] for permission in updated.json()["permissions"]}
        assert first_permissions["workspace.gmail"] is False

        second = client.get("/api/plugins/google", headers=second_headers)
        second_permissions = {permission["id"]: permission["enabled"] for permission in second.json()["permissions"]}
        assert second_permissions["workspace.gmail"] is True


def test_titan_connection_requires_idle_and_baselines_new_mail() -> None:
    class Client:
        capabilities: tuple[str, ...] = ()
        def capability(self) -> tuple[str, list[bytes | str]]: return "OK", [b"IMAP4REV1 AUTH=PLAIN", "IDLE"]
        def select(self, *_: object, **__: object) -> tuple[str, list[bytes]]: return "OK", [b"4"]
        def response(self, name: str) -> tuple[str, list[bytes]]:
            return "OK", [b"456"] if name == "UIDVALIDITY" else [b"19"]
        def logout(self) -> None: pass

    with TestClient(app) as client:
        account = create_account(client, "titan-connect@example.com", "Titan Connect")
        imap_client = Client()
        with patch.object(mailbox_service, "_login", return_value=imap_client):
            with SessionLocal() as session:
                status = mailbox_service.connect_titan_mailbox(session, account["id"], "support@aqualabs.tech", "secret")
        assert status["email"] == "support@aqualabs.tech"
        assert status["lastUid"] == 18
        assert "IDLE" in imap_client.capabilities
        with SessionLocal() as session:
            connection = session.query(MailboxConnection).filter_by(account_id=account["id"]).one()
            assert connection.uid_validity == "456"
            session.delete(connection)
            session.commit()

    assert mailbox_service._imap_event_name("EXISTS") == "EXISTS"
    assert mailbox_service._imap_event_name(b"EXISTS") == "EXISTS"


def test_titan_inbound_message_is_queued_for_email_agent_without_creating_goal() -> None:
    with TestClient(app) as client:
        account = create_account(client, "titan-events@example.com", "Titan Events")
        headers = account_headers(account["id"])
        assert client.get("/api/skills", headers=headers).status_code == 200
        with SessionLocal() as session:
            connection = MailboxConnection(account_id=account["id"], provider="titan", email="support@aqualabs.tech", incoming_host="imap.titan.email", incoming_port=993, outgoing_host="smtp.titan.email", outgoing_port=465, encrypted_password="encrypted", uid_validity="1", last_uid=0, state="connected")
            session.add(connection)
            session.commit()
            mailbox_id = connection.id

        first = mailbox_service.IncomingMessage(1, "<complaint@example.com>", "", "", "Potato Customer <customer@example.com>", "support@aqualabs.tech", "Order marked unpaid", "I paid for AQ-1042. Please fix it.", datetime.now(timezone.utc))
        created = mailbox_service._record_incoming(mailbox_id, first)
        assert created
        assert mailbox_service._record_incoming(mailbox_id, first) is None

        with SessionLocal() as session:
            assert session.query(Goal).filter_by(account_id=account["id"]).count() == 0
            inbound = session.query(MailMessage).filter_by(message_id=first.message_id).one()
            assert inbound.agent_status == "queued"
            assert inbound.goal_id is None
        threads = client.get("/api/mailbox/threads", headers=headers)
        assert threads.status_code == 200
        assert len(threads.json()) == 1
        assert threads.json()[0]["subject"] == "Order marked unpaid"
        assert threads.json()[0]["clientName"] == "Potato Customer"
        assert threads.json()[0]["agentStatus"] == "queued"


def test_retry_email_agent_requeues_the_existing_inbound_message() -> None:
    with TestClient(app) as client:
        account = create_account(client, "email-retry@example.com", "Email Retry")
        headers = account_headers(account["id"])
        with SessionLocal() as session:
            connection = MailboxConnection(account_id=account["id"], provider="titan", email="support@aqualabs.tech", incoming_host="imap.titan.email", incoming_port=993, outgoing_host="smtp.titan.email", outgoing_port=465, encrypted_password="encrypted", uid_validity="1", last_uid=0, state="connected")
            session.add(connection)
            session.flush()
            message = MailMessage(mailbox_id=connection.id, direction="inbound", message_id="<retry@example.com>", sender="customer@example.com", recipients="support@aqualabs.tech", subject="Retry this case", body="Please continue.", agent_status="failed", agent_action="request_attention", agent_failure="Previous run failed.", attention_required=True)
            session.add(message)
            session.commit()
            message_id = message.id

        with patch.object(email_agent_service.email_agent, "start", new=AsyncMock()) as start:
            response = client.post(f"/api/mailbox/messages/{message_id}/retry", headers=headers)

        assert response.status_code == 202
        assert response.json() == {"status": "queued", "message_id": message_id}
        start.assert_awaited_once()
        assert start.await_args.args[0] == message_id
        assert "current persisted context" in start.await_args.args[1]
        assert start.await_args.kwargs == {"fresh_session": True}
        with SessionLocal() as session:
            retried = session.get(MailMessage, message_id)
            assert retried and retried.agent_status == "queued"
            assert retried.agent_action == ""
            assert retried.agent_failure == ""
            assert retried.attention_required is False


def test_workspace_avatar_url_is_versioned_by_connected_identity() -> None:
    with TestClient(app) as client:
        account = create_account(client, "avatar-revision@example.com", "Avatar Revision")
        with SessionLocal() as session:
            connection = OAuthConnection(
                account_id=account["id"],
                provider="google_workspace",
                email="first@example.com",
                profile_name="First",
                picture_url="https://lh3.googleusercontent.com/a/first",
                refresh_token="encrypted",
                scopes=" ".join(google_oauth.SCOPES),
            )
            session.add(connection)
            session.commit()
            first_picture = connection_status(session, account["id"])["picture"]
            connection.email = "second@example.com"
            connection.picture_url = "https://lh3.googleusercontent.com/a/second"
            session.commit()
            second_picture = connection_status(session, account["id"])["picture"]

    assert str(first_picture).startswith("/api/plugins/google/avatar?revision=")
    assert first_picture != second_picture


def test_organization_skill_library_is_persisted_and_custom_skills_are_deletable() -> None:
    with TestClient(app) as client:
        account = create_account(client, "skills-library@example.com", "Skills Library")
        headers = account_headers(account["id"])
        seeded = client.get("/api/skills", headers=headers)
        assert seeded.status_code == 200
        builtins = seeded.json()
        aqualabs = next(skill for skill in builtins if skill["name"] == "AquaLabs Customer Resolution")
        assert aqualabs["batchName"] == "AquaLabs"
        assert aqualabs["deletable"] is False
        assert client.delete(f"/api/skills/{aqualabs['id']}", headers=headers).status_code == 409

        created = client.post("/api/skills", headers=headers, json={
            "name": "VIP Escalation",
            "description": "Escalate high-priority customer cases.",
            "instructions": "Collect evidence and notify the account owner.",
            "batch_name": "Created by you",
            "required_plugin_ids": ["slack"],
        })
        assert created.status_code == 201
        skill = created.json()
        assert skill["deletable"] is True
        updated = client.put(f"/api/skills/{skill['id']}", headers=headers, json={
            "name": "VIP Customer Escalation",
            "description": skill["description"],
            "instructions": skill["instructions"],
            "batch_name": "AquaLabs",
            "required_plugin_ids": ["slack"],
        })
        assert updated.status_code == 200
        assert updated.json()["batchName"] == "AquaLabs"
        assert updated.json()["version"] == 2
        assert client.delete(f"/api/skills/{skill['id']}", headers=headers).status_code == 200
        assert all(item["id"] != skill["id"] for item in client.get("/api/skills", headers=headers).json())


def test_workspace_oauth_accepts_essentials_without_gmail() -> None:
    class Response:
        def __init__(self, success: bool, message: str = "") -> None:
            self.is_success = success
            self.reason_phrase = "Forbidden"
            self._message = message

        def json(self) -> dict[str, object]:
            return {"error": {"message": self._message}}

    class Client:
        async def get(self, url: str, **_: object) -> Response:
            if "gmail.googleapis.com" in url:
                return Response(False, "Mail service not enabled")
            return Response(True)

    unavailable = asyncio.run(google_oauth._validate_workspace_token(Client(), "token"))
    assert unavailable == {"workspace.gmail"}


def test_workspace_oauth_still_rejects_required_service_failure() -> None:
    class Response:
        def __init__(self, success: bool, message: str = "") -> None:
            self.is_success = success
            self.reason_phrase = "Forbidden"
            self._message = message

        def json(self) -> dict[str, object]:
            return {"error": {"message": self._message}}

    class Client:
        async def get(self, url: str, **_: object) -> Response:
            if "gmail.googleapis.com" in url:
                return Response(False, "Mail service not enabled")
            return Response(False, "Drive API disabled")

    try:
        asyncio.run(google_oauth._validate_workspace_token(Client(), "token"))
        raise AssertionError("A required Workspace service failure must reject the connection.")
    except RuntimeError as error:
        assert "Google Drive authorization failed" in str(error)


def test_external_plugin_permissions_are_account_scoped() -> None:
    with TestClient(app) as client:
        first = create_account(client, "plugin-permissions-first@example.com", "Plugin Permissions First")
        second = create_account(client, "plugin-permissions-second@example.com", "Plugin Permissions Second")
        first_headers = account_headers(first["id"])
        second_headers = account_headers(second["id"])

        assert client.post("/api/plugins/github", headers=first_headers).status_code == 201
        updated = client.put("/api/plugins/github/permissions/github.issues", headers=first_headers, json={"enabled": False})
        assert updated.status_code == 200
        first_github = {plugin["id"]: plugin for plugin in updated.json()["plugins"]}["github"]
        first_permissions = {permission["id"]: permission["enabled"] for permission in first_github["permissions"]}
        assert first_permissions["github.issues"] is False

        second_plugins = {plugin["id"]: plugin for plugin in client.get("/api/plugins", headers=second_headers).json()["plugins"]}
        second_permissions = {permission["id"]: permission["enabled"] for permission in second_plugins["github"]["permissions"]}
        assert second_permissions["github.issues"] is True


def test_browser_use_installs_as_local_extension() -> None:
    with TestClient(app) as client:
        account = create_account(client, "browser-plugin@example.com", "Browser Plugin")
        headers = account_headers(account["id"])
        plugins = {plugin["id"]: plugin for plugin in client.get("/api/plugins", headers=headers).json()["plugins"]}

        assert plugins["browser-use"]["connection_type"] == "extension"
        assert plugins["browser-use"]["connection_supported"] is True

        response = client.post("/api/plugins/browser-use", headers=headers)
        assert response.status_code == 201
        installed = {plugin["id"]: plugin for plugin in response.json()["plugins"]}["browser-use"]
        assert installed["installed"] is True
        assert installed["connected"] is True
        assert installed["account_label"] == "Local Chrome"
        assert installed["tool_count"] == 24

        removed = client.delete("/api/plugins/browser-use", headers=headers)
        assert removed.status_code == 200
        browser = {plugin["id"]: plugin for plugin in removed.json()["plugins"]}["browser-use"]
        assert browser["installed"] is False
        assert browser["connected"] is False


def test_aqualabs_store_installs_as_managed_plugin(monkeypatch) -> None:
    monkeypatch.setenv("FRONT_DESK_AQUALABS_STORE_MCP_URL", "https://aqualabs-store.vercel.app/api/mcp")
    monkeypatch.setenv("FRONT_DESK_AQUALABS_STORE_MCP_TOKEN", "test-token")
    from app.config import get_settings
    get_settings.cache_clear()
    try:
        with TestClient(app) as client:
            account = create_account(client, "store-plugin@example.com", "Store Plugin")
            headers = account_headers(account["id"])

            response = client.post("/api/plugins/aqualabs-store", headers=headers)
            assert response.status_code == 201
            store = {plugin["id"]: plugin for plugin in response.json()["plugins"]}["aqualabs-store"]
            assert store["installed"] is True
            assert store["connected"] is True
            assert store["connection_type"] == "managed"
            assert store["account_label"] == "Aqualabs Store"
            assert store["tool_count"] == 11
    finally:
        get_settings.cache_clear()


def test_goal_board_and_scheduled_run_dispatch() -> None:
    with TestClient(app) as client:
        account = create_account(client, "goals@example.com", "Goals")
        headers = account_headers(account["id"])
        created = client.post("/api/goals", headers=headers, json={
            "client_id": "client-acme",
            "text": "Tell me the time every five minutes.",
            "skill_ids": [],
            "plugin_ids": [],
        })
        assert created.status_code == 201
        goal = created.json()
        assert goal["version"] == 1
        assert goal["situation"] == ""
        assert goal["runState"] == "idle"
        assert client.get("/api/notifications", headers=headers, params={"client_id": "client-acme"}).json() == []

        automation = client.post(
            f"/api/goals/{goal['id']}/automations",
            headers=headers,
            json={"instruction": "Tell me the current time using the client message tool.", "interval_seconds": 300, "timezone": "Africa/Nairobi"},
        )
        assert automation.status_code == 201
        with SessionLocal() as session:
            row = session.get(GoalAutomation, automation.json()["id"])
            assert row
            row.next_run_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            session.commit()

        with patch("app.main.goal_tasks.start", new=AsyncMock(return_value=True)) as start:
            run = client.post("/internal/automations/run", headers={"X-Front-Desk-Internal-Secret": "test-internal-secret"})
        assert run.status_code == 200
        assert run.json()["processed"] == 1
        result = run.json()["results"][0]
        assert result["goal_id"] == goal["id"]
        assert result["instruction"] == "Tell me the current time using the client message tool."
        start.assert_awaited_once_with(account["id"], goal["id"], result["instruction"])

        removed = client.delete(f"/api/goals/{goal['id']}", headers=headers)
        assert removed.status_code == 200
        assert removed.json() == {"deleted": True}
        assert client.get("/api/goals", headers=headers, params={"client_id": "client-acme"}).json() == []
        assert client.get("/api/notifications", headers=headers, params={"client_id": "client-acme"}).json() == []


def test_goal_preflight_does_not_connect_browser_before_the_worker_loads_it() -> None:
    with TestClient(app) as client:
        account = create_account(client, "preflight@example.com", "Preflight")
        headers = account_headers(account["id"])
        goal = client.post("/api/goals", headers=headers, json={
            "client_id": "client-preflight",
            "text": "Open example.com and report its title.",
            "skill_ids": [],
            "plugin_ids": [],
        }).json()

    with SessionLocal() as session:
        row = session.get(Goal, goal["id"])
        assert row
        row.plugin_ids = json.dumps(["browser-use"])
        session.add(PluginInstallation(account_id=account["id"], plugin_id="browser-use"))
        session.commit()

    manager = GoalTaskManager()
    assignment_id = create_test_assignment(goal["id"], goal["text"])
    with SessionLocal() as session:
        assignment = session.get(GoalAssignment, assignment_id)
        session.expunge(assignment)
    with patch("tools.goal_tool_registry.connected_playwright_toolset", new=AsyncMock(side_effect=RuntimeError("Chrome extension is not connected."))) as connect:
        tools, toolsets = asyncio.run(manager._preflight(account["id"], manager._goal(account["id"], goal["id"]), assignment))
    connect.assert_not_awaited()
    assert len(tools) == 6
    assert isinstance(toolsets[0], GoalToolRegistry)


def test_recommended_browser_namespace_stays_disconnected_until_explicit_load() -> None:
    registry = GoalToolRegistry("account", ["browser-use"], ["browser-use"], [])
    context = SimpleNamespace(state={})
    with patch("tools.goal_tool_registry.connected_playwright_toolset", new=AsyncMock(side_effect=RuntimeError("Browser disconnected."))) as connect:
        available = asyncio.run(registry.get_tools(SimpleNamespace(state={})))
        assert [tool.name for tool in available] == ["load_goal_tools"]
        connect.assert_not_awaited()
        result = asyncio.run(registry.load_goal_tools(["browser-use"], context))
    assert result == {"status": "failed", "error": "Browser disconnected."}
    assert context.state == {}
    connect.assert_awaited_once_with()


def test_loaded_goal_tools_refresh_during_the_same_adk_invocation() -> None:
    browser_tabs = SimpleNamespace(name="browser_tabs")
    registry = GoalToolRegistry("account", ["browser-use"], ["browser-use"], [])
    registry._tools["browser-use"] = [browser_tabs]
    context = SimpleNamespace(invocation_id="same-invocation", state={})

    initial = asyncio.run(registry.get_tools_with_prefix(context))
    assert [tool.name for tool in initial] == ["load_goal_tools"]

    context.state["loaded_goal_tool_ids"] = ["browser-use"]
    refreshed = asyncio.run(registry.get_tools_with_prefix(context))
    assert [tool.name for tool in refreshed] == ["load_goal_tools", "browser_tabs"]


def test_goal_preflight_loads_aqualabs_store_only_when_requested() -> None:
    with TestClient(app) as client:
        account = create_account(client, "store-worker@example.com", "Store Worker")
        goal_payload = client.post("/api/goals", headers=account_headers(account["id"]), json={
            "client_id": "client-store-worker",
            "text": "Check this customer's order history.",
            "skill_ids": [],
            "plugin_ids": ["aqualabs-store"],
        }).json()

    with SessionLocal() as session:
        session.add(PluginInstallation(account_id=account["id"], plugin_id="aqualabs-store"))
        session.commit()
        goal = session.get(Goal, goal_payload["id"])
        session.expunge(goal)
    assignment_id = create_test_assignment(goal_payload["id"], goal_payload["text"])
    with SessionLocal() as session:
        assignment = session.get(GoalAssignment, assignment_id)
        session.expunge(assignment)

    store_tool = SimpleNamespace(name="find_customer_orders")
    store_toolset = MagicMock()
    store_toolset.get_tools_with_prefix = AsyncMock(return_value=[store_tool])
    store_toolset.close = AsyncMock()
    manager = GoalTaskManager()
    with patch("tools.goal_tool_registry.configured_aqualabs_store_toolset", new=AsyncMock(return_value=store_toolset)) as configured:
        tools, toolsets = asyncio.run(manager._preflight(account["id"], goal, assignment))
        configured.assert_not_awaited()
        registry = toolsets[0]
        context = SimpleNamespace(state={})
        result = asyncio.run(registry.load_goal_tools(["aqualabs-store"], context))
        configured.assert_awaited_once_with()
        assert result["status"] == "loaded"
        loaded_tools = asyncio.run(registry.get_tools(SimpleNamespace(state=context.state)))
        assert [tool.name for tool in loaded_tools] == ["load_goal_tools", "find_customer_orders"]
        asyncio.run(registry.close())
    assert len(tools) == 6


def test_goal_client_tools_resolve_only_from_the_front_desk_directory() -> None:
    with TestClient(app) as client:
        account = create_account(client, "client-tools@example.com", "Client Tools")
        headers = account_headers(account["id"])
        payload = {"nodes": [
            {"id": "victor-client", "parent_id": None, "name": "Victor Bash", "kind": "client"},
            {"id": "victor-profile", "parent_id": "victor-client", "name": "Client Profile", "kind": "profile", "content": "Email: victor@example.com\nSummary: AquaLabs customer."},
        ]}
        assert client.put("/api/filesystem/sync", headers=headers, json=payload).status_code == 200
    context = SimpleNamespace(state={"account_id": account["id"], "client_id": "victor-client"})
    assert list_clients(context) == {
        "status": "completed",
        "clients": [{"id": "victor-client", "name": "Victor Bash"}],
    }
    profile = read_client_profile(context)
    assert profile["status"] == "completed"
    assert profile["client"]["name"] == "Victor Bash"
    assert "victor@example.com" in profile["client"]["profile"]
    assert read_client_profile(context, "someone-from-slack")["status"] == "not_found"


def test_answering_a_blocking_question_resumes_with_the_answer() -> None:
    with TestClient(app) as client:
        account = create_account(client, "resume@example.com", "Resume")
        headers = account_headers(account["id"])
        goal = client.post("/api/goals", headers=headers, json={
            "client_id": "client-resume",
            "text": "Continue after I provide the project name.",
            "skill_ids": [],
            "plugin_ids": [],
        }).json()
        with SessionLocal() as session:
            notification = create_notification(session, account["id"], goal["id"], "clarification", "Which project?")
        with patch("app.main.goal_tasks.start", new=AsyncMock(return_value=True)) as start:
            response = client.post(f"/api/notifications/{notification['id']}/answer", headers=headers, json={"answer": "Front Desk"})
        assert response.status_code == 200
        resumed_instruction = start.await_args.args[2]
        assert "Front Desk" in resumed_instruction
        assert "Continue the goal" in resumed_instruction


def test_open_questions_excludes_questions_from_inactive_tasks() -> None:
    with TestClient(app) as client:
        account = create_account(client, "questions@example.com", "Questions")
        headers = account_headers(account["id"])
        goal = client.post("/api/goals", headers=headers, json={
            "client_id": "client-questions",
            "text": "Resolve the question.",
            "skill_ids": [],
            "plugin_ids": [],
        }).json()
        with SessionLocal() as session:
            blocked = GoalAssignment(goal_id=goal["id"], instruction="Blocked task", status="blocked", phase="blocked", current_step="Which account?")
            cancelled = GoalAssignment(goal_id=goal["id"], instruction="Cancelled task", status="cancelled", phase="cancelled")
            session.add_all([blocked, cancelled])
            session.commit()
            goal_row = session.get(Goal, goal["id"])
            goal_row.run_state = "blocked"
            session.commit()
            open_question = create_notification(session, account["id"], goal["id"], "clarification", "Which account?", blocked.id)
            create_notification(session, account["id"], goal["id"], "clarification", "Superseded question", blocked.id)
            create_notification(session, account["id"], goal["id"], "clarification", "Stale question", cancelled.id)

        response = client.get("/api/notifications", headers=headers, params={"open_questions": "true"})
        assert response.status_code == 200
        assert [item["id"] for item in response.json()] == [open_question["id"]]


def test_workspace_preflight_only_probes_enabled_services() -> None:
    calls: list[str] = []

    class Response:
        is_error = False

    class Client:
        def __init__(self, **_: object) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def get(self, url: str, **_: object) -> Response:
            calls.append(url)
            return Response()

    with patch.object(workspace, "workspace_access_token", new=AsyncMock(return_value="token")), patch.object(workspace, "_permission_map", return_value={"workspace.gmail": False, "workspace.drive": True}), patch.object(workspace.httpx, "AsyncClient", Client):
        asyncio.run(workspace.preflight_workspace("account"))

    assert calls == [f"{workspace.DRIVE_API}/about"]


def test_workspace_preview_returns_the_authenticated_drive_thumbnail() -> None:
    with TestClient(app) as client:
        account = create_account(client, "workspace-preview@example.com", "Workspace Preview")

        class Response:
            def __init__(self, *, content: bytes = b"", content_type: str = "application/json", payload: dict[str, str] | None = None) -> None:
                self.content = content
                self.headers = {"content-type": content_type}
                self.is_error = False
                self.status_code = 200
                self._payload = payload or {}

            def json(self) -> dict[str, str]:
                return self._payload

        class Client:
            def __init__(self, **_: object) -> None:
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_: object) -> None:
                return None

            async def get(self, url: str, **_: object) -> Response:
                if url.startswith(workspace.DRIVE_API):
                    return Response(payload={"thumbnailLink": "https://drive.google.com/thumbnail/document-preview-123"})
                return Response(content=b"workspace-image", content_type="image/png")

        with patch.object(workspace, "workspace_access_token", new=AsyncMock(return_value="token")), patch("app.main.httpx.AsyncClient", Client):
            response = client.get("/api/workspace/previews/document-preview-123", headers=account_headers(account["id"]))
        assert response.status_code == 200
        assert response.content == b"workspace-image"
        assert response.headers["content-type"] == "image/png"


def test_workspace_gmail_send_uses_the_real_send_endpoint() -> None:
    request = AsyncMock(return_value={"id": "message-1", "threadId": "thread-1"})
    context = SimpleNamespace(state={"account_id": "account"})

    async def exercise() -> dict[str, object]:
        with patch.object(workspace, "workspace_request", new=request):
            return await workspace.workspace_gmail_send_message(
                ["recipient@example.com"],
                "Subject",
                "Body",
                context,
            )

    result = asyncio.run(exercise())
    assert result == {"message_id": "message-1", "thread_id": "thread-1", "status": "sent"}
    assert request.await_args.args[:3] == ("account", "POST", f"{workspace.GMAIL_API}/messages/send")
    encoded = request.await_args.kwargs["json"]["raw"]
    message = message_from_bytes(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    assert message["To"] == "recipient@example.com"
    assert message["Subject"] == "Subject"


def test_workspace_api_escape_hatch_rejects_non_google_hosts() -> None:
    context = SimpleNamespace(state={"account_id": "account"})
    try:
        asyncio.run(workspace.workspace_google_api_request("GET", "https://example.com", context))
        raise AssertionError("A non-Google API host must never receive the Workspace token.")
    except RuntimeError as error:
        assert str(error) == "Use an official HTTPS Google Workspace API URL."


def test_cancelling_a_running_goal_persists_cancelled_assignment() -> None:
    with TestClient(app) as client:
        account = create_account(client, "cancel-worker@example.com", "Cancel Worker")
        goal = client.post("/api/goals", headers=account_headers(account["id"]), json={
            "client_id": "client-cancel-worker",
            "text": "Stay active until cancelled.",
            "skill_ids": [],
            "plugin_ids": [],
        }).json()

    async def exercise() -> None:
        manager = GoalTaskManager()
        entered = asyncio.Event()

        async def wait_in_preflight(*_: object):
            entered.set()
            await asyncio.Event().wait()

        assignment_id = create_test_assignment(goal["id"], goal["text"])
        with patch.object(manager, "_planned_assignments", new=AsyncMock(return_value=[assignment_id])), patch.object(manager, "_preflight", new=wait_in_preflight):
            assert await manager.start(account["id"], goal["id"])
            await entered.wait()
            assert await manager.cancel(goal["id"])

    asyncio.run(exercise())
    with SessionLocal() as session:
        assignment = session.query(GoalAssignment).filter_by(goal_id=goal["id"]).one()
        assert assignment.status == "cancelled"
        assert assignment.finished_at is not None


def test_worker_cannot_complete_without_complete_goal_evidence() -> None:
    with TestClient(app) as client:
        account = create_account(client, "evidence-worker@example.com", "Evidence Worker")
        goal = client.post("/api/goals", headers=account_headers(account["id"]), json={
            "client_id": "client-evidence-worker",
            "text": "Do not claim this completed without evidence.",
            "skill_ids": [],
            "plugin_ids": [],
        }).json()

    class RunnerWithoutCompletion:
        app_name = "front_desk_goal_worker"

        async def run_async(self, **_: object):
            if False:
                yield None

    async def exercise() -> None:
        manager = GoalTaskManager()
        assignment_id = create_test_assignment(goal["id"], goal["text"])
        with patch.object(manager, "_preflight", new=AsyncMock(return_value=([], []))), patch.object(manager, "_runner", return_value=RunnerWithoutCompletion()):
            await manager._run_assignment(account["id"], goal["id"], assignment_id)

    asyncio.run(exercise())
    with SessionLocal() as session:
        assignment = session.query(GoalAssignment).filter_by(goal_id=goal["id"]).one()
        assert assignment.status == "failed"
        assert assignment.report == "The worker stopped without explicitly completing its task."
        persisted_goal = session.get(Goal, goal["id"])
        assert persisted_goal and persisted_goal.run_state == "failed"
        assert persisted_goal.current_step == assignment.report


def test_task_completion_requires_evidence_for_every_planned_output() -> None:
    with TestClient(app) as client:
        account = create_account(client, "output-evidence@example.com", "Output Evidence")
        goal_payload = client.post("/api/goals", headers=account_headers(account["id"]), json={
            "client_id": "output-client",
            "text": "Produce a verified report.",
            "skill_ids": [],
            "plugin_ids": [],
        }).json()
    with SessionLocal() as session:
        assignment = GoalAssignment(goal_id=goal_payload["id"], title="Produce report", instruction="Produce the report.", expected_outputs=json.dumps(["Verified report URL"]))
        session.add(assignment)
        session.commit()
        task_id = assignment.id
    context = SimpleNamespace(state={"goal_id": goal_payload["id"], "assignment_id": task_id}, actions=SimpleNamespace(end_of_agent=False))
    missing = complete_goal("Report created.", "Created through Docs.", context, outputs=[])
    assert missing == {"status": "failed", "error": "Task completion evidence is missing for: Verified report URL."}
    assert context.actions.end_of_agent is False
    completed = complete_goal("Report created.", "Created through Docs.", context, outputs=[{"name": "Verified report URL", "evidence": "https://docs.google.com/document/d/report-id/edit"}])
    assert completed["status"] == "completed"
    assert context.actions.end_of_agent is True


def test_planner_creates_ordered_persistent_tasks_and_updates_queued_work() -> None:
    with TestClient(app) as client:
        account = create_account(client, "planner-board@example.com", "Planner Board")
        goal_payload = client.post("/api/goals", headers=account_headers(account["id"]), json={
            "client_id": "planner-client",
            "text": "Prepare and send the client outcome.",
            "skill_ids": [],
            "plugin_ids": [],
        }).json()

    manager = GoalTaskManager()
    goal = manager._goal(account["id"], goal_payload["id"])
    with SessionLocal() as session:
        client_brief_id = next(skill["id"] for skill in list_skills(session, account["id"]) if skill["name"] == "Client Brief")
    created_plan = GoalPlan(operations=[
        GoalTaskOperation(action="create", key="prepare", title="Prepare outcome", instruction="Prepare the verified client outcome.", expected_outputs=["Verified outcome"], skill_ids=[client_brief_id]),
        GoalTaskOperation(action="create", key="send", title="Send outcome", instruction="Send the verified outcome to the client.", depends_on=["prepare"], required_inputs=["Verified outcome"], expected_outputs=["Sent message ID"]),
    ])
    async def inspect_planning_state(*_: object) -> GoalPlan:
        planning = manager._goal(account["id"], goal.id)
        assert planning.run_state == "planning"
        assert planning.current_step == "Defining tasks for: Create the task board."
        return created_plan

    with patch("app.goal_tasks.create_goal_planner_runner"), patch("app.goal_tasks.plan_goal", new=AsyncMock(side_effect=inspect_planning_state)):
        task_ids = asyncio.run(manager._planned_assignments(account["id"], goal, "Create the task board."))

    with SessionLocal() as session:
        tasks = [session.get(GoalAssignment, task_id) for task_id in task_ids]
        assert [task.title for task in tasks if task] == ["Prepare outcome", "Send outcome"]
        assert json.loads(tasks[0].skill_ids) == [client_brief_id]
        assert [skill.name for skill in manager._assignment_skills(account["id"], tasks[0])] == ["Client Brief"]
        assert json.loads(tasks[1].depends_on) == [tasks[0].id]
        persisted_goal = session.get(Goal, goal.id)
        assert persisted_goal and persisted_goal.run_state == "queued"
        assert persisted_goal.current_step == "Prepare outcome"

    updated_plan = GoalPlan(operations=[GoalTaskOperation(action="update", task_id=task_ids[1], key="send", title="Send concise outcome", instruction="Send a concise verified outcome to the client.")])
    with patch("app.goal_tasks.create_goal_planner_runner"), patch("app.goal_tasks.plan_goal", new=AsyncMock(return_value=updated_plan)):
        revised_ids = asyncio.run(manager._planned_assignments(account["id"], goal, "Make the message concise."))
    assert task_ids[1] in revised_ids
    with SessionLocal() as session:
        revised = session.get(GoalAssignment, task_ids[1])
        assert revised and revised.title == "Send concise outcome"
        assert revised.instruction == "Send a concise verified outcome to the client."
        first = session.get(GoalAssignment, task_ids[0])
        assert first
        first.status = "running"
        first.phase = "working"
        session.commit()

    steer_plan = GoalPlan(operations=[GoalTaskOperation(action="steer", task_id=task_ids[0], instruction="Prepare the verified outcome using the new client constraint.")])
    with patch("app.goal_tasks.create_goal_planner_runner"), patch("app.goal_tasks.plan_goal", new=AsyncMock(return_value=steer_plan)):
        asyncio.run(manager._planned_assignments(account["id"], goal, "Apply the new client constraint."))
    with SessionLocal() as session:
        steered = session.get(GoalAssignment, task_ids[0])
        assert steered and steered.status == "queued"
        assert steered.instruction == "Prepare the verified outcome using the new client constraint."
        steered.status = "failed"
        steered.phase = "failed"
        steered.progress = 70
        steered.report = "The previous tool declaration was invalid."
        steered.evidence = json.dumps(["stale evidence"])
        session.commit()

    retry_plan = GoalPlan(operations=[GoalTaskOperation(action="retry", task_id=task_ids[0], instruction="Retry the same outcome with the corrected tool declaration.")])
    with patch("app.goal_tasks.create_goal_planner_runner"), patch("app.goal_tasks.plan_goal", new=AsyncMock(return_value=retry_plan)):
        retried_ids = asyncio.run(manager._planned_assignments(account["id"], goal, "Retry the failed task."))
    assert task_ids[0] in retried_ids
    with SessionLocal() as session:
        retried = session.get(GoalAssignment, task_ids[0])
        assert retried and retried.status == "queued" and retried.phase == "queued"
        assert retried.progress == 0 and retried.report == "" and json.loads(retried.evidence) == []
        assert retried.instruction == "Retry the same outcome with the corrected tool declaration."

    cancel_plan = GoalPlan(operations=[GoalTaskOperation(action="cancel", task_id=task_ids[1])])
    with patch("app.goal_tasks.create_goal_planner_runner"), patch("app.goal_tasks.plan_goal", new=AsyncMock(return_value=cancel_plan)):
        remaining = asyncio.run(manager._planned_assignments(account["id"], goal, "Cancel the send step."))
    assert task_ids[0] in remaining
    with SessionLocal() as session:
        cancelled = session.get(GoalAssignment, task_ids[1])
        assert cancelled and cancelled.status == "cancelled"

    reuse_plan = GoalPlan(operations=[GoalTaskOperation(action="reuse", task_id=task_ids[0])])
    with patch("app.goal_tasks.create_goal_planner_runner"), patch("app.goal_tasks.plan_goal", new=AsyncMock(return_value=reuse_plan)):
        reused = asyncio.run(manager._planned_assignments(account["id"], goal, "Continue the prepared outcome."))
    assert reused == [task_ids[0]]


def test_restart_pauses_interrupted_task_without_starting_it() -> None:
    with TestClient(app) as client:
        account = create_account(client, "recover-task@example.com", "Recover Task")
        goal_payload = client.post("/api/goals", headers=account_headers(account["id"]), json={
            "client_id": "recover-client",
            "text": "Resume this exact task after restart.",
            "skill_ids": [],
            "plugin_ids": [],
        }).json()
    with SessionLocal() as session:
        assignment = GoalAssignment(goal_id=goal_payload["id"], title="Read client evidence", instruction="Read the client evidence.", status="running", phase="working", current_step="Reading the client evidence.")
        session.add(assignment)
        session.commit()
        task_id = assignment.id

    manager = GoalTaskManager()
    with patch.object(manager, "start", new=AsyncMock(return_value=True)) as start:
        asyncio.run(manager.recover())
    start.assert_not_awaited()
    with SessionLocal() as session:
        recovered = session.get(GoalAssignment, task_id)
        goal = session.get(Goal, goal_payload["id"])
        assert recovered and recovered.status == "queued"
        assert recovered.current_step == "Reading the client evidence."
        assert recovered.finished_at is None
        assert goal and goal.status == "paused"
        assert goal.run_state == "paused"


def test_browser_preview_is_persisted_and_account_scoped() -> None:
    with TestClient(app) as client:
        owner = create_account(client, "preview-owner@example.com", "Preview Owner")
        stranger = create_account(client, "preview-stranger@example.com", "Preview Stranger")
        goal_payload = client.post("/api/goals", headers=account_headers(owner["id"]), json={
            "client_id": "preview-client",
            "text": "Verify a browser page.",
            "skill_ids": [],
            "plugin_ids": [],
        }).json()
        with SessionLocal() as session:
            assignment = GoalAssignment(goal_id=goal_payload["id"], title="Verify page", instruction="Verify the page.")
            session.add(assignment)
            session.flush()
            session.add(GoalBrowserPreview(assignment_id=assignment.id, image=b"\x89PNG\r\n", revision="preview-1"))
            session.commit()
            task_id = assignment.id
        owned = client.get(f"/api/browser/previews/{task_id}", headers=account_headers(owner["id"]))
        assert owned.status_code == 200
        assert owned.content == b"\x89PNG\r\n"
        assert owned.headers["content-type"] == "image/png"
        assert client.get(f"/api/browser/previews/{task_id}", headers=account_headers(stranger["id"])).status_code == 404


def test_goals_chat_routes_all_board_changes_through_the_planner() -> None:
    tool_names = {getattr(tool, "name", tool.__name__) for tool in create_goals_chat_app().root_agent.tools}
    assert tool_names == {"list_goal_tasks", "revise_goal_plan"}


def test_goal_worker_rejects_parallel_calls_without_stopping_after_failure() -> None:
    tool = MagicMock(name="browser_tabs")
    tool.name = "browser_tabs"
    context = MagicMock()
    context.state = {}
    context.actions = MagicMock()

    assert asyncio.run(begin_single_tool(tool, {}, context)) is None
    rejected = asyncio.run(begin_single_tool(tool, {}, context))
    assert rejected == {"status": "failed", "error": "Parallel tool call rejected: browser_tabs. Call one tool at a time."}
    assert context.actions.end_of_agent is not True

    context.state = {"goal_tool_in_flight": True}
    finish_single_tool(tool, {}, context, {"status": "failed", "error": "timeout"})
    assert context.state["goal_tool_in_flight"] is False
    assert "goal_terminal_tool_error" not in context.state


def test_browser_tool_publishes_action_and_goal_intent() -> None:
    calls: list[tuple[str, dict[str, str]]] = []

    class Session:
        async def call_tool(self, name: str, arguments: dict[str, str]):
            calls.append((name, arguments))
            return SimpleNamespace(isError=False)

    tool = MagicMock()
    tool.name = "browser_click"
    tool._mcp_session_manager.create_session = AsyncMock(return_value=Session())
    context = MagicMock()
    context.state = {"goal_intent": "Confirm the client's portal access"}
    context.actions = MagicMock()

    assert asyncio.run(begin_single_tool(tool, {"element": "Continue button"}, context)) is None
    assert calls[0][0] == "browser_evaluate"
    function = calls[0][1]["function"]
    assert "Clicking Continue button" in function
    assert "Confirm the client's portal access" in function


def test_event_stream_emits_keepalive_while_idle() -> None:
    broker = AccountEventBroker()

    async def exercise() -> None:
        with patch("app.event_stream.KEEPALIVE_SECONDS", 0.001):
            stream = broker.subscribe("account")
            assert "ready" in await anext(stream)
            assert await anext(stream) == ": keepalive\n\n"
            await stream.aclose()

    asyncio.run(exercise())


def test_browser_preflight_executes_a_real_tabs_command() -> None:
    call_tool = AsyncMock(return_value=SimpleNamespace(isError=False, content=[]))
    session_manager = SimpleNamespace(create_session=AsyncMock(return_value=SimpleNamespace(call_tool=call_tool)))
    tabs_tool = SimpleNamespace(name="browser_tabs", _mcp_session_manager=session_manager)
    toolset = SimpleNamespace(get_tools=AsyncMock(return_value=[tabs_tool]), close=AsyncMock())

    async def exercise() -> None:
        with patch.object(playwright_browser, "create_playwright_toolset", return_value=toolset):
            connected = await playwright_browser.connected_playwright_toolset()
            assert connected is toolset

    asyncio.run(exercise())
    call_tool.assert_awaited_once_with("browser_tabs", arguments={"action": "list"})


def test_browser_toolset_binds_the_configured_chrome_profile() -> None:
    settings = SimpleNamespace(
        playwright_extension_token="extension-token",
        playwright_profile_directory="Profile 3",
    )

    with patch.object(playwright_browser, "get_settings", return_value=settings):
        toolset = playwright_browser.create_playwright_toolset()

    environment = toolset._connection_params.server_params.env
    assert environment["PLAYWRIGHT_MCP_EXTENSION_TOKEN"] == "extension-token"
    assert environment["PLAYWRIGHT_MCP_PROFILE_DIRECTORY"] == "Profile 3"


def test_browser_preview_capture_reads_the_task_scoped_screenshot() -> None:
    async def exercise() -> bytes:
        with TemporaryDirectory() as directory:
            output = playwright_browser.Path(directory)

            async def capture(_: str, arguments: dict[str, str]):
                (output / arguments["filename"]).write_bytes(b"browser-preview")
                return SimpleNamespace(isError=False, content=[])

            session = SimpleNamespace(call_tool=AsyncMock(side_effect=capture))
            screenshot = SimpleNamespace(name="browser_take_screenshot", _mcp_session_manager=SimpleNamespace(create_session=AsyncMock(return_value=session)))
            toolset = SimpleNamespace(get_tools=AsyncMock(return_value=[screenshot]))
            with patch.object(playwright_browser, "PLAYWRIGHT_OUTPUT_DIR", output):
                image = await playwright_browser.capture_browser_preview(toolset, "task-123")
            session.call_tool.assert_awaited_once_with("browser_take_screenshot", arguments={"type": "png", "filename": "goal-task-123.png"})
            return image

    assert asyncio.run(exercise()) == b"browser-preview"


def test_voice_ticket_is_authenticated_scoped_and_uses_sherpa_live_contract() -> None:
    with TestClient(app) as client:
        account = create_account(client, "voice@example.com", "Voice")
        headers = account_headers(account["id"])
        response = client.post(
            "/api/voice/ticket",
            headers=headers,
            json={"client_id": "client-voice", "session_id": "voice-session"},
        )
        assert response.status_code == 200
        assert verify_voice_ticket(response.json()["ticket"], "voice-session") == (
            account["id"],
            "client-voice",
        )
        assert client.post(
            "/api/voice/ticket",
            json={"client_id": "client-voice", "session_id": "voice-session"},
        ).status_code == 401
        try:
            verify_voice_ticket(response.json()["ticket"], "another-session")
            raise AssertionError("A voice ticket must not authorize another session.")
        except ValueError:
            pass

    assert VOICE_MODEL == "gemini-3.1-flash-live-preview"
    assert {declaration.name for declaration in VOICE_TOOLS[0].function_declarations or []} == {
        "get_client_goals",
        "update_goal_board",
        "ask_user",
        "send_client_message",
    }


def test_github_repository_access_is_account_scoped_and_removed_with_plugin() -> None:
    with TestClient(app) as client:
        first = create_account(client, "github-first@example.com", "GitHub First")
        second = create_account(client, "github-second@example.com", "GitHub Second")
        first_headers = account_headers(first["id"])
        second_headers = account_headers(second["id"])
        assert client.post("/api/plugins/github", headers=first_headers).status_code == 201

        with SessionLocal() as session:
            session.add(GitHubRepositoryAccess(account_id=first["id"], full_name="front-desk/private-client"))
            session.commit()

        first_plugins = {plugin["id"]: plugin for plugin in client.get("/api/plugins", headers=first_headers).json()["plugins"]}
        second_plugins = {plugin["id"]: plugin for plugin in client.get("/api/plugins", headers=second_headers).json()["plugins"]}
        assert first_plugins["github"]["repository_count"] == 1
        assert second_plugins["github"]["repository_count"] == 0

        assert client.delete("/api/plugins/github", headers=first_headers).status_code == 200
        with SessionLocal() as session:
            assert session.query(GitHubRepositoryAccess).filter_by(account_id=first["id"]).count() == 0


def test_direct_client_call_cannot_expand_into_adjacent_work_or_false_contact() -> None:
    assert "A direct request to call or speak with a client is one live-call task" in PLANNER_INSTRUCTION
    assert "Do not reinterpret \"call\" as \"open a support case,\" \"post to Slack,\" or \"schedule a future call.\"" in PLANNER_INSTRUCTION
    assert "A request to call or speak with a client without a future time means an immediate call" in WORKER_INSTRUCTION
    assert "Do not ask the Front Desk owner to choose a time for an immediate call" in WORKER_INSTRUCTION
    assert "ask the client for availability through the client's communication channel" in WORKER_INSTRUCTION
    assert "A request to call a client without a future time is an immediate call now" in PLANNER_INSTRUCTION
    assert "posting an internal notification" in WORKER_INSTRUCTION
    assert "Client identity comes only from Front Desk's client directory and profiles" in PLANNER_INSTRUCTION
    assert "Never search Gmail, Slack, Drive, Jira, the browser" in WORKER_INSTRUCTION


def create_account(client: TestClient, email: str, name: str) -> dict[str, str]:
    response = client.post("/accounts", json={"email": email, "password": "password-123", "name": name})
    assert response.status_code == 201
    return response.json()


def account_headers(account_id: str) -> dict[str, str]:
    return {"X-Front-Desk-Account": account_id, "X-Front-Desk-Internal-Secret": "test-internal-secret"}
