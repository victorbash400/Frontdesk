from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


NodeKind = Literal["client", "folder", "profile", "task", "audio", "email", "document", "request", "note"]


class AccountCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=80)


class AccountCredentials(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class AccountRead(BaseModel):
    id: str
    email: str
    name: str


class ChatRequest(BaseModel):
    client_id: str = Field(min_length=1, max_length=128)
    chat_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=20_000)
    create_title: bool = False


class GoalsChatRequest(BaseModel):
    chat_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=20_000)
    create_title: bool = False


class VoiceTicketRequest(BaseModel):
    client_id: str = Field(min_length=1, max_length=128)
    session_id: str = Field(min_length=1, max_length=128)


class MeetingCreate(BaseModel):
    client_id: str = Field(min_length=1, max_length=128)
    client_email: str = Field(min_length=3, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    start_time: datetime
    end_time: datetime
    goal_id: str | None = Field(default=None, max_length=36)
    description: str = Field(default="", max_length=20_000)


class MeetingAgentTicketRequest(BaseModel):
    voice: str = Field(default="Kore", min_length=1, max_length=32)
    language: str = Field(default="en", min_length=2, max_length=8)


class GoalCreate(BaseModel):
    client_id: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=20_000)
    skill_ids: list[str] = Field(default_factory=list, max_length=100)
    plugin_ids: list[str] = Field(default_factory=list, max_length=100)


class GoalUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=20_000)
    situation: str | None = Field(default=None, min_length=1, max_length=40_000)
    skill_ids: list[str] | None = Field(default=None, max_length=100)
    plugin_ids: list[str] | None = Field(default=None, max_length=100)
    status: Literal["active", "paused", "completed"] | None = None
    expected_version: int | None = Field(default=None, ge=1)


class AutomationCreate(BaseModel):
    instruction: str = Field(min_length=1, max_length=20_000)
    interval_seconds: int = Field(ge=300, le=31_536_000)
    timezone: str = Field(default="Africa/Nairobi", min_length=1, max_length=64)


class NotificationAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=20_000)


class SkillCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2_000)
    instructions: str = Field(default="", max_length=40_000)
    batch_name: str = Field(default="Created by you", min_length=1, max_length=128)
    required_plugin_ids: list[str] = Field(default_factory=list, max_length=50)


class SkillUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2_000)
    instructions: str = Field(default="", max_length=40_000)
    batch_name: str = Field(default="Created by you", min_length=1, max_length=128)
    required_plugin_ids: list[str] = Field(default_factory=list, max_length=50)


class TitanMailboxConnect(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=1024)


class PermissionUpdate(BaseModel):
    enabled: bool


class GitHubRepositoryUpdate(BaseModel):
    repositories: list[str] = Field(max_length=10_000)


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


class FileSystemNodeSync(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    parent_id: str | None = Field(default=None, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    kind: NodeKind
    shared: bool = False
    needs_attention: bool = False
    trashed_at: datetime | None = None
    content: str | None = Field(default=None, max_length=200_000)


class FileSystemSync(BaseModel):
    nodes: list[FileSystemNodeSync] = Field(max_length=10_000)


class HealthRead(BaseModel):
    status: Literal["ok"] = "ok"
