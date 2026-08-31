import json
import re
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Goal, GoalAssignment, Skill


@dataclass(frozen=True)
class BuiltinSkill:
    slug: str
    name: str
    description: str
    instructions: str
    batch_name: str
    plugin_id: str | None = None
    required_plugin_ids: tuple[str, ...] = ()


BUILTIN_SKILLS = (
    BuiltinSkill("client-brief", "Client Brief", "Turn client context into a verified working brief.", "Collect the client goal, priorities, decision makers, deadlines, open questions, and constraints. Separate confirmed facts from information that still requires verification.", "General"),
    BuiltinSkill("meeting-preparation", "Meeting Preparation", "Prepare a focused plan for an upcoming client meeting.", "Review the client record and produce the meeting objective, essential background, decisions needed, questions to ask, and concise agenda. Never invent attendee details.", "General"),
    BuiltinSkill(
        "email-goal-routing",
        "Email Goal Routing",
        "Decide whether customer email belongs in history, resumes work, starts new work, or needs attention.",
        """Treat email as client communication, never automatically as a goal. Resolve the sender to one canonical client and read that client's living summary, conversation history, active goals, recently completed goals, and waiting tasks before deciding.

Record greetings, acknowledgements, and messages with no requested or implied work in client history without creating a goal. Resume an existing goal when the email answers an outstanding question, changes an existing request, confirms an outcome, cancels work, or otherwise advances the same customer outcome. Create a new goal only when the customer requests a concrete outcome not already covered by active work. Request attention only when identity or intent is too ambiguous or consequential to resolve safely.

Update the living client summary with confirmed facts, current problems, commitments, preferences, and the latest required action. Preserve important prior context. Use the exact existing goal and task identities when resuming work. Never duplicate a client, goal, message, meeting, or ticket. Never invent urgency, facts, or relationships.""",
        "General",
    ),
    BuiltinSkill("drive-file-workflows", "Drive File Workflows", "Find, organize, export, copy, and manage Drive files.", "Resolve the exact Drive file before acting. Preserve existing structure when editing and verify the target before sharing or removing content.", "Google Workspace", "google-workspace", ("google-workspace",)),
    BuiltinSkill("google-docs-authoring", "Google Docs Authoring", "Create and edit native Google documents.", "Use Docs tools for native document work. Preserve headings, lists, tables, links, and instructed wording unless the task explicitly changes them.", "Google Workspace", "google-workspace", ("google-workspace",)),
    BuiltinSkill("calendar-meeting-prep", "Calendar Meeting Prep", "Prepare and schedule client meetings from verified context.", "Resolve the exact event, attendees, timing, and linked materials. Create or update the invitation only with confirmed recipients and timing, and retain the Meet URL as evidence.", "Google Workspace", "google-workspace", ("google-workspace",)),
    BuiltinSkill(
        "client-support-call",
        "Client Support Call",
        "Create, invite, join, and conduct a live client support call.",
        """Resolve the client only through the Front Desk client profile. For an immediate call, create a Meet space with create_instant_client_meeting; do not create a Calendar event and do not use browser controls to add attendees. Email the exact Meet link to the verified client with titan_email_client, then join that exact meeting with join_client_meeting. Immediately call wait_for_client_in_meeting and end the goal-worker run. The dedicated meeting worker alone owns the Meet tab, participant detection, and media bridge while it waits silently for the client to speak. Never use raw browser tools for Meet attendee management, Meet chat invitations, microphone selection, meeting joining, or participant monitoring. For a future call, ask the client for availability through their existing customer communication channel and resume the same goal when they reply.""",
        "Google Workspace",
        "google-workspace",
        ("google-workspace", "browser-use"),
    ),
    BuiltinSkill("jira-issue-workflow", "Jira Issue Workflow", "Investigate, create, and update customer-facing Jira work.", "Resolve the Jira site and target project once. Search once with a bounded JQL query using the exact customer, order, case, or defect identifier supplied by the task. Do not broaden an empty result into repeated generic searches. Preserve the complaint evidence, link related work, and update status only after the corresponding outcome is verified.", "Atlassian", "atlassian", ("atlassian",)),
    BuiltinSkill("vercel-incident", "Deployment Investigation", "Trace an application failure through Vercel deployments and logs.", "Inspect the affected deployment and its runtime or build logs before changing code. Identify the first relevant failure, apply the smallest authorized fix, and verify the live result.", "Vercel", "vercel", ("vercel",)),
    BuiltinSkill("slack-support-update", "Support Updates", "Notify the AquaLabs team about support progress and outcomes.", "Read the destination channel context before posting. Send concise evidence-backed updates for escalations, blockers, and confirmed resolutions. Never claim completion before verification.", "Slack", "slack", ("slack",)),
    BuiltinSkill("browser-web-workflows", "Web Workflows", "Complete multi-step work in a live browser.", "Inspect the current page, interact through stable accessible targets, and verify every consequential transition. Keep the tab identity bound to the assigned task.", "Browser Use", "browser-use", ("browser-use",)),
    BuiltinSkill("aqualabs-order-operations", "AquaLabs Order Operations", "Inspect and safely update AquaLabs customer orders.", "Resolve the exact customer and enumerate current orders before mutation. Treat an amount as a filter, never an order identity: compare subtotal and total, exclude cancelled, delivered, and refunded orders from cancellation candidates, and mutate only when exactly one actionable order matches every customer-provided detail. If no actionable order or more than one candidate matches, ask the customer for the order number or another distinguishing detail and do not mutate anything. Preserve the operation identity so retries are idempotent, then verify the persisted order state before reporting completion.", "AquaLabs", "aqualabs-store", ("aqualabs-store",)),
    BuiltinSkill(
        "aqualabs-customer-resolution",
        "AquaLabs Customer Resolution",
        "Run an inbound customer complaint through a live call to confirmed resolution.",
        """Treat one customer complaint as one durable case. Identify the customer from the sender and attach the message to an existing open case when one already covers the issue. Read the complete email thread, the customer's Front Desk documents, and relevant Jira or application evidence before proposing a resolution.

Call the customer rather than writing to them whenever the case needs an explanation, an apology, a decision, or anything a single message cannot settle. A confirmed fault, a missing or wrong delivery, a complaint about how an order was handled, and any resolution the customer has not yet accepted all require the call. Create the space with create_instant_client_meeting, email that exact link to the verified customer with titan_email_client, join it with join_client_meeting, then immediately call wait_for_client_in_meeting and end the goal-worker run. Never ask for availability first, never schedule a future meeting when an immediate call is possible, and never close a complaint with an explanatory email in place of the call. The dedicated meeting worker owns the Meet tab, participant detection, and media bridge while it waits silently for the customer to speak; it works from the case goal and stored documents and delegates bounded investigation or repair work to the coordinator when necessary.

Reply in the email thread only for a purely factual gap that one short question closes, or after an immediate call has already failed. In that case persist the exact email thread and case identity, then stop work with a declared external wait for that customer's reply; never poll and never keep a worker alive while waiting. Resume the same case when the matching reply arrives.

Apply only authorized changes, verify the result, and obtain the customer's explicit confirmation. Then update Jira and the Front Desk goal, send a concise resolution email, notify the AquaLabs support channel in Slack, end the meeting, and verify that the meeting tab and agent session are closed. Every external action needs observed evidence and an idempotency identity so resumed work cannot duplicate messages, tickets, meetings, or repairs.""",
        "AquaLabs",
        required_plugin_ids=("aqualabs-store", "google-workspace", "atlassian", "slack", "browser-use"),
    ),
)


