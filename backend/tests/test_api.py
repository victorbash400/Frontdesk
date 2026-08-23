import os
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

test_directory = TemporaryDirectory()
os.environ["OPERATOR_DATABASE_URL"] = f"sqlite:///{test_directory.name}/operator.db"
os.environ["OPERATOR_INTERNAL_SECRET"] = "test-internal-secret"

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
        response = client.post("/accounts/authenticate", json={"email": "demo@operator.local", "password": "operator-demo"})
        assert response.status_code == 200
        assert response.json()["name"] == "Demo"


def create_account(client: TestClient, email: str, name: str) -> dict[str, str]:
    response = client.post("/accounts", json={"email": email, "password": "password-123", "name": name})
    assert response.status_code == 201
    return response.json()


def account_headers(account_id: str) -> dict[str, str]:
    return {"X-Operator-Account": account_id, "X-Operator-Internal-Secret": "test-internal-secret"}
