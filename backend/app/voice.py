import asyncio
import base64
import hashlib
import hmac
import json
import time
from contextlib import suppress

from fastapi import WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

from .config import get_settings
from .database import SessionLocal
from .goals import create_notification, list_goals, update_goal

VOICE_MODEL = "gemini-3.1-flash-live-preview"
LIVE_VOICES = {"Kore", "Aoede", "Leda", "Zephyr", "Puck", "Charon", "Fenrir", "Orus", "Sulafat"}
LANGUAGES = {"en": "English", "sw": "Swahili", "fr": "French", "de": "German", "es": "Spanish", "pt": "Portuguese", "ar": "Arabic", "hi": "Hindi", "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "zu": "Zulu"}

VOICE_TOOLS = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name="get_client_goals", description="Read this client's goals and living boards."),
    types.FunctionDeclaration(name="update_goal_board", description="Update a goal's current situation from confirmed evidence.", parameters={"type": "object", "properties": {"goal_id": {"type": "string"}, "situation": {"type": "string"}, "expected_version": {"type": "integer"}}, "required": ["goal_id", "situation", "expected_version"]}),
    types.FunctionDeclaration(name="ask_user", description="Send a necessary clarification to the user's Needs You inbox.", parameters={"type": "object", "properties": {"goal_id": {"type": "string"}, "question": {"type": "string"}}, "required": ["goal_id", "question"]}),
    types.FunctionDeclaration(name="send_client_message", description="Send a confirmed update to this client's message inbox.", parameters={"type": "object", "properties": {"goal_id": {"type": "string"}, "message": {"type": "string"}}, "required": ["goal_id", "message"]}),
])]

VOICE_INSTRUCTION = """You are Front Desk's realtime voice supervisor for one client. Speak naturally and briefly. You have a separate voice conversation from text chat. Use the provided tools only to read durable goal state, record confirmed context, ask a necessary clarification, or send a confirmed client update. Never claim an action occurred unless its tool result confirms it. Never repeatedly check or poll."""

def create_voice_ticket(account_id: str, client_id: str, session_id: str) -> str:
    payload = {"account_id": account_id, "client_id": client_id, "session_id": session_id, "expires": int(time.time()) + 60}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(get_settings().internal_secret.encode(), encoded.encode(), hashlib.sha256).digest()
    return f"{encoded}.{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"

