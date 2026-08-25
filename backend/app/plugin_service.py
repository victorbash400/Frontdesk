from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import GitHubRepositoryAccess, OAuthConnection, PluginConnection, PluginInstallation, PluginOAuthAttempt, PluginPermission


EXTERNAL_PLUGIN_IDS = ("notion", "linear", "atlassian", "vercel", "github", "slack")
DIRECTORY_ONLY_PLUGIN_IDS = ("browser-use",)
PLUGIN_IDS = ("google-workspace", *EXTERNAL_PLUGIN_IDS, *DIRECTORY_ONLY_PLUGIN_IDS)
PLUGIN_FEATURES = {
    "github": (
        ("github.repositories", "Repositories", "Read and work with selected repositories"),
        ("github.issues", "Issues", "Read and update repository issues"),
        ("github.pull-requests", "Pull requests", "Read and work with pull requests"),
    ),
    "atlassian": (
        ("atlassian.jira", "Jira", "Read and update Jira work"),
        ("atlassian.confluence", "Confluence", "Read and update Confluence pages"),
    ),
    "slack": (
        ("slack.channels", "Channels", "Search connected Slack channels"),
        ("slack.messages", "Messages", "Read and work with Slack messages"),
    ),
}


def plugin_snapshot(session: Session, account_id: str, connection_support: dict[str, tuple[bool, str | None]]) -> dict[str, object]:
    installed_ids = set(session.scalars(select(PluginInstallation.plugin_id).where(PluginInstallation.account_id == account_id)))
    connections = {
        connection.plugin_id: connection
        for connection in session.scalars(select(PluginConnection).where(PluginConnection.account_id == account_id))
    }
    github_repository_count = len(list(session.scalars(select(GitHubRepositoryAccess.id).where(
        GitHubRepositoryAccess.account_id == account_id,
    ))))
    permission_rows = {
        permission.permission_id: permission.enabled
        for permission in session.scalars(select(PluginPermission).where(PluginPermission.account_id == account_id))
    }
    google_connection = session.scalar(select(OAuthConnection).where(
        OAuthConnection.account_id == account_id,
        OAuthConnection.provider == "google_workspace",
    ))
    return {
        "plugins": [
            _plugin_state(plugin_id, plugin_id in installed_ids, connections.get(plugin_id), google_connection, connection_support, github_repository_count, permission_rows)
            for plugin_id in PLUGIN_IDS
        ]
    }


def install_plugin(session: Session, account_id: str, plugin_id: str) -> None:
    _require_plugin(plugin_id)
    if plugin_id in DIRECTORY_ONLY_PLUGIN_IDS:
        raise ValueError("This plugin is not available yet.")
    installation = session.scalar(select(PluginInstallation).where(
        PluginInstallation.account_id == account_id,
        PluginInstallation.plugin_id == plugin_id,
    ))
    if not installation:
        session.add(PluginInstallation(account_id=account_id, plugin_id=plugin_id))
        session.commit()


def uninstall_plugin(session: Session, account_id: str, plugin_id: str) -> None:
    _require_plugin(plugin_id)
    if plugin_id == "google-workspace":
        session.execute(delete(OAuthConnection).where(
            OAuthConnection.account_id == account_id,
            OAuthConnection.provider == "google_workspace",
        ))
    session.execute(delete(PluginConnection).where(
        PluginConnection.account_id == account_id,
        PluginConnection.plugin_id == plugin_id,
    ))
    session.execute(delete(PluginOAuthAttempt).where(
        PluginOAuthAttempt.account_id == account_id,
        PluginOAuthAttempt.plugin_id == plugin_id,
    ))
    if plugin_id == "github":
        session.execute(delete(GitHubRepositoryAccess).where(GitHubRepositoryAccess.account_id == account_id))
    feature_ids = [permission_id for permission_id, _, _ in PLUGIN_FEATURES.get(plugin_id, ())]
    if feature_ids:
        session.execute(delete(PluginPermission).where(
            PluginPermission.account_id == account_id,
            PluginPermission.permission_id.in_(feature_ids),
        ))
    session.execute(delete(PluginInstallation).where(
        PluginInstallation.account_id == account_id,
        PluginInstallation.plugin_id == plugin_id,
    ))
    session.commit()


def _plugin_state(
    plugin_id: str,
    installed: bool,
    connection: PluginConnection | None,
    google_connection: OAuthConnection | None,
    connection_support: dict[str, tuple[bool, str | None]],
    github_repository_count: int,
    permission_rows: dict[str, bool],
) -> dict[str, object]:
    supported, setup_message = connection_support.get(plugin_id, (False, None))
    is_workspace = plugin_id == "google-workspace"
    is_extension = plugin_id in DIRECTORY_ONLY_PLUGIN_IDS
    connected = google_connection is not None if is_workspace else connection is not None
    return {
        "id": plugin_id,
        "installed": installed,
        "connected": installed and connected,
        "connection_type": "google" if is_workspace else "extension" if is_extension else "mcp",
        "connection_supported": True if is_workspace else supported,
        "setup_message": None if is_workspace else setup_message,
        "account_label": google_connection.email if is_workspace and google_connection else connection.account_label if connection else None,
        "tool_count": connection.tool_count if connection else 0,
        "repository_count": github_repository_count if plugin_id == "github" else None,
        "permissions": [
            {"id": permission_id, "name": name, "description": description, "enabled": permission_rows.get(permission_id, True)}
            for permission_id, name, description in PLUGIN_FEATURES.get(plugin_id, ())
        ],
    }


def set_plugin_permission(session: Session, account_id: str, plugin_id: str, permission_id: str, enabled: bool) -> None:
    valid_ids = {item[0] for item in PLUGIN_FEATURES.get(plugin_id, ())}
    if permission_id not in valid_ids:
        raise ValueError("Unknown plugin permission.")
    permission = session.scalar(select(PluginPermission).where(
        PluginPermission.account_id == account_id,
        PluginPermission.permission_id == permission_id,
    ))
    if permission:
        permission.enabled = enabled
    else:
        session.add(PluginPermission(account_id=account_id, permission_id=permission_id, enabled=enabled))
    session.commit()


def _require_plugin(plugin_id: str) -> None:
    if plugin_id not in PLUGIN_IDS:
        raise ValueError("Unknown plugin.")
