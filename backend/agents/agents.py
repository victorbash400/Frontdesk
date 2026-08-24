from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import Client, types

from app.config import get_settings


SYSTEM_PROMPT = """You are Front Desk, a precise assistant for client work.
Answer directly and use clear Markdown when it helps. Never claim to have used a
tool or changed external state because tools are not enabled yet. Keep private
chain of thought private; the interface may show only concise model-provided
thought summaries when the model emits them.
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
        retry_options=types.HttpRetryOptions(attempts=3),
    )
    agent = Agent(
        name="front_desk_agent",
        description="Helps manage client work from Front Desk.",
        model=model,
        instruction=SYSTEM_PROMPT,
        generate_content_config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                include_thoughts=True,
                thinking_level=types.ThinkingLevel.LOW,
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
