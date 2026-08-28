from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def new_id() -> str:
    return str(uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    salt: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    needs_attention: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trashed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    tags: Mapped[list["Tag"]] = relationship(secondary="node_tags", lazy="selectin")


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    color: Mapped[str] = mapped_column(String(16), nullable=False)


class NodeTag(Base):
    __tablename__ = "node_tags"

    node_id: Mapped[str] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[str] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    node_id: Mapped[str] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"), unique=True, index=True)
    bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)


class CustomerMemory(Base):
    __tablename__ = "customer_memory"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    client_id: Mapped[str] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class DocumentContent(Base):
    __tablename__ = "document_contents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    node_id: Mapped[str] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"), unique=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class OAuthConnection(Base):
    __tablename__ = "oauth_connections"
    __table_args__ = (UniqueConstraint("account_id", "provider"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    profile_name: Mapped[str | None] = mapped_column(String(255))
    picture_url: Mapped[str | None] = mapped_column(Text)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[str] = mapped_column(Text, nullable=False)
    unavailable_permissions: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class PluginInstallation(Base):
    __tablename__ = "plugin_installations"
    __table_args__ = (UniqueConstraint("account_id", "plugin_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    plugin_id: Mapped[str] = mapped_column(String(48), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PluginConnection(Base):
    __tablename__ = "plugin_connections"
    __table_args__ = (UniqueConstraint("account_id", "plugin_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    plugin_id: Mapped[str] = mapped_column(String(48), nullable=False)
    account_label: Mapped[str | None] = mapped_column(String(255))
    credentials: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[str] = mapped_column(Text, nullable=False)
    tool_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class PluginOAuthAttempt(Base):
    __tablename__ = "plugin_oauth_attempts"

    state: Mapped[str] = mapped_column(String(128), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    plugin_id: Mapped[str] = mapped_column(String(48), nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class GitHubRepositoryAccess(Base):
    __tablename__ = "github_repository_access"
    __table_args__ = (UniqueConstraint("account_id", "full_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)


class PluginPermission(Base):
    __tablename__ = "plugin_permissions"
    __table_args__ = (UniqueConstraint("account_id", "permission_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    permission_id: Mapped[str] = mapped_column(String(80), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = (UniqueConstraint("account_id", "slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(24), nullable=False, default="organization")
    batch_name: Mapped[str] = mapped_column(String(128), nullable=False, default="Organization")
    plugin_id: Mapped[str | None] = mapped_column(String(48), index=True)
    required_plugin_ids: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    source_url: Mapped[str | None] = mapped_column(Text)
    deletable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[str] = mapped_column(String(128), index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    situation: Mapped[str] = mapped_column(Text, nullable=False)
    skill_ids: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    plugin_ids: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False, index=True)
    run_state: Mapped[str] = mapped_column(String(24), default="idle", nullable=False)
    current_step: Mapped[str] = mapped_column(Text, default="", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class GoalActivity(Base):
    __tablename__ = "goal_activity"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    goal_id: Mapped[str] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class GoalAssignment(Base):
    __tablename__ = "goal_assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    goal_id: Mapped[str] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), index=True)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="queued", nullable=False, index=True)
    phase: Mapped[str] = mapped_column(String(24), default="queued", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_step: Mapped[str] = mapped_column(Text, default="", nullable=False)
    next_step: Mapped[str] = mapped_column(Text, default="", nullable=False)
    depends_on: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    required_inputs: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    expected_outputs: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    skill_ids: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    preview_target: Mapped[str] = mapped_column(Text, default="null", nullable=False)
    report: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evidence: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String(128))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GoalTaskUpdate(Base):
    __tablename__ = "goal_task_updates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    assignment_id: Mapped[str] = mapped_column(ForeignKey("goal_assignments.id", ondelete="CASCADE"), index=True)
    phase: Mapped[str] = mapped_column(String(24), nullable=False)
    progress: Mapped[int] = mapped_column(Integer, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    next_step: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class GoalBrowserPreview(Base):
    __tablename__ = "goal_browser_previews"

    assignment_id: Mapped[str] = mapped_column(ForeignKey("goal_assignments.id", ondelete="CASCADE"), primary_key=True)
    image: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    revision: Mapped[str] = mapped_column(String(128), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class GoalAutomation(Base):
    __tablename__ = "goal_automations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    goal_id: Mapped[str] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), index=True)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Africa/Nairobi", nullable=False)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class GoalNotification(Base):
    __tablename__ = "goal_notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    goal_id: Mapped[str] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[str] = mapped_column(String(128), index=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="open", nullable=False, index=True)
    answer: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
