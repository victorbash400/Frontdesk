import json
from typing import Literal

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.runners import Runner
from google.adk.sessions import BaseSessionService
from google.genai import types
from pydantic import BaseModel, Field

from app.config import get_settings


class GoalTaskOperation(BaseModel):
    action: Literal["create", "reuse", "update", "steer", "cancel"]
    task_id: str = Field(default="", description="Existing task ID for every action except create.")
    key: str = Field(default="", description="Short unique key used by later task dependencies for create operations.")
    title: str = Field(default="", description="Concise task-board title for create or update.")
    instruction: str = Field(default="", description="Complete operational instruction for create, update, or steer.")
    depends_on: list[str] = Field(default_factory=list)
    required_inputs: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)


class GoalPlan(BaseModel):
    operations: list[GoalTaskOperation] = Field(min_length=1)


PLANNER_INSTRUCTION = """You maintain Front Desk's ordered, strictly sequential goal task board. You plan work but never execute it.

Plan the requested outcome, not a list of tools or applications. Create one task for one cohesive outcome. Split only when a later task consumes a clearly named, independently verifiable output from an earlier task, or when long-running work has a real external wait boundary such as a scheduled client meeting. Never split research from the action that directly consumes it.

Return operations that create, reuse, update, steer, or cancel tasks. Read the existing task ledger first. Reuse a task that already covers the requested outcome. Update queued work, steer running or blocked work, and cancel only when the user clearly stops or replaces it. Never duplicate an existing outcome. Create operations need a short unique key, concise task-board title, detailed operational instruction, dependencies on earlier create keys, exact required inputs, and exact expected outputs. Instructions must name the target, actions, constraints, and completion evidence. For meetings, preparation/scheduling, the live client conversation, and post-meeting follow-up are separate tasks because the live conversation has an external wait boundary. The conversation task must require evidence that the client joined, the agent participated, the requested confirmation was recorded, and the meeting ended. The follow-up task must depend on that confirmed conversation output.

Never invent facts, identifiers, links, dates, recipients, or tool results. Preserve the user's wording and constraints. Do not add placeholder work. Return only the structured plan."""


def create_goal_planner_runner(session_service: BaseSessionService) -> Runner:
    settings = get_settings()
    planner = Agent(
        name="front_desk_goal_planner",
        description="Creates the persistent ordered task plan for one Front Desk goal.",
        model=Gemini(
            model=settings.gemini_title_model,
            client_kwargs={"vertexai": True, "project": settings.google_cloud_project, "location": settings.google_cloud_location},
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
        mode="chat",
        output_schema=GoalPlan,
        instruction=PLANNER_INSTRUCTION,
        generate_content_config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
        ),
    )
    return Runner(app=App(name="front_desk_goal_planner", root_agent=planner), session_service=session_service)


async def plan_goal(runner: Runner, account_id: str, session_id: str, request: str, existing_tasks: list[dict[str, object]]) -> GoalPlan:
    await runner.session_service.create_session(app_name=runner.app_name, user_id=account_id, session_id=session_id)
    response = ""
    prompt = json.dumps({"request": request, "task_ledger": existing_tasks})
    async for event in runner.run_async(
        user_id=account_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part.from_text(text=prompt)]),
    ):
        if event.error_message:
            raise RuntimeError(event.error_message)
        if not event.content:
            continue
        for part in event.content.parts or []:
            if part.text and not part.thought:
                response = part.text if part.text.startswith(response) else response + part.text
    return GoalPlan.model_validate_json(response)
