"""Fail-closed contracts for plan-to-result verification."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pilot.actions import Action, ActionPlan, ActionResult, ActionType, FileParams
from pilot.agents.verifier import Verifier


def _action(target: str) -> Action:
    return Action(
        action_type=ActionType.FILE_READ,
        target=target,
        parameters=FileParams(path=target),
    )


@pytest.mark.asyncio
async def test_missing_result_fails_verification() -> None:
    plan = ActionPlan(actions=[_action("one.txt")])

    verification = await Verifier(MagicMock()).verify(plan, [])

    assert verification.passed is False
    assert verification.failed_actions == [0]
    assert any("RESULT COUNT MISMATCH" in detail for detail in verification.details)
    assert any("MISSING" in detail for detail in verification.details)


@pytest.mark.asyncio
async def test_mismatched_result_action_fails_verification() -> None:
    plan = ActionPlan(actions=[_action("planned.txt")])
    result = ActionResult(action=_action("different.txt"), success=True, output="data")

    verification = await Verifier(MagicMock()).verify(plan, [result])

    assert verification.passed is False
    assert verification.failed_actions == [0]
    assert any("MISMATCH" in detail for detail in verification.details)


@pytest.mark.asyncio
async def test_extra_result_fails_verification() -> None:
    planned = _action("planned.txt")
    plan = ActionPlan(actions=[planned])
    results = [
        ActionResult(action=planned, success=True, output="planned"),
        ActionResult(action=_action("unexpected.txt"), success=True, output="unexpected"),
    ]

    verification = await Verifier(MagicMock()).verify(plan, results)

    assert verification.passed is False
    assert verification.failed_actions == [1]
    assert any("UNEXPECTED" in detail for detail in verification.details)
