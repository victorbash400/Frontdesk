import os
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

test_directory = TemporaryDirectory()
os.environ["OPERATOR_DATABASE_URL"] = f"sqlite:///{test_directory.name}/operator.db"

from app.main import app


def test_client_folder_lifecycle() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}

        created = client.post("/api/nodes", json={"name": "Aster Bakery", "kind": "client"})
        assert created.status_code == 201
        client_id = created.json()["id"]

        folder = client.post("/api/nodes", json={"name": "Calls", "kind": "folder", "parent_id": client_id})
        assert folder.status_code == 201

        listed = client.get("/api/nodes", params={"parent_id": client_id})
        assert [item["name"] for item in listed.json()] == ["Calls"]

        renamed = client.patch(f"/api/nodes/{client_id}", json={"name": "Aster"})
        assert renamed.status_code == 200
        assert renamed.json()["name"] == "Aster"

        trashed = client.post(f"/api/nodes/{client_id}/trash")
        assert trashed.status_code == 200
        assert trashed.json()["trashed_at"] is not None
