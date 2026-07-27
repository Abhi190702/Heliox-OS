from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pilot.agents.planner import Planner


class _ModelThatMustNotRun:
    async def generate(self, *args, **kwargs):
        raise AssertionError("simple conversation must not call the planning model")


class _MemoryThatMustNotRun:
    async def get_context(self, user_input):
        raise AssertionError("simple conversation must not load action-planning context")


@pytest.mark.asyncio
async def test_greeting_returns_helpful_zero_action_response_without_model_call():
    planner = Planner(_ModelThatMustNotRun(), _MemoryThatMustNotRun())

    plan = await planner.plan("Hello Heliox")

    assert plan.error is None
    assert plan.actions == []
    assert "inspect your system" in plan.explanation


def test_compound_greeting_with_action_is_not_treated_as_conversation_only():
    assert Planner._try_fast_path("Hello Heliox, open GitHub") is None


def test_parser_accepts_helpful_zero_action_model_response():
    planner = Planner(MagicMock(), MagicMock())

    plan = planner._parse_response(
        '{"explanation":"I can answer that without changing your computer.","actions":[]}',
        "What can you tell me?",
    )

    assert plan.error is None
    assert plan.actions == []
    assert plan.explanation == "I can answer that without changing your computer."


def test_parser_rejects_empty_zero_action_model_response():
    planner = Planner(MagicMock(), MagicMock())

    plan = planner._parse_response('{"explanation":"","actions":[]}', "Hello")

    assert plan.error is not None
    assert "EMPTY RESPONSE" in plan.error
