import asyncio
import hashlib
import json
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
from app.goals import create_notification, require_goal
from app.models import Goal, GoalActivity, GoalAssignment, OAuthConnection, PluginInstallation
from tools.browser_use import connected_playwright_toolset
from tools.external_plugins import connected_external_plugin_toolset
from tools.goal_control import ask_goal_question, complete_goal, update_goal_progress
from tools.tool_failures import begin_single_tool, finish_single_tool, stop_on_tool_error
from tools.workspace import preflight_workspace, workspace_tools


WORKER_INSTRUCTION = """You are Front Desk's goal worker. Complete the assigned goal with only the tools provided for this run. Every provided tool was selected for this goal and verified before you started.

Report only observed results. Use update_goal_progress after each meaningful milestone. Each update must state what you learned, changed, or verified and what you will do next. Never write filler such as task accepted, starting, working, or waiting.

Call exactly one tool per model turn. Never emit parallel tool calls. For browser work, begin with browser_tabs or browser_snapshot, use browser_navigate for every URL change, and never navigate through browser_evaluate. Use fresh references and verify every consequential action with a new observation. If any browser call fails, stop; the runner records that failure. Do not retry a failed call or ask the user to repair it during the same run.

Connected remote plugins expose the complete toolset advertised by their MCP servers. For Google Workspace, prefer a specialized tool when one exists; use workspace_google_api_request for any operation covered by the granted Workspace scopes that does not have a specialized tool. When the goal explicitly asks to open or show a resource and browser tools are available, open its returned URL in Chrome and verify the page.

Finish only with complete_goal. Provide a concise summary and specific observed evidence. If required access or information is missing, use ask_goal_question. Never claim completion from intention, a dispatched action, or an unverified tool result.
"""


