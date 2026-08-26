import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from pilot.agents.autonomous import AutonomousExecutor, JobStatus


def _blocking_executor(started: asyncio.Event) -> AutonomousExecutor:
    async def decompose(_goal: str) -> None:
        started.set()
        await asyncio.sleep(60)

    return AutonomousExecutor(
        planner=None,
        executor=None,
        verifier=None,
        decomposer=SimpleNamespace(decompose=decompose),
    )


@pytest.mark.asyncio
async def test_cancel_waits_for_job_cleanup() -> None:
    started = asyncio.Event()
    autonomous = _blocking_executor(started)
    autonomous.set_broadcast(AsyncMock())
    autonomous.set_speech(AsyncMock())
    job = await autonomous.submit("wait")
    await started.wait()

    assert await autonomous.cancel(job.job_id) is True

    assert job.status == JobStatus.CANCELLED
    assert job.job_id not in autonomous._active_tasks


@pytest.mark.asyncio
async def test_stop_cancels_jobs_without_shutdown_notifications() -> None:
    started = asyncio.Event()
    autonomous = _blocking_executor(started)
    broadcast = AsyncMock()
    speech = AsyncMock()
    autonomous.set_broadcast(broadcast)
    autonomous.set_speech(speech)
    await autonomous.submit("wait")
    await started.wait()
    broadcast.reset_mock()

    await autonomous.stop()

    assert autonomous._active_tasks == {}
    broadcast.assert_not_awaited()
    speech.assert_not_awaited()
    with pytest.raises(RuntimeError, match="stopping"):
        await autonomous.submit("too late")


@pytest.mark.asyncio
async def test_cancel_does_not_relabel_terminal_job() -> None:
    autonomous = AutonomousExecutor(planner=None, executor=None, verifier=None, decomposer=None)
    job = await autonomous.submit("already done")
    task = autonomous._active_tasks.pop(job.job_id)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    job.status = JobStatus.SUCCESS

    assert await autonomous.cancel(job.job_id) is False
    assert job.status == JobStatus.SUCCESS
