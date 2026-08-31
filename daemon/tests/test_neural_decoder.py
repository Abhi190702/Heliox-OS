from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pilot.neural.acquisition import NeuralSampleWindow, SyntheticNeuralSource
from pilot.neural.decoder import (
    CalibrationEpoch,
    NeuralCalibrationError,
    SSVEPCalibrationArtifact,
    SSVEPCalibrator,
    SSVEPDecoder,
    SSVEPTarget,
)
from pilot.neural.gate import NeuralIntentSigner
from pilot.neural.protocol import (
    NeuralCalibrationMetricsV1,
    NeuralIntentClass,
    NeuralScope,
    SignalQuality,
)
from pilot.neural.quality import NeuralSignalQualityAnalyzer
from pilot.neural.service import NeuralDecoderService

TARGETS = (
    SSVEPTarget(target_id="left", frequency_hz=8, intent_class=NeuralIntentClass.FOCUS_LEFT),
    SSVEPTarget(target_id="right", frequency_hz=12, intent_class=NeuralIntentClass.FOCUS_RIGHT),
    SSVEPTarget(target_id="select", frequency_hz=15, intent_class=NeuralIntentClass.SELECT),
    SSVEPTarget(target_id="cancel", frequency_hz=20, intent_class=NeuralIntentClass.CANCEL),
)


def _synthetic_window(frequency: float, *, seed: int, count: int = 500) -> NeuralSampleWindow:
    source = SyntheticNeuralSource(
        target_hz=frequency,
        noise_uv=2.0,
        amplitude_uv=12,
        seed=seed,
    )
    source.start()
    return source.read(count)


def _artifact() -> SSVEPCalibrationArtifact:
    epochs = [
        CalibrationEpoch(
            _synthetic_window(target.frequency_hz, seed=block * 11 + index),
            target.target_id,
            f"block-{block}",
        )
        for block in range(3)
        for index, target in enumerate(TARGETS)
    ]
    return SSVEPCalibrator(targets=TARGETS).fit(
        epochs,
        subject_key="local-test-subject",
        sample_rate_hz=250,
        channel_names=("O1", "Oz", "O2"),
        reference="synthetic-common-reference",
    )


def test_calibration_is_block_disjoint_accurate_and_content_addressed(tmp_path: Path) -> None:
    artifact = _artifact()
    assert artifact.metrics.block_count == 3
    assert artifact.metrics.balanced_accuracy >= 0.95
    path = tmp_path / "calibration.json"
    artifact.save(path)
    assert SSVEPCalibrationArtifact.load(path) == artifact
    assert "samples_uv" not in path.read_text(encoding="utf-8")

    tampered = path.read_text(encoding="utf-8").replace('"harmonics": 2', '"harmonics": 3')
    path.write_text(tampered, encoding="utf-8")
    with pytest.raises(NeuralCalibrationError, match="content hash"):
        SSVEPCalibrationArtifact.load(path)


def test_decoder_recovers_synthetic_target_with_calibrated_probability() -> None:
    artifact = _artifact()
    window = _synthetic_window(15, seed=200)
    quality = NeuralSignalQualityAnalyzer().analyze(window, sample_rate_hz=250, channel_names=("O1", "Oz", "O2"))
    assert quality.quality == SignalQuality.GOOD
    candidate = SSVEPDecoder(artifact).decode(window, quality=quality)
    assert candidate.intent_class == NeuralIntentClass.SELECT
    assert candidate.posterior_permille >= 700
    assert candidate.margin_permille >= 500


def test_decoder_rejects_window_drift_and_weak_calibration() -> None:
    artifact = _artifact()
    short = _synthetic_window(15, seed=201, count=250)
    quality = NeuralSignalQualityAnalyzer().analyze(short, sample_rate_hz=250, channel_names=("O1", "Oz", "O2"))
    with pytest.raises(NeuralCalibrationError, match="window length"):
        SSVEPDecoder(artifact).decode(short, quality=quality)

    noise_epochs = [
        CalibrationEpoch(
            _synthetic_window(None, seed=block * 11 + index),
            target.target_id,
            f"block-{block}",
        )
        for block in range(3)
        for index, target in enumerate(TARGETS)
    ]
    with pytest.raises(NeuralCalibrationError, match="balanced accuracy"):
        SSVEPCalibrator(targets=TARGETS, minimum_balanced_accuracy=0.9).fit(
            noise_epochs,
            subject_key="weak-subject",
            sample_rate_hz=250,
            channel_names=("O1", "Oz", "O2"),
            reference="synthetic-common-reference",
        )