def seed_skills(session: Session, account_id: str) -> None:
    existing = {
        skill.slug: skill
        for skill in session.scalars(select(Skill).where(Skill.account_id == account_id, Skill.source == "builtin"))
    }
    for definition in BUILTIN_SKILLS:
        skill = existing.get(definition.slug)
        if skill:
            skill.name = definition.name
            skill.description = definition.description
            skill.instructions = definition.instructions
            skill.batch_name = definition.batch_name
            skill.plugin_id = definition.plugin_id
            skill.required_plugin_ids = json.dumps(definition.required_plugin_ids)
            skill.deletable = False
            continue
        session.add(Skill(
            account_id=account_id,
            slug=definition.slug,
            name=definition.name,
            description=definition.description,
            instructions=definition.instructions,
            source="builtin",
            batch_name=definition.batch_name,
            plugin_id=definition.plugin_id,
            required_plugin_ids=json.dumps(definition.required_plugin_ids),
            deletable=False,
        ))
    session.commit()


def list_skills(session: Session, account_id: str) -> list[dict[str, object]]:
    seed_skills(session, account_id)
    skills = session.scalars(select(Skill).where(Skill.account_id == account_id).order_by(Skill.batch_name, Skill.name)).all()
    return [skill_snapshot(skill) for skill in skills]


