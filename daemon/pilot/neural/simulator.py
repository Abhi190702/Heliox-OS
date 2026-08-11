"""Deterministic zero-hardware calibration fixtures for the neural simulator."""

from __future__ import annotations

from pathlib import Path

from pilot.neural.acquisition import SyntheticNeuralSource
from pilot.neural.decoder import (
    CalibrationEpoch,
    SSVEPCalibrationArtifact,
    SSVEPCalibrator,
    SSVEPTarget,
)
from pilot.neural.protocol import NeuralIntentClass

SYNTHETIC_TARGETS = (
    SSVEPTarget(target_id="focus_left", frequency_hz=8.0, intent_class=NeuralIntentClass.FOCUS_LEFT),
    SSVEPTarget(target_id="focus_right", frequency_hz=10.0, intent_class=NeuralIntentClass.FOCUS_RIGHT),
    SSVEPTarget(target_id="select", frequency_hz=12.0, intent_class=NeuralIntentClass.SELECT),
    SSVEPTarget(target_id="cancel", frequency_hz=15.0, intent_class=NeuralIntentClass.CANCEL),
)


def build_synthetic_calibration_artifact() -> SSVEPCalibrationArtifact:
    """Build the registered four-target artifact without pretending it is human EEG."""

    sample_rate_hz = 250
    channel_names = ("O1", "Oz", "O2")
    epochs: list[CalibrationEpoch] = []
    for block_index in range(4):
        for target_index, target in enumerate(SYNTHETIC_TARGETS):
            source = SyntheticNeuralSource(
                sample_rate_hz=sample_rate_hz,
                channel_names=channel_names,
                target_hz=target.frequency_hz,
                noise_uv=1.0,
                seed=block_index * 10 + target_index,
            )
            source.start()
            try:
                epochs.append(
                    CalibrationEpoch(
                        window=source.read(sample_rate_hz * 2),
                        target_id=target.target_id,
                        block_id=f"synthetic-block-{block_index}",
                    )
                )
            finally:
                source.stop()
    return SSVEPCalibrator(targets=SYNTHETIC_TARGETS).fit(
        epochs,
        subject_key="synthetic-demo",
        sample_rate_hz=sample_rate_hz,
        channel_names=channel_names,
        reference="synthetic-reference",
    )


def ensure_synthetic_calibration_artifact(path: Path) -> SSVEPCalibrationArtifact:
    destination = path.expanduser().resolve()
    if destination.is_file():
        return SSVEPCalibrationArtifact.load(destination)
    artifact = build_synthetic_calibration_artifact()
    artifact.save(destination)
    return artifact
