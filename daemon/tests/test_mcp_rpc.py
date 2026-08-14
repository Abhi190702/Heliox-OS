from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import websockets

from pilot.actions import Action, ActionPlan, ActionType, EmptyParams
from pilot.config import PilotConfig
from pilot.security.gateway import InvocationSource
from pilot.security.rpc_identity import RpcClientRole
from pilot.server import PendingConfirmation, PilotServer
from pilot.workflows.durable_tasks import DurableTask, TaskStatus


class _Socket:
    pass


def _authorized_server() -> tuple[PilotServer, _Socket]:
    server = PilotServer(PilotConfig())
    socket = _Socket()
    server._client_roles[socket] = RpcClientRole.MCP_LOCAL
    return server, socket


@pytest.mark.asyncio
async def test_mcp_plan_preview_is_advisory_and_forces_visible_approval() -> None:
    server, socket = _authorized_server()
    server._planner = SimpleNamespace(
        plan=AsyncMock(
            return_value=ActionPlan(
                actions=[
                    Action(
                        action_type=ActionType.SYSTEM_INFO,
                        target="system",
                        parameters=EmptyParams(),
                    )
                ],
                explanation="Inspect the system.",
                raw_input="show system info",
            )
        )
    )

    result = await server._handle_mcp_plan_task(
        {"input": "show system info", "session_id": "host-1"},
        socket,
    )

    assert result["status"] == "preview"
    assert result["authoritative"] is False
    assert result["requires_user_approval"] is True
    assert result["actions"][0]["action_type"] == "system_info"
    assert result["actions"][0]["permission_tier"] == "USER_WRITE"
    assert result["actions"][0]["normally_requires_confirmation"] is False
    assert result["actions"][0]["mcp_requires_confirmation"] is True
    server._planner.plan.assert_awaited_once_with("show system info", session_id="host-1")


def test_mcp_execution_uses_the_bounded_gateway_profile() -> None:
    server = PilotServer(PilotConfig())

    source, scope = server._execution_scope_for_source("mcp")

    assert source == InvocationSource.MCP
    assert scope is not None
    assert scope.allow_root is False
    assert "browser_execute_js" in scope.deny_action_types
    assert "power_shutdown" in scope.deny_action_types


@pytest.mark.asyncio
async def test_mcp_submit_runs_as_mcp_local_and_returns_without_waiting() -> None:
    server, socket = _authorized_server()
    server._durable_tasks = SimpleNamespace()
    server._broadcast_notification = AsyncMock()
    server._handle_execute = AsyncMock(return_value={"status": "success", "message": "Verified.", "task_id": "ignored"})

    submitted = await server._handle_mcp_submit_task(
        {"input": "show system info", "session_id": "codex"},
        socket,
    )

    assert submitted["status"] == "submitted"
    assert submitted["requires_user_approval"] is True
    await asyncio.wait_for(next(iter(server._mcp_tasks.values())), timeout=1)
    execute_params = server._handle_execute.await_args.args[0]
    assert execute_params["source"] == "mcp"
    assert execute_params["user_id"] == "mcp-local"
    assert execute_params["session_id"] == "mcp:codex"
    assert execute_params["task_id"] == submitted["task_id"]


@pytest.mark.asyncio
async def test_mcp_status_and_cancel_cannot_target_a_ui_task() -> None:
    server, socket = _authorized_server()
    ui_task = DurableTask(
        task_id="ui-task",
        session_id="default",
        user_id="local",
        user_input="do something",
        status=TaskStatus.EXECUTING,
        plan_id="plan-1",
        cancellation_requested=False,
        terminal_response=None,
        version=1,
        created_at="2026-08-14T00:00:00Z",
        updated_at="2026-08-14T00:00:00Z",
    )
    server._durable_tasks = SimpleNamespace(
        get=AsyncMock(return_value=ui_task),
        request_cancel=AsyncMock(),
    )

    status = await server._handle_mcp_task_status({"task_id": "ui-task"}, socket)
    cancelled = await server._handle_mcp_cancel_task({"task_id": "ui-task"}, socket)

    assert status["status"] == "not_found"
    assert cancelled["status"] == "not_found"
    server._durable_tasks.request_cancel.assert_not_awaited()


@pytest.mark.asyncio
async def test_abort_releases_an_active_confirmation_wait() -> None:
    server = PilotServer(PilotConfig())
    server._active_plan_id = "plan-approval"
    server._active_task_id = ""
    pending = PendingConfirmation(plan_id="plan-approval", event=asyncio.Event())
    server._pending_confirms[pending.plan_id] = pending

    result = await server._handle_abort({}, None)

    assert result == {"status": "aborted"}
    assert pending.confirmed is False
    assert pending.event.is_set()


@pytest.mark.asyncio
async def test_mcp_websocket_token_cannot_call_ui_methods() -> None:
    config = PilotConfig()
    config.server.auth_token = "ui-token"
    server = PilotServer(config)
    server._mcp_auth_token = "mcp-token"
    server._handlers = {
        "health": AsyncMock(return_value={"status": "ok"}),
        "execute": AsyncMock(return_value={"status": "should-not-run"}),
    }
    listener = await websockets.serve(server._handle_connection, "127.0.0.1", 0)
    port = listener.sockets[0].getsockname()[1]
    socket = await websockets.connect(f"ws://127.0.0.1:{port}")
    try:
        await socket.send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "auth",
                    "params": {"token": "mcp-token"},
                    "id": "auth",
                }
            )
        )
        authenticated = json.loads(await socket.recv())
        assert authenticated["result"]["role"] == "mcp_local"

        await socket.send(json.dumps({"jsonrpc": "2.0", "method": "health", "params": {}, "id": "health"}))
        health = json.loads(await socket.recv())
        assert health["result"] == {"status": "ok"}

        await socket.send(json.dumps({"jsonrpc": "2.0", "method": "execute", "params": {}, "id": "execute"}))
        denied = json.loads(await socket.recv())
        assert denied["error"]["code"] == -32601
        server._handlers["execute"].assert_not_awaited()
    finally:
        await socket.close()
        listener.close()
        await listener.wait_closed()
