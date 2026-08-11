from __future__ import annotations

import hashlib

from pilot.neural.acquisition import SyntheticNeuralSource
from pilot.neural.decoder import SSVEPCalibrationArtifact, SSVEPDecoder
from pilot.neural.gate import NeuralIntentSigner
from pilot.neural.service import NeuralDecoderService
from pilot.neural.simulator import build_synthetic_calibration_artifact, ensure_synthetic_calibration_artifact


def test_synthetic_artifact_is_reproducible_and_passes_held_block_gate(tmp_path) -> None:
    first = build_synthetic_calibration_artifact()
    second = build_synthetic_calibration_artifact()
    assert first.calibration_id == second.calibration_id
    assert first.metrics.balanced_accuracy == 1.0
    assert set(first.class_order) == {"focus_left", "focus_right", "select", "cancel"}

    path = tmp_path / "synthetic.json"
    saved = ensure_synthetic_calibration_artifact(path)
    loaded = SSVEPCalibrationArtifact.load(path)
    assert loaded.calibration_id == saved.calibration_id


def test_synthetic_artifact_starts_the_real_decoder_service() -> None:
    artifact = build_synthetic_calibration_artifact()
    source = SyntheticNeuralSource(
        sample_rate_hz=artifact.sample_rate_hz,
        channel_names=artifact.channel_names,
        target_hz=12.0,
    )
    service = NeuralDecoderService(
        source=source,
        decoder=SSVEPDecoder(artifact),
        signer=NeuralIntentSigner(b"k" * 32),
    )
    service.start()
    try:
        assert service.descriptor.reference == artifact.reference
    finally:
        service.stop()


def test_ensure_replaces_an_old_incompatible_synthetic_artifact(tmp_path) -> None:
    path = tmp_path / "synthetic.json"
    incompatible = build_synthetic_calibration_artifact().model_copy(update={"reference": "old-synthetic-reference"})
    # Recompute the content address to make this a valid but incompatible
    # artifact rather than a malformed-file test.
    incompatible = incompatible.model_copy(
        update={"calibration_id": hashlib.sha256(incompatible.content_payload()).hexdigest()}
    )
    incompatible.save(path)

    refreshed = ensure_synthetic_calibration_artifact(path)
    assert refreshed.reference == "synthetic-common-reference"
    assert refreshed.calibration_id != incompatible.calibration_id
