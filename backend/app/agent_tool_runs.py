"""Durable identities and replay ledger for Agent Engine tool invocations."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentToolRun(Base):
    __tablename__ = "agent_tool_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[str] = mapped_column(String(36))
    ticket_hash: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AgentToolCall(Base):
    __tablename__ = "agent_tool_calls"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_tool_runs.id", ondelete="CASCADE"), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="executing")
    response: Mapped[str | None] = mapped_column(Text)


class AgentSessionLink(Base):
    __tablename__ = "agent_session_links"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    remote_id: Mapped[str] = mapped_column(String(255))


class AgentToolRequest(Base):
    __tablename__ = "agent_tool_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_tool_runs.id", ondelete="CASCADE"), index=True)
    operation: Mapped[str] = mapped_column(String(20))
    payload: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    response: Mapped[str | None] = mapped_column(Text)
