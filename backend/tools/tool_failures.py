from typing import Any

from google.adk.tools import BaseTool, ToolContext

from tools.browser_use.intent import show_browser_intent


async def begin_single_tool(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
) -> dict[str, str] | None:
    if tool_context.state.get("goal_tool_in_flight"):
        return {"status": "failed", "error": f"Parallel tool call rejected: {tool.name}. Call one tool at a time."}
    tool_context.state["goal_tool_in_flight"] = True
    await show_browser_intent(tool, args, tool_context)
    return None


def finish_single_tool(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    tool_response: dict[str, Any],
) -> dict[str, Any] | None:
    del args
    tool_context.state["goal_tool_in_flight"] = False
    if tool.name == "update_goal_progress":
        next_step = str(tool_response.get("next_step") or "").strip()
        message = str(tool_response.get("message") or "").strip()
        tool_context.state["goal_intent"] = next_step or message
    return None


def stop_on_tool_error(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    error: Exception,
) -> dict[str, str]:
    del args
    tool_context.state["goal_tool_in_flight"] = False
    return {"status": "failed", "error": f"{tool.name} failed: {error}"}
