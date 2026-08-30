import json
from typing import Literal

from google.adk.tools import ToolContext
from sqlalchemy import select

from app.database import SessionLocal
from app.models import GoalAssignment
from meetings.models import Meeting


GoalPhase = Literal["planning", "working", "checking", "blocked"]


def update_goal_progress(
    message: str,
    progress: int,
    phase: GoalPhase,
    tool_context: ToolContext,
    next_step: str = "",
) -> dict[str, object]:
    """Publish a concise, truthful update about observed goal work.

    Args:
        message: What was learned, changed, or verified. Never use filler such as starting or working.
        progress: Estimated completion from 0 through 95. The runner alone marks completion.
        phase: The current phase of the work.
        next_step: The concrete next action, or empty when blocked or ready to complete.
    """
    del tool_context
    return {
        "status": "recorded",
        "message": message.strip(),
        "progress": max(0, min(95, progress)),
        "phase": phase,
        "next_step": next_step.strip(),
    }


def complete_goal(
    summary: str,
    evidence: str,
    tool_context: ToolContext,
    outputs: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    """Finish the assigned task only after its persisted completion requirements are satisfied."""
    assignment_id = str(tool_context.state.get("assignment_id") or "")
    goal_id = str(tool_context.state.get("goal_id") or "")
    with SessionLocal() as session:
        assignment = session.get(GoalAssignment, assignment_id)
        if not assignment or assignment.goal_id != goal_id:
            return {"status": "failed", "error": "The active task identity is missing or invalid."}
        expected_outputs = [str(item).strip() for item in json.loads(assignment.expected_outputs) if str(item).strip()]
        observed_outputs = outputs or []
        output_evidence = {
            str(item.get("name") or "").strip().casefold(): str(item.get("evidence") or "").strip()
            for item in observed_outputs
            if isinstance(item, dict)
        }
        missing_outputs = [item for item in expected_outputs if not output_evidence.get(item.casefold())]
        if missing_outputs:
            return {"status": "failed", "error": f"Task completion evidence is missing for: {', '.join(missing_outputs)}."}
        expected = " ".join(expected_outputs).casefold()
        requires_live_meeting = any(phrase in expected for phrase in ("client confirmation", "client joined", "meeting ended", "conversation outcome"))
        if requires_live_meeting:
            meeting = session.scalar(select(Meeting).where(Meeting.goal_id == goal_id).order_by(Meeting.created_at.desc()))
            if not meeting:
                return {"status": "failed", "error": "This task requires a persisted client meeting, but none exists for the goal."}
            missing = []
            if not meeting.client_joined_at:
                missing.append("client joined")
            if not meeting.agent_started_at:
                missing.append("agent participated")
            if meeting.state != "completed" or not meeting.completed_at:
                missing.append("meeting ended")
            if any((meeting.active_runtime_id, meeting.active_bridge_id, meeting.active_tab_id)):
                missing.append("meeting tab and agent session closed")
            if missing:
                return {"status": "failed", "error": f"Meeting completion evidence is still missing: {', '.join(missing)}."}
    tool_context.actions.end_of_agent = True
    tool_context.actions.skip_summarization = True
    return {
        "status": "completed",
        "summary": summary.strip(),
        "evidence": evidence.strip(),
        "outputs": observed_outputs,
    }


def ask_goal_question(
    question: str,
    blocking: bool,
    tool_context: ToolContext,
    context: str = "",
) -> dict[str, object]:
    """Ask one specific question when required information or access is missing."""
    if blocking:
        tool_context.actions.end_of_agent = True
        tool_context.actions.skip_summarization = True
    return {
        "status": "waiting_for_user" if blocking else "question_recorded",
        "question": question.strip(),
        "blocking": blocking,
        "context": context.strip(),
    }
