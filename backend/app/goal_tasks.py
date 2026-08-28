import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

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
from app.goal_tool_ui import describe_goal_tool, goal_requires_browser
from app.goals import create_notification, require_goal
from app.models import Goal, GoalActivity, GoalAssignment, GoalBrowserPreview, GoalTaskUpdate, OAuthConnection, PluginInstallation, Skill
from app.skills import list_skills
from agents.goal_planner import create_goal_planner_runner, plan_goal
from tools.browser_use import capture_browser_preview, connected_playwright_toolset
from tools.external_plugins import connected_external_plugin_toolset
from tools.goal_control import ask_goal_question, complete_goal, update_goal_progress
from tools.tool_failures import begin_single_tool, finish_single_tool, stop_on_tool_error
from tools.workspace import preflight_workspace, workspace_tools
from meetings.tools import create_client_meeting


WORKER_INSTRUCTION = """You are Front Desk's goal worker. Complete the assigned goal with only the tools provided for this run. Every provided tool was selected for this goal and verified before you started.

Report only observed results. Use update_goal_progress after each meaningful milestone. Each update must state what you learned, changed, or verified and what you will do next. Never write filler such as task accepted, starting, working, or waiting.

Call exactly one tool per model turn. Never emit parallel tool calls. A failed tool call is an observation, not a failed task: read its exact error, correct the action, and continue. Never repeat the same invalid call unchanged. For browser work, begin with browser_tabs or browser_snapshot, use browser_navigate for every URL change, and never navigate through browser_evaluate. Use fresh references and verify every consequential action with a new observation.

Connected remote plugins expose the complete toolset advertised by their MCP servers. For Google Workspace, prefer a specialized tool when one exists; use workspace_google_api_request for any operation covered by the granted Workspace scopes that does not have a specialized tool. Google Docs editor files must be read through the Docs API or exported through Drive files.export; Drive files.get?alt=media is only for binary files. If a read reports that exact download/export mismatch, correct the request once and continue. When the goal explicitly asks to open or show a resource and browser tools are available, open its returned URL in Chrome and verify the page.

Finish only with complete_goal. Provide a concise summary, specific observed evidence, and one output entry for every expected output on the task. Each output entry must use the expected output text as its name and include its observed evidence. If required access or information is missing, use ask_goal_question. Never claim completion from intention, a dispatched action, or an unverified tool result.
"""

logger = logging.getLogger(__name__)


