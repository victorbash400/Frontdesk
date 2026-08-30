from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from app.database import SessionLocal
from app.goal_tasks import goal_tasks
from app.goals import answer_notification, assignment_snapshot
from app.models import Goal, GoalAssignment, GoalNotification
from meetings.models import Meeting


_pending_confirmations: dict[str, dict[str, object]] = {}


async def execute_coordinator_tool(
    account_id: str,
    client_id: str,
    meeting_id: str,
    name: str,
    args: dict[str, object],
) -> dict[str, object]:
    """Execute a coordinator action scoped to one live meeting and its goal."""
    try:
        goal_id = _meeting_goal_id(account_id, client_id, meeting_id)
        if name == "prepare_coordinator_action":
            instruction = _required_text(args, "instruction")
            question = _required_text(args, "question")
            confirmation_id = f"confirmation_{uuid4().hex}"
            _pending_confirmations[confirmation_id] = {
                "account_id": account_id,
                "client_id": client_id,
                "meeting_id": meeting_id,
                "goal_id": goal_id,
                "instruction": instruction,
                "question": question,
                "prepared_at": datetime.now(timezone.utc),
                "client_turn_sequence": int(args.get("_client_turn_sequence") or 0),
            }
            return {
                "status": "awaiting_client_confirmation",
                "confirmation_id": confirmation_id,
                "question": question,
            }
        if name == "confirm_coordinator_action":
            confirmation_id = _required_text(args, "confirmation_id")
            answer = _required_text(args, "answer")
            observed_answer = str(args.get("_observed_client_answer") or "").strip()
            observed_sequence = int(args.get("_client_turn_sequence") or 0)
            pending = _pending_confirmations.get(confirmation_id)
            if not pending or any(pending[key] != value for key, value in (
                ("account_id", account_id), ("client_id", client_id), ("meeting_id", meeting_id), ("goal_id", goal_id),
            )):
                raise ValueError("That pending client confirmation is unavailable for this meeting.")
            if observed_sequence <= int(pending["client_turn_sequence"]):
                raise ValueError("Wait for the client to answer the confirmation question before starting work.")
            if not observed_answer or answer.strip().casefold() != observed_answer.casefold():
                raise ValueError("Pass the client's exact latest answer before starting work.")
            result = await goal_tasks.delegate_from_meeting(
                account_id,
                goal_id,
                meeting_id,
                f"The client explicitly confirmed this action in meeting {meeting_id}: {observed_answer}\n\n{pending['instruction']}",
            )
            if result.get("status") == "accepted":
                _pending_confirmations.pop(confirmation_id, None)
            return result
        if name == "inspect_coordinator_task":
            return {"status": "success", "task": _meeting_task(account_id, meeting_id, str(args.get("task_id") or ""))}
        if name == "list_coordinator_tasks":
            return {"status": "success", "tasks": _meeting_tasks(account_id, meeting_id), "submissions": goal_tasks.meeting_submissions(account_id, meeting_id)}
        if name == "steer_coordinator_task":
            task_id = _required_task_id(account_id, meeting_id, args)
            return await goal_tasks.steer_task(account_id, task_id, _required_text(args, "instruction"))
        if name == "cancel_coordinator_task":
            task_id = _required_task_id(account_id, meeting_id, args)
            return await goal_tasks.cancel_task(account_id, task_id)
        if name == "answer_coordinator_question":
            task_id = _required_task_id(account_id, meeting_id, args)
            answer = _required_text(args, "answer")
            with SessionLocal() as session:
                task = session.get(GoalAssignment, task_id)
                notification = session.scalar(select(GoalNotification).where(
                    GoalNotification.goal_id == task.goal_id,
                    GoalNotification.assignment_id == task_id,
                    GoalNotification.kind == "clarification",
                    GoalNotification.status == "open",
                ).order_by(GoalNotification.created_at.desc()))
                if not notification:
                    raise ValueError("This coordinator task has no open question.")
                result = answer_notification(session, account_id, notification.id, answer)
                continued_instruction = (
                    f"{task.instruction}\n\nThe client answered during meeting {meeting_id}: {answer}\n"
                    "Continue this same task using the answer."
                )
            resumed = await goal_tasks.steer_task(
                account_id,
                task_id,
                continued_instruction,
            )
            if resumed.get("status") != "steered":
                return {"status": "failed", "error": str(resumed.get("error") or "The coordinator task did not resume.")}
            return {"status": "answered", "task_id": task_id, "notification": result}
        return {"status": "failed", "error": f"Unsupported coordinator tool: {name}."}
    except Exception as error:
        return {"status": "failed", "error": str(error).strip() or error.__class__.__name__}


def _meeting_goal_id(account_id: str, client_id: str, meeting_id: str) -> str:
    with SessionLocal() as session:
        meeting = session.scalar(select(Meeting).where(
            Meeting.id == meeting_id,
            Meeting.account_id == account_id,
            Meeting.client_id == client_id,
        ))
        if not meeting:
            raise ValueError("The active meeting identity is invalid.")
        if not meeting.goal_id:
            raise ValueError("This meeting is not attached to a Front Desk goal.")
        goal = session.scalar(select(Goal).where(
            Goal.id == meeting.goal_id,
            Goal.account_id == account_id,
            Goal.client_id == client_id,
        ))
        if not goal:
            raise ValueError("The meeting goal is unavailable.")
        return goal.id


def _meeting_tasks(account_id: str, meeting_id: str) -> list[dict[str, object]]:
    with SessionLocal() as session:
        tasks = list(session.scalars(select(GoalAssignment).join(Goal).where(
            Goal.account_id == account_id,
            GoalAssignment.source_meeting_id == meeting_id,
        ).order_by(GoalAssignment.created_at)))
        return [assignment_snapshot(session, task) for task in tasks]


def _meeting_task(account_id: str, meeting_id: str, task_id: str) -> dict[str, object]:
    if not task_id:
        raise ValueError("A coordinator task ID is required.")
    with SessionLocal() as session:
        task = session.scalar(select(GoalAssignment).join(Goal).where(
            GoalAssignment.id == task_id,
            Goal.account_id == account_id,
            GoalAssignment.source_meeting_id == meeting_id,
        ))
        if not task:
            raise ValueError("That coordinator task does not belong to this meeting.")
        return assignment_snapshot(session, task)


def _required_task_id(account_id: str, meeting_id: str, args: dict[str, object]) -> str:
    task_id = _required_text(args, "task_id")
    _meeting_task(account_id, meeting_id, task_id)
    return task_id


def _required_text(args: dict[str, object], key: str) -> str:
    value = str(args.get(key) or "").strip()
    if not value:
        raise ValueError(f"{key.replace('_', ' ').capitalize()} is required.")
    return value
