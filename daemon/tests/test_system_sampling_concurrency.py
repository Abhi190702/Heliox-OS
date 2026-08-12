"""CPU sampling must not suppress concurrent Heliox services."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

import psutil
import pytest

from pilot.agents.background import BackgroundTaskManager
from pilot.config import PilotConfig
from pilot.server import PilotServer
from pilot.system.triggers import TriggerEngine


async def _assert_event_loop_progresses_while(call: Callable[[], Awaitable[object]]) -> object:
    task = asyncio.create_task(call())
    await asyncio.sleep(0.01)
    assert not task.done(), "the simulated blocking sample should still be running"
    return await task


@pytest.fixture
def slow_cpu_percent(monkeypatch: pytest.MonkeyPatch) -> None:
    def sample(*, interval: float) -> float:
        assert interval > 0
        time.sleep(0.05)
        return 42.0

    monkeypatch.setattr(psutil, "cpu_percent", sample)


@pytest.mark.asyncio
async def test_background_cpu_monitor_does_not_block_event_loop(slow_cpu_percent: None) -> None:
    result = await _assert_event_loop_progresses_while(BackgroundTaskManager._cpu_check)

    assert result["cpu_percent"] == 42.0


@pytest.mark.asyncio
async def test_cpu_trigger_does_not_block_event_loop(slow_cpu_percent: None) -> None:
    engine = TriggerEngine()

    result = await _assert_event_loop_progresses_while(lambda: engine._check_cpu({"threshold": 40}))

    assert result is True


@pytest.mark.asyncio
async def test_hud_system_info_does_not_block_event_loop(slow_cpu_percent: None) -> None:
    server = PilotServer(PilotConfig())

    result = await _assert_event_loop_progresses_while(lambda: server._handle_system_info({}, None))  # type: ignore[arg-type]

    assert result["cpu_percent"] == 42
