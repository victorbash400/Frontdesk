import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
from contextlib import suppress
from dataclasses import dataclass
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect
from google.genai import errors, types

from agents.meet_agent import MeetAgentContext, live_config
from app.config import get_settings
from app.database import SessionLocal
from app.goals import list_goals
from app.gemini import create_genai_client
from tools.supervisor_tools import execute_client_tool
from .models import Meeting
from .service import append_turn, mark_agent_active, mark_meeting_state, record_agent_tool, record_meeting_diagnostic, require_meeting


AUDIO_PACKET = 1
VIDEO_PACKET = 2
SUPPORTED_VOICES = {"Kore", "Aoede", "Leda", "Zephyr", "Puck", "Charon", "Fenrir", "Orus", "Sulafat"}
LANGUAGES = {"en": "English", "sw": "Swahili", "fr": "French", "de": "German", "es": "Spanish", "pt": "Portuguese", "ar": "Arabic", "hi": "Hindi", "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "zu": "Zulu"}
@dataclass(frozen=True)
class AgentIdentity:
    account_id: str
    meeting_id: str
    runtime_id: str
    bridge_id: str
    ticket_id: str


_active_sockets: dict[str, tuple[str, WebSocket]] = {}
_runtime_locks: dict[str, asyncio.Lock] = {}
_live_sessions: dict[str, dict[str, object]] = {}
logger = logging.getLogger("uvicorn.error")


def create_agent_ticket(
    account_id: str,
    meeting_id: str,
    ttl_seconds: int = 86_400,
    *,
    runtime_id: str | None = None,
    bridge_id: str | None = None,
) -> str:
    if ttl_seconds < 60 or ttl_seconds > 86_400:
        raise ValueError("Meeting agent ticket lifetime must be between 60 seconds and 24 hours.")
    ticket_id = str(uuid4())
    runtime_id = runtime_id or str(uuid4())
    bridge_id = bridge_id or str(uuid4())
    with SessionLocal() as session:
        meeting = session.get(Meeting, meeting_id)
        if meeting:
            if meeting.account_id != account_id:
                raise ValueError("Meeting agent ticket account does not own this meeting.")
            meeting.active_agent_ticket_id = ticket_id
            meeting.active_runtime_id = runtime_id
            meeting.active_bridge_id = bridge_id
            meeting.active_tab_id = None
            session.commit()
    payload = {
        "account_id": account_id,
        "meeting_id": meeting_id,
        "runtime_id": runtime_id,
        "bridge_id": bridge_id,
        "ticket_id": ticket_id,
        "expires": int(time.time()) + ttl_seconds,
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(get_settings().internal_secret.encode(), encoded.encode(), hashlib.sha256).digest()
    return f"{encoded}.{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"


def verify_agent_ticket(ticket: str, meeting_id: str) -> AgentIdentity:
    try:
        encoded, supplied = ticket.split(".", 1)
        expected = base64.urlsafe_b64encode(hmac.new(get_settings().internal_secret.encode(), encoded.encode(), hashlib.sha256).digest()).decode().rstrip("=")
        if not hmac.compare_digest(supplied, expected):
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if payload["meeting_id"] != meeting_id or int(payload["expires"]) < int(time.time()):
            raise ValueError
        with SessionLocal() as session:
            meeting = session.get(Meeting, meeting_id)
            if not meeting or (
                meeting.active_agent_ticket_id != payload.get("ticket_id")
                or meeting.active_runtime_id != payload.get("runtime_id")
                or meeting.active_bridge_id != payload.get("bridge_id")
            ):
                raise ValueError
        return AgentIdentity(
            account_id=str(payload["account_id"]),
            meeting_id=meeting_id,
            runtime_id=str(payload["runtime_id"]),
            bridge_id=str(payload["bridge_id"]),
            ticket_id=str(payload["ticket_id"]),
        )
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("Meeting agent authentication expired. Start the media bridge again.") from error


async def run_meet_agent(websocket: WebSocket, meeting_id: str, ticket: str, voice: str, language: str) -> None:
    await websocket.accept()
    connection_id = str(uuid4())
    owns_socket = False
    try:
        identity = verify_agent_ticket(ticket, meeting_id)
        previous = _active_sockets.get(meeting_id)
        _active_sockets[meeting_id] = (connection_id, websocket)
        owns_socket = True
        if previous and previous[1] is not websocket:
            with suppress(RuntimeError):
                await previous[1].close(code=4001, reason="Superseded by the current bridge connection.")
        async with _runtime_locks.setdefault(meeting_id, asyncio.Lock()):
            identity = verify_agent_ticket(ticket, meeting_id)
            await _run_identity_bound_agent(websocket, identity, connection_id, voice, language)
    except WebSocketDisconnect:
        logger.info("meeting=%s connection=%s bridge=disconnected", meeting_id, connection_id)
    except errors.APIError as error:
        await _handle_live_error(websocket, meeting_id, ticket, error)
    except ValueError as error:
        logger.info("meeting=%s connection=%s bridge=rejected reason=%s", meeting_id, connection_id, error)
        with suppress(RuntimeError):
            await websocket.send_json({"type": "error", "error": str(error)})
        with suppress(RuntimeError):
            await websocket.close(code=1008)
    except RuntimeError as error:
        logger.exception("meeting=%s connection=%s agent=failed error=%s", meeting_id, connection_id, error)
        with suppress(RuntimeError):
            await websocket.send_json({"type": "error", "error": str(error)})
        with suppress(RuntimeError):
            await websocket.close(code=1008)
    finally:
        if owns_socket and _active_sockets.get(meeting_id, (None, None))[0] == connection_id:
            _active_sockets.pop(meeting_id, None)


async def _run_identity_bound_agent(
    websocket: WebSocket,
    identity: AgentIdentity,
    connection_id: str,
    voice: str,
    language: str,
) -> None:
    meeting_id = identity.meeting_id
    account_id = identity.account_id
    logger.info(
        "meeting=%s runtime=%s bridge=%s connection=%s bridge=connected",
        meeting_id, identity.runtime_id, identity.bridge_id, connection_id,
    )
    try:
        if voice not in SUPPORTED_VOICES or language not in LANGUAGES:
            raise ValueError("Unsupported meeting voice or spoken language.")
        settings = get_settings()
        with SessionLocal() as session:
            meeting = require_meeting(session, account_id, meeting_id)
            goals = list_goals(session, account_id, meeting.client_id)
            documents = execute_client_tool(account_id, meeting.client_id, "get_client_documents", {}).get("documents", [])
            context = MeetAgentContext(
                meeting_id=meeting.id,
                client_id=meeting.client_id,
                title=meeting.title,
                purpose=meeting.description,
                goals=goals,
                documents=list(documents) if isinstance(documents, list) else [],
                voice=voice,
                language=LANGUAGES[language],
            )
        tab_id = await _register_bridge_and_wait_for_participant(websocket, identity)
        with SessionLocal() as session:
            mark_agent_active(session, require_meeting(session, account_id, meeting_id))
        client = create_genai_client(settings)
        session_state = _live_sessions.setdefault(identity.runtime_id, {"handle": None})
        session_handle = session_state.get("handle")
        live_session_id = str(uuid4())
        logger.info(
            "meeting=%s runtime=%s tab=%s live=%s agent=connecting_gemini resumed=%s",
            meeting_id, identity.runtime_id, tab_id, live_session_id, bool(session_handle),
        )
        async with client.aio.live.connect(
            model=settings.gemini_voice_model,
            config=live_config(context, str(session_handle) if session_handle else None),
        ) as live:
            await websocket.send_json({"type": "agent_ready"})
            logger.info("meeting=%s runtime=%s live=%s agent=ready_waiting_for_speech resumed=%s", meeting_id, identity.runtime_id, live_session_id, bool(session_handle))
            outcome = await _bridge(websocket, live, account_id, context.client_id, meeting_id, session_state)
        if outcome == "completed":
            with SessionLocal() as session:
                meeting = require_meeting(session, account_id, meeting_id)
                if meeting.state != "completed":
                    mark_meeting_state(session, meeting, "completed")
            with suppress(RuntimeError):
                await websocket.send_json({"type": "meeting_complete"})
            _live_sessions.pop(identity.runtime_id, None)
    finally:
        logger.info("meeting=%s runtime=%s connection=%s agent=stopped", meeting_id, identity.runtime_id, connection_id)


async def _register_bridge_and_wait_for_participant(websocket: WebSocket, identity: AgentIdentity) -> str:
    registered_tab_id: str | None = None
    while True:
        message = await websocket.receive()
        if message.get("type") == "websocket.disconnect":
            raise WebSocketDisconnect
        text = message.get("text")
        if not text:
            continue
        payload = json.loads(text)
        if registered_tab_id is None:
            if payload.get("type") != "bridge_registered":
                raise ValueError("The media bridge must register its exact identity before sending meeting events.")
            if (
                payload.get("meetingId") != identity.meeting_id
                or payload.get("runtimeId") != identity.runtime_id
                or payload.get("bridgeId") != identity.bridge_id
                or not str(payload.get("tabId") or "").isdigit()
            ):
                raise ValueError("The media bridge identity does not match the active meeting runtime.")
            registered_tab_id = str(payload["tabId"])
            with SessionLocal() as session:
                meeting = require_meeting(session, identity.account_id, identity.meeting_id)
                if meeting.active_runtime_id != identity.runtime_id or meeting.active_bridge_id != identity.bridge_id:
                    raise ValueError("The meeting runtime was replaced before the bridge registered.")
                meeting.active_tab_id = registered_tab_id
                session.commit()
            await websocket.send_json({"type": "waiting_for_participant"})
            logger.info("meeting=%s runtime=%s bridge=%s tab=%s agent=waiting_for_client", identity.meeting_id, identity.runtime_id, identity.bridge_id, registered_tab_id)
            continue
        browser_state = {"browser_ready": "browser_ready", "browser_joined": "waiting_for_client"}.get(payload.get("type"))
        if browser_state:
            with SessionLocal() as session:
                mark_meeting_state(session, require_meeting(session, identity.account_id, identity.meeting_id), browser_state)
        if payload.get("type") == "participant_arrived":
            logger.info("meeting=%s runtime=%s tab=%s participant=arrived source=meet_ui", identity.meeting_id, identity.runtime_id, registered_tab_id)
            return registered_tab_id
        if payload.get("type") == "end_meeting":
            raise RuntimeError("The meeting ended before the client arrived.")


async def _handle_live_error(websocket: WebSocket, meeting_id: str, ticket: str, error: errors.APIError) -> None:
    error_text = str(error)
    aborted = error_text.startswith("1008 ") or "operation was aborted" in error_text.lower()
    with suppress(ValueError):
        identity = verify_agent_ticket(ticket, meeting_id)
        if aborted:
            _live_sessions.pop(identity.runtime_id, None)
    event_type = "gemini.session_aborted" if aborted else "gemini.session_exhausted"
    logger.warning("meeting=%s gemini=%s error=%s", meeting_id, "session_reset" if aborted else "capacity_reset", error)
    with SessionLocal() as session:
        record_meeting_diagnostic(session, meeting_id, event_type, {"error": error_text})
    with suppress(RuntimeError):
        await websocket.send_json({"type": "retrying", "error": "Gemini Live session ended. Reconnecting automatically."})
    with suppress(RuntimeError):
        await websocket.close(code=1012 if aborted else 1013, reason="Gemini Live session reset")


async def _bridge(
    websocket: WebSocket,
    live: object,
    account_id: str,
    client_id: str,
    meeting_id: str,
    session_state: dict[str, object],
) -> str:
    async def receive_media() -> str:
        audio_received = False
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                raise WebSocketDisconnect
            packet = message.get("bytes")
            if packet:
                channel, payload = packet[0], packet[1:]
                if channel == AUDIO_PACKET and payload:
                    if not audio_received:
                        audio_received = True
                        with SessionLocal() as session:
                            record_meeting_diagnostic(session, meeting_id, "media.client_audio_received", {"bytes": len(payload)})
                        logger.info("meeting=%s media=client_audio_received", meeting_id)
                    await live.send_realtime_input(audio=types.Blob(data=payload, mime_type="audio/pcm;rate=16000"))
                elif channel == VIDEO_PACKET and payload:
                    await live.send_realtime_input(video=types.Blob(data=payload, mime_type="image/jpeg"))
                else:
                    raise RuntimeError("The media bridge sent an unsupported packet.")
                continue
            text = message.get("text")
            if text:
                event_type = json.loads(text).get("type")
                if event_type == "participant_left":
                    logger.info("meeting=%s participant=left source=meet_ui", meeting_id)
                    continue
                if event_type == "end_meeting":
                    return "completed"

    async def send_agent_events() -> str:
        sequence = 0
        transcript_ids: dict[str, str] = {}
        transcript_text: dict[str, str] = {"user": "", "assistant": ""}
        audio_sent = False
        while True:
            async for response in live.receive():
                resumption = response.session_resumption_update
                if resumption and resumption.resumable and resumption.new_handle:
                    first_handle = not session_state.get("handle")
                    session_state["handle"] = resumption.new_handle
                    if first_handle:
                        logger.info("meeting=%s gemini=session_resumable", meeting_id)
                if response.tool_call:
                    for call in response.tool_call.function_calls or []:
                        call_id = call.id or f"{call.name}-{uuid4()}"
                        arguments = dict(call.args or {})
                        logger.info("meeting=%s tool=%s status=started", meeting_id, call.name)
                        await websocket.send_json({"type": "tool_call", "id": call_id, "name": call.name, "args": arguments})
                        if call.name == "end_meeting":
                            result = {"status": "completed", "summary": str(arguments.get("summary") or "")}
                            await live.send_tool_response(function_responses=[types.FunctionResponse(id=call.id, name=call.name, response=result)])
                            with SessionLocal() as session:
                                record_agent_tool(session, meeting_id, call_id, call.name, arguments, result)
                                mark_meeting_state(session, require_meeting(session, account_id, meeting_id), "completed")
                            await websocket.send_json({"type": "meeting_complete", "summary": result["summary"]})
                            return "completed"
                        result = execute_client_tool(account_id, client_id, call.name, arguments)
                        await live.send_tool_response(function_responses=[types.FunctionResponse(id=call.id, name=call.name, response=result)])
                        with SessionLocal() as session:
                            record_agent_tool(session, meeting_id, call_id, call.name, arguments, result)
                        logger.info("meeting=%s tool=%s status=completed", meeting_id, call.name)
                        await websocket.send_json({"type": "tool_response", "id": call_id, "name": call.name, "result": result})
                content = response.server_content
                if not content:
                    continue
                if content.interrupted:
                    await websocket.send_json({"type": "interrupted"})
                for role, transcription in (("user", content.input_transcription), ("assistant", content.output_transcription)):
                    if not transcription or not transcription.text:
                        continue
                    if role not in transcript_ids:
                        sequence += 1
                        transcript_ids[role] = f"meeting-{role}-{sequence}"
                    transcript_text[role] += transcription.text
                    await websocket.send_json({"type": "transcript_update", "id": transcript_ids[role], "role": role, "sequence": sequence, "text": transcript_text[role], "final": bool(transcription.finished)})
                    if transcription.finished:
                        with SessionLocal() as session:
                            append_turn(session, meeting_id, role, transcript_text[role])
                        transcript_ids.pop(role, None)
                        transcript_text[role] = ""
                if content.model_turn:
                    for part in content.model_turn.parts or []:
                        if part.inline_data and part.inline_data.data:
                            if not audio_sent:
                                audio_sent = True
                                with SessionLocal() as session:
                                    record_meeting_diagnostic(session, meeting_id, "media.agent_audio_sent", {"bytes": len(part.inline_data.data)})
                                logger.info("meeting=%s media=agent_audio_sent", meeting_id)
                            await websocket.send_bytes(bytes([AUDIO_PACKET]) + part.inline_data.data)
                if content.turn_complete:
                    for role in ("user", "assistant"):
                        if transcript_text[role].strip():
                            with SessionLocal() as session:
                                append_turn(session, meeting_id, role, transcript_text[role])
                            transcript_ids.pop(role, None)
                            transcript_text[role] = ""
                    await websocket.send_json({"type": "turn_complete"})

    input_task = asyncio.create_task(receive_media())
    output_task = asyncio.create_task(send_agent_events())
    done, pending = await asyncio.wait({input_task, output_task}, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    pending_results = await asyncio.gather(*pending, return_exceptions=True)
    del pending_results
    errors_found = [task.exception() for task in done if not task.cancelled() and task.exception() is not None]
    api_error = next((error for error in errors_found if isinstance(error, errors.APIError)), None)
    if api_error:
        raise api_error
    if errors_found:
        raise errors_found[0]
    return next((task.result() for task in done if not task.cancelled()), "disconnected")
