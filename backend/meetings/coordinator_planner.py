import hashlib
import json
from uuid import uuid4

from sqlalchemy import select

from agents.goal_planner import create_goal_planner_runner, plan_goal
from app.chat_stream import sessions
from app.database import SessionLocal
from app.goals import require_goal
from app.models import GoalAssignment, PluginInstallation, Skill
from app.skills import list_skills


async def plan_meeting_assignment(
    account_id: str,
    goal_id: str,
    meeting_id: str,
    instruction: str,
) -> tuple[str, str]:
    """Plan and persist one independent task for a live client meeting."""
    planner = create_goal_planner_runner(sessions)
    session_id = hashlib.sha256(f"{account_id}:meeting-planner:{meeting_id}:{uuid4().hex}".encode()).hexdigest()
    with SessionLocal() as session:
        goal = require_goal(session, account_id, goal_id)
        skill_catalog = list_skills(session, account_id)
        installed_plugins = set(session.scalars(select(PluginInstallation.plugin_id).where(
            PluginInstallation.account_id == account_id,
        )))
    skill_index = [{
        "id": item["id"],
        "name": item["name"],
        "description": item["description"],
        "required_plugin_ids": item["requiredPluginIds"],
        "available": set(item["requiredPluginIds"]).issubset(installed_plugins),
    } for item in skill_catalog if set(item["requiredPluginIds"]).issubset({"aqualabs-store"})]
    permitted_skill_ids = {str(item["id"]) for item in skill_index}
    plan = await plan_goal(
        planner,
        account_id,
        session_id,
        (
            "Create one bounded background task for work requested during an already-active live client meeting. "
            "The call, client identity, Meet space, invitation, participant, and conversation already exist. "
            "Never create, schedule, email, join, replace, or end a meeting. Never repeat client discovery or "
            "reconstruct the call workflow. AquaLabs Store is the only permitted application; never select or use "
            "Jira, Slack, Google Workspace, Titan Mail, Drive, Docs, Browser Use, or another plugin. Plan only the "
            "exact AquaLabs Store investigation or application action requested "
            f"inside the existing conversation. Do not alter existing goal tasks.\n\n{instruction}"
        ),
        [],
        skill_index,
        [skill_id for skill_id in json.loads(goal.skill_ids) if skill_id in permitted_skill_ids],
    )
    if len(plan.operations) != 1 or plan.operations[0].action != "create":
        raise RuntimeError("The coordinator planner must return one independent meeting task.")
    operation = plan.operations[0]
    if not operation.key or not operation.title or not operation.instruction or operation.depends_on:
        raise RuntimeError("The coordinator returned an incomplete or dependent meeting task.")

    available_skill_ids = {str(item["id"]) for item in skill_catalog}
    unknown_skills = [skill_id for skill_id in operation.skill_ids if skill_id not in available_skill_ids]
    if unknown_skills:
        raise RuntimeError(f"The coordinator selected unknown organization skills: {', '.join(unknown_skills)}")
    with SessionLocal() as session:
        goal = require_goal(session, account_id, goal_id)
        skills = {
            skill.id: skill
            for skill in session.scalars(select(Skill).where(Skill.account_id == account_id))
        }
        required_plugins = {
            plugin_id
            for skill_id in operation.skill_ids
            for plugin_id in json.loads(skills[skill_id].required_plugin_ids)
        }
        missing_plugins = sorted(required_plugins - installed_plugins)
        if missing_plugins:
            raise RuntimeError(f"Coordinator work requires plugins that are not installed: {', '.join(missing_plugins)}")
        selected_plugins = set(json.loads(goal.plugin_ids)) | required_plugins
        assignment = GoalAssignment(
            goal_id=goal_id,
            source_meeting_id=meeting_id,
            auxiliary=True,
            title=operation.title,
            instruction=operation.instruction,
            status="queued",
            phase="queued",
            current_step=operation.title,
            required_inputs=json.dumps(operation.required_inputs),
            expected_outputs=json.dumps(operation.expected_outputs),
            skill_ids=json.dumps(operation.skill_ids),
        )
        session.add(assignment)
        goal.plugin_ids = json.dumps(sorted(selected_plugins))
        session.commit()
        return assignment.id, goal.client_id
