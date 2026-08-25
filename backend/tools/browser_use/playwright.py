import os
from pathlib import Path

from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

from app.config import PROJECT_ROOT, get_settings


PLAYWRIGHT_MCP_BINARY = PROJECT_ROOT / "node_modules" / ".bin" / "playwright-mcp"
PLAYWRIGHT_OUTPUT_DIR = PROJECT_ROOT / "backend" / ".browser-artifacts"
BROWSER_COMMAND_TIMEOUT_SECONDS = 5
async def connected_playwright_toolset() -> McpToolset:
    """Prove Chrome can answer a command before a model invocation starts."""
    toolset = create_playwright_toolset()
    try:
        tools = await toolset.get_tools()
        tabs_tool = next((tool for tool in tools if tool.name == "browser_tabs"), None)
        if tabs_tool is None:
            raise RuntimeError("Browser Use did not expose browser_tabs.")
        session = await tabs_tool._mcp_session_manager.create_session()  # type: ignore[attr-defined]
        result = await session.call_tool("browser_tabs", arguments={"action": "list"})
        if result.isError:
            message = " ".join(getattr(item, "text", "") for item in result.content).strip()
            raise RuntimeError(message or "Chrome rejected the browser preflight command.")
    except Exception:
        await toolset.close()
        raise RuntimeError("Browser Use is not connected to the Front Desk extension.") from None
    if not tools:
        await toolset.close()
        raise RuntimeError("Browser Use connected without exposing browser tools.")
    return toolset


def create_playwright_toolset() -> McpToolset:
    binary = _playwright_binary()
    token = get_settings().playwright_extension_token
    if not token:
        raise RuntimeError("Browser Use is missing its extension connection token.")
    PLAYWRIGHT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment["PLAYWRIGHT_MCP_EXTENSION_TOKEN"] = token
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=str(binary),
                args=[
                    "--extension",
                    "--browser",
                    "chrome",
                    "--snapshot-boxes",
                    "--image-responses",
                    "omit",
                    "--codegen",
                    "none",
                    "--timeout-settle",
                    "250",
                ],
                env=environment,
            ),
            timeout=BROWSER_COMMAND_TIMEOUT_SECONDS,
        ),
        use_mcp_resources=False,
    )


def _playwright_binary() -> Path:
    if not PLAYWRIGHT_MCP_BINARY.is_file():
        raise RuntimeError("Playwright MCP is not installed. Run `pnpm install` from the Front Desk root.")
    return PLAYWRIGHT_MCP_BINARY
