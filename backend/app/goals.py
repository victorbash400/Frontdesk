import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import delete as sql_delete, select
from sqlalchemy.orm import Session

from .models import Goal, GoalActivity, GoalAssignment, GoalAutomation, GoalNotification
from .event_stream import account_events


def list_goals(session: Session, account_id: str, client_id: str | None = None) -> list[dict[str, object]]:
    query = select(Goal).where(Goal.account_id == account_id)
    if client_id:
        query = query.where(Goal.client_id == client_id)
    goals = list(session.scalars(query.order_by(Goal.updated_at.desc())))
    return [goal_snapshot(session, goal) for goal in goals]


def create_goal(
    session: Session,
    account_id: str,
    client_id: str,
    text: str,
    skill_ids: list[str],
    plugin_ids: list[str],
) -> dict[str, object]:
    goal = Goal(
        account_id=account_id,
        client_id=client_id,
        text=text.strip(),
        situation="",
        skill_ids=json.dumps(skill_ids),
        plugin_ids=json.dumps(plugin_ids),
    )
    session.add(goal)
    session.flush()
    session.add(GoalActivity(goal_id=goal.id, kind="goal_created", summary="Goal created."))
    session.commit()
    session.refresh(goal)
    account_events.publish(account_id, {"type": "goals_changed", "client_id": client_id, "goal_id": goal.id})
    return goal_snapshot(session, goal)


def update_goal(
    session: Session,
    account_id: str,
    goal_id: str,
    *,
    text: str | None = None,
    situation: str | None = None,
    skill_ids: list[str] | None = None,
    plugin_ids: list[str] | None = None,
    status: str | None = None,
    expected_version: int | None = None,
) -> dict[str, object]:
    goal = require_goal(session, account_id, goal_id)
    if expected_version is not None and goal.version != expected_version:
        raise HTTPException(409, "The goal changed while it was being updated. Refresh and reconcile the latest board first.")
    if text is not None:
        goal.text = text.strip()
    if situation is not None:
        goal.situation = situation.strip()
    if skill_ids is not None:
        goal.skill_ids = json.dumps(skill_ids)
    if plugin_ids is not None:
        goal.plugin_ids = json.dumps(plugin_ids)
    if status is not None:
        goal.status = status
        goal.completed_at = datetime.now(timezone.utc) if status == "completed" else None
    goal.version += 1
    session.add(GoalActivity(goal_id=goal.id, kind="goal_updated", summary="Goal definition or current situation updated."))
    session.commit()
    session.refresh(goal)
    account_events.publish(account_id, {"type": "goals_changed", "client_id": goal.client_id, "goal_id": goal.id})
    return goal_snapshot(session, goal)


def delete_goal(session: Session, account_id: str, goal_id: str) -> None:
    goal = require_goal(session, account_id, goal_id)
    client_id = goal.client_id
    for model in (GoalNotification, GoalAutomation, GoalAssignment, GoalActivity):
        session.execute(sql_delete(model).where(model.goal_id == goal.id))
    session.delete(goal)
    session.commit()
    account_events.publish(account_id, {"type": "goals_changed", "client_id": client_id, "goal_id": goal_id})


def create_automation(
    session: Session,
    account_id: str,
    goal_id: str,
    instruction: str,
    interval_seconds: int,
    timezone_name: str,
) -> dict[str, object]:
    goal = require_goal(session, account_id, goal_id)
    if interval_seconds < 300:
        raise HTTPException(422, "Goal automations must be at least five minutes apart.")
    try:
        ZoneInfo(timezone_name)
    except Exception as error:
        raise HTTPException(422, "Unknown automation timezone.") from error
    automation = GoalAutomation(
        goal_id=goal.id,
        instruction=instruction.strip(),
        interval_seconds=interval_seconds,
        timezone=timezone_name,
        next_run_at=datetime.now(timezone.utc) + timedelta(seconds=interval_seconds),
    )
    session.add(automation)
    session.add(GoalActivity(goal_id=goal.id, kind="automation_created", summary=f"Automation scheduled every {interval_seconds // 60} minutes."))
    session.commit()
    session.refresh(automation)
    account_events.publish(account_id, {"type": "goals_changed", "client_id": goal.client_id, "goal_id": goal.id})
    return automation_snapshot(automation)


def claim_due_automations(session: Session, now: datetime | None = None) -> list[dict[str, object]]:
    current = now or datetime.now(timezone.utc)
    due = list(session.scalars(select(GoalAutomation).where(
        GoalAutomation.enabled.is_(True),
        GoalAutomation.next_run_at <= current,
    ).order_by(GoalAutomation.next_run_at.asc())))
    results: list[dict[str, object]] = []
    for automation in due:
        goal = session.get(Goal, automation.goal_id)
        if not goal or goal.status != "active":
            automation.enabled = False
            continue
        next_run_at = automation.next_run_at
        if next_run_at.tzinfo is None:
            next_run_at = next_run_at.replace(tzinfo=timezone.utc)
        while next_run_at <= current:
            next_run_at += timedelta(seconds=automation.interval_seconds)
        automation.next_run_at = next_run_at
        results.append({"automation_id": automation.id, "account_id": goal.account_id, "goal_id": goal.id, "instruction": automation.instruction})
    session.commit()
    return results


def list_notifications(session: Session, account_id: str, client_id: str | None = None) -> list[dict[str, object]]:
    query = select(GoalNotification).join(Goal).where(Goal.account_id == account_id)
    if client_id:
        query = query.where(GoalNotification.client_id == client_id)
    rows = list(session.scalars(query.order_by(GoalNotification.created_at.desc())))
    return [notification_snapshot(item) for item in rows]


def create_notification(session: Session, account_id: str, goal_id: str, kind: str, message: str) -> dict[str, object]:
    goal = require_goal(session, account_id, goal_id)
    notification = GoalNotification(goal_id=goal.id, client_id=goal.client_id, kind=kind, message=message.strip())
    session.add(notification)
    session.add(GoalActivity(goal_id=goal.id, kind=f"{kind}_created", summary=message.strip()))
    session.commit()
    session.refresh(notification)
    account_events.publish(account_id, {"type": "notifications_changed", "client_id": goal.client_id, "goal_id": goal.id})
    return notification_snapshot(notification)


def create_assignment(session: Session, account_id: str, goal_id: str, instruction: str) -> dict[str, object]:
    goal = require_goal(session, account_id, goal_id)
    assignment = GoalAssignment(goal_id=goal.id, instruction=instruction.strip())
    session.add(assignment)
    session.add(GoalActivity(goal_id=goal.id, kind="assignment_created", summary=f"Worker assigned: {instruction.strip()}"))
    session.commit()
    session.refresh(assignment)
    account_events.publish(account_id, {"type": "goals_changed", "client_id": goal.client_id, "goal_id": goal.id})
    return assignment_snapshot(assignment)


def add_goal_activity(session: Session, account_id: str, goal_id: str, kind: str, summary: str) -> dict[str, object]:
    goal = require_goal(session, account_id, goal_id)
    activity = GoalActivity(goal_id=goal.id, kind=kind, summary=summary.strip())
    session.add(activity)
    session.commit()
    session.refresh(activity)
    account_events.publish(account_id, {"type": "goals_changed", "client_id": goal.client_id, "goal_id": goal.id})
    return activity_snapshot(activity)


def answer_notification(session: Session, account_id: str, notification_id: str, answer: str) -> dict[str, object]:
    notification = session.scalar(select(GoalNotification).join(Goal).where(
        GoalNotification.id == notification_id,
        Goal.account_id == account_id,
    ))
    if not notification:
        raise HTTPException(404, "Notification not found.")
    if notification.status != "open" or notification.kind != "clarification":
        raise HTTPException(409, "This clarification is no longer open.")
    notification.answer = answer.strip()
    notification.status = "answered"
    notification.answered_at = datetime.now(timezone.utc)
    session.add(GoalActivity(goal_id=notification.goal_id, kind="clarification_answered", summary=f"User answered: {notification.answer}"))
    session.commit()
    session.refresh(notification)
    account_events.publish(account_id, {"type": "notifications_changed", "client_id": notification.client_id, "goal_id": notification.goal_id})
    return notification_snapshot(notification)


