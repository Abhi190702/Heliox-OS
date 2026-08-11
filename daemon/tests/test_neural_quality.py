from __future__ import annotations

import numpy as np

from pilot.neural.acquisition import NeuralSampleWindow
from pilot.neural.protocol import ArtifactFlag, SignalQuality
from pilot.neural.quality import NeuralSignalQualityAnalyzer


def _window(samples: np.ndarray, timestamps: np.ndarray | None = None) -> NeuralSampleWindow:
    count = samples.shape[1]
    if timestamps is None:
        timestamps = np.rint(np.arange(count) * 4_000_000).astype(np.int64) + 1
    return NeuralSampleWindow(samples, timestamps, 0)


def test_clean_oscillatory_signal_is_good() -> None:
    seconds = np.arange(500) / 250
    samples = np.stack([10 * np.sin(2 * np.pi * 12 * seconds + phase) for phase in (0, 0.2, 0.4)])
    summary = NeuralSignalQualityAnalyzer().analyze(
        _window(samples), sample_rate_hz=250, channel_names=("O1", "Oz", "O2")
    )
    assert summary.quality == SignalQuality.GOOD
    assert summary.artifact_flags == ()


def test_flat_saturated_and_missing_samples_fail_closed() -> None:
    flat = np.zeros((2, 128))
    flat[0, 20] = 600
    timestamps = np.rint(np.arange(128) * 4_000_000).astype(np.int64) + 1
    timestamps[64:] += 8_000_000
    summary = NeuralSignalQualityAnalyzer().analyze(
        _window(flat, timestamps), sample_rate_hz=250, channel_names=("O1", "Oz")
    )
    assert summary.quality == SignalQuality.REJECT
    assert ArtifactFlag.FLAT_CHANNEL in summary.artifact_flags
    assert ArtifactFlag.SATURATION in summary.artifact_flags
    assert ArtifactFlag.PACKET_LOSS in summary.artifact_flags


def test_frontal_blink_and_line_noise_are_labeled_not_cleaned() -> None:
    seconds = np.arange(500) / 250
    samples = np.stack(
        [
            220 * np.exp(-((seconds - 1) ** 2) / 0.002),
            50 * np.sin(2 * np.pi * 50 * seconds),
        ]
    )
    summary = NeuralSignalQualityAnalyzer().analyze(_window(samples), sample_rate_hz=250, channel_names=("Fp1", "Oz"))
    assert summary.quality != SignalQuality.GOOD
    assert ArtifactFlag.BLINK in summary.artifact_flags
    assert ArtifactFlag.LINE_NOISE in summary.artifact_flags
