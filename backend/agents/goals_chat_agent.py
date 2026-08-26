from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

from app.config import get_settings
from tools.goals_chat_tools import list_goal_tasks, revise_goal_plan


INSTRUCTION = """You are Front Desk's Goals supervisor. You converse about the authoritative task boards across every client.

Always call list_goal_tasks before answering a question about current work. Report the persisted goal, task, phase, progress, current step, next step, and evidence accurately. Never invent status or use placeholder language.

Use revise_goal_plan for every requested task-board change. The dedicated planner—not this conversation agent—decides whether to create, reuse, update, steer, or cancel tasks. Preserve the user's requested outcome and constraints. Never silently broaden, simplify, or replace a goal. A failed tool call is information: explain or correct it and continue; it does not end your turn. Never claim a task changed unless its tool result confirms it."""


def create_goals_chat_app() -> App:
    settings = get_settings()
    agent = Agent(
        name="front_desk_goals_supervisor",
        description="Answers questions about and steers Front Desk goal tasks across clients.",
        model=Gemini(model=settings.gemini_model, client_kwargs={"vertexai": True, "project": settings.google_cloud_project, "location": settings.google_cloud_location}, retry_options=types.HttpRetryOptions(attempts=1)),
        instruction=INSTRUCTION,
        tools=[list_goal_tasks, revise_goal_plan],
        generate_content_config=types.GenerateContentConfig(thinking_config=types.ThinkingConfig(include_thoughts=True, thinking_level=types.ThinkingLevel.MEDIUM)),
    )
    return App(name="front_desk_goals_chat", root_agent=agent)
