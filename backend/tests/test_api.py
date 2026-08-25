import os
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

test_directory = TemporaryDirectory()
os.environ["FRONT_DESK_DATABASE_URL"] = f"sqlite:///{test_directory.name}/front-desk.db"
os.environ["FRONT_DESK_AGENT_SESSION_DATABASE_URL"] = f"sqlite+aiosqlite:///{test_directory.name}/front-desk-sessions.db"
os.environ["FRONT_DESK_INTERNAL_SECRET"] = "test-internal-secret"

from app.main import app
from app.database import SessionLocal
from app.models import GitHubRepositoryAccess


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


def test_browser_use_is_directory_only() -> None:
    with TestClient(app) as client:
        account = create_account(client, "browser-plugin@example.com", "Browser Plugin")
        headers = account_headers(account["id"])
        plugins = {plugin["id"]: plugin for plugin in client.get("/api/plugins", headers=headers).json()["plugins"]}

        assert plugins["browser-use"]["connection_type"] == "extension"
        assert plugins["browser-use"]["connection_supported"] is False
        assert client.post("/api/plugins/browser-use", headers=headers).status_code == 404


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
