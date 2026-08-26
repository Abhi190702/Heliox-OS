from unittest.mock import patch

import pytest

from pilot.system.triggers import TriggerEngine, _evaluate_custom_node, _parse_custom_expression


def test_custom_expression_supports_bounded_metrics() -> None:
    expression = _parse_custom_expression("memory_percent >= 80 and cpu_percent > 50 and not on_battery")

    assert (
        _evaluate_custom_node(
            expression,
            {
                "battery_percent": 100.0,
                "cpu_percent": 75.0,
                "disk_percent": 20.0,
                "hour": 12.0,
                "memory_percent": 90.0,
                "on_battery": False,
                "timestamp": 0.0,
            },
        )
        is True
    )


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('whoami')",
        "(1).__class__.__mro__",
        "unknown_metric > 1",
        "memory_percent in [90]",
    ],
)
def test_custom_expression_rejects_code_and_unbounded_constructs(expression: str) -> None:
    with pytest.raises(ValueError):
        _parse_custom_expression(expression)


def test_trigger_creation_rejects_unsafe_expression_before_registration() -> None:
    engine = TriggerEngine()

    with patch("os.system") as system, pytest.raises(ValueError):
        engine.create_trigger(
            "unsafe",
            "custom_condition",
            {"expression": "__import__('os').system('whoami')"},
            "show status",
        )

    system.assert_not_called()
    assert engine.list_triggers() == []


@pytest.mark.parametrize(
    ("name", "command", "max_fires", "cooldown"),
    [
        ("", "show status", 0, 0),
        ("watch", "", 0, 0),
        ("watch", "show status", -1, 0),
        ("watch", "show status", 0, -1),
    ],
)
def test_trigger_creation_rejects_incomplete_or_negative_values(
    name: str,
    command: str,
    max_fires: int,
    cooldown: int,
) -> None:
    engine = TriggerEngine()

    with pytest.raises(ValueError):
        engine.create_trigger(
            name,
            "time_interval",
            {},
            command,
            max_fires=max_fires,
            cooldown_seconds=cooldown,
        )

    assert engine.list_triggers() == []
