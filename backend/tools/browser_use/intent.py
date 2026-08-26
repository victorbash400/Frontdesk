import json
import logging
from typing import Any

from google.adk.tools import BaseTool, ToolContext


logger = logging.getLogger("uvicorn.error")


def describe_browser_action(name: str, args: dict[str, Any]) -> str:
    target = next((str(args[key]).strip() for key in ("element", "url", "text") if args.get(key)), "")
    if name == "browser_navigate":
        return f"Opening {target or 'the page'}"
    if name in {"browser_snapshot", "browser_find"}:
        return f"Reading {target or 'the page'}"
    if name == "browser_click":
        return f"Clicking {target or 'the page control'}"
    if name in {"browser_type", "browser_fill_form"}:
        return f"Typing in {target or 'the page'}"
    if name == "browser_select_option":
        return f"Selecting {target or 'an option'}"
    if name == "browser_press_key":
        return "Using the keyboard"
    if name == "browser_tabs":
        return "Checking browser tabs"
    if name == "browser_wait_for":
        return "Waiting for the page"
    return name.removeprefix("browser_").replace("_", " ").capitalize()


async def show_browser_intent(tool: BaseTool, args: dict[str, Any], tool_context: ToolContext) -> None:
    if not tool.name.startswith("browser_") or tool.name == "browser_evaluate":
        return
    session_manager = getattr(tool, "_mcp_session_manager", None)
    if session_manager is None:
        logger.warning("browser_intent tool=%s status=missing_session", tool.name)
        return
    message = describe_browser_action(tool.name, args)
    intent = str(tool_context.state.get("goal_intent") or "").strip()
    payload = json.dumps({"type": "frontDeskBrowserIntent", "message": message, "intent": intent})
    function = f"() => window.postMessage({payload}, '*')"
    try:
        session = await session_manager.create_session()
        result = await session.call_tool("browser_evaluate", arguments={"function": function})
        if result.isError:
            logger.warning("browser_intent tool=%s status=rejected", tool.name)
    except Exception as error:
        logger.warning("browser_intent tool=%s status=failed error=%s", tool.name, error)
