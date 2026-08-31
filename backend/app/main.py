from contextlib import asynccontextmanager
import asyncio
import html
import json
import logging

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.responses import HTMLResponse, Response, StreamingResponse

from .accounts import authenticate_account, create_account, ensure_demo_account
from .auth import require_account_id, require_scheduler
from .chat_stream import stream_agent_events
from .config import get_settings
from .database import SessionLocal, get_session, initialize_database
from .event_stream import account_events
from .email_agent import email_agent
from .goal_tasks import goal_tasks
from .goals_chat_stream import stream_goals_chat
from .google_oauth import begin_connection, connection_status, disconnect, finish_connection, profile_photo, set_workspace_permission
from .goals import answer_notification, claim_due_automations, create_automation, create_goal, delete_goal, list_goals, list_notifications, update_goal
from .github_repositories import repository_access, set_repository_access
from .mcp_oauth import begin_connection as begin_mcp_connection
from .mcp_oauth import connection_support, disconnect as disconnect_mcp, finish_connection as finish_mcp_connection
from .mailboxes import connect_titan_mailbox, disconnect_mailbox, list_mailbox_threads, mailbox_status, mailboxes
from .models import Goal, GoalAssignment, GoalBrowserPreview, MailboxConnection
from .plugin_service import install_plugin, plugin_snapshot, set_plugin_permission, uninstall_plugin
from .repository import create_node, filesystem_snapshot, list_nodes, search_nodes, set_trashed, sync_nodes, update_node
from .schemas import AccountCreate, AccountCredentials, AccountRead, AutomationCreate, ChatRequest, FileSystemSync, GitHubRepositoryUpdate, GoalCreate, GoalsChatRequest, GoalUpdate, HealthRead, NodeCreate, NodeRead, NodeUpdate, NotificationAnswer, PermissionUpdate, SkillCreate, SkillUpdate, TitanMailboxConnect, VoiceTicketRequest
from .skills import create_skill, delete_skill, list_skills, update_skill
from .voice import create_voice_ticket, run_voice_session
from meetings.routes import router as meetings_router
from tools.browser_use.cloud_relay import router as browser_relay_router
from tools.browser_use.relay_worker import browser_relay_workers
from .agent_tool_gateway import router as agent_tool_router


# Application loggers have no handler of their own, so without this the standard
# library's last-resort handler drops everything below WARNING. Operational lines such
# as mailbox ownership and message delivery are logged at INFO and were invisible in
# Cloud Run, leaving only failures visible and making live diagnosis guesswork.
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    with SessionLocal() as session:
        ensure_demo_account(session)
    await goal_tasks.recover()
    await email_agent.recover()
    await mailboxes.recover()
    try:
        yield
    finally:
        await browser_relay_workers.close()
        await mailboxes.close()
        await email_agent.close()


app = FastAPI(title="Front Desk API", version="0.1.0", lifespan=lifespan)
app.include_router(meetings_router)
app.include_router(browser_relay_router)
app.include_router(agent_tool_router)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-Front-Desk-Account", "X-Front-Desk-Internal-Secret"],
)


@app.get("/health", response_model=HealthRead)
def health() -> HealthRead:
    return HealthRead()


@app.post("/accounts", response_model=AccountRead, status_code=201)
def post_account(body: AccountCreate, session: Session = Depends(get_session)) -> AccountRead:
    try:
        return AccountRead.model_validate(create_account(session, body.email, body.password, body.name), from_attributes=True)
    except ValueError as error:
        code = 409 if "already exists" in str(error) else 422
        raise HTTPException(code, str(error)) from error


@app.post("/accounts/authenticate", response_model=AccountRead)
def authenticate(body: AccountCredentials, session: Session = Depends(get_session)) -> AccountRead:
    account = authenticate_account(session, body.email, body.password)
    if not account:
        raise HTTPException(401, "Email or password is incorrect.")
    return AccountRead.model_validate(account, from_attributes=True)


