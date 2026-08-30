import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from google.adk.agents import Agent
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.runners import Runner
from google.genai import types
from sqlalchemy import select

from app.chat_stream import sessions
from app.config import get_settings
from app.database import SessionLocal
from app.event_stream import account_events
from app.goal_tool_ui import describe_goal_tool
from app.goals import create_notification, require_goal
from app.models import Goal, GoalActivity, GoalAssignment, GoalBrowserPreview, GoalTaskUpdate, PluginInstallation, Skill
from app.skills import list_skills
from app.mailboxes import titan_tools
from agents.goal_planner import create_goal_planner_runner, plan_goal
from tools.client_context import list_clients, read_client_profile
from tools.goal_tool_registry import GoalToolRegistry
from tools.goal_control import ask_goal_question, complete_goal, update_goal_progress
from tools.tool_failures import begin_single_tool, finish_single_tool, stop_on_tool_error
from meetings.models import MeetingSubmission


WORKER_INSTRUCTION = """You are Front Desk's goal worker. Complete the assigned goal with the direct tools and plugin namespaces available for this run. Direct tools are always available; plugin namespaces validate their connection only when you load them.

Preserve the exact requested outcome. Do not add optional research artifacts, tickets, account notes, Slack posts, email, scheduling, or follow-up work unless the task requires them. A request to call or speak with a client without a future time means an immediate call: create a 30-minute meeting beginning at the current time, invite the client's profile email, join it, and wait silently for the client. Do not ask the Front Desk owner to choose a time for an immediate call. A call is complete only after an actual live meeting with that client. Creating a support case, posting an internal notification, or proposing a meeting time is not contact and must never be reported as contact. For an explicitly future meeting with no confirmed time, ask the client for availability through the client's communication channel and persist the external wait. Use ask_goal_question only for a decision or ambiguity that the Front Desk owner must resolve; never use it to ask the owner for information that should come from the client.

Front Desk's client directory is the only authority for client identity. The task session contains the assigned client ID, so call read_client_profile without an ID first. If the request names a different or unclear client, call list_clients and match only an unambiguous client name, then read_client_profile with its exact ID. Never search Gmail, Slack, Drive, Jira, the browser, or another plugin to discover who a client is. If the client is absent or ambiguous in the Front Desk list, use ask_goal_question and do not guess. After identity is resolved, load only the plugin namespace required for the next concrete action. Do not load unrelated namespaces speculatively.

Report only observed results. Use update_goal_progress after each meaningful milestone. Each update must state what you learned, changed, or verified and what you will do next. Never write filler such as task accepted, starting, working, or waiting.

Call exactly one tool per model turn. Never emit parallel tool calls. A failed tool call is an observation, not a failed task: read its exact error, correct the action, and continue. Never repeat the same invalid call unchanged. For browser work, begin with browser_tabs or browser_snapshot, use browser_navigate for every URL change, and never navigate through browser_evaluate. Use fresh references and verify every consequential action with a new observation.

Connected remote plugins expose the complete toolset advertised by their MCP servers. For Google Workspace, prefer a specialized tool when one exists; use workspace_google_api_request for any operation covered by the granted Workspace scopes that does not have a specialized tool. Google Docs editor files must be read through the Docs API or exported through Drive files.export; Drive files.get?alt=media is only for binary files. If a read reports that exact download/export mismatch, correct the request once and continue. When the goal explicitly asks to open or show a resource and browser tools are available, open its returned URL in Chrome and verify the page.

Before any customer-data mutation, resolve one unique actionable target from current evidence. A customer name, approximate amount, product description, or other partial attribute is not an identifier. For order cancellation, compare both subtotal and total, exclude orders already cancelled, delivered, or refunded, and proceed only when exactly one remaining order matches the customer's words. If zero or multiple actionable candidates remain, use ask_goal_question to request the order number or another distinguishing detail. Never mutate a historical record merely because it is the closest match.

Finish only with complete_goal. Provide a concise summary, specific observed evidence, and one output entry for every expected output on the task. Each output entry must use the expected output text as its name and include its observed evidence. If required access or information is missing, use ask_goal_question. Never claim completion from intention, a dispatched action, or an unverified tool result.
"""

logger = logging.getLogger("uvicorn.error")


