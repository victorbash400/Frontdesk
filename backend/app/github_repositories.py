import json

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import GitHubRepositoryAccess, PluginConnection
from .secret_store import decrypt_secret


GITHUB_API = "https://api.github.com"
GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


async def repository_access(session: Session, account_id: str) -> dict[str, object]:
    token = _access_token(session, account_id)
    repositories = await _repositories(token)
    selected = set(session.scalars(select(GitHubRepositoryAccess.full_name).where(
        GitHubRepositoryAccess.account_id == account_id,
    )))
    return {
        "repositories": repositories,
        "selected": sorted(selected),
    }


async def set_repository_access(session: Session, account_id: str, selected: list[str]) -> dict[str, object]:
    token = _access_token(session, account_id)
    repositories = await _repositories(token)
    available = {repository["full_name"] for repository in repositories}
    requested = set(selected)
    unavailable = sorted(requested - available)
    if unavailable:
        raise ValueError(f"Repository access is unavailable for: {', '.join(unavailable)}")
    session.execute(delete(GitHubRepositoryAccess).where(GitHubRepositoryAccess.account_id == account_id))
    session.add_all(GitHubRepositoryAccess(account_id=account_id, full_name=full_name) for full_name in sorted(requested))
    session.commit()
    return {
        "repositories": repositories,
        "selected": sorted(requested),
    }


def repository_is_allowed(session: Session, account_id: str, owner: str, repository: str) -> bool:
    full_name = f"{owner}/{repository}".casefold()
    allowed = session.scalars(select(GitHubRepositoryAccess.full_name).where(
        GitHubRepositoryAccess.account_id == account_id,
    ))
    return any(candidate.casefold() == full_name for candidate in allowed)


def _access_token(session: Session, account_id: str) -> str:
    connection = session.scalar(select(PluginConnection).where(
        PluginConnection.account_id == account_id,
        PluginConnection.plugin_id == "github",
    ))
    if not connection:
        raise ValueError("Connect GitHub before choosing repositories.")
    credentials = json.loads(decrypt_secret(connection.credentials))
    token = credentials.get("tokens", {}).get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("The GitHub connection does not contain an access token.")
    return token


async def _repositories(access_token: str) -> list[dict[str, object]]:
    repositories: list[dict[str, object]] = []
    url: str | None = f"{GITHUB_API}/user/repos"
    params = {"affiliation": "owner,collaborator,organization_member", "per_page": "100", "sort": "full_name"}
    headers = {**GITHUB_HEADERS, "Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
        while url:
            response = await client.get(url, params=params if not repositories else None, headers=headers)
            if response.is_error:
                raise RuntimeError(_github_error(response))
            payload = response.json()
            if not isinstance(payload, list):
                raise RuntimeError("GitHub returned an invalid repository list.")
            for item in payload:
                if not isinstance(item, dict) or not isinstance(item.get("full_name"), str):
                    raise RuntimeError("GitHub returned an invalid repository entry.")
                repositories.append({
                    "full_name": item["full_name"],
                    "private": bool(item.get("private")),
                })
            url = response.links.get("next", {}).get("url")
    return repositories


def _github_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return "GitHub repositories could not be loaded."
    message = payload.get("message") if isinstance(payload, dict) else None
    return str(message) if message else "GitHub repositories could not be loaded."
