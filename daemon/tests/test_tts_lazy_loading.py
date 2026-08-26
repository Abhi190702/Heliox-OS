from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from pilot.config import PilotConfig
from pilot.server import PilotServer


def test_local_tts_warmup_is_deferred_until_first_speech() -> None:
    config = PilotConfig()
    config.voice.tts_engine = "kokoro_tts"
    server = PilotServer(config)
    stale_warmup = MagicMock(spec=asyncio.Task)
    stale_warmup.done.return_value = False
    server._tts_warmup_task = stale_warmup

    server._start_tts_warmup()

    stale_warmup.cancel.assert_called_once_with()
    assert server._tts_warmup_task is None
