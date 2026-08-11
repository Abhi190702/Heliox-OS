from __future__ import annotations

from pilot.neural.decoder import SSVEPCalibrationArtifact
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
