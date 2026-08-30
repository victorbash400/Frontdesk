"""Shared ADK session storage with a bounded PostgreSQL connection pool."""

from google.adk.sessions import DatabaseSessionService

from app.config import get_settings


url = get_settings().agent_session_database_url
options = {"pool_size": 1, "max_overflow": 1} if url.startswith("postgresql") else {}
sessions = DatabaseSessionService(url, **options)
