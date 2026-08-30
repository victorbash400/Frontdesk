"""One ADK runtime; each scoped run receives its actual Front Desk agent definition."""

import os

from google.adk.agents import Agent
from google.adk.models import Gemini
from google.genai import types

from .relay import MANIFEST_STATE, RemoteToolset, RunManifest, declarations, relay_request


async def prepare_run(callback_context):
    response = await relay_request(callback_context, "manifest", {})
    manifest = RunManifest.model_validate(response)
    declarations(manifest)
    callback_context.state[MANIFEST_STATE] = manifest.model_dump()


def instruction(context) -> str:
    return RunManifest.model_validate(context.state[MANIFEST_STATE]).instruction


def configure_model(callback_context, llm_request):
    manifest = RunManifest.model_validate(callback_context.state[MANIFEST_STATE])
    configuration = types.GenerateContentConfig.model_validate(manifest.generation_config)
    if configuration.tools or configuration.system_instruction:
        raise RuntimeError("Model configuration must not replace the scoped tools or instruction.")
    llm_request.model = manifest.model
    updates = configuration.model_dump(exclude_unset=True)
    for key in updates:
        setattr(llm_request.config, key, getattr(configuration, key))
    if manifest.output_schema is not None:
        llm_request.config.response_mime_type = "application/json"
        llm_request.config.response_json_schema = manifest.output_schema


def tool_failed(tool, args, tool_context, error):
    del args
    tool_context.state["goal_tool_in_flight"] = False
    return {"status": "failed", "error": f"{tool.name} failed: {error}"}


def create_agent() -> Agent:
    return Agent(
        name="front_desk_runtime",
        model=Gemini(
            model="gemini-3-flash-preview",
            client_kwargs={"vertexai": True, "project": os.environ["FRONT_DESK_CLOUD_PROJECT"], "location": "global"},
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
        instruction=instruction,
        tools=[RemoteToolset()],
        before_agent_callback=prepare_run,
        before_model_callback=configure_model,
        on_tool_error_callback=tool_failed,
    )
