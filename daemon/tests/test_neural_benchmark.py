from __future__ import annotations

import time

import numpy as np

from pilot.neural import benchmark
from pilot.neural.acquisition import NeuralSampleWindow
from pilot.neural.protocol import NeuralEvidenceKind, NeuralStreamDescriptorV1, NeuralTransport


def test_brainflow_synthetic_benchmark_reports_truthful_provenance(monkeypatch) -> None:
    class Source:
        def __init__(self, **kwargs) -> None:
            self.descriptor = NeuralStreamDescriptorV1(
                session_id="210cbbef-490b-4925-8485-151862364611",
                source_id=kwargs["source_id"],
                board_kind="brainflow--1",
                transport=NeuralTransport.BRAINFLOW,
                evidence_kind=NeuralEvidenceKind.SYNTHETIC,
                sample_rate_hz=250,
                channel_count=4,
                channel_names=kwargs["channel_names"],
                reference=kwargs["reference"],
                sequence_start=0,
                started_monotonic_ns=time.monotonic_ns(),
            )

        def start(self) -> None:
            pass

        def read(self, sample_count: int) -> NeuralSampleWindow:
            timestamps = np.arange(1, sample_count + 1, dtype=np.int64) * 4_000_000
            seconds = np.arange(sample_count) / 250
            samples = np.stack([10 * np.sin(2 * np.pi * (8 + channel) * seconds) for channel in range(4)])
            return NeuralSampleWindow(samples, timestamps, 0)

        def stop(self) -> None:
            pass

    monkeypatch.setattr(benchmark, "BrainFlowNeuralSource", Source)
    result = benchmark.benchmark_brainflow_synthetic(seconds=1.0)
    assert result.evidence_kind == "synthetic"
    assert result.board_kind == "brainflow--1"
    assert result.sample_count == 250
    assert result.realtime_ratio > 1