def verify_voice_ticket(ticket: str, session_id: str) -> tuple[str, str]:
    try:
        encoded, supplied = ticket.split(".", 1)
        expected = base64.urlsafe_b64encode(hmac.new(get_settings().internal_secret.encode(), encoded.encode(), hashlib.sha256).digest()).decode().rstrip("=")
        if not hmac.compare_digest(supplied, expected): raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if payload["session_id"] != session_id or int(payload["expires"]) < int(time.time()): raise ValueError
        return str(payload["account_id"]), str(payload["client_id"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("Voice authentication expired. Start the session again.") from error

async def run_voice_session(websocket: WebSocket, session_id: str, ticket: str, voice: str, language: str) -> None:
    await websocket.accept()
    try:
        account_id, client_id = verify_voice_ticket(ticket, session_id)
        settings = get_settings()
        if voice not in LIVE_VOICES or language not in LANGUAGES: raise ValueError("Unsupported voice or spoken language.")
        if not settings.gemini_api_key: raise RuntimeError("FRONT_DESK_GEMINI_API_KEY is required for voice.")
        with SessionLocal() as database:
            goals = list_goals(database, account_id, client_id)
        config = types.LiveConnectConfig(
            response_modalities=[types.Modality.AUDIO],
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            realtime_input_config=types.RealtimeInputConfig(activity_handling=types.ActivityHandling.START_OF_ACTIVITY_INTERRUPTS, automatic_activity_detection=types.AutomaticActivityDetection(disabled=False, start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_HIGH, prefix_padding_ms=20, end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW, silence_duration_ms=800)),
            speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice))),
            thinking_config=types.ThinkingConfig(thinking_level="minimal"),
            context_window_compression=types.ContextWindowCompressionConfig(sliding_window=types.SlidingWindow()),
            system_instruction=f"{VOICE_INSTRUCTION}\n\nCurrent client goal snapshot:\n{json.dumps(goals)}\n\nRespond unmistakably in {LANGUAGES[language]}.",
            tools=VOICE_TOOLS,
        )
        client = genai.Client(api_key=settings.gemini_api_key, vertexai=False)
        async with client.aio.live.connect(model=settings.gemini_voice_model, config=config) as live:
            await websocket.send_json({"type": "ready"})
            async def receive_input() -> None:
                while True:
                    message = await websocket.receive()
                    if audio := message.get("bytes"):
                        await live.send_realtime_input(audio=types.Blob(data=audio, mime_type="audio/pcm;rate=16000"))
                    elif text := message.get("text"):
                        payload = json.loads(text)
                        if payload.get("type") == "preview":
                            await live.send_realtime_input(text="Say only: Hi, I'm Front Desk. Nice to meet you.")
                    elif message.get("type") == "websocket.disconnect": break

            async def send_events() -> None:
                sequence = 0
                transcript_ids: dict[str, str] = {}
                transcript_text: dict[str, str] = {"user": "", "assistant": ""}
                async for response in live.receive():
                    if response.tool_call:
                        for call in response.tool_call.function_calls or []:
                            await websocket.send_json({"type": "tool_call", "id": call.id or call.name, "name": call.name, "args": call.args or {}})
                            result = handle_tool(account_id, client_id, call.name, dict(call.args or {}))
                            await live.send_tool_response(function_responses=[types.FunctionResponse(id=call.id, name=call.name, response=result)])
                            await websocket.send_json({"type": "tool_response", "id": call.id or call.name, "name": call.name, "result": result})
                    content = response.server_content
                    if not content: continue
                    if content.interrupted: await websocket.send_json({"type": "interrupted"})
                    for role, transcription in (("user", content.input_transcription), ("assistant", content.output_transcription)):
                        if transcription and transcription.text:
                            if role not in transcript_ids:
                                sequence += 1
                                transcript_ids[role] = f"voice-{role}-{sequence}"
                            transcript_text[role] += transcription.text
                            await websocket.send_json({"type": "transcript_update", "id": transcript_ids[role], "role": role, "sequence": sequence, "text": transcript_text[role], "final": bool(transcription.finished)})
                            if transcription.finished:
                                transcript_ids.pop(role, None); transcript_text[role] = ""
                    if content.model_turn:
                        for part in content.model_turn.parts or []:
                            if part.inline_data and part.inline_data.data: await websocket.send_bytes(part.inline_data.data)
                    if content.turn_complete: await websocket.send_json({"type": "turn_complete"})
            input_task = asyncio.create_task(receive_input())
            output_task = asyncio.create_task(send_events())
            done, pending = await asyncio.wait({input_task, output_task}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending: task.cancel()
            for task in done:
                with suppress(WebSocketDisconnect, asyncio.CancelledError): await task
    except (ValueError, RuntimeError) as error:
        with suppress(RuntimeError): await websocket.send_json({"type": "error", "error": str(error)})
        with suppress(RuntimeError): await websocket.close(code=1008)

def handle_tool(account_id: str, client_id: str, name: str, args: dict) -> dict:
    with SessionLocal() as session:
        if name == "get_client_goals": return {"goals": list_goals(session, account_id, client_id)}
        if name == "update_goal_board": return update_goal(session, account_id, args["goal_id"], situation=args["situation"], expected_version=args["expected_version"])
        if name == "ask_user": return create_notification(session, account_id, args["goal_id"], "clarification", args["question"])
        if name == "send_client_message": return create_notification(session, account_id, args["goal_id"], "message", args["message"])
        return {"status": "failed", "error": "Unsupported voice tool."}
