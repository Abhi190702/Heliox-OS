from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from pilot.agents.executor import Executor
from pilot.security.controller_lease import ControllerLeaseBusy, ControllerLeaseManager
from pilot.security.gateway import InvocationSource


@pytest.mark.asyncio
async def test_cooperative_controllers_queue_and_release_in_order() -> None:
    lease = ControllerLeaseManager()
    entered = asyncio.Event()
    release = asyncio.Event()
    order: list[str] = []

    async def first() -> None:
        async with lease.claim("interactive:first", wait=True):
            order.append("first")
            entered.set()
            await release.wait()

    async def second() -> None:
        async with lease.claim("voice:second", wait=True):
            order.append("second")

    first_task = asyncio.create_task(first())
    await entered.wait()
    second_task = asyncio.create_task(second())
    await asyncio.sleep(0)
    assert order == ["first"]
    release.set()
    await asyncio.gather(first_task, second_task)
    assert order == ["first", "second"]
    assert (await lease.status()).owner is None


@pytest.mark.asyncio
async def test_neural_executor_fails_closed_instead_of_waiting_on_stale_context() -> None:
    lease = ControllerLeaseManager()
    executor = Executor.__new__(Executor)
    executor._controller_lease = lease
    executor._execute_without_controller_lease = AsyncMock(return_value=[])
    plan = MagicMock()

    async with lease.claim("interactive:busy", wait=True):
        with pytest.raises(ControllerLeaseBusy, match="must be refreshed"):
            await executor.execute(
                plan,
                plan_id="neural-plan",
                invocation_source=InvocationSource.NEURAL,
            )
    executor._execute_without_controller_lease.assert_not_awaited()


@pytest.mark.asyncio
async def test_reentrant_owner_does_not_deadlock() -> None:
    lease = ControllerLeaseManager()
    async with lease.claim("neural:one", wait=False), lease.claim("neural:one", wait=False) as nested:
        assert nested.depth == 2
    assert (await lease.status()).owner is None
