from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from pilot.system import voice


class _FakeStdin:
    def __init__(self) -> None:
        self.payload = b""
        self.closed = False

    def write(self, payload: bytes) -> None:
        self.payload = payload

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


class _FakeStdout:
    def __init__(self, worker: _SuccessfulWorker) -> None:
        self.worker = worker
        self.closed = False

    def readline(self) -> bytes:
        request = json.loads(self.worker.stdin.payload)
        Path(request["output_file"]).write_bytes(b"RIFF-test-audio")
        return b'{"status":"ok"}\n'

    def close(self) -> None:
        self.closed = True


class _SuccessfulWorker:
    def __init__(self) -> None:
        self.stdin = _FakeStdin()
        self.stdout = _FakeStdout(self)
        self.returncode: int | None = None

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        self.returncode = 0
        return self.returncode


class _CancelledStdout:
    def readline(self) -> bytes:
        raise asyncio.CancelledError

    def close(self) -> None:
        return None


class _CancelledWorker(_SuccessfulWorker):
    def __init__(self) -> None:
        super().__init__()
        self.stdout = _CancelledStdout()


@pytest.fixture(autouse=True)
def _reset_worker_state() -> None:
    voice._local_tts_process = None
    voice._local_tts_engine = None
    voice._local_tts_idle_task = None


@pytest.mark.asyncio
async def test_local_tts_inference_runs_in_isolated_reusable_worker() -> None:
    worker = _SuccessfulWorker()

    with (
        patch.object(voice.subprocess, "Popen", return_value=worker) as spawn,
        patch.object(voice, "_play_local_tts_file", new=AsyncMock()) as play,
    ):
        await voice._run_local_tts_worker("kokoro_tts", "hello", "af_heart", None)
        await voice._run_local_tts_worker("kokoro_tts", "again", "af_heart", None)
        await voice._shutdown_local_tts_worker()

    command = spawn.call_args.args[0]
    assert command[1:3] == ["-m", "pilot.system.local_tts_worker"]
    assert command[-3:] == ["--engine", "kokoro_tts", "--serve"]
    spawn.assert_called_once()
    assert play.await_count == 2
    assert worker.stdin.closed is True


@pytest.mark.asyncio
async def test_local_tts_cancellation_closes_worker() -> None:
    worker = _CancelledWorker()

    with (
        patch.object(voice.subprocess, "Popen", return_value=worker),
        pytest.raises(asyncio.CancelledError),
    ):
        await voice._run_local_tts_worker("pocket_tts", "hello", "alba", None)

    assert worker.stdin.closed is True
    assert worker.returncode == 0
    assert voice._local_tts_process is None


@pytest.mark.asyncio
async def test_local_tts_worker_preserves_requested_output_file(tmp_path: Path) -> None:
    output = tmp_path / "speech.wav"
    worker = _SuccessfulWorker()

    with (
        patch.object(voice.subprocess, "Popen", return_value=worker),
        patch.object(voice, "_play_local_tts_file", new=AsyncMock()) as play,
    ):
        await voice._run_local_tts_worker("kokoro_tts", "hello", "af_heart", str(output))
        await voice._shutdown_local_tts_worker()

    assert output.read_bytes() == b"RIFF-test-audio"
    play.assert_not_awaited()


@pytest.mark.asyncio
async def test_local_tts_shutdown_closes_streams_after_worker_already_exited() -> None:
    worker = _SuccessfulWorker()
    worker.returncode = 1
    voice._local_tts_process = worker
    voice._local_tts_engine = "kokoro_tts"

    await voice._shutdown_local_tts_worker()

    assert worker.stdin.closed is True
    assert worker.stdout.closed is True
    assert voice._local_tts_process is None
