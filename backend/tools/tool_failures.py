from typing import Any

from google.adk.tools import BaseTool, ToolContext


def begin_single_tool(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
) -> dict[str, str] | None:
    del args
    if tool_context.state.get("goal_terminal_tool_error"):
        tool_context.actions.end_of_agent = True
        return {"status": "failed", "error": "The run already stopped after a tool failure."}
    if tool_context.state.get("goal_tool_in_flight"):
        tool_context.actions.end_of_agent = True
        tool_context.state["goal_terminal_tool_error"] = True
        return {"status": "failed", "error": f"Parallel tool call rejected: {tool.name}."}
    tool_context.state["goal_tool_in_flight"] = True
    return None


def finish_single_tool(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    tool_response: dict[str, Any],
) -> dict[str, Any] | None:
    del tool, args
    tool_context.state["goal_tool_in_flight"] = False
    if _failed(tool_response):
        tool_context.state["goal_terminal_tool_error"] = True
        tool_context.actions.end_of_agent = True
    return None


def stop_on_tool_error(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    error: Exception,
) -> dict[str, str]:
    del args
    tool_context.state["goal_tool_in_flight"] = False
    tool_context.state["goal_terminal_tool_error"] = True
    tool_context.actions.end_of_agent = True
    return {"status": "failed", "error": f"{tool.name} failed: {error}"}


def _failed(response: dict[str, Any]) -> bool:
    return bool(
        response.get("error")
        or response.get("isError")
        or response.get("status") in {"error", "failed"}
    )
