from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models import new_id, now


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[str] = mapped_column(String(128), index=True)
    goal_id: Mapped[str | None] = mapped_column(ForeignKey("goals.id", ondelete="SET NULL"), index=True)
    client_email: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    state: Mapped[str] = mapped_column(String(32), default="creating", nullable=False, index=True)
    calendar_event_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    meet_space_name: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    meet_uri: Mapped[str | None] = mapped_column(Text)
    event_subscription_name: Mapped[str | None] = mapped_column(String(255), unique=True)
    event_subscription_operation: Mapped[str | None] = mapped_column(String(255), unique=True)
    conference_record_name: Mapped[str | None] = mapped_column(String(255), index=True)
    active_agent_ticket_id: Mapped[str | None] = mapped_column(String(36), index=True)
    active_runtime_id: Mapped[str | None] = mapped_column(String(36), index=True)
    active_bridge_id: Mapped[str | None] = mapped_column(String(36), index=True)
    active_tab_id: Mapped[str | None] = mapped_column(String(64), index=True)
    failure: Mapped[str] = mapped_column(Text, default="", nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    client_joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    agent_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class MeetingEvent(Base):
    __tablename__ = "meeting_events"
    __table_args__ = (UniqueConstraint("source", "external_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    payload: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class MeetingTurn(Base):
    __tablename__ = "meeting_turns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
