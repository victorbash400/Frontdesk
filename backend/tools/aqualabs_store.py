from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

from app.config import get_settings


MCP_COMMAND_TIMEOUT_SECONDS = 10


async def configured_aqualabs_store_toolset() -> McpToolset:
    settings = get_settings()
    if not settings.aqualabs_store_mcp_url or not settings.aqualabs_store_mcp_token:
        raise RuntimeError("Aqualabs Store MCP is not configured.")

    toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=settings.aqualabs_store_mcp_url,
            headers={"Authorization": f"Bearer {settings.aqualabs_store_mcp_token}"},
            timeout=MCP_COMMAND_TIMEOUT_SECONDS,
        ),
        use_mcp_resources=False,
    )
    try:
        tools = await toolset.get_tools()
    except Exception:
        await toolset.close()
        raise RuntimeError("Aqualabs Store MCP did not authenticate or return its tool list.") from None
    if not tools:
        await toolset.close()
        raise RuntimeError("Aqualabs Store MCP connected without exposing tools.")
    toolset.front_desk_tool_names = tuple(tool.name for tool in tools)
    return toolset
