import asyncio

import pytest

from pilot.agents.orchestrator import AgentOrchestrator, PrioritizedTask, TaskPriority


@pytest.mark.asyncio
async def test_failed_realtime_task_resumes_background_scheduler() -> None:
    orchestrator = AgentOrchestrator(object())
    background_ran = asyncio.Event()

    async def fail() -> None:
        raise RuntimeError("expected failure")

    async def run_background() -> None:
        background_ran.set()

    try:
        await orchestrator.task_queue.put(PrioritizedTask(TaskPriority.USER_REALTIME, "realtime", fail()))
        await orchestrator.task_queue.put(
            PrioritizedTask(TaskPriority.BACKGROUND_BATCH, "background", run_background())
        )

        await asyncio.wait_for(background_ran.wait(), timeout=1)

        assert orchestrator.background_allowed.is_set()
        assert not orchestrator._scheduler_task.done()
    finally:
        await orchestrator.stop()


@pytest.mark.asyncio
async def test_stop_cancels_scheduler_owned_background_tasks() -> None:
    orchestrator = AgentOrchestrator(object())
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def long_running() -> None:
        started.set()
        try:
            await asyncio.sleep(60)
        finally:
            cancelled.set()

    await orchestrator.task_queue.put(PrioritizedTask(TaskPriority.BACKGROUND_BATCH, "long-running", long_running()))
    await asyncio.wait_for(started.wait(), timeout=1)

    await orchestrator.stop()

    assert cancelled.is_set()
    assert orchestrator._background_tasks == set()
    assert orchestrator.background_allowed.is_set()


@pytest.mark.asyncio
async def test_stop_closes_queued_coroutine_that_cannot_start() -> None:
    orchestrator = AgentOrchestrator(object())
    orchestrator.background_allowed.clear()

    async def queued() -> None:
        return None

    coroutine = queued()
    await orchestrator.task_queue.put(PrioritizedTask(TaskPriority.BACKGROUND_BATCH, "queued", coroutine))
    await asyncio.sleep(0)

    await orchestrator.stop()

    assert coroutine.cr_frame is None
