from __future__ import annotations

import json
import time

import numpy as np
import pytest

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


def test_motor_imagery_mapping_is_bounded_to_navigation_previews() -> None:
    assert benchmark.motor_imagery_preview_action(0).value == "focus_left"
    assert benchmark.motor_imagery_preview_action(1).value == "focus_right"
    with pytest.raises(ValueError, match="zero or one"):
        benchmark.motor_imagery_preview_action(2)


def test_recorded_eeg_evaluation_is_grouped_and_truthfully_labelled(monkeypatch) -> None:
    class FakeCSP:
        def __init__(self, **kwargs) -> None:
            pass

        def fit(self, data, labels):
            return self

        def transform(self, data):
            return np.column_stack((data[:, 0].mean(axis=1), data[:, 1].mean(axis=1)))

        def fit_transform(self, data, labels):
            return self.fit(data, labels).transform(data)

    import mne.decoding

    monkeypatch.setattr(mne.decoding, "CSP", FakeCSP)
    epochs = np.zeros((12, 2, 16), dtype=np.float64)
    labels = np.tile([0, 1], 6)
    groups = np.repeat([6, 10, 14], 4)
    epochs[:, 0, :] = np.where(labels[:, None] == 0, -2.0, 2.0)
    epochs[:, 1, :] = np.where(labels[:, None] == 0, 1.0, -1.0)
    epochs += np.random.default_rng(7).normal(0.0, 0.05, size=epochs.shape)
    result = benchmark.evaluate_motor_imagery_epochs(
        epochs,
        labels,
        groups,
        subject=1,
        runs=(6, 10, 14),
        sample_rate_hz=160.0,
    )
    assert result.evidence_kind == "recorded_eeg"
    assert result.fold_count == 3
    assert result.classifier_to_preview_mapping_verified is True
    assert set(result.decoded_preview_actions) == {"focus_left", "focus_right"}


def test_eegbci_benchmark_rejects_non_imagery_or_single_run_inputs() -> None:
    with pytest.raises(ValueError, match="at least two"):
        benchmark.benchmark_eegbci(subject=1, runs=(6,))
    with pytest.raises(ValueError, match="motor-imagery"):
        benchmark.benchmark_eegbci(subject=1, runs=(1, 2))


def test_control_trial_manifest_scores_the_full_commit_gate(tmp_path) -> None:
    manifest = tmp_path / "trials.json"
    manifest.write_text(
        json.dumps(
            {
                "evidence_kind": "recorded_eeg",
                "trials": [
                    {
                        "duration_seconds": 2,
                        "expected_intent": "focus_left",
                        "predicted_intent": "focus_left",
                        "committed": True,
                        "latency_ms": 800,
                    },
                    {
                        "duration_seconds": 60,
                        "expected_intent": None,
                        "predicted_intent": None,
                        "committed": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    report = benchmark.benchmark_control_trials(manifest)

    assert report["evidence_kind"] == "recorded_eeg"
    assert report["precision"] == 1.0
    assert report["idle_abstention_rate"] == 1.0
    assert report["median_commit_latency_ms"] == 800.0


def test_control_trial_manifest_rejects_unknown_fields(tmp_path) -> None:
    manifest = tmp_path / "trials.json"
    manifest.write_text(
        json.dumps({"trials": [{"duration_seconds": 1, "unexpected": True}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown fields"):
        benchmark.benchmark_control_trials(manifest)
