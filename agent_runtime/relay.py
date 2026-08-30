"""Keep connected plugin execution in the authenticated Cloud Run tool relay."""

import os
from typing import Any
from urllib.parse import urlparse

import httpx
from google.adk.tools import ToolContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.base_toolset import BaseToolset
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field


MANIFEST_STATE = "temp:front_desk_manifest"


class RunManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction: str = Field(min_length=1)
    model: str = Field(min_length=1)
    generation_config: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] | None = None
    tools: list[dict[str, Any]] = Field(default_factory=list)


async def relay_request(context, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
    origin = str(context.state.get("temp:front_desk_tool_relay_url") or os.environ["FRONT_DESK_TOOL_RELAY_URL"]).rstrip("/")
    parsed = urlparse(origin)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RuntimeError("Agent Engine requires an HTTPS tool relay URL.")
    run_id = context.state.get("temp:front_desk_run_id")
    ticket = context.state.get("temp:front_desk_run_ticket")
    if not run_id or not ticket:
        raise RuntimeError("The scoped Front Desk tool run is missing.")
    async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=15)) as client:
        response = await client.post(
            f"{origin}/internal/agent-runs/{run_id}/{operation}",
            headers={
                "X-Front-Desk-Agent-Secret": os.environ["FRONT_DESK_INTERNAL_SECRET"],
                "Authorization": f"Bearer {ticket}",
            },
            json=payload,
        )
        response.raise_for_status()
        result = response.json()
    if not isinstance(result, dict):
        raise RuntimeError("The Front Desk tool relay returned an invalid response.")
    return result


def declarations(manifest: RunManifest) -> list[types.FunctionDeclaration]:
    parsed = [types.FunctionDeclaration.model_validate(item) for item in manifest.tools]
    names = [item.name for item in parsed]
    if any(not name for name in names) or len(names) != len(set(names)):
        raise RuntimeError("The Front Desk tool manifest contains missing or duplicate names.")
    return parsed


class RemoteTool(BaseTool):
    def __init__(self, declaration: types.FunctionDeclaration) -> None:
        super().__init__(name=declaration.name, description=declaration.description or "")
        self.declaration = declaration

    def _get_declaration(self) -> types.FunctionDeclaration:
        return self.declaration

    async def run_async(self, *, args: dict[str, Any], tool_context: ToolContext) -> Any:
        response = await relay_request(tool_context, "call", {
            "name": self.name,
            "call_id": tool_context.function_call_id,
            "args": args,
            "state": {key: value for key, value in tool_context.state.to_dict().items() if not key.startswith("temp:")},
        })
        if "result" not in response:
            raise RuntimeError("The Front Desk tool relay omitted the tool result.")
        # Apply the same state changes and stop signal as the local ADK tool.
        for key, value in response.get("state_delta", {}).items():
            if key.startswith("temp:"):
                raise RuntimeError("A tool attempted to overwrite runtime credentials.")
            tool_context.state[key] = value
        if response.get("end_of_agent"):
            tool_context.actions.end_of_agent = True
            tool_context.actions.skip_summarization = True
        if "manifest" in response:
            manifest = RunManifest.model_validate(response["manifest"])
            declarations(manifest)
            tool_context.state[MANIFEST_STATE] = manifest.model_dump()
        return response["result"]


class RemoteToolset(BaseToolset):
    def __init__(self) -> None:
        super().__init__()
        self._use_invocation_cache = False

    async def get_tools(self, readonly_context=None) -> list[BaseTool]:
        if readonly_context is None:
            raise RuntimeError("Front Desk tool discovery requires a scoped invocation.")
        manifest = RunManifest.model_validate(readonly_context.state[MANIFEST_STATE])
        return [RemoteTool(item) for item in declarations(manifest)]

    async def close(self) -> None:
        pass
