"""Tests for PilotServer._execute_tracked -- the real, cancellable
asyncio.Task wrapper around Executor.execute() that lets _handle_abort
(Part 3) cancel the CURRENTLY in-flight interactive execution, not just
signal cancel_event for the next action boundary.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from pilot.actions import (
    Action,
    ActionPlan,
    ActionResult,
    ActionType,
    BrowserParams,
    PowerParams,
    SystemInfoParams,
    VerificationResult,
)
from pilot.agents.destructive_critic import CriticVerdict
from pilot.config import PilotConfig
from pilot.server import PilotServer


class _SlowExecutor:
    """Fake Executor.execute() that blocks until cancelled or released."""

    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.cancelled = False

    async def execute(self, plan, **kwargs):
        self.started.set()
        try:
            await self.release.wait()
            return ["done"]
        except asyncio.CancelledError:
            self.cancelled = True
            raise


def _server() -> PilotServer:
    return PilotServer(PilotConfig())


@pytest.mark.asyncio
async def test_execute_tracked_tracks_the_task_while_running():
    server = _server()
    executor = _SlowExecutor()
    server._executor = executor

    # `task` is the OUTER task wrapping _execute_tracked() itself; the task it
    # stores in _active_execution_task is the INNER one wrapping
    # executor.execute() -- these are deliberately two different Task objects.
    task = asyncio.ensure_future(server._execute_tracked(None))
    await executor.started.wait()

    assert server._active_execution_task is not None
    assert not server._active_execution_task.done()

    executor.release.set()
    result = await task
    assert result == ["done"]


@pytest.mark.asyncio
async def test_execute_tracked_clears_slot_after_normal_completion():
    server = _server()
    executor = _SlowExecutor()
    server._executor = executor

    task = asyncio.ensure_future(server._execute_tracked(None))
    await executor.started.wait()
    executor.release.set()
    await task

    assert server._active_execution_task is None


@pytest.mark.asyncio
async def test_cancelling_active_execution_task_propagates_to_executor():
    server = _server()
    executor = _SlowExecutor()
    server._executor = executor

    task = asyncio.ensure_future(server._execute_tracked(None))
    await executor.started.wait()

    server._active_execution_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert executor.cancelled is True
    assert server._active_execution_task is None


@pytest.mark.asyncio
async def test_execute_tracked_clears_slot_even_when_cancelled():
    server = _server()
    executor = _SlowExecutor()
    server._executor = executor

    task = asyncio.ensure_future(server._execute_tracked(None))
    await executor.started.wait()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert server._active_execution_task is None


@pytest.mark.asyncio
async def test_execute_tracked_passes_through_kwargs():
    server = _server()

    received = {}

    class _Recording:
        async def execute(self, plan, **kwargs):
            received.update(kwargs)
            return []

    server._executor = _Recording()
    await server._execute_tracked(None, plan_id="abc", critic_already_reviewed=True)

    assert received == {"plan_id": "abc", "critic_already_reviewed": True}


class _FakeWs:
    """Minimal stand-in for ServerConnection -- _handle_execute only calls
    ws.send(json_string); nothing needs to actually go anywhere."""

    def __init__(self, confirmation: bool | None = None):
        self.sent: list[str] = []
        self.confirmation = confirmation
        self.server: PilotServer | None = None

    async def send(self, message):
        self.sent.append(message)
        payload = json.loads(message)
        if payload.get("method") == "confirm_required" and self.confirmation is not None:
            assert self.server is not None
            await self.server._handle_confirm(
                {
                    "plan_id": payload["params"]["plan_id"],
                    "confirmed": self.confirmation,
                },
                self,
            )


class _FakeReflector:
    async def get_improvement_context(self, user_input):
        return ""

    async def reflect(self, *args, **kwargs):
        return None


class _FakeMultiAgent:
    def get_routing_summary(self, user_input):
        return {"assigned_agents": []}


class _FakePermissionChecker:
    def __init__(self, requires_confirmation: bool = False):
        self.requires_confirmation = requires_confirmation

    def plan_requires_confirmation(self, plan):
        return self.requires_confirmation


class _FakeMemory:
    async def record(self, *args, **kwargs):
        return None


def _server_ready_for_handle_execute(executor, plan: ActionPlan | None = None) -> PilotServer:
    """Builds a PilotServer with just enough wired up to drive
    _handle_execute's fresh-plan path through _execute_tracked, without
    running the real (heavy, ML-loading) PilotServer.initialize()."""
    server = _server()
    server._reflector = _FakeReflector()
    server._multi_agent = _FakeMultiAgent()
    server._permission_checker = _FakePermissionChecker()
    server._executor = executor
    server._memory = _FakeMemory()
    server._orchestrator = None
    server._destructive_critic = None
    server.test_broadcasts = []

    async def _capture_broadcast(method, params):
        server.test_broadcasts.append((method, params))

    server._broadcast_notification = _capture_broadcast

    resolved_plan = plan or ActionPlan(
        actions=[
            Action(
                action_type=ActionType.SYSTEM_INFO,
                target="system",
                parameters=SystemInfoParams(),
            )
        ],
        explanation="Mocked plan",
    )

    class _FakePlanner:
        async def plan(self, user_input, error_context="", screen_context="", stream_callback=None):
            return resolved_plan

    server._planner = _FakePlanner()
    return server


@pytest.mark.asyncio
async def test_handle_execute_returns_conversation_without_preview_or_execution():
    class _ExecutorThatMustNotRun:
        async def execute(self, plan, **kwargs):
            raise AssertionError("a zero-action conversation must not reach the executor")

    response = "Hello! I’m ready to help."
    server = _server_ready_for_handle_execute(
        _ExecutorThatMustNotRun(),
        ActionPlan(actions=[], explanation=response, raw_input="Hello Heliox"),
    )
    ws = _FakeWs()

    result = await server._handle_execute({"input": "Hello Heliox"}, ws)

    assert result == {
        "status": "success",
        "conversational": True,
        "dry_run": False,
        "results": [],
        "explanation": response,
        "agent_routing": {"assigned_agents": []},
    }
    assert any('"method": "conversation_response"' in message for message in ws.sent)
    assert not any('"method": "plan_preview"' in message for message in ws.sent)
    assert not any('"method": "confirm_required"' in message for message in ws.sent)


@pytest.mark.asyncio
async def test_handle_execute_returns_clean_response_when_cancelled_mid_flight():
    """End-to-end (bypassing the real, ML-heavy PilotServer.initialize()):
    drives a real 'execute' RPC through _handle_execute and confirms that
    cancelling the tracked task mid-flight -- exactly as Part 3's
    _handle_abort will do -- returns a clean {"status": "cancelled"} dict
    rather than letting the CancelledError escape the RPC handler."""
    executor = _SlowExecutor()
    server = _server_ready_for_handle_execute(executor)
    ws = _FakeWs()

    handle_task = asyncio.ensure_future(server._handle_execute({"input": "do something"}, ws))
    await executor.started.wait()

    # Mirrors _handle_abort's Part-3 ordering: set the cooperative cancel
    # token first, then cancel the tracked task -- by the time the
    # CancelledError reaches _handle_execute's try/except, cancel_event is
    # already set, so it falls through to the pre-existing "Cancel Token"
    # response path instead of needing new response-shaping logic.
    server._cancel_event.set()
    server._active_execution_task.cancel()

    result = await asyncio.wait_for(handle_task, timeout=10)

    assert result["status"] == "cancelled"
    assert "stopped by user" in result["message"]
    assert executor.cancelled is True
    assert server._active_execution_task is None
    assert [method for method, _ in server.test_broadcasts].count("task_complete") == 1


@pytest.mark.asyncio
async def test_handle_execute_denial_has_one_truthful_terminal_response_and_does_not_execute():
    class _ExecutorThatMustNotRun:
        async def execute(self, plan, **kwargs):
            raise AssertionError("a denied plan must not reach the executor")

    plan = ActionPlan(
        actions=[
            Action(
                action_type=ActionType.BROWSER_NAVIGATE,
                target="https://example.com",
                parameters=BrowserParams(url="https://example.com"),
            )
        ],
        explanation="Open example.com.",
    )
    server = _server_ready_for_handle_execute(_ExecutorThatMustNotRun(), plan)
    server._permission_checker = _FakePermissionChecker(requires_confirmation=True)
    ws = _FakeWs(confirmation=False)
    ws.server = server

    result = await server._handle_execute({"input": "open example.com"}, ws)

    assert result["status"] == "cancelled"
    assert result["message"] == "Cancelled before execution: the plan was denied."
    assert sum('"method": "confirm_required"' in message for message in ws.sent) == 1
    assert [method for method, _ in server.test_broadcasts].count("task_complete") == 1


@pytest.mark.asyncio
async def test_handle_execute_approved_success_reports_verified_outcome():
    class _Executor:
        async def execute(self, plan, **kwargs):
            return [ActionResult(action=plan.actions[0], success=True, output="opened")]

    class _Verifier:
        async def verify(self, plan, results):
            return VerificationResult(
                passed=True,
                details=["Action 0 (browser_navigate): VERIFIED"],
                failed_actions=[],
            )

    plan = ActionPlan(
        actions=[
            Action(
                action_type=ActionType.BROWSER_NAVIGATE,
                target="https://example.com",
                parameters=BrowserParams(url="https://example.com"),
            )
        ],
        explanation="Open example.com.",
    )
    server = _server_ready_for_handle_execute(_Executor(), plan)
    server._permission_checker = _FakePermissionChecker(requires_confirmation=True)
    server._verifier = _Verifier()
    ws = _FakeWs(confirmation=True)
    ws.server = server

    result = await server._handle_execute({"input": "open example.com"}, ws)

    assert result["status"] == "success"
    assert result["verification"]["passed"] is True
    assert result["message"] == "Completed and verified 1 action. Open example.com."
    assert sum('"method": "confirm_required"' in message for message in ws.sent) == 1
    assert [method for method, _ in server.test_broadcasts].count("task_complete") == 1


@pytest.mark.asyncio
async def test_handle_execute_partial_failure_reports_execution_error_not_plan_intent():
    class _Executor:
        async def execute(self, plan, **kwargs):
            return [ActionResult(action=plan.actions[0], success=False, error="Process exited with code 125")]

    class _Verifier:
        async def verify(self, plan, results):
            return VerificationResult(
                passed=False,
                details=["Action 0 (system_info): FAILED — Process exited with code 125"],
                failed_actions=[0],
            )

    server = _server_ready_for_handle_execute(_Executor())
    server._verifier = _Verifier()
    server.MAX_RETRIES = 0
    ws = _FakeWs()

    result = await server._handle_execute({"input": "run the task"}, ws)

    assert result["status"] == "partial_failure"
    assert "Process exited with code 125" in result["message"]
    assert result["message"] != result["explanation"]
    assert [method for method, _ in server.test_broadcasts].count("task_complete") == 1


@pytest.mark.asyncio
async def test_handle_execute_critic_block_is_terminal_and_never_executes():
    class _ExecutorThatMustNotRun:
        async def execute(self, plan, **kwargs):
            raise AssertionError("a critic-blocked plan must not reach the executor")

    class _BlockingCritic:
        async def review(self, user_input, plan):
            return CriticVerdict(
                verdict="BLOCK",
                risk_score=1.0,
                recommendation="Unsafe power operation.",
            )

    plan = ActionPlan(
        actions=[
            Action(
                action_type=ActionType.POWER_SHUTDOWN,
                target="system",
                parameters=PowerParams(),
                requires_root=True,
            )
        ],
        explanation="Shut down the computer.",
    )
    server = _server_ready_for_handle_execute(_ExecutorThatMustNotRun(), plan)
    server._destructive_critic = _BlockingCritic()
    ws = _FakeWs()

    result = await server._handle_execute({"input": "shut down"}, ws)

    assert result["status"] == "blocked_by_critic"
    assert result["message"] == "Blocked before execution by safety review: Unsafe power operation."
    assert [method for method, _ in server.test_broadcasts].count("task_complete") == 1
