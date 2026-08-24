from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import PluginConnection, PluginInstallation, PluginOAuthAttempt


BUILTIN_PLUGIN_IDS = ("code", "web-search")
EXTERNAL_PLUGIN_IDS = ("notion", "linear", "atlassian", "vercel", "github", "slack")
PLUGIN_IDS = frozenset((*BUILTIN_PLUGIN_IDS, *EXTERNAL_PLUGIN_IDS))


def plugin_snapshot(session: Session, account_id: str, connection_support: dict[str, tuple[bool, str | None]]) -> dict[str, object]:
    installed_ids = set(session.scalars(select(PluginInstallation.plugin_id).where(PluginInstallation.account_id == account_id)))
    installed_ids.update(BUILTIN_PLUGIN_IDS)
    connections = {
        connection.plugin_id: connection
        for connection in session.scalars(select(PluginConnection).where(PluginConnection.account_id == account_id))
    }
    return {
        "plugins": [
            _plugin_state(plugin_id, plugin_id in installed_ids, connections.get(plugin_id), connection_support)
            for plugin_id in (*BUILTIN_PLUGIN_IDS, *EXTERNAL_PLUGIN_IDS)
        ]
    }


def install_plugin(session: Session, account_id: str, plugin_id: str) -> None:
    _require_plugin(plugin_id)
    if plugin_id in BUILTIN_PLUGIN_IDS:
        return
    installation = session.scalar(select(PluginInstallation).where(
        PluginInstallation.account_id == account_id,
        PluginInstallation.plugin_id == plugin_id,
    ))
    if not installation:
        session.add(PluginInstallation(account_id=account_id, plugin_id=plugin_id))
        session.commit()


def uninstall_plugin(session: Session, account_id: str, plugin_id: str) -> None:
    _require_plugin(plugin_id)
    if plugin_id in BUILTIN_PLUGIN_IDS:
        raise ValueError("Built-in plugins cannot be removed.")
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
    connection_support: dict[str, tuple[bool, str | None]],
) -> dict[str, object]:
    built_in = plugin_id in BUILTIN_PLUGIN_IDS
    supported, setup_message = connection_support.get(plugin_id, (False, None))
    return {
        "id": plugin_id,
        "installed": installed,
        "connected": built_in or connection is not None,
        "built_in": built_in,
        "connection_supported": built_in or supported,
        "setup_message": setup_message,
        "account_label": connection.account_label if connection else None,
        "tool_count": connection.tool_count if connection else 0,
    }


def _require_plugin(plugin_id: str) -> None:
    if plugin_id not in PLUGIN_IDS:
        raise ValueError("Unknown plugin.")