def test_calibration_rejects_collapsed_or_overconfident_targets() -> None:
    calibrator = SSVEPCalibrator(targets=TARGETS)
    base = {
        "epoch_count": 40,
        "block_count": 4,
        "balanced_accuracy": 0.8,
        "expected_calibration_error": 0.1,
        "per_class_recall": {target.target_id: 0.8 for target in TARGETS},
    }
    collapsed = NeuralCalibrationMetricsV1.model_validate(
        {
            **base,
            "per_class_recall": {**base["per_class_recall"], "cancel": 0.2},
        }
    )
    with pytest.raises(NeuralCalibrationError, match="collapsed target"):
        calibrator._validate_metrics(collapsed)

    overconfident = NeuralCalibrationMetricsV1.model_validate({**base, "expected_calibration_error": 0.4})
    with pytest.raises(NeuralCalibrationError, match="sufficiently calibrated"):
        calibrator._validate_metrics(overconfident)


def test_calibration_requires_registered_advantage_over_chance() -> None:
    calibrator = SSVEPCalibrator(
        targets=TARGETS,
        minimum_balanced_accuracy=0.0,
        minimum_chance_advantage=0.2,
    )
    metrics = NeuralCalibrationMetricsV1(
        epoch_count=40,
        block_count=4,
        balanced_accuracy=0.4,
        expected_calibration_error=0.1,
        per_class_recall={target.target_id: 0.6 for target in TARGETS},
    )
    with pytest.raises(NeuralCalibrationError, match="balanced accuracy"):
        calibrator._validate_metrics(metrics)


def test_calibration_artifact_binds_acceptance_criteria_and_target_metrics(tmp_path: Path) -> None:
    artifact = _artifact()
    payload = artifact.model_dump(mode="json")
    payload["metrics"]["per_class_recall"] = {
        "unrelated-a": 1.0,
        "unrelated-b": 1.0,
        "unrelated-c": 1.0,
        "unrelated-d": 1.0,
    }

    with pytest.raises(ValueError, match="cover every calibrated target"):
        SSVEPCalibrationArtifact.model_validate(payload)

    payload = artifact.model_dump(mode="json")
    payload["metrics"]["balanced_accuracy"] = 0.2
    with pytest.raises(ValueError, match="below its registered threshold"):
        SSVEPCalibrationArtifact.model_validate(payload)

    artifact.save(tmp_path / "calibration.json")
    loaded = SSVEPCalibrationArtifact.load(tmp_path / "calibration.json")
    assert loaded.minimum_per_class_recall == 0.5
    assert loaded.maximum_expected_calibration_error == 0.25


def test_sidecar_emits_only_signed_derived_intent_and_tracks_dwell() -> None:
    artifact = _artifact()
    source = SyntheticNeuralSource(target_hz=15, noise_uv=1.0, seed=99)
    signer = NeuralIntentSigner(b"s" * 32)
    service = NeuralDecoderService(source=source, decoder=SSVEPDecoder(artifact), signer=signer)
    service.start()
    observations = [service.observe_once(state_revision=7, requested_scope=NeuralScope.NAVIGATE) for _ in range(3)]
    service.stop()
    intents = [observation.intent for observation in observations]
    assert all(intent is not None for intent in intents)
    assert [intent.dwell_windows for intent in intents if intent] == [1, 2, 3]
    assert all(signer.verify(intent) for intent in intents if intent)
    wire = intents[-1].model_dump(mode="json", by_alias=True) if intents[-1] else {}
    assert "samples_uv" not in wire and "timestamps_ns" not in wire


def test_sidecar_dwell_saturates_at_the_wire_contract_limit() -> None:
    artifact = _artifact()
    service = NeuralDecoderService(
        source=SyntheticNeuralSource(target_hz=15, noise_uv=1.0, seed=100),
        decoder=SSVEPDecoder(artifact),
        signer=NeuralIntentSigner(b"d" * 32),
    )
    service.start()
    try:
        observations = [service.observe_once(state_revision=7, requested_scope=NeuralScope.NAVIGATE) for _ in range(70)]
    finally:
        service.stop()
    assert observations[-1].intent is not None
    assert observations[-1].intent.dwell_windows == 64


def test_sidecar_records_every_acquired_chunk_only_when_factory_is_supplied() -> None:
    artifact = _artifact()
    source = SyntheticNeuralSource(target_hz=15, noise_uv=1.0, seed=101)
    recorded: list[NeuralSampleWindow] = []

    class Recorder:
        def append(self, window: NeuralSampleWindow) -> None:
            recorded.append(window)

    service = NeuralDecoderService(
        source=source,
        decoder=SSVEPDecoder(artifact),
        signer=NeuralIntentSigner(b"r" * 32),
        recorder_factory=lambda descriptor: Recorder(),
    )
    service.start()
    warmup_chunks = len(recorded)
    service.observe_once(state_revision=1, requested_scope=NeuralScope.NAVIGATE)
    service.stop()
    assert warmup_chunks > 0
    assert len(recorded) == warmup_chunks + 1
