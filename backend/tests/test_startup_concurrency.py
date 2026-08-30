from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app import accounts, database


def test_demo_account_concurrent_creation_reads_winning_account():
    winner = object()
    with patch.object(accounts, "account_by_email", side_effect=[None, winner]), patch.object(
        accounts, "create_account", side_effect=ValueError("already exists"),
    ):
        assert accounts.ensure_demo_account(MagicMock()) is winner


def test_demo_account_failure_without_existing_account_is_not_hidden():
    with patch.object(accounts, "account_by_email", return_value=None), patch.object(
        accounts, "create_account", side_effect=ValueError("creation failed"),
    ), pytest.raises(ValueError, match="creation failed"):
        accounts.ensure_demo_account(MagicMock())


def test_schema_lock_releases_even_when_initialization_fails():
    engine = MagicMock()
    engine.dialect = SimpleNamespace(name="postgresql")
    connection = engine.connect.return_value.execution_options.return_value.__enter__.return_value
    with patch.object(database, "engine", engine), patch.object(
        database, "_initialize_database", side_effect=RuntimeError("migration failed"),
    ), pytest.raises(RuntimeError, match="migration failed"):
        database.initialize_database()
    assert [str(call.args[0]) for call in connection.execute.call_args_list] == [
        "SELECT pg_advisory_lock(734926180521)",
        "SELECT pg_advisory_unlock(734926180521)",
    ]
