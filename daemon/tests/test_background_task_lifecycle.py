import asyncio

import pytest

from pilot.agents.background import BackgroundTask, BackgroundTaskManager, TaskStatus


@pytest.mark.asyncio
async def test_shutdown_cancels_and_drains_owned_monitor_loops() -> None:
    action_started = asyncio.Event()
    action_cancelled = asyncio.Event()

    async def blocking_action() -> dict[str, object]:
        action_started.set()
        try:
            await asyncio.sleep(30)
        finally:
            action_cancelled.set()
        return {}

    manager = BackgroundTaskManager()
    monitor = BackgroundTask(
        task_id="blocking",
        name="Blocking monitor",
        description="Test monitor",
        interval_seconds=60,
        action_fn=blocking_action,
    )
    manager.register(monitor)
    assert manager.start("blocking") is True
    await asyncio.wait_for(action_started.wait(), timeout=2)

    await manager.shutdown()

    assert action_cancelled.is_set()
    assert monitor.status is TaskStatus.STOPPED
    assert monitor._handle is None
