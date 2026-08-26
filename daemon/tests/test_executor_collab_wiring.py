from unittest.mock import AsyncMock

import pytest

from pilot.actions import Action, ActionPlan, ActionResult, ActionType, SystemInfoParams
from pilot.agents.executor import Executor
from pilot.config import PilotConfig
from pilot.security.audit import AuditLogger
from pilot.security.gateway import InvocationSource
from pilot.security.permissions import PermissionChecker
from pilot.security.validator import ActionValidator


def _executor(tmp_path) -> Executor:
    config = PilotConfig()
    return Executor(
        config,
        ActionValidator(config),
        PermissionChecker(config),
        AuditLogger(audit_file=tmp_path / "audit.jsonl"),
    )


def _plan() -> ActionPlan:
    action = Action(action_type=ActionType.SYSTEM_INFO, parameters=SystemInfoParams())
    return ActionPlan(actions=[action], raw_input="show system information")


class _Collab:
    def __init__(self, result):
        self.result = result
        self.distribute = AsyncMock(return_value=result)
        self.should_distribute_calls = []

    def should_distribute(self, plan, batches):
        self.should_distribute_calls.append((plan, batches))
        return True


@pytest.mark.asyncio
async def test_executor_routes_eligible_plan_through_attached_mesh(tmp_path):
    executor = _executor(tmp_path)
    plan = _plan()
    expected = [ActionResult(action=plan.actions[0], success=True, output="remote")]
    collab = _Collab(expected)
    executor.set_collab_executor(collab)

    results = await executor.execute(plan, plan_id="plan-1", invocation_source=InvocationSource.INTERACTIVE)

    assert results == expected
    assert collab.should_distribute_calls == [(plan, [plan.actions])]
    options = collab.distribute.await_args.kwargs["execution_options"]
    assert options["plan_id"] == "plan-1"
    assert options["invocation_source"] is InvocationSource.INTERACTIVE


@pytest.mark.asyncio
@pytest.mark.parametrize("source", [InvocationSource.GESTURE, InvocationSource.NEURAL, InvocationSource.NETWORK_AGENT])
async def test_non_delegable_sources_never_reenter_mesh(tmp_path, source):
    executor = _executor(tmp_path)
    plan = _plan()
    expected = [ActionResult(action=plan.actions[0], success=True, output="local")]
    collab = _Collab([])
    executor.set_collab_executor(collab)
    executor._execute_without_controller_lease = AsyncMock(return_value=expected)

    results = await executor.execute(plan, invocation_source=source)

    assert results == expected
    collab.distribute.assert_not_awaited()


@pytest.mark.asyncio
async def test_explicit_local_execution_bypasses_mesh(tmp_path):
    executor = _executor(tmp_path)
    plan = _plan()
    expected = [ActionResult(action=plan.actions[0], success=True, output="local")]
    collab = _Collab([])
    executor.set_collab_executor(collab)
    executor._execute_without_controller_lease = AsyncMock(return_value=expected)

    results = await executor.execute(plan, allow_collaboration=False)

    assert results == expected
    collab.distribute.assert_not_awaited()
