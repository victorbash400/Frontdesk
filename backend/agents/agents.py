from pathlib import Path

import boto3
from strands import Agent
from strands.hooks import AfterToolCallEvent, HookRegistry
from strands.models import BedrockModel
from strands.session.file_session_manager import FileSessionManager

from app.config import Settings, get_settings
from tools.time_tool import get_current_time


SESSION_DIRECTORY = Path(__file__).resolve().parents[1] / ".sessions"
SYSTEM_PROMPT = """You are Operator, a precise client-work assistant.
Answer clearly and directly. Use the get_current_time tool whenever the user asks for the current time or date.
Never estimate the current time from model knowledge.
"""
TITLE_PROMPT = """You name chats for Operator.
Return only a concise title of two to five words, without quotes, punctuation, or explanation.
"""


class ToolEventRecorder:
    def __init__(self) -> None:
        self._completed: list[dict[str, str]] = []

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(AfterToolCallEvent, self.after_tool_call)

    def after_tool_call(self, event: AfterToolCallEvent) -> None:
        self._completed.append({
            "id": str(event.tool_use.get("toolUseId") or ""),
            "name": str(event.tool_use.get("name") or "tool"),
            "status": "error" if event.exception or event.result.get("status") == "error" else "done",
        })

    def drain(self) -> list[dict[str, str]]:
        completed, self._completed = self._completed, []
        return completed


def create_operator_agent(session_id: str, tool_events: ToolEventRecorder | None = None, settings: Settings | None = None) -> Agent:
    config = settings or get_settings()
    SESSION_DIRECTORY.mkdir(parents=True, exist_ok=True)
    return Agent(
        agent_id="operator",
        callback_handler=None,
        hooks=[tool_events] if tool_events else None,
        model=create_bedrock_model(config),
        name="Operator",
        session_manager=FileSessionManager(session_id=session_id, storage_dir=str(SESSION_DIRECTORY)),
        system_prompt=SYSTEM_PROMPT,
        tools=[get_current_time],
    )


async def name_chat(user_message: str, assistant_message: str, settings: Settings | None = None) -> str:
    config = settings or get_settings()
    agent = Agent(
        agent_id="operator-chat-namer",
        callback_handler=None,
        model=create_bedrock_model(config),
        name="Chat Namer",
        system_prompt=TITLE_PROMPT,
        tools=[],
    )
    result = await agent.invoke_async(f"User: {user_message}\nAssistant: {assistant_message[:1200]}")
    words = " ".join(str(result).strip().strip('"').split()).rstrip(".!?").split()
    return " ".join(words[:5])[:60] or "New chat"


def create_bedrock_model(settings: Settings) -> BedrockModel:
    session = boto3.Session(
        profile_name=settings.aws_profile or None,
        region_name=settings.strands_region,
    )
    return BedrockModel(
        boto_session=session,
        model_id=settings.strands_model_id,
        temperature=0.2,
    )
