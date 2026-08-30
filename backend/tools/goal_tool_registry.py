import asyncio
from typing import Any

from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools import FunctionTool, ToolContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.base_toolset import BaseToolset

from app.database import SessionLocal
from app.models import OAuthConnection
from meetings.tools import create_client_meeting, create_instant_client_meeting, join_client_meeting, wait_for_client_in_meeting
from sqlalchemy import select
from tools.aqualabs_store import configured_aqualabs_store_toolset
from tools.browser_use import capture_browser_preview, connected_playwright_toolset
from tools.external_plugins import connected_external_plugin_toolset
from tools.workspace import preflight_workspace, workspace_tools


LOADED_GOAL_TOOL_IDS = "loaded_goal_tool_ids"
CAPABILITY_DESCRIPTIONS = {
    "aqualabs-store": "Inspect and update AquaLabs customers, orders, billing, and support cases.",
    "atlassian": "Inspect and update Jira and Confluence.",
    "browser-use": "Operate the connected Chrome browser.",
    "github": "Inspect and update enabled GitHub repositories and issues.",
    "workspace.api": "Use an enabled Google Workspace API when no specialized namespace covers it.",
    "workspace.calendar-meet": "Create and inspect Calendar events and Google Meet calls.",
    "workspace.docs": "Read and create Google Docs.",
    "workspace.drive": "Search Google Drive files.",
    "workspace.gmail": "Search, read, draft, send, reply to, organize, or trash Gmail messages.",
    "slack": "Read or post Slack messages when the task explicitly requires Slack.",
    "titan-mail": "Read or reply in the customer email thread already attached to this goal.",
    "vercel": "Inspect and manage the connected Vercel project.",
}


class GoalToolRegistry(BaseToolset):
    """Expose a compact capability loader and materialize only selected namespaces."""

    def __init__(self, account_id: str, allowed_ids: list[str], initial_ids: list[str], titan_functions: list[FunctionTool]) -> None:
        super().__init__()
        self._use_invocation_cache = False
        self._account_id = account_id
        self._allowed_ids = tuple(dict.fromkeys(allowed_ids))
        self._recommended_ids = tuple(item for item in dict.fromkeys(initial_ids) if item in self._allowed_ids)
        self._titan_functions = titan_functions
        self._load_tool = FunctionTool(self.load_goal_tools)
        self._tools: dict[str, list[BaseTool]] = {}
        self._toolsets: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    @property
    def directory_prompt(self) -> str:
        if not self._allowed_ids:
            return "No plugin namespaces are available for this goal."
        return "\n".join(
            f"- `{tool_id}`{' (recommended for this task)' if tool_id in self._recommended_ids else ''}: {CAPABILITY_DESCRIPTIONS.get(tool_id, f'Use the connected {tool_id} plugin.')}"
            for tool_id in self._allowed_ids
        )

    async def load_goal_tools(self, tool_ids: list[str], tool_context: ToolContext) -> dict[str, object]:
        """Load exact plugin namespace IDs from the capability directory."""
        unknown = [tool_id for tool_id in tool_ids if tool_id not in self._allowed_ids]
        if unknown:
            return {
                "status": "not_found",
                "unknown_ids": unknown,
                "guidance": "Use only exact namespace IDs from the capability directory.",
            }
        try:
            for tool_id in tool_ids:
                await self._namespace_tools(tool_id)
        except Exception as error:
            return {"status": "failed", "error": str(error).strip() or type(error).__name__}
        loaded = list(tool_context.state.get(LOADED_GOAL_TOOL_IDS, []))
        for tool_id in tool_ids:
            if tool_id not in loaded:
                loaded.append(tool_id)
        tool_context.state[LOADED_GOAL_TOOL_IDS] = loaded
        return {
            "status": "loaded",
            "loaded_tool_ids": loaded,
            "next": "The selected tools are available on the next model step.",
        }

    async def get_tools(self, readonly_context: ReadonlyContext | None = None) -> list[BaseTool]:
        loaded = list(readonly_context.state.get(LOADED_GOAL_TOOL_IDS, [])) if readonly_context else []
        tools: list[BaseTool] = [self._load_tool]
        for tool_id in loaded:
            tools.extend(await self._namespace_tools(tool_id))
        _require_unique_names(tools)
        return tools

    async def capture_browser_preview(self, assignment_id: str) -> bytes | None:
        browser = self._toolsets.get("browser-use")
        if browser is None:
            return None
        return await capture_browser_preview(browser, assignment_id)

    async def close(self) -> None:
        for toolset in self._toolsets.values():
            await toolset.close()
        self._toolsets.clear()
        self._tools.clear()

    async def _namespace_tools(self, tool_id: str) -> list[BaseTool]:
        cached = self._tools.get(tool_id)
        if cached is not None:
            return cached
        async with self._lock:
            cached = self._tools.get(tool_id)
            if cached is not None:
                return cached
            tools = await self._connect_namespace(tool_id)
            self._tools[tool_id] = tools
            return tools

    async def _connect_namespace(self, tool_id: str) -> list[BaseTool]:
        if tool_id == "titan-mail":
            return list(self._titan_functions)
        if tool_id.startswith("workspace."):
            with SessionLocal() as session:
                connected = session.scalar(select(OAuthConnection.id).where(
                    OAuthConnection.account_id == self._account_id,
                    OAuthConnection.provider == "google_workspace",
                )) is not None
            if not connected:
                raise RuntimeError("Google Workspace is not connected.")
            await preflight_workspace(self._account_id)
            workspace = workspace_tools(self._account_id)
            if tool_id == "workspace.gmail":
                return [tool for tool in workspace if tool.name.startswith("workspace_gmail_")]
            if tool_id == "workspace.drive":
                return [tool for tool in workspace if tool.name == "workspace_drive_search"]
            if tool_id == "workspace.docs":
                return [tool for tool in workspace if tool.name in {"workspace_drive_search", "workspace_docs_read", "workspace_docs_create"}]
            if tool_id == "workspace.calendar-meet":
                return [FunctionTool(create_client_meeting), FunctionTool(create_instant_client_meeting), FunctionTool(join_client_meeting), FunctionTool(wait_for_client_in_meeting), *[tool for tool in workspace if tool.name == "workspace_google_api_request"]]
            if tool_id == "workspace.api":
                return [tool for tool in workspace if tool.name == "workspace_google_api_request"]
        if tool_id == "browser-use":
            toolset = await connected_playwright_toolset()
        elif tool_id == "aqualabs-store":
            toolset = await configured_aqualabs_store_toolset()
        else:
            toolset = await connected_external_plugin_toolset(self._account_id, tool_id)
        self._toolsets[tool_id] = toolset
        return list(await toolset.get_tools_with_prefix(None))


def _require_unique_names(tools: list[BaseTool]) -> None:
    names = [tool.name for tool in tools]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise RuntimeError(f"Selected plugins expose duplicate tool names: {', '.join(duplicates)}")
