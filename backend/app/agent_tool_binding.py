"""Execute the existing agent's tools and callbacks without copying business logic."""

import inspect
from typing import Any

from google.adk.agents.invocation_context import InvocationContext
from google.adk.tools import FunctionTool, ToolContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.base_toolset import BaseToolset


async def invoke_callbacks(callbacks, **kwargs):
    for callback in callbacks if isinstance(callbacks, list) else [callbacks] if callbacks else []:
        result = callback(**kwargs)
        if inspect.isawaitable(result):
            result = await result
        if result is not None:
            return result
    return None


class AgentToolBinding:
    def __init__(self, runner, session, run_id: str) -> None:
        self.agent = runner.agent
        self.session = session.model_copy(deep=True)
        self.session_service = runner.session_service
        self.run_id = run_id

    def context(self, call_id: str | None = None) -> ToolContext:
        return ToolContext(InvocationContext(
            agent=self.agent, session=self.session, session_service=self.session_service,
            invocation_id=self.run_id,
        ), function_call_id=call_id)

    async def tools(self, context: ToolContext) -> dict[str, BaseTool]:
        resolved = []
        for item in self.agent.tools:
            if isinstance(item, BaseToolset):
                resolved.extend(await item.get_tools_with_prefix(context))
            else:
                resolved.append(item if isinstance(item, BaseTool) else FunctionTool(item))
        tools = {tool.name: tool for tool in resolved}
        if len(tools) != len(resolved):
            raise RuntimeError("The selected tools contain duplicate function names.")
        return tools

    async def manifest(self) -> dict[str, Any]:
        context = self.context()
        instruction = self.agent.instruction
        if callable(instruction):
            instruction = instruction(context)
            if inspect.isawaitable(instruction):
                instruction = await instruction
        tools = await self.tools(context)
        return {
            "instruction": instruction,
            "model": self.agent.model if isinstance(self.agent.model, str) else self.agent.model.model,
            "generation_config": self.agent.generate_content_config.model_dump(mode="json", exclude_none=True) if self.agent.generate_content_config else {},
            "output_schema": self.agent.output_schema.model_json_schema() if self.agent.output_schema else None,
            "tools": [tool._get_declaration().model_dump(mode="json", exclude_none=True) for tool in tools.values()],
        }

    async def call(self, name: str, args: dict[str, Any], call_id: str) -> dict[str, Any]:
        context = self.context(call_id)
        tools = await self.tools(context)
        if name not in tools:
            return {"result": {"status": "failed", "error": f"Tool {name} is not loaded for this run."}}
        tool = tools[name]
        callback_args = {"tool": tool, "args": args, "tool_context": context}
        try:
            result = await invoke_callbacks(self.agent.before_tool_callback, **callback_args)
            if result is None:
                result = await tool.run_async(args=args, tool_context=context)
            replacement = await invoke_callbacks(self.agent.after_tool_callback, **callback_args, tool_response=result)
            if replacement is not None:
                result = replacement
        except Exception as error:
            result = await invoke_callbacks(self.agent.on_tool_error_callback, **callback_args, error=error)
            if result is None:
                result = {"status": "failed", "error": f"{name} failed: {str(error).strip() or type(error).__name__}"}
        self.session.state.update(context.state.to_dict())
        return {
            "result": result,
            "state_delta": context.actions.state_delta,
            "end_of_agent": bool(context.actions.end_of_agent),
            "manifest": await self.manifest(),
        }
