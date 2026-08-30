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
from app.agent_runner import create_runner


class GoalTaskOperation(BaseModel):
    action: Literal["create", "reuse", "update", "steer", "retry", "cancel"]
    task_id: str = Field(default="", description="Existing task ID for every action except create.")
    key: str = Field(default="", description="Short unique key used by later task dependencies for create operations.")
    title: str = Field(default="", description="Concise task-board title for create or update.")
    instruction: str = Field(default="", description="Complete operational instruction for create, update, steer, or retry.")
    depends_on: list[str] = Field(default_factory=list)
    required_inputs: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    skill_ids: list[str] = Field(default_factory=list, description="Organization skill IDs needed to execute this task.")


class GoalPlan(BaseModel):
    operations: list[GoalTaskOperation] = Field(min_length=1)


PLANNER_INSTRUCTION = """You maintain Front Desk's ordered, strictly sequential goal task board. You plan work but never execute it. You receive a compact organization skill index containing IDs, names, descriptions, required plugins, and availability. Select only available skills necessary for each task. Preferred skill IDs are suggestions, never requirements: ignore any preferred skill that would broaden or replace the requested outcome. You do not receive or reproduce full skill instructions; workers resolve those after the plan is persisted.

Plan the requested outcome, not a list of tools or applications. Create one task for one cohesive outcome. Do not add research briefs, tickets, account notes, calendar scheduling, email, Slack notifications, or follow-up work unless the request requires them. A direct request to call or speak with a client is one live-call task: resolve the client's contact details, create and join the Google Meet, speak with the client, and record the actual outcome. A support case, internal notification, proposed time, or calendar artifact is not evidence that the client was contacted. Split only when a later task consumes a clearly named, independently verifiable output from an earlier task, or when the user explicitly requests a future meeting whose scheduled time creates a real external wait boundary. Never split research from the action that directly consumes it.

Return operations that create, reuse, update, steer, retry, or cancel tasks. Read the existing task ledger first. Reuse a task that already covers the requested outcome. Update queued work, steer running or blocked work, retry failed work, and cancel only when the user clearly stops or replaces it. A retry must target the same failed task identity and provide a complete corrected instruction informed by the failure in its ledger; never create a replacement task for the same outcome. Never duplicate an existing outcome. Create operations need a short unique key, concise task-board title, detailed operational instruction, dependencies on earlier create keys, exact required inputs, and exact expected outputs. Instructions must name the target, actions, constraints, and completion evidence. Only an explicitly future or scheduled meeting creates an external wait boundary: in that case scheduling, the later live conversation, and requested post-meeting follow-up may be separate tasks. A live conversation task must require evidence that the client joined, the agent participated, the requested confirmation was recorded, and the meeting ended. Add follow-up work only when the request asks for it.

Client identity comes only from Front Desk's client directory and profiles. Never instruct a worker to search Gmail, Slack, Drive, Jira, the browser, or another plugin to discover who a named client is. When the named client cannot be matched unambiguously in Front Desk, instruct the worker to ask the user which client they mean.

Never invent facts, identifiers, links, dates, recipients, proposed meeting times, or tool results. A request to call a client without a future time is an immediate call now, not a missing scheduling choice. If a future meeting lacks client availability, instruct the worker to ask the client through the client's communication channel and wait for the reply. Use the owner question tool only for a choice or ambiguity the Front Desk owner must resolve. Preserve the user's wording and constraints. Do not reinterpret "call" as "open a support case," "post to Slack," or "schedule a future call." Do not add placeholder work. Return only the structured plan."""


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
        instruction=PLANNER_INSTRUCTION + "\n\nFor a direct client call, select the Client Support Call skill when it is available; do not substitute the generic Web Workflows skill. The call worker creates an immediate Meet space, emails its link to the client, and joins it through the dedicated meeting worker.",
        generate_content_config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
        ),
    )
    return create_runner(app=App(name="front_desk_goal_planner", root_agent=planner), session_service=session_service)


async def plan_goal(runner: Runner, account_id: str, session_id: str, request: str, existing_tasks: list[dict[str, object]], skills: list[dict[str, object]], preferred_skill_ids: list[str]) -> GoalPlan:
    await runner.session_service.create_session(app_name=runner.app_name, user_id=account_id, session_id=session_id)
    response = ""
    prompt = json.dumps({"request": request, "task_ledger": existing_tasks, "available_skills": skills, "preferred_skill_ids": preferred_skill_ids})
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