class GoalTaskManager:
    def __init__(self) -> None:
        self._workers: dict[str, asyncio.Task[None]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def start(self, account_id: str, goal_id: str, instruction: str | None = None) -> bool:
        existing = self._workers.get(goal_id)
        if existing and not existing.done():
            return False
        worker = asyncio.create_task(self._run(account_id, goal_id, instruction), name=f"goal-{goal_id}")
        self._workers[goal_id] = worker
        worker.add_done_callback(lambda _: self._workers.pop(goal_id, None))
        return True

    async def cancel(self, goal_id: str) -> bool:
        worker = self._workers.get(goal_id)
        if not worker or worker.done():
            return False
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
        return True

    async def recover(self) -> None:
        with SessionLocal() as session:
            interrupted = list(session.scalars(select(GoalAssignment).where(GoalAssignment.status.in_(("queued", "running")))))
            recoverable: list[tuple[str, str]] = []
            for assignment in interrupted:
                goal = session.get(Goal, assignment.goal_id)
                assignment.status = "cancelled"
                assignment.finished_at = datetime.now(timezone.utc)
                assignment.report = ""
                if goal and goal.status == "active":
                    recoverable.append((goal.account_id, goal.id))
            session.commit()
        for account_id, goal_id in recoverable:
            await self.start(account_id, goal_id)

    async def _run(self, account_id: str, goal_id: str, instruction: str | None = None) -> None:
        lock = self._locks.setdefault(goal_id, asyncio.Lock())
        async with lock:
            assignment_id = self._create_assignment(account_id, goal_id, instruction)
            toolsets: list[Any] = []
            try:
                goal = self._goal(account_id, goal_id)
                tools, toolsets = await self._preflight(account_id, goal)
                self._set_assignment(assignment_id, status="running", started_at=datetime.now(timezone.utc))
                self._publish(account_id, goal_id, "running")
                runner = self._runner(tools)
                session_id = hashlib.sha256(f"{account_id}:goal-worker:{goal_id}:{assignment_id}".encode()).hexdigest()
                existing = await sessions.get_session(app_name=runner.app_name, user_id=account_id, session_id=session_id)
                if not existing:
                    await sessions.create_session(app_name=runner.app_name, user_id=account_id, session_id=session_id, state={"account_id": account_id, "client_id": goal.client_id, "goal_id": goal.id})
                completion: dict[str, Any] | None = None
                blocked = False
                terminal_tool_error: str | None = None
                seen_calls: set[str] = set()
                seen_responses: set[str] = set()
                events = runner.run_async(
                    user_id=account_id,
                    session_id=session_id,
                    new_message=types.Content(role="user", parts=[types.Part.from_text(text=f"Goal ID: {goal.id}\nGoal: {goal.text}\nRun instruction: {instruction or goal.text}")]),
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
                        account_events.publish(account_id, {"type": "goal_tool", "goal_id": goal_id, "name": call.name, "args": call.args or {}})
                    for response in event.get_function_responses() if hasattr(event, "get_function_responses") else []:
                        response_id = response.id or response.name
                        if response_id in seen_responses:
                            continue
                        seen_responses.add(response_id)
                        payload = dict(response.response or {})
                        failed = _tool_failed(payload)
                        if failed:
                            account_events.publish(account_id, {"type": "goal_tool_result", "goal_id": goal_id, "name": response.name, "status": "error"})
                            if terminal_tool_error is None:
                                terminal_tool_error = _tool_error_message(response.name, payload)
                        elif response.name == "update_goal_progress":
                            self._record_update(account_id, goal_id, payload)
                        elif response.name == "complete_goal":
                            completion = payload
                        elif response.name == "ask_goal_question":
                            self._record_question(account_id, goal_id, payload)
                            blocked = bool(payload.get("blocking"))
                        else:
                            account_events.publish(account_id, {"type": "goal_tool_result", "goal_id": goal_id, "name": response.name, "status": "done"})
                if terminal_tool_error:
                    raise RuntimeError(terminal_tool_error)
                if blocked:
                    self._set_assignment(assignment_id, status="blocked", finished_at=datetime.now(timezone.utc), report="Waiting for the user's answer.")
                    self._publish(account_id, goal_id, "blocked")
                    return
                self._complete(account_id, goal_id, assignment_id, completion)
            except asyncio.CancelledError:
                self._set_assignment(assignment_id, status="cancelled", finished_at=datetime.now(timezone.utc), report="Stopped by the user.")
                self._publish(account_id, goal_id, "cancelled")
                raise
            except Exception as error:
                message = str(error).strip() or error.__class__.__name__
                self._set_assignment(assignment_id, status="failed", finished_at=datetime.now(timezone.utc), report=message)
                self._record_activity(account_id, goal_id, "run_failed", message)
                self._publish(account_id, goal_id, "failed", message)
            finally:
                for toolset in toolsets:
                    await toolset.close()

    async def _preflight(self, account_id: str, goal: Goal) -> tuple[list[Any], list[Any]]:
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
            else:
                external = await connected_external_plugin_toolset(account_id, plugin_id)
                toolsets.append(external)
                tools.append(external)
        return tools, toolsets

    def _runner(self, tools: list[Any]) -> Runner:
        settings = get_settings()
        model = Gemini(model=settings.gemini_model, client_kwargs={"vertexai": True, "project": settings.google_cloud_project, "location": settings.google_cloud_location}, retry_options=types.HttpRetryOptions(attempts=1))
        agent = Agent(name="front_desk_goal_worker", description="Completes one persistent Front Desk goal.", model=model, instruction=WORKER_INSTRUCTION, tools=tools, before_tool_callback=begin_single_tool, after_tool_callback=finish_single_tool, on_tool_error_callback=stop_on_tool_error, generate_content_config=types.GenerateContentConfig(thinking_config=types.ThinkingConfig(include_thoughts=True, thinking_level=types.ThinkingLevel.MEDIUM)))
        return Runner(app=App(name="front_desk_goal_worker", root_agent=agent), session_service=sessions)

    def _goal(self, account_id: str, goal_id: str) -> Goal:
        with SessionLocal() as session:
            goal = require_goal(session, account_id, goal_id)
            session.expunge(goal)
            return goal

    def _create_assignment(self, account_id: str, goal_id: str, instruction: str | None = None) -> str:
        with SessionLocal() as session:
            goal = require_goal(session, account_id, goal_id)
            assignment = GoalAssignment(goal_id=goal.id, instruction=instruction or goal.text, status="queued")
            session.add(assignment)
            session.commit()
            session.refresh(assignment)
            return assignment.id

    def _set_assignment(self, assignment_id: str, **changes: Any) -> None:
        with SessionLocal() as session:
            assignment = session.get(GoalAssignment, assignment_id)
            if not assignment:
                return
            for key, value in changes.items():
                setattr(assignment, key, value)
            session.commit()

    def _record_update(self, account_id: str, goal_id: str, update: dict[str, Any]) -> None:
        message = str(update.get("message") or "").strip()
        if not message:
            return
        evidence = json.dumps({"phase": update.get("phase"), "progress": update.get("progress"), "next_step": update.get("next_step")}, default=str)
        self._record_activity(account_id, goal_id, "worker_update", message, evidence)
        self._publish(account_id, goal_id, "running", message)

    def _record_question(self, account_id: str, goal_id: str, payload: dict[str, Any]) -> None:
        question = str(payload.get("question") or "").strip()
        if not question:
            return
        with SessionLocal() as session:
            create_notification(session, account_id, goal_id, "clarification", question)

    def _record_activity(self, account_id: str, goal_id: str, kind: str, summary: str, evidence: str = "[]") -> None:
        with SessionLocal() as session:
            goal = require_goal(session, account_id, goal_id)
            session.add(GoalActivity(goal_id=goal.id, kind=kind, summary=summary, evidence=evidence))
            session.commit()
            account_events.publish(account_id, {"type": "goals_changed", "client_id": goal.client_id, "goal_id": goal.id})

    def _complete(self, account_id: str, goal_id: str, assignment_id: str, completion: dict[str, Any] | None) -> None:
        if not completion:
            raise RuntimeError("The worker stopped without explicitly completing the goal.")
        summary = str(completion.get("summary") or "").strip()
        evidence = str(completion.get("evidence") or "").strip()
        if not summary or not evidence:
            raise RuntimeError("The worker attempted completion without evidence.")
        outputs = completion.get("outputs") or []
        with SessionLocal() as session:
            goal = require_goal(session, account_id, goal_id)
            assignment = session.get(GoalAssignment, assignment_id)
            if not assignment:
                raise RuntimeError("The persisted goal run is missing.")
            assignment.status = "completed"
            assignment.finished_at = datetime.now(timezone.utc)
            assignment.report = summary
            assignment.evidence = json.dumps({"evidence": evidence, "outputs": outputs}, default=str)
            goal.status = "completed"
            goal.completed_at = datetime.now(timezone.utc)
            goal.version += 1
            session.add(GoalActivity(goal_id=goal.id, kind="run_completed", summary=summary, evidence=json.dumps({"evidence": evidence, "outputs": outputs}, default=str)))
            session.commit()
            account_events.publish(account_id, {"type": "goals_changed", "client_id": goal.client_id, "goal_id": goal.id})
        self._publish(account_id, goal_id, "completed", summary)

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


goal_tasks = GoalTaskManager()
