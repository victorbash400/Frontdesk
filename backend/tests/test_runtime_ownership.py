import asyncio
from unittest.mock import patch

import pytest

from app.accounts import create_account
from app.database import SessionLocal, initialize_database
from app.goal_tasks import GoalTaskManager
from app.models import Goal, GoalAssignment
from app.runtime_lock import runtime_lock


@pytest.mark.parametrize("cancel_before_start", [False, True])
def test_goal_ownership_precedes_worker_start_and_releases_on_cancellation(cancel_before_start) -> None:
    async def exercise():
        first, second = GoalTaskManager(), GoalTaskManager()
        started, release = asyncio.Event(), asyncio.Event()

        async def work(*_):
            started.set()
            await release.wait()

        with patch.object(first, "_orchestrate", side_effect=work):
            assert await first.start("test-account", "owned-test-goal")
            assert not await second.start("test-account", "owned-test-goal")
            if not cancel_before_start:
                await started.wait()
            worker = first._workers["owned-test-goal"]
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
        with runtime_lock("goal", "owned-test-goal") as acquired:
            assert acquired

    asyncio.run(exercise())


def test_startup_does_not_pause_a_goal_owned_by_another_runtime() -> None:
    initialize_database()
    with SessionLocal() as database:
        account = create_account(database, "ownership-test@example.test", "ownership-password", "Ownership")
        goal = Goal(account_id=account.id, client_id="client", text="Check ownership", situation="Working", status="active", run_state="running")
        database.add(goal)
        database.flush()
        goal_id = goal.id
        tasks = [GoalAssignment(goal_id=goal_id, instruction=f"Step {index}", status="running", phase="working") for index in range(2)]
        database.add_all(tasks)
        database.commit()
        task_ids = [task.id for task in tasks]
    manager = GoalTaskManager()
    with runtime_lock("goal", goal_id):
        asyncio.run(manager.recover())
        with SessionLocal() as database:
            assert database.get(Goal, goal_id).status == "active"
            assert all(database.get(GoalAssignment, task_id).status == "running" for task_id in task_ids)
    asyncio.run(manager.recover())
    with SessionLocal() as database:
        assert database.get(Goal, goal_id).status == "paused"
        assert all(database.get(GoalAssignment, task_id).status == "queued" for task_id in task_ids)
