from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


NodeKind = Literal["client", "folder", "audio", "email", "document", "request", "note"]


class NodeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    kind: NodeKind
    parent_id: str | None = None


class NodeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    parent_id: str | None = None
    shared: bool | None = None
    needs_attention: bool | None = None


class NodeRead(BaseModel):
    id: str
    workspace_id: str
    parent_id: str | None
    name: str
    kind: str
    shared: bool
    needs_attention: bool
    trashed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HealthRead(BaseModel):
    status: Literal["ok"] = "ok"
