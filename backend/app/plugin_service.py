from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import OAuthConnection, PluginConnection, PluginInstallation, PluginOAuthAttempt


EXTERNAL_PLUGIN_IDS = ("notion", "linear", "atlassian", "vercel", "github", "slack")
PLUGIN_IDS = ("google-workspace", *EXTERNAL_PLUGIN_IDS)


def plugin_snapshot(session: Session, account_id: str, connection_support: dict[str, tuple[bool, str | None]]) -> dict[str, object]:
    installed_ids = set(session.scalars(select(PluginInstallation.plugin_id).where(PluginInstallation.account_id == account_id)))
    connections = {
        connection.plugin_id: connection
        for connection in session.scalars(select(PluginConnection).where(PluginConnection.account_id == account_id))
    }
    google_connection = session.scalar(select(OAuthConnection).where(
        OAuthConnection.account_id == account_id,
        OAuthConnection.provider == "google_workspace",
    ))
    return {
        "plugins": [
            _plugin_state(plugin_id, plugin_id in installed_ids, connections.get(plugin_id), google_connection, connection_support)
            for plugin_id in PLUGIN_IDS
        ]
    }


def install_plugin(session: Session, account_id: str, plugin_id: str) -> None:
    _require_plugin(plugin_id)
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
) -> dict[str, object]:
    supported, setup_message = connection_support.get(plugin_id, (False, None))
    is_workspace = plugin_id == "google-workspace"
    connected = google_connection is not None if is_workspace else connection is not None
    return {
        "id": plugin_id,
        "installed": installed,
        "connected": installed and connected,
        "connection_type": "google" if is_workspace else "mcp",
        "connection_supported": True if is_workspace else supported,
        "setup_message": None if is_workspace else setup_message,
        "account_label": google_connection.email if is_workspace and google_connection else connection.account_label if connection else None,
        "tool_count": connection.tool_count if connection else 0,
    }


def _require_plugin(plugin_id: str) -> None:
    if plugin_id not in PLUGIN_IDS:
        raise ValueError("Unknown plugin.")