def client_goal_context(session: Session, account_id: str, client_id: str) -> str:
    goals = list_goals(session, account_id, client_id)
    active = [goal for goal in goals if goal["status"] == "active"]
    if not active:
        return "This client has no active goals."
    return "\n\n".join(
        f"Goal {goal['id']}: {goal['text']}\nCurrent situation: {goal['situation']}\n"
        f"Allowed plugins: {', '.join(goal['pluginIds']) or 'none'}\n"
        f"Allowed skills: {', '.join(goal['skillIds']) or 'none'}"
        for goal in active
    )


def require_goal(session: Session, account_id: str, goal_id: str) -> Goal:
    goal = session.scalar(select(Goal).where(Goal.id == goal_id, Goal.account_id == account_id))
    if not goal:
        raise HTTPException(404, "Goal not found.")
    return goal


def goal_snapshot(session: Session, goal: Goal) -> dict[str, object]:
    activities = list(session.scalars(select(GoalActivity).where(GoalActivity.goal_id == goal.id).order_by(GoalActivity.created_at.desc()).limit(20)))
    automations = list(session.scalars(select(GoalAutomation).where(GoalAutomation.goal_id == goal.id).order_by(GoalAutomation.created_at.desc())))
    assignments = list(session.scalars(select(GoalAssignment).where(GoalAssignment.goal_id == goal.id).order_by(GoalAssignment.created_at.desc()).limit(20)))
    run_state = goal.status
    if goal.status == "active":
        run_state = assignments[0].status if assignments else "idle"
    return {
        "id": goal.id,
        "clientId": goal.client_id,
        "text": goal.text,
        "situation": goal.situation,
        "skillIds": json.loads(goal.skill_ids),
        "pluginIds": json.loads(goal.plugin_ids),
        "status": goal.status,
        "runState": run_state,
        "version": goal.version,
        "createdAt": goal.created_at.isoformat(),
        "updatedAt": goal.updated_at.isoformat(),
        "startedAt": goal.started_at.isoformat(),
        "completedAt": goal.completed_at.isoformat() if goal.completed_at else None,
        "activities": [activity_snapshot(item) for item in activities],
        "assignments": [assignment_snapshot(item) for item in assignments],
        "automations": [automation_snapshot(item) for item in automations],
    }


def activity_snapshot(activity: GoalActivity) -> dict[str, object]:
    return {"id": activity.id, "kind": activity.kind, "summary": activity.summary, "evidence": json.loads(activity.evidence), "createdAt": activity.created_at.isoformat()}


def assignment_snapshot(assignment: GoalAssignment) -> dict[str, object]:
    return {"id": assignment.id, "instruction": assignment.instruction, "status": assignment.status, "report": assignment.report, "evidence": json.loads(assignment.evidence), "createdAt": assignment.created_at.isoformat(), "startedAt": assignment.started_at.isoformat() if assignment.started_at else None, "finishedAt": assignment.finished_at.isoformat() if assignment.finished_at else None}


def automation_snapshot(automation: GoalAutomation) -> dict[str, object]:
    return {"id": automation.id, "instruction": automation.instruction, "intervalSeconds": automation.interval_seconds, "timezone": automation.timezone, "nextRunAt": automation.next_run_at.isoformat(), "enabled": automation.enabled, "createdAt": automation.created_at.isoformat()}


def notification_snapshot(notification: GoalNotification) -> dict[str, object]:
    return {"id": notification.id, "goalId": notification.goal_id, "clientId": notification.client_id, "kind": notification.kind, "message": notification.message, "status": notification.status, "answer": notification.answer, "createdAt": notification.created_at.isoformat(), "answeredAt": notification.answered_at.isoformat() if notification.answered_at else None}