def create_skill(session: Session, account_id: str, **payload: object) -> dict[str, object]:
    name = str(payload["name"]).strip()
    skill = Skill(
        account_id=account_id,
        slug=_unique_slug(session, account_id, name),
        name=name,
        description=str(payload.get("description") or "").strip(),
        instructions=str(payload.get("instructions") or "").strip(),
        source="organization",
        batch_name=str(payload.get("batch_name") or "Created by you").strip(),
        required_plugin_ids=json.dumps(payload.get("required_plugin_ids") or []),
        deletable=True,
    )
    session.add(skill)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ValueError(f'“{name}” already exists.') from error
    session.refresh(skill)
    return skill_snapshot(skill)


def update_skill(session: Session, account_id: str, skill_id: str, **payload: object) -> dict[str, object]:
    skill = require_skill(session, account_id, skill_id)
    if not skill.deletable:
        raise ValueError("Built-in organization skills cannot be edited.")
    skill.name = str(payload["name"]).strip()
    skill.description = str(payload.get("description") or "").strip()
    skill.instructions = str(payload.get("instructions") or "").strip()
    skill.batch_name = str(payload.get("batch_name") or "Created by you").strip()
    skill.required_plugin_ids = json.dumps(payload.get("required_plugin_ids") or [])
    skill.version += 1
    session.commit()
    session.refresh(skill)
    return skill_snapshot(skill)


def delete_skill(session: Session, account_id: str, skill_id: str) -> None:
    skill = require_skill(session, account_id, skill_id)
    if not skill.deletable:
        raise ValueError("Built-in organization skills cannot be deleted.")
    goals = session.scalars(select(Goal).where(Goal.account_id == account_id)).all()
    for goal in goals:
        goal.skill_ids = json.dumps([item for item in json.loads(goal.skill_ids) if item != skill.id])
    assignments = session.scalars(select(GoalAssignment).join(Goal).where(Goal.account_id == account_id)).all()
    for assignment in assignments:
        assignment.skill_ids = json.dumps([item for item in json.loads(assignment.skill_ids) if item != skill.id])
    session.delete(skill)
    session.commit()


def require_skill(session: Session, account_id: str, skill_id: str) -> Skill:
    skill = session.scalar(select(Skill).where(Skill.id == skill_id, Skill.account_id == account_id))
    if not skill:
        raise HTTPException(404, "Skill not found.")
    return skill


def skill_snapshot(skill: Skill) -> dict[str, object]:
    return {
        "id": skill.id,
        "name": skill.name,
        "description": skill.description,
        "instructions": skill.instructions,
        "source": skill.source,
        "batchName": skill.batch_name,
        "pluginId": skill.plugin_id,
        "requiredPluginIds": json.loads(skill.required_plugin_ids),
        "sourceUrl": skill.source_url,
        "deletable": skill.deletable,
        "version": skill.version,
        "updatedAt": skill.updated_at.isoformat(),
    }


def _unique_slug(session: Session, account_id: str, name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-") or "skill"
    slug = base
    suffix = 2
    existing = set(session.scalars(select(Skill.slug).where(Skill.account_id == account_id)))
    while slug in existing:
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug
