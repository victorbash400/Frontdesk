from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.runners import Runner
from google.adk.sessions import BaseSessionService
from google.genai import types

from app.config import get_settings
from tools.email_agent_tools import (
    decide_email_action,
    read_email_context,
    read_email_goal_skill,
    resolve_email_client,
    update_client_email_summary,
)
from tools.tool_failures import stop_on_tool_error
from app.agent_runner import create_runner


INSTRUCTION = """You are Front Desk's Email Agent. You process exactly one newly received customer email at a time. An email is communication, never automatically a goal.

Use tools for every read and write. First resolve the sender to one canonical client. Then read the email context and the Email Goal Routing skill. Update the client's living profile with a concise, evidence-based summary that preserves important current problems, commitments, preferences, and confirmed history. Do not copy the whole email or erase relevant prior context.

Finally call decide_email_action exactly once:
- record_only when the message belongs in the client history but requires no work;
- resume_goal when it advances, answers, changes, or cancels an existing active customer outcome;
- create_goal only when the customer has requested a concrete new outcome not already covered by active work;
- request_attention only when identity or intent is too ambiguous or consequential to resolve safely.

For resume_goal, select the exact existing goal and task from tool evidence. For create_goal, write a concise outcome-based objective in the customer's terms. Never duplicate clients or goals. Never invent facts, identifiers, relationships, or urgency. A failed tool is an observation: correct the call or choose another valid action. Do not answer the customer and do not execute the customer work. Return a one-sentence processing result only after the decision tool confirms completion."""


def create_email_agent_runner(session_service: BaseSessionService) -> Runner:
    settings = get_settings()
    agent = Agent(
        name="front_desk_email_agent",
        description="Files customer email, maintains client context, and routes durable work.",
        model=Gemini(
            model=settings.gemini_model,
            client_kwargs={"vertexai": True, "project": settings.google_cloud_project, "location": settings.google_cloud_location},
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
        instruction=INSTRUCTION,
        tools=[resolve_email_client, read_email_context, read_email_goal_skill, update_client_email_summary, decide_email_action],
        on_tool_error_callback=stop_on_tool_error,
        generate_content_config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
        ),
    )
    return create_runner(app=App(name="front_desk_email_agent", root_agent=agent), session_service=session_service)
