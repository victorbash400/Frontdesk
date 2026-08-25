from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import Client, types

from app.config import get_settings
from tools.supervisor_tools import ask_user, get_client_goals, send_client_message, update_goal_board


SYSTEM_PROMPT = """You are Front Desk's client supervisor. You own the client's
ongoing goals and use the supplied goal board as authoritative current context.
Answer direct questions about the goals, their current situation, elapsed time,
tools, recent work, and what is outstanding. A worker knows only its bounded
assignment; never describe a worker as owning or redefining a goal. Never claim
to have used a tool or changed external state unless confirmed tool evidence is
present in the board. If the available tools are insufficient, state exactly
what capability is missing and ask one concise clarification. Use clear Markdown
when it helps. Keep private chain of thought private; the interface may show only
concise model-provided thought summaries when the model emits them.
"""


def create_front_desk_app() -> App:
    settings = get_settings()
    model = Gemini(
        model=settings.gemini_model,
        client_kwargs={
            "vertexai": True,
            "project": settings.google_cloud_project,
            "location": settings.google_cloud_location,
        },
        retry_options=types.HttpRetryOptions(attempts=1),
    )
    agent = Agent(
        name="front_desk_agent",
        description="Helps manage client work from Front Desk.",
        model=model,
        instruction=SYSTEM_PROMPT,
        tools=[
            get_client_goals,
            update_goal_board,
            ask_user,
            send_client_message,
        ],
        generate_content_config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                include_thoughts=True,
                thinking_level=types.ThinkingLevel.MEDIUM,
            ),
        ),
    )
    return App(name="front_desk", root_agent=agent)


async def name_chat(user_message: str, assistant_message: str) -> str:
    settings = get_settings()
    response = await Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
    ).aio.models.generate_content(
        model=settings.gemini_title_model,
        contents=(
            "Name this chat in 2 to 5 words. Return only the title, without quotes "
            f"or punctuation.\n\nUser: {user_message}\nAssistant: {assistant_message[:1200]}"
        ),
        config=types.GenerateContentConfig(
            max_output_tokens=24,
            temperature=0.2,
            thinking_config=types.ThinkingConfig(
                thinking_level=types.ThinkingLevel.MINIMAL,
            ),
        ),
    )
    title = " ".join((response.text or "").strip().strip('"').split())
    return title[:60] or "New chat"
