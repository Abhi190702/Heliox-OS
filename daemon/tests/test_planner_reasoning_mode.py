from unittest.mock import MagicMock

from pilot.agents.planner import Planner
from pilot.config import PilotConfig


def test_lightweight_reasoning_bounds_context_and_retry_work():
    config = PilotConfig()
    config.model.mode = "lightweight"
    config.memory.max_context_tokens = 12_000
    config.memory.max_recent_messages = 20

    assert Planner._reasoning_limits(config) == (4000, 6, 2)


def test_full_reasoning_uses_complete_configured_context_and_retries():
    config = PilotConfig()
    config.model.mode = "full"
    config.memory.max_context_tokens = 12_000
    config.memory.max_recent_messages = 20

    assert Planner._reasoning_limits(config) == (12_000, 20, 3)


def test_missing_reasoning_config_fails_safe_to_lightweight_limits():
    config = MagicMock()
    config.memory.max_context_tokens = 9000
    config.memory.max_recent_messages = 15
    config.model.mode = "unexpected"

    assert Planner._reasoning_limits(config) == (4000, 6, 2)
