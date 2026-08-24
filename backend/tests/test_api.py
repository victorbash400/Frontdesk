import os
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

test_directory = TemporaryDirectory()
os.environ["FRONT_DESK_DATABASE_URL"] = f"sqlite:///{test_directory.name}/front-desk.db"
os.environ["FRONT_DESK_AGENT_SESSION_DATABASE_URL"] = f"sqlite+aiosqlite:///{test_directory.name}/front-desk-sessions.db"
os.environ["FRONT_DESK_INTERNAL_SECRET"] = "test-internal-secret"

from app.main import app


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
        assert initial_states["code"]["installed"] is True
        assert initial_states["code"]["connected"] is True
        assert initial_states["notion"]["installed"] is False

        installed = client.post("/api/plugins/notion", headers=first_headers)
        assert installed.status_code == 201
        assert {plugin["id"]: plugin for plugin in installed.json()["plugins"]}["notion"]["installed"] is True
        second_states = {plugin["id"]: plugin for plugin in client.get("/api/plugins", headers=second_headers).json()["plugins"]}
        assert second_states["notion"]["installed"] is False

        removed = client.delete("/api/plugins/notion", headers=first_headers)
        assert removed.status_code == 200
        assert {plugin["id"]: plugin for plugin in removed.json()["plugins"]}["notion"]["installed"] is False


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


def create_account(client: TestClient, email: str, name: str) -> dict[str, str]:
    response = client.post("/accounts", json={"email": email, "password": "password-123", "name": name})
    assert response.status_code == 201
    return response.json()


def account_headers(account_id: str) -> dict[str, str]:
    return {"X-Front-Desk-Account": account_id, "X-Front-Desk-Internal-Secret": "test-internal-secret"}
