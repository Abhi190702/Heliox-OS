"""Regression tests for PilotServer._broadcast_notification.

Prior to this fix, the method never actually sent the (method, params) it
was given to any connected client outside one narrow edge case (attention
buffering happening to flush previously-buffered events) -- the real send
loop existed but was dead code, misplaced after a different handler's
return statements. These tests lock in that every call actually reaches
connected clients.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from unittest.mock import AsyncMock

import pytest

from pilot.config import PilotConfig
from pilot.server import MAX_ATTENTION_NOTIFICATION_BUFFER, PilotServer


class _FakeClient:
    def __init__(self):
        self.send = AsyncMock()


def _server_with_clients(n: int = 2) -> tuple[PilotServer, list[_FakeClient]]:
    server = PilotServer(PilotConfig())
    clients = [_FakeClient() for _ in range(n)]
    server._clients = set(clients)
    return server, clients


@pytest.mark.asyncio
async def test_plain_notification_is_sent_to_every_client():
    server, clients = _server_with_clients()
    await server._broadcast_notification("self_healing_complete", {"attempt_id": "heal_1"})

    for client in clients:
        client.send.assert_awaited_once()
        sent = json.loads(client.send.call_args[0][0])
        assert sent["method"] == "self_healing_complete"
        assert sent["params"]["attempt_id"] == "heal_1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method",
    [
        "task_complete",
        "confirm_required",
        "execution_interrupt",
        "voice_result",
        "neural_preview",
        "mcp_task_update",
        "air_handoff_state",
        "future_feature_event",
    ],
)
async def test_delivery_contract_notifications_bypass_attention_gate_and_still_send(method: str):
    server, clients = _server_with_clients()

    @dataclass
    class _AttentionUI:
        enabled: bool = True
        score_event: AsyncMock = field(default_factory=AsyncMock)

    server._attention_ui = _AttentionUI()
    await server._broadcast_notification(method, {"job_id": "abc"})

    server._attention_ui.score_event.assert_not_awaited()
    for client in clients:
        client.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_attention_ui_should_display_still_sends_current_notification():
    server, clients = _server_with_clients()

    @dataclass
    class _Scored:
        should_display: bool = True
        priority: str = "normal"
        attention_score: float = 0.8
        should_animate: bool = True
        display_duration_ms: int = 3000

    class _AttentionUI:
        enabled = True

        async def score_event(self, method, content):
            return _Scored()

    server._attention_ui = _AttentionUI()
    await server._broadcast_notification("plugin_event", {"region": "left"})

    for client in clients:
        client.send.assert_awaited_once()
        sent = json.loads(client.send.call_args[0][0])
        assert sent["params"]["region"] == "left"
        assert "_cognitive" in sent["params"]


@pytest.mark.asyncio
async def test_attention_ui_buffers_non_critical_and_does_not_send_immediately():
    server, clients = _server_with_clients()

    @dataclass
    class _Scored:
        should_display: bool = False
        priority: str = "low"
        attention_score: float = 0.9
        should_animate: bool = False
        display_duration_ms: int = 0

    class _AttentionUI:
        enabled = True

        async def score_event(self, method, content):
            return _Scored()

    server._attention_ui = _AttentionUI()
    await server._broadcast_notification("background_update", {"task_id": "monitor_cpu"})

    for client in clients:
        client.send.assert_not_awaited()
    assert len(server._notification_buffer) == 1


@pytest.mark.asyncio
async def test_attention_buffer_coalesces_repeated_screen_vision_updates():
    server, clients = _server_with_clients()

    @dataclass
    class _Scored:
        should_display: bool = False
        priority: str = "low"
        attention_score: float = 0.9
        should_animate: bool = False
        display_duration_ms: int = 0

    class _AttentionUI:
        enabled = True

        async def score_event(self, method, content):
            return _Scored()

    server._attention_ui = _AttentionUI()
    for frame in range(100):
        await server._broadcast_notification("screen_vision_update", {"frame": frame})

    assert server._notification_buffer == [("screen_vision_update", {"frame": 99})]
    for client in clients:
        client.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_attention_buffer_is_bounded_across_distinct_background_tasks():
    server, _ = _server_with_clients()

    @dataclass
    class _Scored:
        should_display: bool = False
        priority: str = "low"
        attention_score: float = 0.9
        should_animate: bool = False
        display_duration_ms: int = 0

    class _AttentionUI:
        enabled = True

        async def score_event(self, method, content):
            return _Scored()

    server._attention_ui = _AttentionUI()
    for task in range(MAX_ATTENTION_NOTIFICATION_BUFFER + 10):
        await server._broadcast_notification("background_update", {"task_id": f"task-{task}"})

    assert len(server._notification_buffer) == MAX_ATTENTION_NOTIFICATION_BUFFER
    assert server._notification_buffer[0][1]["task_id"] == "task-10"
    assert server._notification_buffer[-1][1]["task_id"] == f"task-{MAX_ATTENTION_NOTIFICATION_BUFFER + 9}"


@pytest.mark.asyncio
async def test_attention_ui_flushes_buffer_and_still_sends_current_notification():
    server, clients = _server_with_clients()
    server._notification_buffer = [("background_update", {"task_id": "monitor_cpu"})]

    @dataclass
    class _Scored:
        should_display: bool = True
        priority: str = "normal"
        attention_score: float = 0.1  # below 0.4 -> triggers flush
        should_animate: bool = True
        display_duration_ms: int = 3000

    class _AttentionUI:
        enabled = True

        async def score_event(self, method, content):
            return _Scored()

    server._attention_ui = _AttentionUI()
    await server._broadcast_notification("plugin_event", {"attempt_id": "heal_2"})

    # Each client got 2 sends: the flushed buffered event, then the current one.
    for client in clients:
        assert client.send.await_count == 2
        first_sent = json.loads(client.send.call_args_list[0][0][0])
        second_sent = json.loads(client.send.call_args_list[1][0][0])
        assert first_sent["method"] == "background_update"
        assert second_sent["method"] == "plugin_event"
    assert server._notification_buffer == []


@pytest.mark.asyncio
async def test_no_clients_does_not_raise():
    server, _ = _server_with_clients(n=0)
    await server._broadcast_notification("self_healing_complete", {"attempt_id": "heal_3"})


@pytest.mark.asyncio
async def test_a_client_send_exception_does_not_block_other_clients():
    server, clients = _server_with_clients(n=2)
    clients[0].send.side_effect = RuntimeError("connection closed")

    await server._broadcast_notification("self_healing_complete", {"attempt_id": "heal_4"})

    clients[0].send.assert_awaited_once()
    clients[1].send.assert_awaited_once()
