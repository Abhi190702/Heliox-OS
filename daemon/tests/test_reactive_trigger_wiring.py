import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from pilot.config import PilotConfig
from pilot.server import PilotServer
from pilot.system.triggers import TriggerEngine


@pytest.mark.asyncio
async def test_trigger_engine_dispatches_callback() -> None:
    engine = TriggerEngine()
    fired = asyncio.Event()

    async def callback(_trigger) -> None:
        fired.set()

    engine.create_trigger("periodic", "time_interval", {}, "show status", cooldown_seconds=0)
    engine.set_fire_callback(callback)
    await engine.start()
    try:
        await asyncio.wait_for(fired.wait(), timeout=1)
    finally:
        await engine.stop()

    assert engine._callback_tasks == set()


@pytest.mark.asyncio
async def test_trigger_engine_stop_cancels_callback() -> None:
    engine = TriggerEngine()
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def callback(_trigger) -> None:
        started.set()
        try:
            await asyncio.sleep(60)
        finally:
            cancelled.set()

    engine.create_trigger("periodic", "time_interval", {}, "show status", cooldown_seconds=0)
    engine.set_fire_callback(callback)
    await engine.start()
    await asyncio.wait_for(started.wait(), timeout=1)

    await engine.stop()

    assert cancelled.is_set()
    assert engine._callback_tasks == set()


@pytest.mark.asyncio
async def test_server_routes_trigger_through_guarded_autonomous_executor() -> None:
    server = PilotServer(PilotConfig())
    server._running = True
    server._broadcast_notification = AsyncMock()
    server._autonomous = SimpleNamespace(
        submit=AsyncMock(return_value=SimpleNamespace(job_id="job-1")),
    )
    trigger = SimpleNamespace(id="trigger-1", name="CPU alert", action_command="show system status")

    await server._dispatch_reactive_trigger(trigger)

    server._autonomous.submit.assert_awaited_once_with(
        "show system status",
        source="trigger",
        session_id="trigger:trigger-1",
    )
    server._broadcast_notification.assert_awaited_once_with(
        "trigger_dispatched",
        {"trigger_id": "trigger-1", "name": "CPU alert", "job_id": "job-1"},
    )


@pytest.mark.asyncio
async def test_server_fails_closed_when_autonomous_executor_is_unavailable() -> None:
    server = PilotServer(PilotConfig())
    server._running = True
    server._broadcast_notification = AsyncMock()
    server._autonomous = None
    trigger = SimpleNamespace(id="trigger-1", name="CPU alert", action_command="show system status")

    await server._dispatch_reactive_trigger(trigger)

    server._broadcast_notification.assert_awaited_once_with(
        "trigger_dispatch_failed",
        {
            "trigger_id": "trigger-1",
            "name": "CPU alert",
            "reason": "Guarded autonomous execution is unavailable",
        },
    )
