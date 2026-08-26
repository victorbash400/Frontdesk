import asyncio
from types import SimpleNamespace

from app import github_repositories


def test_repository_token_uses_refresh_aware_plugin_credentials(monkeypatch) -> None:
    async def refreshed_token(account_id: str, plugin_id: str) -> str:
        assert account_id == "account-id"
        assert plugin_id == "github"
        return "refreshed-token"

    monkeypatch.setattr(github_repositories, "connected_external_plugin_access_token", refreshed_token)
    session = SimpleNamespace(scalar=lambda statement: object())

    assert asyncio.run(github_repositories._access_token(session, "account-id")) == "refreshed-token"
