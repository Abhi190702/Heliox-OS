"""Regression + routing tests for PilotServer._voice_command_dispatch.

Before this fix, _voice_command_dispatch called self._executor.execute_plan(plan)
— a method Executor never defines (only execute()) — so every voice command
threw AttributeError, silently caught by the method's own broad except and
reported as "something went wrong." These tests cover both the crash fix and
the new specialist-orchestrator routing with a voice-derived scope_override.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from pilot.config import PilotConfig
from pilot.security.gateway import DEFAULT_SOURCE_PROFILES, InvocationSource
from pilot.server import PilotServer
from pilot.system.companion_speech import SpeechChannel


def _bare_server() -> PilotServer:
    server = PilotServer(PilotConfig())
    server._voice_listener = None
    server._broadcast_notification = AsyncMock()
    server._handle_execute = AsyncMock(
        return_value={"status": "success", "message": "The notes are ready."},
    )
    server._speak_voice_response = AsyncMock(return_value=False)
    server._spawn_interaction_speech = MagicMock()
    return server


@pytest.mark.asyncio
async def test_voice_runs_through_unified_interactive_handler():
    server = _bare_server()

    await server._voice_command_dispatch("read my notes")

    server._handle_execute.assert_awaited_once()
    params = server._handle_execute.await_args.args[0]
    assert params["input"] == "read my notes"
    assert params["source"] == "voice"
    server._spawn_interaction_speech.assert_called_once()
    server._speak_voice_response.assert_awaited_once_with(
        "The notes are ready.",
        channel=SpeechChannel.FINAL_ANSWER,
        dedupe_key="voice-result:read my notes",
    )


def test_voice_source_resolves_to_voice_scope_override():
    server = PilotServer(PilotConfig())

    invocation_source, override = server._execution_scope_for_source("voice")

    assert invocation_source == InvocationSource.VOICE
    voice_profile = DEFAULT_SOURCE_PROFILES["voice"]
    assert override.max_tier == voice_profile.max_tier
    assert override.deny_action_types == voice_profile.deny_action_types
    assert override.allow_root == voice_profile.allow_root


def test_voice_scope_override_is_never_wider_than_voice_profile():
    """A user-configured 'voice' profile in gateway.source_profiles (not just
    the hardcoded default) must be what's used to build the override."""
    server = PilotServer(PilotConfig())
    server.config.gateway.source_profiles["voice"].allow_root = False
    _, override = server._execution_scope_for_source("voice")
    assert override.allow_root is False


@pytest.mark.asyncio
async def test_voice_command_becomes_live_correction_during_active_task():
    server = PilotServer(PilotConfig())
    server._interactive_request_active = True
    server._handle_interject = AsyncMock(
        return_value={"status": "revising", "message": "Applying correction"},
    )
    server._broadcast_notification = AsyncMock()
    server._planner = AsyncMock()

    await server._voice_command_dispatch("use the other folder instead")

    server._handle_interject.assert_awaited_once_with(
        {"input": "use the other folder instead"},
        None,
    )
    server._planner.plan.assert_not_called()
    payload = server._broadcast_notification.call_args.args[1]
    assert payload["coordinated_correction"] is True
