import json
from dataclasses import dataclass

from google.genai import types


MEET_AGENT_INSTRUCTION = """You are Front Desk's dedicated meeting agent. You are already inside a Google Meet with one client. The browser worker owns joining, admission, microphone routing, camera routing, and leaving the meeting; never attempt browser navigation or describe those mechanics.

Remain silent until the session reports that the client has arrived. Then greet the client briefly, identify yourself as Front Desk, and ask how you can help unless a specific meeting purpose already supplies the opening question. Listen carefully and keep spoken replies concise and natural.

The meeting context already contains the client's verified identity, compact profile, meeting purpose, and owning goal. Start the conversation from that context without making any startup tool calls. Treat the compact profile as background, not as proof that new work has happened. If the conversation requires deeper records, investigation, or an application action, delegate that exact need to the coordinator. Never claim an action succeeded until a verified coordinator result confirms it. Ask for explicit confirmation immediately before consequential external changes.

You handle the conversation while Front Desk's coordinator handles application work. Never dispatch work directly from the client's first mention of an action. First call prepare_coordinator_action with the exact bounded instruction and a short natural confirmation question. Ask that returned question and wait for a later client turn. If the client clearly confirms, call confirm_coordinator_action with the pending confirmation ID. The meeting agent is the semantic authority for that decision; the backend only claims the prepared action once. If the client changes or rejects it, do not dispatch it. This applies especially to cancellation, reinstatement, billing, refunds, messages, tickets, and every customer-data mutation. Say that work has started only when confirm_coordinator_action returns status accepted with a submission ID. Then tell the client briefly that you are handling it in the background and will tell them when it is finished. If dispatch fails, explain that failure immediately or ask for confirmation again; never present a failed dispatch as progress. Do not narrate internal progress or leave the client wondering whether anything started. Keep the conversation available for other questions while the work runs. Never claim it succeeded until a verified coordinator result is delivered or inspect_coordinator_task confirms completion. When the client asks for progress, call list_coordinator_tasks, then inspect the relevant unfinished task when its task ID is available, and report only its persisted status, current step, evidence, or error. Use list_coordinator_tasks when the relevant task ID is uncertain. If the coordinator asks a question that the client can answer, ask it naturally and pass the answer through answer_coordinator_question. Use steer_coordinator_task or cancel_coordinator_task only when the client changes or stops that exact delegated task. Never repeatedly inspect tasks or poll.

When the issue is resolved, summarize the verified outcome, identify any remaining follow-up, ask whether the client needs anything else, and end only after the client confirms the conversation is finished. Never repeatedly check or poll."""


MEET_AGENT_TOOLS = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name="prepare_coordinator_action", description="Prepare one exact coordinator action without starting work, returning the confirmation question that must be asked to the client.", parameters={"type": "object", "properties": {"instruction": {"type": "string"}, "question": {"type": "string"}}, "required": ["instruction", "question"]}),
    types.FunctionDeclaration(name="confirm_coordinator_action", description="Start one prepared action after the client clearly confirms it. Pass only the pending confirmation ID.", parameters={"type": "object", "properties": {"confirmation_id": {"type": "string"}}, "required": ["confirmation_id"]}),
    types.FunctionDeclaration(name="inspect_coordinator_task", description="Read the exact persisted status, progress, evidence, and verified result of one task delegated by this meeting.", parameters={"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}),
    types.FunctionDeclaration(name="list_coordinator_tasks", description="List the tasks delegated by this exact meeting when the relevant task ID is uncertain."),
    types.FunctionDeclaration(name="steer_coordinator_task", description="Change one running or blocked task delegated by this meeting.", parameters={"type": "object", "properties": {"task_id": {"type": "string"}, "instruction": {"type": "string"}}, "required": ["task_id", "instruction"]}),
    types.FunctionDeclaration(name="cancel_coordinator_task", description="Cancel one unfinished task delegated by this meeting when the client asks to stop it.", parameters={"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}),
    types.FunctionDeclaration(name="answer_coordinator_question", description="Give the client's answer to an open question from a coordinator task delegated by this meeting.", parameters={"type": "object", "properties": {"task_id": {"type": "string"}, "answer": {"type": "string"}}, "required": ["task_id", "answer"]}),
    types.FunctionDeclaration(name="end_meeting", description="End the call only after the client confirms the conversation is finished.", parameters={"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}),
])]


@dataclass(frozen=True)
class MeetAgentContext:
    meeting_id: str
    client_id: str
    client_name: str
    client_email: str
    client_profile: str
    title: str
    purpose: str
    goal: dict[str, object] | None
    voice: str
    language: str


def live_config(context: MeetAgentContext, session_handle: str | None = None) -> types.LiveConnectConfig:
    session_context = json.dumps({
        "meeting_id": context.meeting_id,
        "client_id": context.client_id,
        "client_name": context.client_name,
        "client_email": context.client_email,
        "client_profile": context.client_profile,
        "meeting_title": context.title,
        "meeting_purpose": context.purpose,
        "owning_goal": context.goal,
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
