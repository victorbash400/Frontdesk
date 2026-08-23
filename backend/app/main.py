from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import get_settings
from .database import Base, engine, get_session
from .repository import create_node, ensure_default_workspace, list_nodes, search_nodes, set_trashed, update_node
from .schemas import HealthRead, NodeCreate, NodeRead, NodeUpdate


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        ensure_default_workspace(session)
    yield


app = FastAPI(title="Operator API", version="0.1.0", lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/health", response_model=HealthRead)
def health() -> HealthRead:
    return HealthRead()


@app.get("/api/nodes", response_model=list[NodeRead])
def get_nodes(parent_id: str | None = None, include_trashed: bool = False, session: Session = Depends(get_session)) -> list[NodeRead]:
    return list_nodes(session, parent_id, include_trashed)


@app.get("/api/search", response_model=list[NodeRead])
def search(q: str = Query(min_length=1, max_length=255), session: Session = Depends(get_session)) -> list[NodeRead]:
    return search_nodes(session, q)


@app.post("/api/nodes", response_model=NodeRead, status_code=201)
def post_node(body: NodeCreate, session: Session = Depends(get_session)) -> NodeRead:
    return create_node(session, body)


@app.patch("/api/nodes/{node_id}", response_model=NodeRead)
def patch_node(node_id: str, body: NodeUpdate, session: Session = Depends(get_session)) -> NodeRead:
    return update_node(session, node_id, body)


@app.post("/api/nodes/{node_id}/trash", response_model=NodeRead)
def trash_node(node_id: str, session: Session = Depends(get_session)) -> NodeRead:
    return set_trashed(session, node_id, True)


@app.post("/api/nodes/{node_id}/restore", response_model=NodeRead)
def restore_node(node_id: str, session: Session = Depends(get_session)) -> NodeRead:
    return set_trashed(session, node_id, False)
