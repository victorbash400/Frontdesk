import os
from pathlib import Path

from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

from app.config import PROJECT_ROOT, get_settings


PLAYWRIGHT_MCP_BINARY = PROJECT_ROOT / "node_modules" / ".bin" / "playwright-mcp"
PLAYWRIGHT_OUTPUT_DIR = PROJECT_ROOT / "backend" / ".browser-artifacts"
BROWSER_COMMAND_TIMEOUT_SECONDS = 60
PLAYWRIGHT_ALLOWED_TOOLS = [
    "browser_click",
    "browser_close",
    "browser_console_messages",
    "browser_drag",
    "browser_drop",
    "browser_evaluate",
    "browser_file_upload",
    "browser_fill_form",
    "browser_find",
    "browser_handle_dialog",
    "browser_hover",
    "browser_navigate",
    "browser_navigate_back",
    "browser_network_request",
    "browser_network_requests",
    "browser_press_key",
    "browser_resize",
    "browser_select_option",
    "browser_snapshot",
    "browser_tabs",
    "browser_type",
    "browser_wait_for",
]


async def connected_playwright_toolset(account_id: str | None = None) -> McpToolset:
    """Prove Chrome can answer a command before a model invocation starts."""
    toolset = create_playwright_toolset(account_id)
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
    except Exception as error:
        await toolset.close()
        detail = str(error).strip() or type(error).__name__
        raise RuntimeError(f"Browser Use connection failed: {detail}") from error
    if not tools:
        await toolset.close()
        raise RuntimeError("Browser Use connected without exposing browser tools.")
    toolset.front_desk_tool_names = tuple(tool.name for tool in tools)
    return toolset


async def capture_browser_preview(toolset: McpToolset, assignment_id: str) -> bytes:
    """Capture the controlled tab into a stable task-scoped image."""
    filename = f"goal-{assignment_id}.png"
    tools = await toolset.get_tools()
    screenshot_tool = next((tool for tool in tools if tool.name == "browser_take_screenshot"), None)
    if screenshot_tool is None:
        raise RuntimeError("Browser Use did not expose browser_take_screenshot.")
    session = await screenshot_tool._mcp_session_manager.create_session()  # type: ignore[attr-defined]
    result = await session.call_tool("browser_take_screenshot", arguments={"type": "png", "filename": filename})
    if result.isError:
        message = " ".join(getattr(item, "text", "") for item in result.content).strip()
        raise RuntimeError(message or "Chrome rejected the browser preview capture.")
    preview_path = PLAYWRIGHT_OUTPUT_DIR / filename
    if not preview_path.is_file():
        raise RuntimeError("Browser Use did not write the preview image.")
    return preview_path.read_bytes()


def create_playwright_toolset(account_id: str | None = None) -> McpToolset:
    binary = _playwright_binary()
    settings = get_settings()
    PLAYWRIGHT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    if settings.browser_cloud_relay:
        if not account_id:
            raise RuntimeError("Cloud Browser Use requires an account identity.")
        environment.pop("PLAYWRIGHT_MCP_EXTENSION_TOKEN", None)
        environment.pop("PLAYWRIGHT_MCP_PROFILE_DIRECTORY", None)
        environment["FRONT_DESK_BROWSER_CONNECT_URL"] = f"http://127.0.0.1:{os.environ.get('PORT', '8000')}/internal/browser/connections"
        environment["FRONT_DESK_BROWSER_ACCOUNT_ID"] = account_id
        environment["FRONT_DESK_INTERNAL_SECRET"] = settings.internal_secret
    else:
        token = settings.playwright_extension_token
        if not token:
            raise RuntimeError("Browser Use is missing its extension connection token.")
        environment["PLAYWRIGHT_MCP_EXTENSION_TOKEN"] = token
        profile_directory = settings.playwright_profile_directory.strip()
        if not profile_directory:
            raise RuntimeError("Browser Use is missing its Chrome profile directory.")
        environment["PLAYWRIGHT_MCP_PROFILE_DIRECTORY"] = profile_directory
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=str(binary),
                args=[
                    "--extension",
                    "--browser",
                    "chrome",
                    "--snapshot-boxes",
                    "--output-dir",
                    str(PLAYWRIGHT_OUTPUT_DIR),
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
        tool_filter=PLAYWRIGHT_ALLOWED_TOOLS,
        use_mcp_resources=False,
    )


def _playwright_binary() -> Path:
    if not PLAYWRIGHT_MCP_BINARY.is_file():
        raise RuntimeError("Playwright MCP is not installed. Run `pnpm install` from the Front Desk root.")
    return PLAYWRIGHT_MCP_BINARY
