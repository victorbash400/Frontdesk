from google import genai

from .config import Settings


def create_genai_client(settings: Settings) -> genai.Client:
    if not settings.gemini_api_key:
        raise RuntimeError("FRONT_DESK_GEMINI_API_KEY is required for Gemini Live. The configured live model is not available through Vertex AI.")
    return genai.Client(api_key=settings.gemini_api_key, vertexai=False)