class GoalTaskManager:
    def __init__(self) -> None:
        self._workers: dict[str, asyncio.Task[None]] = {}
        self._delegated_workers: dict[str, asyncio.Task[None]] = {}
        self._meeting_submission_workers: dict[str, asyncio.Task[None]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._replanning: set[str] = set()

    async def start(self, account_id: str, goal_id: str, instruction: str | None = None) -> bool:
        existing = self._workers.get(goal_id)
        if existing and not existing.done():
            return False
        worker = asyncio.create_task(self._orchestrate(account_id, goal_id, instruction), name=f"goal-{goal_id}")
        self._workers[goal_id] = worker
        worker.add_done_callback(lambda finished: self._workers.pop(goal_id, None) if self._workers.get(goal_id) is finished else None)
        return True

    async def delegate_from_meeting(
        self,
        account_id: str,
        goal_id: str,
        meeting_id: str,
        instruction: str,
    ) -> dict[str, object]:
        """Plan and run bounded meeting work without interrupting the owning goal worker."""
        direction = instruction.strip()
        if not direction:
            return {"status": "failed", "error": "A coordinator instruction is required."}
        goal = self._goal(account_id, goal_id)
        if goal.status != "active":
            return {"status": "failed", "error": "Only an active meeting goal can accept delegated work."}
        submission_id = f"submission_{uuid4().hex}"
        submission = {
            "id": submission_id,
            "account_id": account_id,
            "goal_id": goal_id,
            "meeting_id": meeting_id,
            "instruction": direction,
            "status": "received",
            "task_id": None,
            "error": None,
        }
        with SessionLocal() as session:
            session.add(MeetingSubmission(**submission))
            session.commit()
        worker = asyncio.create_task(
            self._admit_meeting_submission(submission_id),
            name=f"meeting-submission-{submission_id}",
        )
        self._meeting_submission_workers[submission_id] = worker
        worker.add_done_callback(
            lambda finished: self._meeting_submission_workers.pop(submission_id, None)
            if self._meeting_submission_workers.get(submission_id) is finished
            else None
        )
        logger.info("meeting=%s submission=%s coordinator=accepted instruction=%r", meeting_id, submission_id, direction)
        return {"status": "accepted", "goal_id": goal_id, "submission_id": submission_id}

    async def _admit_meeting_submission(self, submission_id: str) -> None:
        with SessionLocal() as session:
            record = session.get(MeetingSubmission, submission_id)
            if not record:
                raise ValueError("Meeting submission not found.")
            submission = {key: getattr(record, key) for key in ("id", "account_id", "goal_id", "meeting_id", "instruction", "status", "task_id", "error")}
        account_id = str(submission["account_id"])
        goal_id = str(submission["goal_id"])
        meeting_id = str(submission["meeting_id"])
        try:
            from meetings.coordinator_planner import plan_meeting_assignment

            assignment_id, client_id = await plan_meeting_assignment(
                account_id, goal_id, meeting_id, str(submission["instruction"]),
            )
            submission.update(status="planned", task_id=assignment_id)
            self._save_submission(submission)
            account_events.publish(account_id, {"type": "goals_changed", "client_id": client_id, "goal_id": goal_id})
            account_events.publish(account_id, {"type": "meeting_submission_changed", "meeting_id": meeting_id, **self._meeting_submission_snapshot(submission)})
            self._publish_task(account_id, assignment_id)
            logger.info("meeting=%s submission=%s coordinator=planned task=%s", meeting_id, submission_id, assignment_id)
            await self._run_delegated_assignments(account_id, goal_id, [assignment_id])
        except asyncio.CancelledError:
            submission.update(status="cancelled", error=None)
            self._save_submission(submission)
            account_events.publish(
                account_id,
                {"type": "meeting_submission_changed", "meeting_id": meeting_id, **self._meeting_submission_snapshot(submission)},
            )
            raise
        except Exception as error:
            message = str(error).strip() or type(error).__name__
            submission.update(status="failed", error=message)
            self._save_submission(submission)
            account_events.publish(account_id, {"type": "meeting_submission_changed", "meeting_id": meeting_id, **self._meeting_submission_snapshot(submission)})
            logger.exception("meeting=%s submission=%s coordinator=failed error=%s", meeting_id, submission_id, message)

    def meeting_submissions(self, account_id: str, meeting_id: str) -> list[dict[str, object]]:
        with SessionLocal() as session:
            records = session.scalars(select(MeetingSubmission).where(
                MeetingSubmission.account_id == account_id,
                MeetingSubmission.meeting_id == meeting_id,
            ).order_by(MeetingSubmission.created_at))
            return [{key: getattr(item, key) for key in ("id", "status", "task_id", "instruction", "error")} for item in records]

    @staticmethod
    def _save_submission(submission: dict[str, object]) -> None:
        with SessionLocal() as session:
            record = session.get(MeetingSubmission, submission["id"])
            if not record:
                raise ValueError("Meeting submission not found.")
            for key in ("status", "task_id", "error"):
                setattr(record, key, submission[key])
            session.commit()

    @staticmethod
    def _meeting_submission_snapshot(submission: dict[str, object]) -> dict[str, object]:
        return {key: submission.get(key) for key in ("id", "status", "task_id", "instruction", "error")}

    async def _run_delegated_assignments(self, account_id: str, goal_id: str, assignment_ids: list[str]) -> None:
        for assignment_id in assignment_ids:
            if await self._run_assignment(account_id, goal_id, assignment_id) != "completed":
                return
        self._complete_goal(account_id, goal_id)

    async def cancel(self, goal_id: str) -> bool:
        worker = self._workers.get(goal_id)
        with SessionLocal() as session:
            submission_ids = set(session.scalars(select(MeetingSubmission.id).where(MeetingSubmission.goal_id == goal_id)))
            delegated_ids = set(session.scalars(select(GoalAssignment.id).where(
                GoalAssignment.goal_id == goal_id,
                GoalAssignment.auxiliary.is_(True),
            )))
        delegated = [
            delegated_worker
            for task_id, delegated_worker in self._delegated_workers.items()
            if task_id in delegated_ids and not delegated_worker.done()
        ]
        submissions = [
            submission_worker
            for submission_id, submission_worker in self._meeting_submission_workers.items()
            if submission_id in submission_ids and not submission_worker.done()
        ]
        active = [item for item in [worker, *delegated, *submissions] if item and not item.done()]
        for item in active:
            item.cancel()
        if active:
            await asyncio.gather(*active, return_exceptions=True)
        return bool(active)

    async def steer_task(self, account_id: str, task_id: str, instruction: str) -> dict[str, object]:
        task = self._owned_assignment(account_id, task_id)
        if task.status not in {"running", "blocked"}:
            return {"status": "failed", "error": "Only a running or blocked task can be steered."}
        worker = self._delegated_workers.get(task_id) if task.auxiliary else self._workers.get(task.goal_id)
        if worker and not worker.done():
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
        with SessionLocal() as session:
            persisted = session.get(GoalAssignment, task_id)
            if not persisted:
                return {"status": "failed", "error": "Goal task not found."}
            persisted.instruction = instruction.strip()
            persisted.status = "queued"
            persisted.phase = "queued"
            persisted.current_step = persisted.title or persisted.instruction
            persisted.next_step = ""
            persisted.finished_at = None
            session.commit()
        if task.auxiliary:
            worker = asyncio.create_task(self._run_delegated_assignments(account_id, task.goal_id, [task_id]), name=f"meeting-delegation-{task_id}")
            self._delegated_workers[task_id] = worker
            worker.add_done_callback(lambda finished: self._delegated_workers.pop(task_id, None) if self._delegated_workers.get(task_id) is finished else None)
        else:
            await self.start(account_id, task.goal_id)
        return {"status": "steered", "task_id": task_id, "goal_id": task.goal_id}

    async def cancel_task(self, account_id: str, task_id: str) -> dict[str, object]:
        task = self._owned_assignment(account_id, task_id)
        if task.status not in {"queued", "running", "blocked"}:
            return {"status": "failed", "error": "Only queued, running, or blocked tasks can be cancelled."}
        if task.status == "running":
            worker = self._delegated_workers.get(task_id) if task.auxiliary else self._workers.get(task.goal_id)
            if worker and not worker.done():
                worker.cancel()
                await asyncio.gather(worker, return_exceptions=True)
        self._set_assignment(task_id, status="cancelled", phase="cancelled", finished_at=datetime.now(timezone.utc), current_step="Cancelled by the user.")
        self._publish_task(account_id, task_id)
        return {"status": "cancelled", "task_id": task_id, "goal_id": task.goal_id}

    async def revise_goal(
        self,
        account_id: str,
        goal_id: str,
        instruction: str,
    ) -> dict[str, object]:
        """Apply a supervisor request through the planner, then run its authoritative board."""
        direction = instruction.strip()
        if not direction:
            return {"status": "failed", "error": "A planner instruction is required."}
        goal = self._goal(account_id, goal_id)
        if goal.status != "active":
            return {"status": "failed", "error": "Only an active goal can be revised."}
        worker = self._workers.get(goal_id)
        if worker and not worker.done():
            self._replanning.add(goal_id)
            try:
                worker.cancel()
                await asyncio.gather(worker, return_exceptions=True)
            finally:
                self._replanning.discard(goal_id)
        try:
            assignment_ids = await self._planned_assignments(account_id, self._goal(account_id, goal_id), direction)
        except Exception:
            if self._goal(account_id, goal_id).status != "active":
                raise
            self._requeue_running_assignments(goal_id)
            await self.start(account_id, goal_id)
            raise
        if assignment_ids:
            await self.start(account_id, goal_id)
        return {"status": "planned", "goal_id": goal_id, "task_ids": assignment_ids}

    async def recover(self) -> None:
        """Pause interrupted user goals; startup must never execute external work."""
        with SessionLocal() as session:
            interrupted = list(session.scalars(select(GoalAssignment).where(GoalAssignment.status.in_(("queued", "running")))))
            for assignment in interrupted:
                goal = session.get(Goal, assignment.goal_id)
                if goal and goal.status == "active":
                    previous_status = assignment.status
                    if assignment.status == "running":
                        assignment.status = "queued"
                        assignment.phase = "queued"
                        assignment.finished_at = None
                    goal.status = "paused"
                    goal.run_state = "paused"
                    goal.current_step = assignment.current_step or assignment.title
                    logger.info(
                        "goal=%s task=%s startup=paused previous_status=%s",
                        goal.id, assignment.id, previous_status,
                    )
            session.commit()

    async def _orchestrate(self, account_id: str, goal_id: str, instruction: str | None = None) -> None:
        lock = self._locks.setdefault(goal_id, asyncio.Lock())
        async with lock:
            try:
                goal = self._goal(account_id, goal_id)
                assignments = await self._planned_assignments(account_id, goal, instruction)
                for assignment_id in assignments:
                    status = await self._run_assignment(account_id, goal_id, assignment_id)
                    if status != "completed":
                        return
                self._complete_goal(account_id, goal_id)
            except asyncio.CancelledError:
                if goal_id not in self._replanning:
                    self._cancel_active_assignments(goal_id)
                    self._publish(account_id, goal_id, "cancelled")
                raise
            except Exception as error:
                message = str(error).strip() or error.__class__.__name__
                self._fail_active_assignment(account_id, goal_id, message)

    async def _run_assignment(self, account_id: str, goal_id: str, assignment_id: str) -> str:
        assignment = self._assignment(assignment_id)
        if assignment.status == "completed":
            return "completed"
        instruction = assignment.instruction
        handoff = self._dependency_handoff(assignment)
        toolsets: list[Any] = []
        try:
            goal = self._goal(account_id, goal_id)
            tools, toolsets = await self._preflight(account_id, goal, assignment)
            logger.info("goal=%s task=%s worker=starting skills=%s plugins=%s instruction=%r", goal_id, assignment_id, assignment.skill_ids, goal.plugin_ids, instruction)
            self._set_assignment(assignment_id, status="running", phase="working", started_at=datetime.now(timezone.utc), current_step=instruction)
            self._set_goal_state(goal_id, "running", instruction)
            self._publish_task(account_id, assignment_id)
            self._publish(account_id, goal_id, "running")
            selected_skills = self._assignment_skills(account_id, assignment)
            runner = self._runner(tools, selected_skills)
            session_id = hashlib.sha256(f"{account_id}:goal-worker:{goal_id}:{assignment_id}:{uuid4().hex}".encode()).hexdigest()
            existing = await sessions.get_session(app_name=runner.app_name, user_id=account_id, session_id=session_id)
            if not existing:
                await sessions.create_session(app_name=runner.app_name, user_id=account_id, session_id=session_id, state={
                    "account_id": account_id,
                    "client_id": goal.client_id,
                    "goal_id": goal.id,
                    "assignment_id": assignment_id,
                    "goal_intent": instruction,
                })
            completion: dict[str, Any] | None = None
            blocked = False
            external_wait = False
            seen_calls: set[str] = set()
            seen_responses: set[str] = set()
            events = runner.run_async(
                user_id=account_id,
                session_id=session_id,
                new_message=types.Content(role="user", parts=[types.Part.from_text(text=f"Goal ID: {goal.id}\nTask ID: {assignment_id}\nTask: {instruction}{handoff}")]),
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            )
            async for event in events:
                if event.error_message:
                    raise RuntimeError(event.error_message)
                for call in event.get_function_calls() if hasattr(event, "get_function_calls") else []:
                    call_id = call.id or call.name
                    if call_id in seen_calls:
                        continue
                    seen_calls.add(call_id)
                    event_args = dict(call.args or {})
                    logger.info("goal=%s task=%s tool=%s status=started args=%s", goal_id, assignment_id, call.name, json.dumps(event_args, default=str, separators=(",", ":")))
                    message, service = describe_goal_tool(call.name, event_args)
                    self._set_assignment(assignment_id, current_step=message)
                    self._set_goal_state(goal_id, "running", message)
                    account_events.publish(account_id, {"type": "goal_tool", "goal_id": goal_id, "task_id": assignment_id, "id": call_id, "name": call.name, "args": event_args, "message": message, "service": service})
                for response in event.get_function_responses() if hasattr(event, "get_function_responses") else []:
                    response_id = response.id or response.name
                    if response_id in seen_responses:
                        continue
                    seen_responses.add(response_id)
                    payload = dict(response.response or {})
                    failed = _tool_failed(payload)
                    logger.info("goal=%s task=%s tool=%s status=%s result=%s", goal_id, assignment_id, response.name, "failed" if failed else "completed", json.dumps(payload, default=str, separators=(",", ":")))
                    if failed:
                        message = _tool_error_message(response.name, payload)
                        account_events.publish(account_id, {"type": "goal_tool_result", "goal_id": goal_id, "task_id": assignment_id, "id": response_id, "name": response.name, "status": "error", "error": message})
                    elif response.name == "update_goal_progress":
                        self._record_update(account_id, goal_id, assignment_id, payload)
                    elif response.name == "complete_goal":
                        completion = payload
                    elif response.name == "ask_goal_question":
                        self._record_question(account_id, goal_id, assignment_id, payload)
                        blocked = bool(payload.get("blocking"))
                    elif response.name == "wait_for_client_in_meeting" and payload.get("status") == "waiting":
                        external_wait = True
                        self._record_activity(account_id, goal_id, "external_wait", str(payload.get("reason") or "Waiting for the client to join the meeting."), json.dumps({"task_id": assignment_id, "meeting_id": payload.get("meeting_id")}))
                    else:
                        preview = _workspace_preview(response.name, payload)
                        if preview:
                            self._set_assignment(assignment_id, preview_target=json.dumps({**preview, "revision": response_id}))
                            account_events.publish(account_id, {"type": "goals_changed", "client_id": goal.client_id, "goal_id": goal_id})
                        account_events.publish(account_id, {"type": "goal_tool_result", "goal_id": goal_id, "task_id": assignment_id, "id": response_id, "name": response.name, "status": "done"})
            if blocked or external_wait:
                report = "Waiting for the client to join the emailed meeting link." if external_wait else "Waiting for the user's answer."
                phase = "external_wait" if external_wait else "blocked"
                self._set_assignment(assignment_id, status="blocked", phase=phase, finished_at=datetime.now(timezone.utc), report=report)
                self._set_goal_state(goal_id, "blocked", self._assignment(assignment_id).current_step)
                self._publish_task(account_id, assignment_id)
                self._publish(account_id, goal_id, "blocked", report)
                logger.info("goal=%s task=%s worker=stopped phase=%s reason=%r", goal_id, assignment_id, phase, report)
                return "blocked"
            self._complete_assignment(account_id, goal_id, assignment_id, completion)
            return "completed"
        except asyncio.CancelledError:
            if goal_id not in self._replanning:
                self._set_assignment(assignment_id, status="cancelled", phase="cancelled", finished_at=datetime.now(timezone.utc), report="Stopped by the user.")
            raise
        except Exception as error:
            message = str(error).strip() or error.__class__.__name__
            self._set_assignment(assignment_id, status="failed", phase="failed", finished_at=datetime.now(timezone.utc), report=message, current_step=message)
            if not assignment.auxiliary:
                self._set_goal_state(goal_id, "failed", message)
            self._record_activity(account_id, goal_id, "run_failed", message)
            self._publish_task(account_id, assignment_id)
            if not assignment.auxiliary:
                self._publish(account_id, goal_id, "failed", message)
            logger.exception("goal=%s task=%s worker=failed error=%s", goal_id, assignment_id, message)
            return "failed"
        finally:
            for toolset in toolsets:
                try:
                    await toolset.close()
                except Exception as error:
                    logger.warning("task=%s toolset_cleanup=failed error=%s", assignment_id, error)

    async def _planned_assignments(
        self,
        account_id: str,
        goal: Goal,
        instruction: str | None,
    ) -> list[str]:
        with SessionLocal() as session:
            existing = list(session.scalars(select(GoalAssignment).where(
                GoalAssignment.goal_id == goal.id,
                GoalAssignment.auxiliary.is_(False),
            ).order_by(GoalAssignment.created_at)))
            pending = [item.id for item in existing if item.status == "queued"]
            if pending and not instruction:
                return pending
            ledger = [{"id": item.id, "title": item.title, "instruction": item.instruction, "status": item.status, "phase": item.phase, "progress": item.progress, "current_step": item.current_step} for item in existing]
        planner = create_goal_planner_runner(sessions)
        planning_request = instruction or goal.text
        self._set_goal_state(goal.id, "planning", f"Defining tasks for: {planning_request}")
        self._publish(account_id, goal.id, "planning", f"Defining tasks for: {planning_request}")
        planner_session_id = hashlib.sha256(f"{account_id}:goal-planner:{goal.id}:{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest()
        with SessionLocal() as session:
            skill_catalog = list_skills(session, account_id)
            installed_for_plan = set(session.scalars(select(PluginInstallation.plugin_id).where(PluginInstallation.account_id == account_id)))
        skill_index = [{"id": item["id"], "name": item["name"], "description": item["description"], "required_plugin_ids": item["requiredPluginIds"], "available": set(item["requiredPluginIds"]).issubset(installed_for_plan)} for item in skill_catalog]
        available_skill_ids = {str(item["id"]) for item in skill_catalog}
        plan = await plan_goal(planner, account_id, planner_session_id, planning_request, ledger, skill_index, json.loads(goal.skill_ids))
        logger.info("goal=%s planner=completed request=%r operations=%s", goal.id, planning_request, plan.model_dump_json())
        keys: dict[str, str] = {}
        existing_by_id = {item.id: item for item in existing}
        assignment_ids: list[str] = []
        with SessionLocal() as session:
            skill_rows = session.scalars(select(Skill).where(Skill.account_id == account_id)).all()
            skills_by_id = {skill.id: skill for skill in skill_rows}
            installed_plugins = set(session.scalars(select(PluginInstallation.plugin_id).where(PluginInstallation.account_id == account_id)))
            persisted_goal = require_goal(session, account_id, goal.id)
            if persisted_goal.status != "active":
                raise RuntimeError("The goal changed while its plan was being prepared. Reload its current state before revising it.")
            selected_plugins = set(json.loads(persisted_goal.plugin_ids))
            for operation in plan.operations:
                unknown_skills = [skill_id for skill_id in operation.skill_ids if skill_id not in available_skill_ids]
                if unknown_skills:
                    raise RuntimeError(f"The goal planner selected unknown organization skills: {', '.join(unknown_skills)}")
                required_plugins = {
                    plugin_id
                    for skill_id in operation.skill_ids
                    for plugin_id in json.loads(skills_by_id[skill_id].required_plugin_ids)
                }
                missing_plugins = sorted(required_plugins - installed_plugins)
                if missing_plugins:
                    raise RuntimeError(f"Selected skills require plugins that are not installed: {', '.join(missing_plugins)}")
                selected_plugins.update(required_plugins)
                if operation.action == "create":
                    if not operation.key or operation.key in keys or not operation.title or not operation.instruction:
                        raise RuntimeError("The goal planner returned an incomplete or duplicate create operation.")
                    unknown = [key for key in operation.depends_on if key not in keys]
                    if unknown:
                        raise RuntimeError(f"The goal planner referenced tasks that do not precede this task: {', '.join(unknown)}")
                    assignment = GoalAssignment(goal_id=goal.id, title=operation.title, instruction=operation.instruction, status="queued", phase="queued", current_step=operation.title, depends_on=json.dumps([keys[key] for key in operation.depends_on]), required_inputs=json.dumps(operation.required_inputs), expected_outputs=json.dumps(operation.expected_outputs), skill_ids=json.dumps(operation.skill_ids))
                    session.add(assignment)
                    session.flush()
                    keys[operation.key] = assignment.id
                    assignment_ids.append(assignment.id)
                    continue
                existing_task = existing_by_id.get(operation.task_id)
                persisted = session.get(GoalAssignment, operation.task_id) if existing_task else None
                if not persisted:
                    raise RuntimeError(f"The goal planner returned an invalid {operation.action} task.")
                if operation.action == "reuse":
                    if persisted.status in {"queued", "blocked"}:
                        if persisted.status == "blocked" and instruction:
                            persisted.instruction = f"{persisted.instruction}\n\nNew supervisor direction:\n{instruction}"
                            persisted.status = "queued"
                            persisted.phase = "queued"
                            persisted.finished_at = None
                        assignment_ids.append(persisted.id)
                elif operation.action == "update":
                    if persisted.status != "queued" or not operation.instruction:
                        raise RuntimeError("The goal planner can update only queued tasks with a complete instruction.")
                    persisted.title = operation.title or persisted.title
                    persisted.instruction = operation.instruction
                    persisted.current_step = persisted.title
                    persisted.skill_ids = json.dumps(operation.skill_ids)
                    assignment_ids.append(persisted.id)
                elif operation.action == "steer":
                    if persisted.status not in {"running", "blocked"} or not operation.instruction:
                        raise RuntimeError("The goal planner can steer only running or blocked tasks with a complete instruction.")
                    persisted.instruction = operation.instruction
                    persisted.status = "queued"
                    persisted.phase = "queued"
                    persisted.finished_at = None
                    persisted.report = ""
                    persisted.evidence = "[]"
                    persisted.skill_ids = json.dumps(operation.skill_ids)
                    assignment_ids.append(persisted.id)
                elif operation.action == "retry":
                    if persisted.status != "failed" or not operation.instruction:
                        raise RuntimeError("The goal planner can retry only failed tasks with a complete instruction.")
                    persisted.title = operation.title or persisted.title
                    persisted.instruction = operation.instruction
                    persisted.status = "queued"
                    persisted.phase = "queued"
                    persisted.current_step = persisted.title
                    persisted.next_step = ""
                    persisted.progress = 0
                    persisted.started_at = None
                    persisted.finished_at = None
                    persisted.report = ""
                    persisted.evidence = "[]"
                    persisted.skill_ids = json.dumps(operation.skill_ids)
                    assignment_ids.append(persisted.id)
                elif operation.action == "cancel":
                    if persisted.status not in {"queued", "running", "blocked"}:
                        raise RuntimeError("The goal planner can cancel only active tasks.")
                    persisted.status = "cancelled"
                    persisted.phase = "cancelled"
                    persisted.finished_at = datetime.now(timezone.utc)
            active_assignments = list(session.scalars(select(GoalAssignment).where(
                GoalAssignment.goal_id == goal.id,
                GoalAssignment.status != "cancelled",
            )))
            task_plugins = {
                plugin_id
                for task in active_assignments
                for skill_id in json.loads(task.skill_ids)
                if skill_id in skills_by_id
                for plugin_id in json.loads(skills_by_id[skill_id].required_plugin_ids)
            }
            persisted_goal.plugin_ids = json.dumps(sorted(task_plugins or selected_plugins))
            session.commit()
            remaining = list(session.scalars(select(GoalAssignment.id).where(
                GoalAssignment.goal_id == goal.id,
                GoalAssignment.status == "queued",
                GoalAssignment.auxiliary.is_(False),
            ).order_by(GoalAssignment.created_at)))
        assignment_ids.extend(item_id for item_id in remaining if item_id not in assignment_ids)
        if not assignment_ids and any(operation.action != "cancel" for operation in plan.operations):
            raise RuntimeError("The goal planner returned no executable task.")
        account_events.publish(account_id, {"type": "goals_changed", "client_id": goal.client_id, "goal_id": goal.id})
        next_assignment = self._assignment(assignment_ids[0]) if assignment_ids else None
        self._set_goal_state(goal.id, "queued" if next_assignment else "idle", next_assignment.title if next_assignment else "")
        return assignment_ids

    async def _preflight(self, account_id: str, goal: Goal, assignment: GoalAssignment) -> tuple[list[Any], list[Any]]:
        plugin_ids = list(dict.fromkeys(json.loads(goal.plugin_ids)))
        titan_functions = titan_tools(account_id)
        with SessionLocal() as session:
            installed = set(session.scalars(select(PluginInstallation.plugin_id).where(PluginInstallation.account_id == account_id)))
            assigned_skills = list(session.scalars(select(Skill).where(
                Skill.account_id == account_id,
                Skill.id.in_(json.loads(assignment.skill_ids)),
            ))) if json.loads(assignment.skill_ids) else []
        missing = [plugin_id for plugin_id in plugin_ids if plugin_id not in installed]
        if missing:
            raise RuntimeError(f"Selected plugins are not installed: {', '.join(missing)}")
        allowed_ids = [
            namespace
            for plugin_id in plugin_ids
            for namespace in _plugin_namespaces(plugin_id)
        ]
        if titan_functions:
            allowed_ids.append("titan-mail")
        initial_ids = _initial_tool_ids(assigned_skills, plugin_ids)
        registry = GoalToolRegistry(account_id, allowed_ids, initial_ids, titan_functions)
        tools: list[Any] = [
            update_goal_progress,
            ask_goal_question,
            complete_goal,
            list_clients,
            read_client_profile,
            registry,
        ]
        return tools, [registry]

    def _runner(self, tools: list[Any], skills: list[Skill]) -> Runner:
        settings = get_settings()
        model = Gemini(model=settings.gemini_model, client_kwargs={"vertexai": True, "project": settings.google_cloud_project, "location": settings.google_cloud_location}, retry_options=types.HttpRetryOptions(attempts=1))
        skill_instructions = "\n\n".join(f"Skill: {skill.name} (version {skill.version})\n{skill.instructions}" for skill in skills)
        registry = next((tool for tool in tools if isinstance(tool, GoalToolRegistry)), None)
        directory = registry.directory_prompt if registry else "No plugin namespaces are available for this goal."
        call_instruction = "For a direct client call, create a Meet space without a Calendar event, email its exact link to the client's profile email, join it with join_client_meeting, then call wait_for_client_in_meeting and end this worker run. The dedicated meeting worker alone monitors the participant and handles audio. Never use raw browser controls to add Meet attendees, send Meet chat invitations, choose meeting media, join a Front Desk meeting, or monitor a participant."
        instruction = f"{WORKER_INSTRUCTION}\n\n{call_instruction}\n\nPlugin namespace directory:\n{directory}" + (f"\n\nSelected organization skills for this task:\n{skill_instructions}" if skill_instructions else "")
        agent = Agent(name="front_desk_goal_worker", description="Completes one persistent Front Desk goal.", model=model, instruction=instruction, tools=tools, before_tool_callback=begin_single_tool, after_tool_callback=finish_single_tool, on_tool_error_callback=stop_on_tool_error, generate_content_config=types.GenerateContentConfig(thinking_config=types.ThinkingConfig(include_thoughts=True, thinking_level=types.ThinkingLevel.MEDIUM)))
        return Runner(app=App(name="front_desk_goal_worker", root_agent=agent), session_service=sessions)

    def _assignment_skills(self, account_id: str, assignment: GoalAssignment) -> list[Skill]:
        skill_ids = json.loads(assignment.skill_ids)
        if not skill_ids:
            return []
        with SessionLocal() as session:
            skills = list(session.scalars(select(Skill).where(Skill.account_id == account_id, Skill.id.in_(skill_ids))))
            by_id = {skill.id: skill for skill in skills}
            missing = [skill_id for skill_id in skill_ids if skill_id not in by_id]
            if missing:
                raise RuntimeError(f"Assigned organization skills are unavailable: {', '.join(missing)}")
            for skill in skills:
                session.expunge(skill)
        return [by_id[skill_id] for skill_id in skill_ids]

    def _goal(self, account_id: str, goal_id: str) -> Goal:
        with SessionLocal() as session:
            goal = require_goal(session, account_id, goal_id)
            session.expunge(goal)
            return goal

    def _assignment(self, assignment_id: str) -> GoalAssignment:
        with SessionLocal() as session:
            assignment = session.get(GoalAssignment, assignment_id)
            if not assignment:
                raise RuntimeError("The persisted goal task is missing.")
            session.expunge(assignment)
            return assignment

    def _owned_assignment(self, account_id: str, assignment_id: str) -> GoalAssignment:
        with SessionLocal() as session:
            assignment = session.scalar(select(GoalAssignment).join(Goal, Goal.id == GoalAssignment.goal_id).where(GoalAssignment.id == assignment_id, Goal.account_id == account_id))
            if not assignment:
                raise RuntimeError("Goal task not found.")
            session.expunge(assignment)
            return assignment

    def _dependency_handoff(self, assignment: GoalAssignment) -> str:
        dependency_ids = json.loads(assignment.depends_on)
        if not dependency_ids:
            return ""
        with SessionLocal() as session:
            dependencies = [session.get(GoalAssignment, dependency_id) for dependency_id in dependency_ids]
            missing = [dependency_id for dependency_id, dependency in zip(dependency_ids, dependencies, strict=True) if not dependency or dependency.status != "completed"]
            if missing:
                raise RuntimeError(f"Task prerequisites are not complete: {', '.join(missing)}")
            payload = [{"task_id": item.id, "title": item.title, "summary": item.report, "evidence": json.loads(item.evidence)} for item in dependencies if item]
        return f"\n\nVerified prerequisite outputs:\n{json.dumps(payload, default=str)}"

    def _set_assignment(self, assignment_id: str, **changes: Any) -> None:
        with SessionLocal() as session:
            assignment = session.get(GoalAssignment, assignment_id)
            if not assignment:
                return
            for key, value in changes.items():
                setattr(assignment, key, value)
            session.commit()

    def _set_goal_state(self, goal_id: str, state: str, current_step: str) -> None:
        with SessionLocal() as session:
            goal = session.get(Goal, goal_id)
            if not goal:
                return
            if goal.status == "completed" and state != "completed":
                return
            goal.run_state = state
            goal.current_step = current_step
            session.commit()

    def _record_update(self, account_id: str, goal_id: str, assignment_id: str, update: dict[str, Any]) -> None:
        message = str(update.get("message") or "").strip()
        if not message:
            return
        phase = str(update.get("phase") or "working")
        progress = max(0, min(95, int(update.get("progress") or 0)))
        next_step = str(update.get("next_step") or "").strip()
        self._record_task_update(account_id, goal_id, assignment_id, phase, progress, message, next_step)
        evidence = json.dumps({"task_id": assignment_id, "phase": phase, "progress": progress, "next_step": next_step}, default=str)
        self._record_activity(account_id, goal_id, "worker_update", message, evidence)
        self._publish(account_id, goal_id, "running")

    def _record_task_update(self, account_id: str, goal_id: str, assignment_id: str, phase: str, progress: int, message: str, next_step: str) -> None:
        with SessionLocal() as session:
            assignment = session.get(GoalAssignment, assignment_id)
            goal = require_goal(session, account_id, goal_id)
            if not assignment or assignment.goal_id != goal.id:
                raise RuntimeError("The goal task update target is invalid.")
            assignment.phase = phase
            assignment.progress = progress
            assignment.current_step = message
            assignment.next_step = next_step
            goal.run_state = "blocked" if phase == "blocked" else "running"
            goal.current_step = message
            session.add(GoalTaskUpdate(assignment_id=assignment.id, phase=phase, progress=progress, message=message, next_step=next_step))
            session.commit()
            account_events.publish(account_id, {"type": "goals_changed", "client_id": goal.client_id, "goal_id": goal.id})
        self._publish_task(account_id, assignment_id)

    def _record_question(self, account_id: str, goal_id: str, assignment_id: str, payload: dict[str, Any]) -> None:
        question = str(payload.get("question") or "").strip()
        if not question:
            return
        with SessionLocal() as session:
            create_notification(session, account_id, goal_id, "clarification", question, assignment_id)
        self._set_assignment(assignment_id, current_step=question, next_step="Waiting for the Front Desk owner's answer.")
        self._publish_task(account_id, assignment_id)

    async def _store_browser_preview(self, toolsets: list[Any], assignment_id: str, revision: str) -> bool:
        image: bytes | None = None
        for toolset in toolsets:
            try:
                capture = getattr(toolset, "capture_browser_preview", None)
                if capture:
                    image = await capture(assignment_id)
                if image:
                    break
            except Exception as error:
                logger.warning("task=%s browser_preview=failed error=%s", assignment_id, error)
        if image is None:
            return False
        with SessionLocal() as session:
            preview = session.get(GoalBrowserPreview, assignment_id)
            if preview:
                preview.image = image
                preview.revision = revision
            else:
                session.add(GoalBrowserPreview(assignment_id=assignment_id, image=image, revision=revision))
            assignment = session.get(GoalAssignment, assignment_id)
            if assignment:
                assignment.preview_target = json.dumps({"kind": "browser", "resource_id": assignment_id, "title": assignment.title, "mime_type": "image/png", "revision": revision})
            session.commit()
        return True

    def _record_activity(self, account_id: str, goal_id: str, kind: str, summary: str, evidence: str = "[]") -> None:
        with SessionLocal() as session:
            goal = require_goal(session, account_id, goal_id)
            session.add(GoalActivity(goal_id=goal.id, kind=kind, summary=summary, evidence=evidence))
            session.commit()
            account_events.publish(account_id, {"type": "goals_changed", "client_id": goal.client_id, "goal_id": goal.id})

    def _complete_assignment(self, account_id: str, goal_id: str, assignment_id: str, completion: dict[str, Any] | None) -> None:
        if not completion:
            raise RuntimeError("The worker stopped without explicitly completing its task.")
        summary = str(completion.get("summary") or "").strip()
        evidence = str(completion.get("evidence") or "").strip()
        if not summary or not evidence:
            raise RuntimeError("The worker attempted task completion without evidence.")
        outputs = completion.get("outputs") or []
        with SessionLocal() as session:
            goal = require_goal(session, account_id, goal_id)
            assignment = session.get(GoalAssignment, assignment_id)
            if not assignment:
                raise RuntimeError("The persisted goal run is missing.")
            assignment.status = "completed"
            assignment.phase = "completed"
            assignment.progress = 100
            assignment.current_step = summary
            assignment.next_step = ""
            assignment.finished_at = datetime.now(timezone.utc)
            assignment.report = summary
            assignment.evidence = json.dumps({"evidence": evidence, "outputs": outputs}, default=str)
            session.add(GoalTaskUpdate(assignment_id=assignment.id, phase="completed", progress=100, message=summary, next_step=""))
            session.add(GoalActivity(goal_id=goal.id, kind="task_completed", summary=summary, evidence=json.dumps({"task_id": assignment.id, "evidence": evidence, "outputs": outputs}, default=str)))
            session.commit()
            account_events.publish(account_id, {"type": "goals_changed", "client_id": goal.client_id, "goal_id": goal.id})
        self._publish_task(account_id, assignment_id)

    def _complete_goal(self, account_id: str, goal_id: str) -> bool:
        with SessionLocal() as session:
            goal = require_goal(session, account_id, goal_id)
            assignments = list(session.scalars(select(GoalAssignment).where(GoalAssignment.goal_id == goal.id)))
            required = [item for item in assignments if item.status != "cancelled"]
            if not required or any(item.status != "completed" for item in required):
                return False
            summary = required[-1].report
            goal.status = "completed"
            goal.run_state = "completed"
            goal.current_step = summary
            goal.completed_at = datetime.now(timezone.utc)
            goal.version += 1
            session.add(GoalActivity(goal_id=goal.id, kind="run_completed", summary=summary, evidence=json.dumps({"task_ids": [item.id for item in required]})))
            session.commit()
            account_events.publish(account_id, {"type": "goals_changed", "client_id": goal.client_id, "goal_id": goal.id})
        self._publish(account_id, goal_id, "completed", summary)
        return True

    def _cancel_active_assignments(self, goal_id: str) -> None:
        with SessionLocal() as session:
            assignments = list(session.scalars(select(GoalAssignment).where(GoalAssignment.goal_id == goal_id, GoalAssignment.status == "running")))
            for assignment in assignments:
                assignment.status = "cancelled"
                assignment.phase = "cancelled"
                assignment.finished_at = datetime.now(timezone.utc)
            goal = session.get(Goal, goal_id)
            if goal:
                goal.run_state = "cancelled"
                goal.current_step = ""
            session.commit()

    def _requeue_running_assignments(self, goal_id: str) -> None:
        with SessionLocal() as session:
            assignments = list(session.scalars(select(GoalAssignment).where(GoalAssignment.goal_id == goal_id, GoalAssignment.status == "running")))
            for assignment in assignments:
                assignment.status = "queued"
                assignment.phase = "queued"
                assignment.finished_at = None
            goal = session.get(Goal, goal_id)
            if goal and goal.status == "active":
                goal.run_state = "queued"
                goal.current_step = assignments[0].current_step if assignments else ""
            session.commit()

    def _fail_active_assignment(self, account_id: str, goal_id: str, message: str) -> None:
        with SessionLocal() as session:
            goal = require_goal(session, account_id, goal_id)
            if goal.status == "completed":
                return
            assignment = session.scalar(select(GoalAssignment).where(GoalAssignment.goal_id == goal.id, GoalAssignment.status.in_(("queued", "running"))).order_by(GoalAssignment.created_at))
            if assignment:
                assignment.status = "failed"
                assignment.phase = "failed"
                assignment.current_step = message
                assignment.report = message
                assignment.finished_at = datetime.now(timezone.utc)
            goal.run_state = "failed"
            goal.current_step = message
            session.add(GoalActivity(goal_id=goal.id, kind="run_failed", summary=message))
            session.commit()
            account_events.publish(account_id, {"type": "goals_changed", "client_id": goal.client_id, "goal_id": goal.id})
        self._publish(account_id, goal_id, "failed", message)

    def _publish(self, account_id: str, goal_id: str, state: str, summary: str | None = None) -> None:
        event: dict[str, object] = {"type": "goal_run", "goal_id": goal_id, "state": state}
        if summary:
            event["summary"] = summary
        account_events.publish(account_id, event)

    def _publish_task(self, account_id: str, assignment_id: str) -> None:
        with SessionLocal() as session:
            assignment = session.get(GoalAssignment, assignment_id)
            if not assignment or not assignment.source_meeting_id:
                return
            event = {
                "type": "meeting_task_changed",
                "meeting_id": assignment.source_meeting_id,
                "goal_id": assignment.goal_id,
                "task_id": assignment.id,
                "status": assignment.status,
                "phase": assignment.phase,
                "progress": assignment.progress,
                "current_step": assignment.current_step,
                "next_step": assignment.next_step,
                "summary": assignment.report,
                "evidence": json.loads(assignment.evidence),
            }
        account_events.publish(account_id, event)
def _plugin_namespaces(plugin_id: str) -> tuple[str, ...]:
    if plugin_id == "google-workspace":
        return (
            "workspace.gmail",
            "workspace.drive",
            "workspace.docs",
            "workspace.calendar-meet",
            "workspace.api",
        )
    return (plugin_id,)


def _initial_tool_ids(skills: list[Skill], selected_plugin_ids: list[str]) -> list[str]:
    workspace_skills = {
        "calendar-meeting-prep": "workspace.calendar-meet",
        "client-support-call": "workspace.calendar-meet",
        "drive-file-workflows": "workspace.drive",
        "google-docs-authoring": "workspace.docs",
    }
    namespaces: list[str] = []
    for skill in skills:
        required = [plugin_id for plugin_id in json.loads(skill.required_plugin_ids) if plugin_id in selected_plugin_ids]
        namespace = workspace_skills.get(skill.slug)
        if namespace:
            namespaces.append(namespace)
        elif len(required) == 1 and required[0] != "google-workspace":
            namespaces.append(required[0])
    return list(dict.fromkeys(namespaces))


def _tool_failed(payload: dict[str, Any]) -> bool:
    return bool(payload.get("error") or payload.get("isError") or payload.get("status") in {"error", "failed"})


def _tool_error_message(name: str, payload: dict[str, Any]) -> str:
    error = payload.get("error")
    if error:
        return f"{name} failed: {error}"
    content = payload.get("content")
    if isinstance(content, list):
        text = " ".join(str(block.get("text") or "") for block in content if isinstance(block, dict)).strip()
        if text:
            return f"{name} failed: {text}"
    return f"{name} failed."


def _workspace_preview(name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    preview = payload.get("preview")
    if isinstance(preview, dict) and preview.get("kind") == "workspace" and preview.get("resource_id"):
        return preview
    if name == "workspace_docs_create" and payload.get("document_id"):
        return {"kind": "workspace", "resource_id": str(payload["document_id"]), "title": payload.get("title"), "mime_type": "application/vnd.google-apps.document"}
    return None


goal_tasks = GoalTaskManager()
