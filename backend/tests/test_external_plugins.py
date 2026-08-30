import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from tools.external_plugins import connected_external_plugin_toolset


def test_external_plugin_toolsets_do_not_register_duplicate_resource_loaders() -> None:
    connection = SimpleNamespace(id="connection-1", tool_count=1)
    credentials = {"server_url": "https://example.com/mcp", "tokens": {"access_token": "token"}}
    toolset = MagicMock()
    toolset.get_tools = AsyncMock(return_value=[SimpleNamespace(name="one_tool")])

    with (
        patch("tools.external_plugins._connection_credentials", new=AsyncMock(return_value=(connection, credentials))),
        patch("tools.external_plugins.McpToolset", return_value=toolset) as constructor,
    ):
        result = asyncio.run(connected_external_plugin_toolset("account-1", "slack"))

    assert result is toolset
    assert constructor.call_args.kwargs["use_mcp_resources"] is False
