from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from pilot.actions import Action, ActionType, BrowserParams, EmptyParams
from pilot.agents.executor import Executor
from pilot.config import PilotConfig
from pilot.security.audit import AuditLogger
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


def test_browser_workflow_actions_are_serialized(tmp_path):
    actions = [
        Action(
            action_type=ActionType.BROWSER_NAVIGATE,
            target="https://example.com",
            parameters=BrowserParams(url="https://example.com"),
        ),
        Action(
            action_type=ActionType.BROWSER_CLICK_TEXT,
            target="Learn more",
            parameters=BrowserParams(text="Learn more"),
        ),
        Action(
            action_type=ActionType.BROWSER_EXTRACT,
            target="main",
            parameters=BrowserParams(selector="main"),
        ),
    ]

    batches = _executor(tmp_path)._analyze_dependencies(actions)

    assert batches == [[actions[0]], [actions[1]], [actions[2]]]


def test_unrelated_read_only_system_actions_can_share_a_batch(tmp_path):
    actions = [
        Action(action_type=ActionType.CPU_USAGE, target="", parameters=EmptyParams()),
        Action(action_type=ActionType.MEMORY_USAGE, target="", parameters=EmptyParams()),
    ]

    batches = _executor(tmp_path)._analyze_dependencies(actions)

    assert batches == [actions]


@pytest.mark.asyncio
async def test_close_releases_only_an_existing_browser_backend(tmp_path):
    executor = _executor(tmp_path)

    await executor.close()
    assert not hasattr(executor, "_browser_backend")

    backend = SimpleNamespace(close=AsyncMock())
    executor._browser_backend = backend
    await executor.close()

    backend.close.assert_awaited_once()
    assert not hasattr(executor, "_browser_backend")
