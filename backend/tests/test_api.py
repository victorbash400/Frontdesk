import asyncio
import base64
import json
import os
from email import message_from_bytes
from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

test_directory = TemporaryDirectory()
os.environ["FRONT_DESK_DATABASE_URL"] = f"sqlite:///{test_directory.name}/front-desk.db"
os.environ["FRONT_DESK_AGENT_SESSION_DATABASE_URL"] = f"sqlite+aiosqlite:///{test_directory.name}/front-desk-sessions.db"
os.environ["FRONT_DESK_INTERNAL_SECRET"] = "test-internal-secret"

from app.main import app
from app.database import SessionLocal
from app.goal_tasks import GoalTaskManager
from app.goals import create_notification
from app.models import GitHubRepositoryAccess, Goal, GoalAssignment, GoalAutomation, PluginInstallation
from app.voice import VOICE_MODEL, VOICE_TOOLS, verify_voice_ticket
from tools import workspace
from tools.browser_use import playwright as playwright_browser
from tools.tool_failures import begin_single_tool, finish_single_tool


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


def test_goal_tool_preflight_failure_never_creates_gemini_runner() -> None:
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
    runner = MagicMock()
    with patch("app.goal_tasks.connected_playwright_toolset", new=AsyncMock(side_effect=RuntimeError("Chrome extension is not connected."))), patch.object(manager, "_runner", runner):
        asyncio.run(manager._run(account["id"], goal["id"]))

    runner.assert_not_called()
    with SessionLocal() as session:
        assignment = session.query(GoalAssignment).filter_by(goal_id=goal["id"]).one()
        assert assignment.status == "failed"
        assert assignment.report == "Chrome extension is not connected."


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

        with patch.object(manager, "_preflight", new=wait_in_preflight):
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
        with patch.object(manager, "_preflight", new=AsyncMock(return_value=([], []))), patch.object(manager, "_runner", return_value=RunnerWithoutCompletion()):
            await manager._run(account["id"], goal["id"])

    asyncio.run(exercise())
    with SessionLocal() as session:
        assignment = session.query(GoalAssignment).filter_by(goal_id=goal["id"]).one()
        assert assignment.status == "failed"
        assert assignment.report == "The worker stopped without explicitly completing the goal."


def test_goal_worker_rejects_parallel_calls_and_stops_after_failure() -> None:
    tool = MagicMock(name="browser_tabs")
    tool.name = "browser_tabs"
    context = MagicMock()
    context.state = {}
    context.actions = MagicMock()

    assert begin_single_tool(tool, {}, context) is None
    rejected = begin_single_tool(tool, {}, context)
    assert rejected == {"status": "failed", "error": "Parallel tool call rejected: browser_tabs."}
    assert context.actions.end_of_agent is True

    context.state = {"goal_tool_in_flight": True}
    finish_single_tool(tool, {}, context, {"status": "failed", "error": "timeout"})
    assert context.state["goal_tool_in_flight"] is False
    assert context.state["goal_terminal_tool_error"] is True


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


def create_account(client: TestClient, email: str, name: str) -> dict[str, str]:
    response = client.post("/accounts", json={"email": email, "password": "password-123", "name": name})
    assert response.status_code == 201
    return response.json()


def account_headers(account_id: str) -> dict[str, str]:
    return {"X-Front-Desk-Account": account_id, "X-Front-Desk-Internal-Secret": "test-internal-secret"}
