import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from pilot.config import PilotConfig
from pilot.server import PilotServer
from pilot.system.voice import ContinuousVoiceListener


@pytest.mark.asyncio
async def test_listener_keeps_listening_while_previous_command_runs():
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    second_received = asyncio.Event()
    received: list[str] = []

    async def dispatch(command: str) -> None:
        received.append(command)
        if command == "first task":
            first_started.set()
            await release_first.wait()
        else:
            second_received.set()

    listener = ContinuousVoiceListener(
        wake_words=["hey heliox"],
        on_command=dispatch,
        config=PilotConfig(),
    )
    listener._wake_calibrator = MagicMock()
    transcripts = iter(["Hey Heliox, first task", "Hey Heliox, second task"])

    async def transcribe(**_kwargs):
        try:
            return next(transcripts)
        except StopIteration:
            await second_received.wait()
            listener._running = False
            return "No speech detected"

    listener._record_and_transcribe = transcribe
    listener._running = True

    listen_task = asyncio.create_task(listener._listen_loop())
    await asyncio.wait_for(first_started.wait(), timeout=1)
    await asyncio.wait_for(second_received.wait(), timeout=1)

    assert received == ["first task", "second task"]

    release_first.set()
    await listen_task
    await asyncio.gather(*tuple(listener._command_tasks))


@pytest.mark.asyncio
async def test_new_voice_command_stops_current_speech_before_live_correction():
    server = PilotServer(PilotConfig())
    server._interactive_request_active = True
    server._handle_interject = AsyncMock(
        return_value={"status": "revising", "message": "Applying correction"},
    )
    server._broadcast_notification = AsyncMock()
    server._speech_coordinator = MagicMock()
    server._speech_coordinator.status.return_value = {"active": True}
    server._speech_coordinator.stop_all = AsyncMock(return_value=1)

    await server._voice_command_dispatch("use the other folder instead")

    server._speech_coordinator.stop_all.assert_awaited_once()
    server._handle_interject.assert_awaited_once_with(
        {"input": "use the other folder instead"},
        None,
    )
    assert server._broadcast_notification.await_args_list[0].args == (
        "voice_status",
        {"status": "interrupted", "reason": "new voice command"},
    )
