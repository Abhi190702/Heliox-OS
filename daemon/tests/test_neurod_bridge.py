from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from pilot.neural.protocol import NeuralStreamDescriptorV1, NeuralTransport
from pilot.neural.rpc_client import NeurodBridge


class FakeTransport:
    def __init__(self, stop: asyncio.Event) -> None:
        self.stop = stop
        self.calls: list[tuple[str, dict]] = []
        self.status_count = 0
        self.connected = False
        self.closed = False
        self.markers: list[dict] = []

    async def connect(self) -> None:
        self.connected = True

    async def close(self) -> None:
        self.closed = True

    async def call(self, method: str, params: dict | None = None) -> dict:
        payload = params or {}
        self.calls.append((method, payload))
        if method == "neural_status":
            self.status_count += 1
            return (
                {"status": "ok", "state": "calibrating", "state_revision": 2}
                if self.status_count == 1
                else {"status": "ok", "state": "armed_safe_ui", "state_revision": 4}
            )
        if method == "neural_stimulus_markers":
            markers, self.markers = self.markers, []
            return {"status": "ok", "markers": markers}
        if method == "neural_intent_preview":
            self.stop.set()
            return {"status": "previewed"}
        return {"status": "ok"}


class FakeService:
    def __init__(self) -> None:
        self.descriptor = NeuralStreamDescriptorV1(
            session_id=uuid.uuid4(),
            source_id="synthetic-test",
            board_kind="synthetic",
            transport=NeuralTransport.SYNTHETIC,
            sample_rate_hz=250,
            channel_count=2,
            channel_names=("O1", "Oz"),
            reference="synthetic-reference",
            sequence_start=0,
            started_monotonic_ns=1,
        )
        self.buffer_health = SimpleNamespace(buffered_samples=500, dropped_samples=0)
        self.started = False
        self.stopped = False
        self.markers = []

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def observe_once(self, *, state_revision: int, requested_scope):
        quality = MagicMock()
        quality.model_dump.return_value = {
            "quality": "good",
            "artifact_flags": [],
            "channel_std_uv": [4.2, 4.1],
            "line_noise_ratio": 0.01,
            "muscle_ratio": 0.02,
            "estimated_missing_samples": 0,
            "timestamp_jitter_ratio": 0.0,
            "reasons": [],
        }
        intent = MagicMock()
        intent.model_dump.return_value = {
            "schema_version": 1,
            "class": "select",
            "signature": "a" * 64,
        }
        return SimpleNamespace(quality=quality, intent=intent)

    def record_stimulus_marker(self, marker) -> None:
        self.markers.append(marker)


@pytest.mark.asyncio
async def test_bridge_activates_calibration_streams_only_summaries_and_closes() -> None:
    stop = asyncio.Event()
    transport = FakeTransport(stop)
    service = FakeService()
    transport.markers = [
        {
            "schema_version": 1,
            "session_id": str(service.descriptor.session_id),
            "sequence": 0,
            "target_id": "focus_right",
            "event": "target_on",
            "received_monotonic_ns": 100,
            "client_performance_ms": 50.0,
        }
    ]
    metrics = MagicMock()
    metrics.model_dump.return_value = {"balanced_accuracy": 1.0}
    artifact = SimpleNamespace(
        calibration_id="b" * 64,
        decoder_version="a" * 64,
        subject_key="local-subject",
        metrics=metrics,
    )
    bridge = NeurodBridge(
        transport=transport,
        service=service,
        artifact=artifact,
        poll_seconds=0.05,
    )
    await asyncio.wait_for(bridge.run(stop), timeout=2)

    methods = [method for method, _ in transport.calls]
    assert methods[:4] == [
        "neural_connect",
        "neural_stimulus_markers",
        "neural_status",
        "neural_finish_calibration",
    ]
    assert "neural_observation" in methods
    assert "neural_intent_preview" in methods
    observation = next(params for method, params in transport.calls if method == "neural_observation")
    assert "samples_uv" not in observation and "timestamps_ns" not in observation
    assert transport.connected and transport.closed
    assert service.started and service.stopped
    assert service.markers[0].target_id == "focus_right"
