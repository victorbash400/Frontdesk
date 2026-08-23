from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .accounts import authenticate_account, create_account, ensure_demo_account
from .auth import require_account_id
from .config import get_settings
from .database import SessionLocal, get_session, initialize_database
from .repository import create_node, list_nodes, search_nodes, set_trashed, update_node
from .schemas import AccountCreate, AccountCredentials, AccountRead, HealthRead, NodeCreate, NodeRead, NodeUpdate


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    with SessionLocal() as session:
        ensure_demo_account(session)
    yield


app = FastAPI(title="Operator API", version="0.1.0", lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "X-Operator-Account", "X-Operator-Internal-Secret"],
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
