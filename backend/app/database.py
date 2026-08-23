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

engine = create_engine(settings.database_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def initialize_database() -> None:
    from . import models  # noqa: F401

    inspector = inspect(engine)
    if "workspaces" in inspector.get_table_names() and "owner_id" not in {column["name"] for column in inspector.get_columns("workspaces")}:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE workspaces ADD COLUMN owner_id VARCHAR(36)"))
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        with engine.begin() as connection:
            connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_workspaces_owner_id ON workspaces (owner_id)"))


def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
