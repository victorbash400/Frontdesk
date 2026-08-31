from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine_options = {"pool_pre_ping": True}
if settings.database_url.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
else:
    engine_options.update(pool_size=5, max_overflow=5)

engine = create_engine(settings.database_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def initialize_database() -> None:
    if engine.dialect.name != "postgresql":
        _initialize_database()
        return
    # Serialize schema inspection and migration across concurrently starting replicas.
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text("SELECT pg_advisory_lock(734926180521)"))
        try:
            _initialize_database()
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(734926180521)"))


def _initialize_database() -> None:
    from . import models  # noqa: F401
    from meetings import models as meeting_models  # noqa: F401

    inspector = inspect(engine)
    if "workspaces" in inspector.get_table_names() and "owner_id" not in {column["name"] for column in inspector.get_columns("workspaces")}:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE workspaces ADD COLUMN owner_id VARCHAR(36)"))
    if "oauth_connections" in inspector.get_table_names():
        oauth_columns = {column["name"] for column in inspector.get_columns("oauth_connections")}
        with engine.begin() as connection:
            if "profile_name" not in oauth_columns:
                connection.execute(text("ALTER TABLE oauth_connections ADD COLUMN profile_name VARCHAR(255)"))
            if "picture_url" not in oauth_columns:
                connection.execute(text("ALTER TABLE oauth_connections ADD COLUMN picture_url TEXT"))
            if "unavailable_permissions" not in oauth_columns:
                connection.execute(text("ALTER TABLE oauth_connections ADD COLUMN unavailable_permissions TEXT NOT NULL DEFAULT '[]'"))
    if "meetings" in inspector.get_table_names():
        meeting_columns = {column["name"] for column in inspector.get_columns("meetings")}
        if "event_subscription_operation" not in meeting_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE meetings ADD COLUMN event_subscription_operation VARCHAR(255)"))
        if "active_agent_ticket_id" not in meeting_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE meetings ADD COLUMN active_agent_ticket_id VARCHAR(36)"))
        for column in ("active_runtime_id", "active_bridge_id", "active_tab_id"):
            if column not in meeting_columns:
                with engine.begin() as connection:
                    connection.execute(text(f"ALTER TABLE meetings ADD COLUMN {column} VARCHAR(64)"))
    if "goals" in inspector.get_table_names():
        goal_columns = {column["name"] for column in inspector.get_columns("goals")}
        with engine.begin() as connection:
            if "run_state" not in goal_columns:
                connection.execute(text("ALTER TABLE goals ADD COLUMN run_state VARCHAR(24) NOT NULL DEFAULT 'idle'"))
            if "current_step" not in goal_columns:
                connection.execute(text("ALTER TABLE goals ADD COLUMN current_step TEXT NOT NULL DEFAULT ''"))
    if "goal_assignments" in inspector.get_table_names():
        assignment_columns = {column["name"] for column in inspector.get_columns("goal_assignments")}
        additions = {
            "source_meeting_id": "VARCHAR(36)",
            "auxiliary": "BOOLEAN NOT NULL DEFAULT FALSE",
            "title": "VARCHAR(255) NOT NULL DEFAULT ''",
            "phase": "VARCHAR(24) NOT NULL DEFAULT 'queued'",
            "progress": "INTEGER NOT NULL DEFAULT 0",
            "current_step": "TEXT NOT NULL DEFAULT ''",
            "next_step": "TEXT NOT NULL DEFAULT ''",
            "depends_on": "TEXT NOT NULL DEFAULT '[]'",
            "required_inputs": "TEXT NOT NULL DEFAULT '[]'",
            "expected_outputs": "TEXT NOT NULL DEFAULT '[]'",
            "preview_target": "TEXT NOT NULL DEFAULT 'null'",
            "skill_ids": "TEXT NOT NULL DEFAULT '[]'",
        }
        with engine.begin() as connection:
            for column, definition in additions.items():
                if column not in assignment_columns:
                    connection.execute(text(f"ALTER TABLE goal_assignments ADD COLUMN {column} {definition}"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_goal_assignments_source_meeting_id ON goal_assignments (source_meeting_id)"))
    if "mail_messages" in inspector.get_table_names():
        message_columns = {column["name"] for column in inspector.get_columns("mail_messages")}
        additions = {
            "client_id": "VARCHAR(36)",
            "conversation_id": "VARCHAR(36)",
            "assignment_id": "VARCHAR(36)",
            "agent_status": "VARCHAR(24) NOT NULL DEFAULT 'completed'",
            "agent_action": "VARCHAR(32) NOT NULL DEFAULT ''",
            "agent_summary": "TEXT NOT NULL DEFAULT ''",
            "attention_required": "BOOLEAN NOT NULL DEFAULT FALSE",
            "agent_failure": "TEXT NOT NULL DEFAULT ''",
        }
        with engine.begin() as connection:
            for column, definition in additions.items():
                if column not in message_columns:
                    connection.execute(text(f"ALTER TABLE mail_messages ADD COLUMN {column} {definition}"))
    if "goal_notifications" in inspector.get_table_names():
        notification_columns = {column["name"] for column in inspector.get_columns("goal_notifications")}
        if "assignment_id" not in notification_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE goal_notifications ADD COLUMN assignment_id VARCHAR(36)"))
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_goal_notifications_assignment_id ON goal_notifications (assignment_id)"))
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        with engine.begin() as connection:
            connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_workspaces_owner_id ON workspaces (owner_id)"))


def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
