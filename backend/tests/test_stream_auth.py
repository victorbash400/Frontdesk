from unittest.mock import MagicMock

from fastapi import Depends, FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from app.auth import require_account_id
from app.database import get_session


def test_authentication_releases_database_before_streaming():
    app = FastAPI()
    closed = []

    def session():
        try:
            yield MagicMock()
        finally:
            closed.append(True)

    app.dependency_overrides[get_session] = session

    @app.get("/stream")
    def stream(account: str = Depends(require_account_id)):
        async def events():
            assert closed == [True]
            yield account

        return StreamingResponse(events())

    with TestClient(app) as client:
        response = client.get("/stream", headers={
            "X-Front-Desk-Account": "test-account",
            "X-Front-Desk-Internal-Secret": "test-internal-secret",
        })
    assert response.status_code == 200
    assert response.text == "test-account"
