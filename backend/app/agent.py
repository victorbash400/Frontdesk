from strands import Agent
from strands.models import BedrockModel

from .config import Settings, get_settings


SYSTEM_PROMPT = """You are Operator, a precise client-work assistant.
Use only information and tools available in the current client workspace.
State clearly when required context or a connection is unavailable.
"""


def create_operator_agent(settings: Settings | None = None) -> Agent:
    config = settings or get_settings()
    model = BedrockModel(
        model_id=config.strands_model_id,
        region_name=config.strands_region,
        temperature=0.2,
    )
    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        callback_handler=None,
    )
