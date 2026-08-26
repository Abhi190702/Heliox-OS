from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from pilot.config import PilotConfig
from pilot.server import PilotServer


def _server() -> PilotServer:
    return PilotServer(PilotConfig())


@pytest.mark.asyncio
async def test_canary_consent_rejects_truthy_string() -> None:
    server = _server()
    server._strategy_evolution = SimpleNamespace(start_canary=AsyncMock())

    result = await server._handle_strategy_start_canary(
        {"candidate_id": "candidate", "consent_confirmed": "false"},
        ws=None,
    )

    assert result == {"status": "error", "message": "consent_confirmed must be a boolean"}
    server._strategy_evolution.start_canary.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler_name", "attribute"),
    [
        ("_handle_attention_toggle", "_attention_ui"),
        ("_handle_stress_gate_toggle", "_stress_gate"),
        ("_handle_intent_predictor_toggle", "_intent_predictor"),
    ],
)
async def test_cognitive_toggles_reject_truthy_strings(handler_name: str, attribute: str) -> None:
    server = _server()
    component = SimpleNamespace(toggle=MagicMock())
    setattr(server, attribute, component)

    result = await getattr(server, handler_name)({"enabled": "false"}, ws=None)

    assert result == {"status": "error", "message": "enabled must be a boolean"}
    component.toggle.assert_not_called()


@pytest.mark.asyncio
async def test_plugin_toggle_rejects_truthy_string() -> None:
    server = _server()
    server._plugin_registry = SimpleNamespace(
        enable_plugin=MagicMock(),
        disable_plugin=MagicMock(),
    )

    result = await server._handle_plugin_toggle({"name": "example", "enabled": "false"}, ws=None)

    assert result == {"error": "enabled must be a boolean"}
    server._plugin_registry.enable_plugin.assert_not_called()
    server._plugin_registry.disable_plugin.assert_not_called()


@pytest.mark.asyncio
async def test_screen_vision_rejects_ambiguous_switches_and_interval() -> None:
    server = _server()
    server._screen_vision = SimpleNamespace(start=AsyncMock(), stop=AsyncMock())

    wrong_switch = await server._handle_screen_vision_toggle({"enabled": "false"}, ws=None)
    wrong_describe = await server._handle_screen_vision_toggle(
        {"enabled": True, "enable_describe": "false"},
        ws=None,
    )
    wrong_interval = await server._handle_screen_vision_toggle(
        {"enabled": True, "interval_seconds": "3"},
        ws=None,
    )

    assert wrong_switch["status"] == "error"
    assert wrong_describe["status"] == "error"
    assert wrong_interval["status"] == "error"
    server._screen_vision.start.assert_not_awaited()
    server._screen_vision.stop.assert_not_awaited()


@pytest.mark.asyncio
async def test_screen_vision_disable_ignores_irrelevant_stale_options() -> None:
    server = _server()
    server._screen_vision = SimpleNamespace(start=AsyncMock(), stop=AsyncMock())

    result = await server._handle_screen_vision_toggle(
        {"enabled": False, "enable_describe": "stale", "interval_seconds": "stale"},
        ws=None,
    )

    assert result == {"status": "ok", "enabled": False}
    server._screen_vision.stop.assert_awaited_once()
    server._screen_vision.start.assert_not_awaited()


@pytest.mark.asyncio
async def test_sensitive_list_flags_reject_truthy_strings() -> None:
    server = _server()
    server._strategy_evolution = SimpleNamespace(list_candidates=AsyncMock())
    server._evolution_harness = SimpleNamespace(list_candidates=AsyncMock())
    server._voice_gesture_workflows = SimpleNamespace(list_workflows=AsyncMock())

    strategy = await server._handle_strategy_candidates({"include_content": "false"}, ws=None)
    evolution = await server._handle_evolution_candidates({"include_patch": "false"}, ws=None)
    workflows = await server._handle_voice_gesture_workflow_list({"include_terminal": "false"}, ws=None)

    assert strategy["status"] == "error"
    assert evolution["status"] == "error"
    assert workflows["status"] == "error"
    server._strategy_evolution.list_candidates.assert_not_awaited()
    server._evolution_harness.list_candidates.assert_not_awaited()
    server._voice_gesture_workflows.list_workflows.assert_not_awaited()


@pytest.mark.asyncio
async def test_voice_and_subscription_flags_reject_truthy_strings() -> None:
    server = _server()
    server._fusion = SimpleNamespace(on_voice_event=AsyncMock())
    server._append_experience = AsyncMock()
    subscription = SimpleNamespace(status=AsyncMock())
    server._subscription_client = MagicMock(return_value=subscription)

    voice = await server._handle_voice_event({"transcript": "hello", "is_final": "false"}, ws=None)
    status = await server._handle_subscription_status({"refresh": "false"}, ws=None)

    assert voice == {"status": "error", "message": "is_final must be a boolean"}
    assert status == {"status": "error", "message": "refresh must be a boolean"}
    server._fusion.on_voice_event.assert_not_awaited()
    server._append_experience.assert_not_awaited()
    subscription.status.assert_not_awaited()
