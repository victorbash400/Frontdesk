"""Always isolate tests before importing application modules or startup hooks."""

import os
from tempfile import TemporaryDirectory


_database_directory = TemporaryDirectory(prefix="front-desk-tests-")
os.environ["FRONT_DESK_DATABASE_URL"] = f"sqlite:///{_database_directory.name}/app.db"
os.environ["FRONT_DESK_AGENT_SESSION_DATABASE_URL"] = f"sqlite+aiosqlite:///{_database_directory.name}/sessions.db"
os.environ["FRONT_DESK_INTERNAL_SECRET"] = "test-internal-secret"