@app.post("/api/chat/stream")
def chat_stream(body: ChatRequest, account_id: str = Depends(require_account_id)) -> StreamingResponse:
    events = stream_agent_events(
        account_id=account_id,
        client_id=body.client_id,
        chat_id=body.chat_id,
        message=body.message,
        create_title=body.create_title,
    )
    return StreamingResponse(events, media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/goals/chat/stream")
def goals_chat_stream(body: GoalsChatRequest, account_id: str = Depends(require_account_id)) -> StreamingResponse:
    events = stream_goals_chat(account_id=account_id, chat_id=body.chat_id, message=body.message, create_title=body.create_title)
    return StreamingResponse(events, media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/voice/ticket")
def post_voice_ticket(body: VoiceTicketRequest, account_id: str = Depends(require_account_id)) -> dict[str, str]:
    return {"ticket": create_voice_ticket(account_id, body.client_id, body.session_id)}


@app.websocket("/api/voice/{session_id}")
async def voice_socket(websocket: WebSocket, session_id: str, ticket: str, voice: str = "Kore", language: str = "en") -> None:
    await run_voice_session(websocket, session_id, ticket, voice, language)


@app.get("/api/goals")
def get_goals(client_id: str | None = None, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> list[dict[str, object]]:
    return list_goals(session, account_id, client_id)


@app.get("/api/mailbox")
def get_mailbox(account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, object]:
    return mailbox_status(session, account_id)


@app.get("/api/mailbox/threads")
def get_mailbox_threads(account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> list[dict[str, object]]:
    return list_mailbox_threads(session, account_id)


@app.post("/api/mailbox/messages/{message_id}/retry", status_code=202)
async def retry_email_agent(message_id: str, account_id: str = Depends(require_account_id)) -> dict[str, str]:
    try:
        return await email_agent.retry(account_id, message_id)
    except RuntimeError as error:
        raise HTTPException(404, str(error)) from error


@app.post("/api/mailbox/titan/connect")
async def post_titan_mailbox(body: TitanMailboxConnect, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        snapshot = await asyncio.to_thread(connect_titan_mailbox, session, account_id, body.email, body.password)
    except RuntimeError as error:
        logger.warning("mailbox=titan account=%s connection=rejected detail=%s", account_id, error)
        raise HTTPException(400, str(error)) from error
    connection = session.scalar(select(MailboxConnection).where(MailboxConnection.account_id == account_id, MailboxConnection.provider == "titan"))
    if connection:
        await mailboxes.start(connection.id)
    return snapshot


@app.delete("/api/mailbox")
async def remove_mailbox(account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, bool]:
    connection = session.scalar(select(MailboxConnection).where(MailboxConnection.account_id == account_id, MailboxConnection.provider == "titan"))
    if connection:
        await mailboxes.stop(connection.id)
    disconnect_mailbox(session, account_id)
    return {"deleted": True}


@app.get("/api/workspace/previews/{file_id}")
async def workspace_file_preview(file_id: str, account_id: str = Depends(require_account_id)) -> Response:
    from tools.workspace import DRIVE_API, google_resource_id, workspace_access_token

    try:
        resource_id = google_resource_id(file_id)
        token = await workspace_access_token(account_id)
    except RuntimeError as error:
        raise HTTPException(400, str(error)) from error
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        metadata = await client.get(f"{DRIVE_API}/files/{resource_id}", headers=headers, params={"fields": "thumbnailLink"})
        if metadata.is_error:
            raise HTTPException(metadata.status_code, "Google Drive preview metadata is unavailable.")
        thumbnail_link = metadata.json().get("thumbnailLink")
        if not thumbnail_link:
            raise HTTPException(404, "This Workspace file does not provide a rendered preview.")
        thumbnail = await client.get(thumbnail_link, headers=headers)
    content_type = thumbnail.headers.get("content-type", "")
    if thumbnail.is_error or not content_type.startswith("image/"):
        raise HTTPException(502, "Google Drive returned an invalid preview image.")
    return Response(content=thumbnail.content, media_type=content_type, headers={"Cache-Control": "private, no-store"})


@app.get("/api/browser/previews/{assignment_id}")
def browser_task_preview(assignment_id: str, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> Response:
    preview = session.scalar(
        select(GoalBrowserPreview)
        .join(GoalAssignment, GoalAssignment.id == GoalBrowserPreview.assignment_id)
        .join(Goal, Goal.id == GoalAssignment.goal_id)
        .where(GoalBrowserPreview.assignment_id == assignment_id, Goal.account_id == account_id)
    )
    if not preview:
        raise HTTPException(404, "This task does not have a browser preview.")
    return Response(content=preview.image, media_type="image/png", headers={"Cache-Control": "private, no-store", "ETag": preview.revision})


@app.post("/api/goals", status_code=201)
async def post_goal(body: GoalCreate, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, object]:
    goal = create_goal(session, account_id, body.client_id, body.text, body.skill_ids, body.plugin_ids)
    if body.plugin_ids:
        await goal_tasks.start(account_id, str(goal["id"]))
    return goal


@app.get("/api/skills")
def get_skills(account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> list[dict[str, object]]:
    return list_skills(session, account_id)


@app.post("/api/skills", status_code=201)
def post_skill(body: SkillCreate, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        return create_skill(session, account_id, **body.model_dump())
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@app.put("/api/skills/{skill_id}")
def put_skill(skill_id: str, body: SkillUpdate, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        return update_skill(session, account_id, skill_id, **body.model_dump())
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@app.delete("/api/skills/{skill_id}")
def remove_skill(skill_id: str, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, bool]:
    try:
        delete_skill(session, account_id, skill_id)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    return {"deleted": True}


@app.patch("/api/goals/{goal_id}")
async def patch_goal(goal_id: str, body: GoalUpdate, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, object]:
    if body.status in {"paused", "completed"}:
        await goal_tasks.cancel(goal_id)
    goal = update_goal(session, account_id, goal_id, **body.model_dump(exclude_unset=True))
    if body.status == "active" and goal["pluginIds"]:
        await goal_tasks.start(account_id, goal_id)
    return goal


@app.delete("/api/goals/{goal_id}")
async def remove_goal(goal_id: str, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, bool]:
    await goal_tasks.cancel(goal_id)
    delete_goal(session, account_id, goal_id)
    return {"deleted": True}


@app.post("/api/goals/{goal_id}/automations", status_code=201)
def post_goal_automation(goal_id: str, body: AutomationCreate, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, object]:
    return create_automation(session, account_id, goal_id, body.instruction, body.interval_seconds, body.timezone)


@app.get("/api/notifications")
def get_notifications(client_id: str | None = None, open_questions: bool = False, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> list[dict[str, object]]:
    return list_notifications(session, account_id, client_id, open_questions=open_questions)


@app.get("/api/events/stream")
def get_event_stream(account_id: str = Depends(require_account_id)) -> StreamingResponse:
    return StreamingResponse(account_events.subscribe(account_id), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/notifications/{notification_id}/answer")
async def post_notification_answer(notification_id: str, body: NotificationAnswer, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, object]:
    notification = answer_notification(session, account_id, notification_id, body.answer)
    await goal_tasks.start(
        account_id,
        str(notification["goalId"]),
        f"The user answered the blocking question: {body.answer}\nContinue the goal using this answer.",
    )
    return notification


@app.post("/internal/automations/run")
async def post_run_automations(
    _: None = Depends(require_scheduler),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    results = claim_due_automations(session)
    for result in results:
        await goal_tasks.start(str(result["account_id"]), str(result["goal_id"]), str(result["instruction"]))
    return {"processed": len(results), "results": results}


@app.get("/api/plugins/google")
def get_google_connection(account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, object]:
    return connection_status(session, account_id)


@app.get("/api/plugins/google/avatar")
async def get_google_avatar(account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> Response:
    try:
        content, content_type = await profile_photo(session, account_id)
    except ValueError as error:
        raise HTTPException(404, str(error)) from error
    except httpx.HTTPError as error:
        raise HTTPException(502, "Google profile photo could not be loaded.") from error
    return Response(content=content, media_type=content_type, headers={"Cache-Control": "private, max-age=31536000, immutable"})


@app.post("/api/plugins/google/start")
def start_google_connection(account_id: str = Depends(require_account_id)) -> dict[str, str]:
    try:
        return {"authorization_url": begin_connection(account_id)}
    except RuntimeError as error:
        raise HTTPException(503, str(error)) from error


@app.delete("/api/plugins/google")
def delete_google_connection(account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, bool]:
    disconnect(session, account_id)
    return {"connected": False}


@app.put("/api/plugins/google/permissions/{permission_id}")
def put_google_permission(permission_id: str, body: PermissionUpdate, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        set_workspace_permission(session, account_id, permission_id, body.enabled)
    except ValueError as error:
        raise HTTPException(404, str(error)) from error
    return connection_status(session, account_id)


@app.get("/api/plugins")
def get_plugins(account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, object]:
    return plugin_snapshot(session, account_id, connection_support())


@app.post("/api/plugins/{plugin_id}", status_code=201)
def post_plugin(plugin_id: str, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        install_plugin(session, account_id, plugin_id)
    except ValueError as error:
        raise HTTPException(404, str(error)) from error
    return plugin_snapshot(session, account_id, connection_support())


@app.delete("/api/plugins/{plugin_id}")
def delete_plugin(plugin_id: str, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        uninstall_plugin(session, account_id, plugin_id)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    return plugin_snapshot(session, account_id, connection_support())


@app.post("/api/plugins/{plugin_id}/connect")
async def post_plugin_connection(plugin_id: str, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, str]:
    try:
        return {"authorization_url": await begin_mcp_connection(session, account_id, plugin_id)}
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    except (RuntimeError, httpx.HTTPError) as error:
        raise HTTPException(503, str(error)) from error


@app.delete("/api/plugins/{plugin_id}/connect")
def delete_plugin_connection(plugin_id: str, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        disconnect_mcp(session, account_id, plugin_id)
    except ValueError as error:
        raise HTTPException(404, str(error)) from error
    return plugin_snapshot(session, account_id, connection_support())


@app.put("/api/plugins/{plugin_id}/permissions/{permission_id}")
def put_plugin_permission(plugin_id: str, permission_id: str, body: PermissionUpdate, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        set_plugin_permission(session, account_id, plugin_id, permission_id, body.enabled)
    except ValueError as error:
        raise HTTPException(404, str(error)) from error
    return plugin_snapshot(session, account_id, connection_support())


@app.get("/api/plugins/github/repositories")
async def get_github_repositories(account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        return await repository_access(session, account_id)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    except (RuntimeError, httpx.HTTPError) as error:
        raise HTTPException(502, str(error)) from error


@app.put("/api/plugins/github/repositories")
async def put_github_repositories(body: GitHubRepositoryUpdate, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        return await set_repository_access(session, account_id, body.repositories)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except (RuntimeError, httpx.HTTPError) as error:
        raise HTTPException(502, str(error)) from error


@app.get("/oauth/google/callback", response_class=HTMLResponse)
async def google_callback(state: str, code: str | None = None, error: str | None = None, session: Session = Depends(get_session)) -> HTMLResponse:
    if error or not code:
        return HTMLResponse("<h2>Front Desk was not connected.</h2><p>You can close this window.</p>", status_code=400)
    try:
        email = await finish_connection(session, state, code)
    except (ValueError, RuntimeError, httpx.HTTPError) as connection_error:
        return HTMLResponse(
            f"<h2>Front Desk was not connected.</h2><p>{html.escape(str(connection_error))}</p>",
            status_code=400,
        )
    return HTMLResponse(
        f"<h2>Front Desk is connected.</h2><p>{html.escape(email)}</p>"
        "<script>window.opener?.postMessage({type:'front-desk-google-connected'}, '*');window.close()</script>"
    )


@app.get("/oauth/mcp/callback", response_class=HTMLResponse)
async def mcp_callback(state: str, code: str | None = None, error: str | None = None, session: Session = Depends(get_session)) -> HTMLResponse:
    if error or not code:
        return HTMLResponse("<h2>Front Desk was not connected.</h2><p>You can close this window.</p>", status_code=400)
    try:
        plugin_id, account_label = await finish_mcp_connection(session, state, code)
    except Exception as connection_error:
        return HTMLResponse(
            f"<h2>Front Desk was not connected.</h2><p>{html.escape(str(connection_error))}</p>",
            status_code=400,
        )
    event = json.dumps({"type": "front-desk-plugin-connected", "pluginId": plugin_id})
    return HTMLResponse(
        f"<h2>{html.escape(plugin_id.title())} is connected.</h2><p>{html.escape(account_label)}</p>"
        f"<script>window.opener?.postMessage({event}, '*');window.close()</script>"
    )


@app.get("/api/nodes", response_model=list[NodeRead])
def get_nodes(parent_id: str | None = None, include_trashed: bool = False, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> list[NodeRead]:
    return list_nodes(session, account_id, parent_id, include_trashed)


@app.get("/api/filesystem/snapshot")
def get_filesystem_snapshot(account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> list[dict[str, object]]:
    return filesystem_snapshot(session, account_id)


@app.get("/api/search", response_model=list[NodeRead])
def search(q: str = Query(min_length=1, max_length=255), account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> list[NodeRead]:
    return search_nodes(session, account_id, q)


@app.post("/api/nodes", response_model=NodeRead, status_code=201)
def post_node(body: NodeCreate, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> NodeRead:
    return create_node(session, account_id, body)


@app.patch("/api/nodes/{node_id}", response_model=NodeRead)
def patch_node(node_id: str, body: NodeUpdate, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> NodeRead:
    return update_node(session, account_id, node_id, body)


@app.post("/api/nodes/{node_id}/trash", response_model=NodeRead)
def trash_node(node_id: str, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> NodeRead:
    return set_trashed(session, account_id, node_id, True)


@app.post("/api/nodes/{node_id}/restore", response_model=NodeRead)
def restore_node(node_id: str, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> NodeRead:
    return set_trashed(session, account_id, node_id, False)


@app.put("/api/filesystem/sync")
def put_filesystem_sync(body: FileSystemSync, account_id: str = Depends(require_account_id), session: Session = Depends(get_session)) -> dict[str, int]:
    return sync_nodes(session, account_id, body.nodes)
