import json
from dataclasses import dataclass

from google.genai import types


MEET_AGENT_INSTRUCTION = """You are Front Desk's dedicated meeting agent. You are already inside a Google Meet with one client. The browser worker owns joining, admission, microphone routing, camera routing, and leaving the meeting; never attempt browser navigation or describe those mechanics.

Remain silent until the session reports that the client has arrived. Then greet the client briefly, identify yourself as Front Desk, and ask how you can help unless a specific meeting purpose already supplies the opening question. Listen carefully and keep spoken replies concise and natural.

At the beginning of the client conversation, call get_client_goals and get_client_documents before giving a substantive resolution. Use those tool results as the authoritative client record, even when an initial snapshot was supplied.

Use the supplied client and goal context as background, not as claims that work has happened. Use tools to inspect authoritative state and record confirmed information. Never claim an action succeeded unless a tool result confirms it. Ask for explicit confirmation immediately before consequential external changes. If a request requires work unavailable in this meeting session, state what you will check and create a clear request for the owning Front Desk workflow rather than inventing a result.

When the issue is resolved, summarize the verified outcome, identify any remaining follow-up, ask whether the client needs anything else, and end only after the client confirms the conversation is finished. Never repeatedly check or poll."""


MEET_AGENT_TOOLS = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name="get_client_goals", description="Read this client's authoritative goals and current work."),
    types.FunctionDeclaration(name="get_client_documents", description="Read the documents stored inside this client's Front Desk folder."),
    types.FunctionDeclaration(name="update_goal_board", description="Record a confirmed change in a goal's current situation.", parameters={"type": "object", "properties": {"goal_id": {"type": "string"}, "situation": {"type": "string"}, "expected_version": {"type": "integer"}}, "required": ["goal_id", "situation", "expected_version"]}),
    types.FunctionDeclaration(name="ask_user", description="Escalate one necessary question to the Front Desk owner.", parameters={"type": "object", "properties": {"goal_id": {"type": "string"}, "question": {"type": "string"}}, "required": ["goal_id", "question"]}),
    types.FunctionDeclaration(name="send_client_message", description="Record a confirmed follow-up message for this client.", parameters={"type": "object", "properties": {"goal_id": {"type": "string"}, "message": {"type": "string"}}, "required": ["goal_id", "message"]}),
    types.FunctionDeclaration(name="end_meeting", description="End the call only after the client confirms the conversation is finished.", parameters={"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}),
])]


@dataclass(frozen=True)
class MeetAgentContext:
    meeting_id: str
    client_id: str
    title: str
    purpose: str
    goals: list[dict[str, object]]
    documents: list[dict[str, object]]
    voice: str
    language: str


def live_config(context: MeetAgentContext, session_handle: str | None = None) -> types.LiveConnectConfig:
    session_context = json.dumps({
        "meeting_id": context.meeting_id,
        "client_id": context.client_id,
        "meeting_title": context.title,
        "meeting_purpose": context.purpose,
        "goals": context.goals,
        "client_documents": context.documents,
    }, default=str)
    return types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        realtime_input_config=types.RealtimeInputConfig(
            activity_handling=types.ActivityHandling.START_OF_ACTIVITY_INTERRUPTS,
            automatic_activity_detection=types.AutomaticActivityDetection(
                disabled=False,
                start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_HIGH,
                prefix_padding_ms=20,
                end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
                silence_duration_ms=800,
            ),
        ),
        speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=context.voice))),
        thinking_config=types.ThinkingConfig(thinking_level="minimal"),
        context_window_compression=types.ContextWindowCompressionConfig(sliding_window=types.SlidingWindow()),
        session_resumption=types.SessionResumptionConfig(handle=session_handle),
        system_instruction=f"{MEET_AGENT_INSTRUCTION}\n\nAuthoritative meeting context:\n{session_context}\n\nSpeak in {context.language}.",
        tools=MEET_AGENT_TOOLS,
    )
