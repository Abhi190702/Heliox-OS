import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from pilot.config import PilotConfig
from pilot.server import PilotServer


@pytest.mark.asyncio
async def test_shutdown_quiesces_tasks_before_closing_their_owners() -> None:
    server = PilotServer(PilotConfig())
    order: list[str] = []

    async def wait_until_cancelled(label: str) -> None:
        try:
            await asyncio.sleep(60)
        finally:
            order.append(f"{label}_cancelled")

    async def write_memory() -> None:
        await asyncio.sleep(0.01)
        order.append("memory_written")

    class FakeWebSocketServer:
        def close(self) -> None:
            order.append("server_closed")

        async def wait_closed(self) -> None:
            order.append("server_waited")

    server._server = FakeWebSocketServer()
    server._autonomous = SimpleNamespace(stop=AsyncMock(side_effect=lambda: order.append("autonomous_stopped")))
    server._active_execution_task = asyncio.create_task(wait_until_cancelled("execution"))
    server._mcp_tasks["mcp"] = asyncio.create_task(wait_until_cancelled("mcp"))
    follow_up = asyncio.create_task(wait_until_cancelled("follow_up"))
    speech = asyncio.create_task(wait_until_cancelled("speech"))
    server._companion_follow_up_tasks.add(follow_up)
    server._interaction_speech_tasks.add(speech)
    server._speech_coordinator = SimpleNamespace(close=AsyncMock(side_effect=lambda: order.append("speech_closed")))
    server._memory = SimpleNamespace(close=AsyncMock(side_effect=lambda: order.append("memory_closed")))
    server._reflector = SimpleNamespace(close=AsyncMock(side_effect=lambda: order.append("reflector_closed")))

    server._spawn_post_execution_task(write_memory(), server._memory_record_tasks, "memory")
    server._spawn_post_execution_task(
        wait_until_cancelled("reflection"),
        server._reflection_tasks,
        "reflection",
    )
    await asyncio.sleep(0)

    await server.stop()

    assert order.index("execution_cancelled") < order.index("server_closed")
    assert order.index("mcp_cancelled") < order.index("server_closed")
    assert order.index("autonomous_stopped") < order.index("server_closed")
    assert order.index("follow_up_cancelled") < order.index("speech_closed")
    assert order.index("speech_cancelled") < order.index("speech_closed")
    assert order.index("reflection_cancelled") < order.index("reflector_closed")
    assert order.index("memory_written") < order.index("memory_closed")
    assert server._mcp_tasks == {}
    assert server._memory_record_tasks == set()
    assert server._reflection_tasks == set()
