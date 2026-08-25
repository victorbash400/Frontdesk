from typing import Literal

from google.adk.tools import ToolContext


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
    """Finish the goal run only after observing evidence that the requested outcome occurred."""
    tool_context.actions.end_of_agent = True
    return {
        "status": "completed",
        "summary": summary.strip(),
        "evidence": evidence.strip(),
        "outputs": outputs or [],
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
    return {
        "status": "waiting_for_user" if blocking else "question_recorded",
        "question": question.strip(),
        "blocking": blocking,
        "context": context.strip(),
    }
