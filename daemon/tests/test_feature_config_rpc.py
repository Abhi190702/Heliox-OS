from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from pilot.config import PilotConfig
from pilot.server import PilotServer


@pytest.mark.asyncio
async def test_preview_enabled_update_requires_boolean():
    config = PilotConfig()
    config.save = MagicMock()
    server = PilotServer(config)

    result = await server._handle_update_config(
        {"section": "preview", "values": {"enabled": "yes"}},
        MagicMock(),
    )

    assert result["status"] == "error"
    assert config.preview.enabled is False
    config.save.assert_not_called()


@pytest.mark.asyncio
async def test_preview_enabled_update_is_applied_and_saved():
    config = PilotConfig()
    config.save = MagicMock()
    server = PilotServer(config)

    result = await server._handle_update_config(
        {"section": "preview", "values": {"enabled": True}},
        MagicMock(),
    )

    assert result["status"] == "ok"
    assert config.preview.enabled is True
    config.save.assert_called_once_with()


@pytest.mark.asyncio
async def test_unknown_config_key_is_rejected_by_rpc():
    server = object.__new__(PilotServer)
    config = PilotConfig()
    config.save = MagicMock()
    server.config = config

    result = await server._handle_update_config(
        {"section": "calendar", "values": {"caldav_usernme": "typo"}},
        MagicMock(),
    )

    assert result["status"] == "error"
    assert "calendar.caldav_usernme" in result["message"]
    config.save.assert_not_called()


@pytest.mark.asyncio
async def test_subscription_provider_update_is_validated_and_saved():
    config = PilotConfig()
    config.save = MagicMock()
    server = PilotServer(config)

    result = await server._handle_update_config(
        {
            "section": "model",
            "values": {
                "provider": "subscription",
                "subscription_provider": "codex",
                "subscription_model": "  gpt-test  ",
                "subscription_timeout_seconds": 90,
                "subscription_max_prompt_chars": 24000,
            },
        },
        MagicMock(),
    )

    assert result["status"] == "ok"
    assert config.model.provider == "subscription"
    assert config.model.subscription_provider == "codex"
    assert config.model.subscription_model == "gpt-test"
    config.save.assert_called_once_with()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"provider": "browser_cookie"}, "model.provider"),
        ({"subscription_provider": "unknown"}, "subscription_provider"),
        ({"subscription_timeout_seconds": 5}, "subscription_timeout_seconds"),
        ({"subscription_max_prompt_chars": 15999}, "subscription_max_prompt_chars"),
    ],
)
async def test_subscription_provider_update_rejects_unsafe_values(values, message):
    config = PilotConfig()
    config.save = MagicMock()
    server = PilotServer(config)

    result = await server._handle_update_config(
        {"section": "model", "values": values},
        MagicMock(),
    )

    assert result["status"] == "error"
    assert message in result["message"]
    config.save.assert_not_called()


@pytest.mark.asyncio
async def test_rejected_multi_field_update_does_not_partially_mutate_runtime_config():
    config = PilotConfig()
    config.save = MagicMock()
    server = PilotServer(config)

    result = await server._handle_update_config(
        {
            "section": "model",
            "values": {
                "provider": "subscription",
                "subscription_timeout_seconds": 5,
            },
        },
        MagicMock(),
    )

    assert result["status"] == "error"
    assert config.model.provider == "ollama"
    assert config.model.subscription_timeout_seconds == 120
    config.save.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"enabled": 1}, "enabled must be a boolean"),
        ({"sensitivity": 0}, "sensitivity must be from 0.1 to 3"),
        ({"prediction_ms": 251}, "prediction_ms must be from 0 to 250"),
        ({"blend": 1.1}, "blend must be from 0 to 1"),
    ],
)
async def test_gesture_cursor_update_rejects_invalid_values(values, message):
    config = PilotConfig()
    config.save = MagicMock()
    server = PilotServer(config)

    result = await server._handle_update_config(
        {"section": "gesture_cursor", "values": values},
        MagicMock(),
    )

    assert result["status"] == "error"
    assert message in result["message"]
    config.save.assert_not_called()


@pytest.mark.asyncio
async def test_gesture_cursor_update_applies_runtime_tuning():
    config = PilotConfig()
    config.save = MagicMock()
    server = PilotServer(config)

    result = await server._handle_update_config(
        {
            "section": "gesture_cursor",
            "values": {"enabled": True, "sensitivity": 1.7, "blend": 0.45},
        },
        MagicMock(),
    )

    assert result["status"] == "ok"
    assert config.gesture_cursor.enabled is True
    assert config.gesture_cursor.sensitivity == 1.7
    assert config.gesture_cursor.blend == 0.45
    config.save.assert_called_once_with()


