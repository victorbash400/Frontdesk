from contextlib import asynccontextmanager
import html
import json

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from starlette.responses import HTMLResponse, Response, StreamingResponse

from .accounts import authenticate_account, create_account, ensure_demo_account
from .auth import require_account_id
from .chat_stream import stream_agent_events
from .config import get_settings
from .database import SessionLocal, get_session, initialize_database
from .google_oauth import begin_connection, connection_status, disconnect, finish_connection, profile_photo, set_workspace_permission
from .mcp_oauth import begin_connection as begin_mcp_connection
from .mcp_oauth import connection_support, disconnect as disconnect_mcp, finish_connection as finish_mcp_connection
from .plugin_service import install_plugin, plugin_snapshot, uninstall_plugin
from .repository import create_node, list_nodes, search_nodes, set_trashed, update_node
from .schemas import AccountCreate, AccountCredentials, AccountRead, ChatRequest, HealthRead, NodeCreate, NodeRead, NodeUpdate, PermissionUpdate


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    with SessionLocal() as session:
        ensure_demo_account(session)
    yield


app = FastAPI(title="Front Desk API", version="0.1.0", lifespan=lifespan)
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
    return Response(content=content, media_type=content_type, headers={"Cache-Control": "private, max-age=3600"})


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