class GoalTaskManager:
    def __init__(self) -> None:
        self._workers: dict[str, asyncio.Task[None]] = {}
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

    async def cancel(self, goal_id: str) -> bool:
        worker = self._workers.get(goal_id)
        if not worker or worker.done():
            return False
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
        return True

    async def steer_task(self, account_id: str, task_id: str, instruction: str) -> dict[str, object]:
        task = self._owned_assignment(account_id, task_id)
        if task.status not in {"running", "blocked"}:
            return {"status": "failed", "error": "Only a running or blocked task can be steered."}
        worker = self._workers.get(task.goal_id)
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
        await self.start(account_id, task.goal_id)
        return {"status": "steered", "task_id": task_id, "goal_id": task.goal_id}

    async def cancel_task(self, account_id: str, task_id: str) -> dict[str, object]:
        task = self._owned_assignment(account_id, task_id)
        if task.status not in {"queued", "running", "blocked"}:
            return {"status": "failed", "error": "Only queued, running, or blocked tasks can be cancelled."}
        if task.status == "running":
            worker = self._workers.get(task.goal_id)
            if worker and not worker.done():
                worker.cancel()
                await asyncio.gather(worker, return_exceptions=True)
        self._set_assignment(task_id, status="cancelled", phase="cancelled", finished_at=datetime.now(timezone.utc), current_step="Cancelled by the user.")
        return {"status": "cancelled", "task_id": task_id, "goal_id": task.goal_id}

    async def revise_goal(self, account_id: str, goal_id: str, instruction: str) -> dict[str, object]:
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
            self._requeue_running_assignments(goal_id)
            await self.start(account_id, goal_id)
            raise
        if assignment_ids:
            await self.start(account_id, goal_id)
        return {"status": "planned", "goal_id": goal_id, "task_ids": assignment_ids}

    async def recover(self) -> None:
        with SessionLocal() as session:
            interrupted = list(session.scalars(select(GoalAssignment).where(GoalAssignment.status.in_(("queued", "running")))))
            recoverable: set[tuple[str, str]] = set()
            for assignment in interrupted:
                goal = session.get(Goal, assignment.goal_id)
                if goal and goal.status == "active":
                    if assignment.status == "running":
                        assignment.status = "queued"
                        assignment.phase = "queued"
                        assignment.finished_at = None
                    recoverable.add((goal.account_id, goal.id))
                    goal.run_state = "queued"
                    goal.current_step = assignment.current_step or assignment.title
            session.commit()
        for account_id, goal_id in recoverable:
            await self.start(account_id, goal_id)

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
            self._set_assignment(assignment_id, status="running", phase="working", started_at=datetime.now(timezone.utc), current_step=instruction)
            self._set_goal_state(goal_id, "running", instruction)
            self._publish(account_id, goal_id, "running")
            selected_skills = self._assignment_skills(account_id, assignment)
            runner = self._runner(tools, selected_skills)
            session_id = hashlib.sha256(f"{account_id}:goal-worker:{goal_id}:{assignment_id}".encode()).hexdigest()
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
                    message, service = describe_goal_tool(call.name, event_args)
                    self._set_assignment(assignment_id, current_step=message)
                    self._set_goal_state(goal_id, "running", message)
                    account_events.publish(account_id, {"type": "goals_changed", "client_id": goal.client_id, "goal_id": goal_id})
                    account_events.publish(account_id, {"type": "goal_tool", "goal_id": goal_id, "task_id": assignment_id, "id": call_id, "name": call.name, "args": event_args, "message": message, "service": service})
                for response in event.get_function_responses() if hasattr(event, "get_function_responses") else []:
                    response_id = response.id or response.name
                    if response_id in seen_responses:
                        continue
                    seen_responses.add(response_id)
                    payload = dict(response.response or {})
                    failed = _tool_failed(payload)
                    if failed:
                        message = _tool_error_message(response.name, payload)
                        self._record_task_update(account_id, goal_id, assignment_id, "working", self._assignment(assignment_id).progress, message, "Choose a corrected action using the tool result.")
                        account_events.publish(account_id, {"type": "goal_tool_result", "goal_id": goal_id, "task_id": assignment_id, "id": response_id, "name": response.name, "status": "error", "error": message})
                    elif response.name == "update_goal_progress":
                        self._record_update(account_id, goal_id, assignment_id, payload)
                    elif response.name == "complete_goal":
                        completion = payload
                    elif response.name == "ask_goal_question":
                        self._record_question(account_id, goal_id, payload)
                        blocked = bool(payload.get("blocking"))
                    else:
                        preview = _workspace_preview(response.name, payload)
                        if preview:
                            self._set_assignment(assignment_id, preview_target=json.dumps({**preview, "revision": response_id}))
                            account_events.publish(account_id, {"type": "goals_changed", "client_id": goal.client_id, "goal_id": goal_id})
                        elif response.name.startswith("browser_") and response.name != "browser_take_screenshot":
                            if await self._store_browser_preview(toolsets, assignment_id, response_id):
                                account_events.publish(account_id, {"type": "goals_changed", "client_id": goal.client_id, "goal_id": goal_id})
                        account_events.publish(account_id, {"type": "goal_tool_result", "goal_id": goal_id, "task_id": assignment_id, "id": response_id, "name": response.name, "status": "done"})
            if blocked:
                self._set_assignment(assignment_id, status="blocked", phase="blocked", finished_at=datetime.now(timezone.utc), report="Waiting for the user's answer.")
                self._set_goal_state(goal_id, "blocked", self._assignment(assignment_id).current_step)
                self._publish(account_id, goal_id, "blocked")
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
            self._set_goal_state(goal_id, "failed", message)
            self._record_activity(account_id, goal_id, "run_failed", message)
            self._publish(account_id, goal_id, "failed", message)
            return "failed"
        finally:
            for toolset in toolsets:
                try:
                    await toolset.close()
                except Exception as error:
                    logger.warning("task=%s toolset_cleanup=failed error=%s", assignment_id, error)

    async def _planned_assignments(self, account_id: str, goal: Goal, instruction: str | None) -> list[str]:
        with SessionLocal() as session:
            existing = list(session.scalars(select(GoalAssignment).where(GoalAssignment.goal_id == goal.id).order_by(GoalAssignment.created_at)))
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
        keys: dict[str, str] = {}
        existing_by_id = {item.id: item for item in existing}
        assignment_ids: list[str] = []
        with SessionLocal() as session:
            skill_rows = session.scalars(select(Skill).where(Skill.account_id == account_id)).all()
            skills_by_id = {skill.id: skill for skill in skill_rows}
            installed_plugins = set(session.scalars(select(PluginInstallation.plugin_id).where(PluginInstallation.account_id == account_id)))
            persisted_goal = require_goal(session, account_id, goal.id)
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
                elif operation.action == "cancel":
                    if persisted.status not in {"queued", "running", "blocked"}:
                        raise RuntimeError("The goal planner can cancel only active tasks.")
                    persisted.status = "cancelled"
                    persisted.phase = "cancelled"
                    persisted.finished_at = datetime.now(timezone.utc)
            persisted_goal.plugin_ids = json.dumps(sorted(selected_plugins))
            session.commit()
            remaining = list(session.scalars(select(GoalAssignment.id).where(GoalAssignment.goal_id == goal.id, GoalAssignment.status == "queued").order_by(GoalAssignment.created_at)))
        assignment_ids.extend(item_id for item_id in remaining if item_id not in assignment_ids)
        if not assignment_ids and any(operation.action != "cancel" for operation in plan.operations):
            raise RuntimeError("The goal planner returned no executable task.")
        account_events.publish(account_id, {"type": "goals_changed", "client_id": goal.client_id, "goal_id": goal.id})
        next_assignment = self._assignment(assignment_ids[0]) if assignment_ids else None
        self._set_goal_state(goal.id, "queued" if next_assignment else "idle", next_assignment.title if next_assignment else "")
        return assignment_ids

    async def _preflight(self, account_id: str, goal: Goal, assignment: GoalAssignment) -> tuple[list[Any], list[Any]]:
        plugin_ids = json.loads(goal.plugin_ids)
        if not plugin_ids:
            raise RuntimeError("This goal has no tools selected.")
        with SessionLocal() as session:
            installed = set(session.scalars(select(PluginInstallation.plugin_id).where(PluginInstallation.account_id == account_id)))
            google_connected = session.scalar(select(OAuthConnection.id).where(OAuthConnection.account_id == account_id, OAuthConnection.provider == "google_workspace")) is not None
        missing = [plugin_id for plugin_id in plugin_ids if plugin_id not in installed]
        if missing:
            raise RuntimeError(f"Selected plugins are not installed: {', '.join(missing)}")
        tools: list[Any] = [update_goal_progress, ask_goal_question, complete_goal]
        toolsets: list[Any] = []
        for plugin_id in plugin_ids:
            if plugin_id == "browser-use":
                if not goal_requires_browser(assignment.instruction):
                    continue
                browser = await connected_playwright_toolset()
                toolsets.append(browser)
                tools.append(browser)
            elif plugin_id == "google-workspace":
                if not google_connected:
                    raise RuntimeError("Google Workspace is not connected.")
                await preflight_workspace(account_id)
                workspace = workspace_tools(account_id)
                if not workspace:
                    raise RuntimeError("Google Workspace has no enabled tools.")
                tools.extend(workspace)
                tools.append(create_client_meeting)
            else:
                external = await connected_external_plugin_toolset(account_id, plugin_id)
                toolsets.append(external)
                tools.append(external)
        return tools, toolsets

    def _runner(self, tools: list[Any], skills: list[Skill]) -> Runner:
        settings = get_settings()
        model = Gemini(model=settings.gemini_model, client_kwargs={"vertexai": True, "project": settings.google_cloud_project, "location": settings.google_cloud_location}, retry_options=types.HttpRetryOptions(attempts=1))
        skill_instructions = "\n\n".join(f"Skill: {skill.name} (version {skill.version})\n{skill.instructions}" for skill in skills)
        instruction = WORKER_INSTRUCTION + (f"\n\nSelected organization skills for this task:\n{skill_instructions}" if skill_instructions else "")
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

    def _record_question(self, account_id: str, goal_id: str, payload: dict[str, Any]) -> None:
        question = str(payload.get("question") or "").strip()
        if not question:
            return
        with SessionLocal() as session:
            create_notification(session, account_id, goal_id, "clarification", question)

    async def _store_browser_preview(self, toolsets: list[Any], assignment_id: str, revision: str) -> bool:
        image: bytes | None = None
        for toolset in toolsets:
            try:
                names = {tool.name for tool in await toolset.get_tools()}
                if "browser_take_screenshot" in names:
                    image = await capture_browser_preview(toolset, assignment_id)
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

    def _complete_goal(self, account_id: str, goal_id: str) -> None:
        with SessionLocal() as session:
            goal = require_goal(session, account_id, goal_id)
            assignments = list(session.scalars(select(GoalAssignment).where(GoalAssignment.goal_id == goal.id)))
            required = [item for item in assignments if item.status != "cancelled"]
            if not required or any(item.status != "completed" for item in required):
                raise RuntimeError("The goal cannot complete until every planned task is complete.")
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
            if goal:
                goal.run_state = "queued"
                goal.current_step = assignments[0].current_step if assignments else ""
            session.commit()

    def _fail_active_assignment(self, account_id: str, goal_id: str, message: str) -> None:
        with SessionLocal() as session:
            goal = require_goal(session, account_id, goal_id)
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