@pytest.mark.asyncio
async def test_gesture_calibration_update_requires_boolean():
    config = PilotConfig()
    config.save = MagicMock()
    server = PilotServer(config)

    result = await server._handle_update_config(
        {
            "section": "adaptive_calibration",
            "values": {"gesture_enabled": "enabled"},
        },
        MagicMock(),
    )

    assert result["status"] == "error"
    assert config.adaptive_calibration.gesture_enabled is True
    config.save.assert_not_called()


@pytest.mark.asyncio
async def test_voice_calibration_update_requires_boolean():
    config = PilotConfig()
    config.save = MagicMock()
    server = PilotServer(config)

    result = await server._handle_update_config(
        {
            "section": "adaptive_calibration",
            "values": {"voice_wake_word_enabled": 1},
        },
        MagicMock(),
    )

    assert result["status"] == "error"
    assert config.adaptive_calibration.voice_wake_word_enabled is True
    config.save.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"tts_engine": "cloud"}, "tts_engine must be kokoro_tts, pocket_tts, or os_native"),
        ({"tts_voice": "unknown"}, "tts_voice must be a supported Kokoro or Pocket TTS voice"),
        ({"input_device": ""}, "input_device must be a valid microphone identifier"),
    ],
)
async def test_voice_output_update_rejects_unknown_options(values, message):
    config = PilotConfig()
    config.save = MagicMock()
    server = PilotServer(config)

    result = await server._handle_update_config(
        {"section": "voice", "values": values},
        MagicMock(),
    )

    assert result["status"] == "error"
    assert message in result["message"]
    config.save.assert_not_called()


@pytest.mark.asyncio
async def test_active_voice_listener_restarts_for_new_input_device(monkeypatch):
    config = PilotConfig()
    config.save = MagicMock()
    server = PilotServer(config)
    current = SimpleNamespace(
        is_running=True,
        wake_words=["hey heliox"],
        stop=AsyncMock(return_value="stopped"),
    )
    server._voice_listener = current
    created = []

    class FakeListener:
        def __init__(self, *, wake_words, config, **kwargs):
            self.wake_words = wake_words
            self.input_device = config.voice.input_device
            self.is_running = False
            created.append(self)

        async def start(self):
            self.is_running = True
            return "started"

        async def stop(self):
            self.is_running = False
            return "stopped"

    monkeypatch.setattr("pilot.system.voice.ContinuousVoiceListener", FakeListener)

    result = await server._handle_update_config(
        {"section": "voice", "values": {"input_device": "WASAPI::Headset"}},
        MagicMock(),
    )

    assert result == {"status": "ok"}
    current.stop.assert_awaited_once()
    assert config.voice.input_device == "WASAPI::Headset"
    assert created[0].input_device == "WASAPI::Headset"
    assert server._voice_listener is created[0]
    assert created[0].is_running is True


@pytest.mark.asyncio
async def test_failed_voice_device_restart_rolls_back_config_and_listener(monkeypatch):
    config = PilotConfig()
    config.save = MagicMock()
    server = PilotServer(config)
    current = SimpleNamespace(
        is_running=True,
        wake_words=["hey heliox"],
        stop=AsyncMock(return_value="stopped"),
    )
    server._voice_listener = current
    attempted_devices = []

    class FakeListener:
        def __init__(self, *, wake_words, config, **kwargs):
            self.wake_words = wake_words
            self.input_device = config.voice.input_device
            self.is_running = False
            attempted_devices.append(self.input_device)

        async def start(self):
            self.is_running = self.input_device != "missing-device"
            return "started" if self.is_running else "selected microphone is unavailable"

        async def stop(self):
            self.is_running = False
            return "stopped"

    monkeypatch.setattr("pilot.system.voice.ContinuousVoiceListener", FakeListener)

    result = await server._handle_update_config(
        {"section": "voice", "values": {"input_device": "missing-device"}},
        MagicMock(),
    )

    assert result["status"] == "error"
    assert "selected microphone is unavailable" in result["message"]
    assert config.voice.input_device == "auto"
    assert attempted_devices == ["missing-device", "auto"]
    assert server._voice_listener.input_device == "auto"
    assert server._voice_listener.is_running is True
    assert config.save.call_count == 2
