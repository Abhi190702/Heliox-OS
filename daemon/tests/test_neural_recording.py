from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from pilot.neural.acquisition import NeuralSampleWindow, SyntheticNeuralSource
from pilot.neural.protocol import NeuralStimulusEvent, NeuralStimulusMarkerV1
from pilot.neural.recording import (
    EncryptedNeuralRecorder,
    NeuralRecordingConsentV1,
    NeuralRecordingError,
    prune_expired_neural_recordings,
)


def _consent(source, *, export: bool = True) -> NeuralRecordingConsentV1:
    now = datetime.now(UTC)
    return NeuralRecordingConsentV1(
        session_id=source.descriptor.session_id,
        subject_key="local-subject",
        purpose="local accessibility calibration",
        granted_at=now,
        expires_at=now + timedelta(days=1),
        retention_days=1,
        allow_bids_export=export,
        authorized=True,
    )


def test_encrypted_recording_contains_no_plain_samples_and_exports_brainvision(tmp_path) -> None:
    source = SyntheticNeuralSource(seed=3)
    source.start()
    window = source.read(50)
    recorder = EncryptedNeuralRecorder(
        destination=tmp_path / "session.neeg",
        descriptor=source.descriptor,
        consent=_consent(source),
        key=b"k" * 32,
    )
    recorder.append(window)
    recorder.append_marker(
        NeuralStimulusMarkerV1(
            session_id=source.descriptor.session_id,
            sequence=0,
            target_id="select",
            event=NeuralStimulusEvent.TARGET_ON,
            received_monotonic_ns=time.monotonic_ns(),
            client_performance_ms=10.0,
        )
    )
    text = recorder.destination.read_text(encoding="utf-8")
    assert "samples_uv" not in text and "timestamps_ns" not in text
    assert "select" not in text and "target_on" not in text
    assert json.loads(text.splitlines()[1])["ciphertext"]

    exported = recorder.export_bids_brainvision(tmp_path / "bids")
    eeg_dir = exported / "sub-localsubject" / "eeg"
    assert (exported / "dataset_description.json").is_file()
    assert (eeg_dir / "sub-localsubject_task-heliox_eeg.vhdr").is_file()
    assert (eeg_dir / "sub-localsubject_task-heliox_eeg.eeg").stat().st_size == 50 * 3 * 4
    assert "select" in (eeg_dir / "sub-localsubject_task-heliox_eeg_events.tsv").read_text(encoding="utf-8")
    assert "select:target_on" in (eeg_dir / "sub-localsubject_task-heliox_eeg.vmrk").read_text(encoding="utf-8")
    reopened = EncryptedNeuralRecorder.open_existing(recorder.destination, key=b"k" * 32)
    assert reopened.export_bids_brainvision(tmp_path / "bids-reopened").is_dir()


def test_recording_fails_closed_without_consent_or_on_tamper(tmp_path) -> None:
    source = SyntheticNeuralSource(seed=4)
    source.start()
    now = datetime.now(UTC)
    with pytest.raises(ValueError, match="explicit authorization"):
        NeuralRecordingConsentV1(
            session_id=source.descriptor.session_id,
            subject_key="local-subject",
            purpose="local research recording",
            granted_at=now,
            expires_at=now + timedelta(hours=1),
            retention_days=1,
            authorized=False,
        )

    recorder = EncryptedNeuralRecorder(
        destination=tmp_path / "tampered.neeg",
        descriptor=source.descriptor,
        consent=_consent(source),
        key=b"q" * 32,
    )
    recorder.append(source.read(20))
    lines = recorder.destination.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[1])
    record["ciphertext"] = record["ciphertext"][:-2] + "AA"
    recorder.destination.write_text(lines[0] + "\n" + json.dumps(record) + "\n", encoding="utf-8")
    with pytest.raises(NeuralRecordingError, match="authentication"):
        recorder.export_bids_brainvision(tmp_path / "bad-export")


def test_recording_rejects_replay_and_export_without_separate_consent(tmp_path) -> None:
    source = SyntheticNeuralSource(seed=5)
    source.start()
    recorder = EncryptedNeuralRecorder(
        destination=tmp_path / "no-export.neeg",
        descriptor=source.descriptor,
        consent=_consent(source, export=False),
        key=b"z" * 32,
    )
    window = source.read(10)
    recorder.append(window)
    with pytest.raises(NeuralRecordingError, match="replayed"):
        recorder.append(NeuralSampleWindow(window.samples_uv, window.timestamps_ns, window.sequence_start))
    with pytest.raises(NeuralRecordingError, match="not included"):
        recorder.export_bids_brainvision(tmp_path / "bids")


def test_recording_export_never_overwrites_an_existing_destination(tmp_path) -> None:
    source = SyntheticNeuralSource(seed=6)
    source.start()
    recorder = EncryptedNeuralRecorder(
        destination=tmp_path / "export.neeg",
        descriptor=source.descriptor,
        consent=_consent(source),
        key=b"e" * 32,
    )
    recorder.append(source.read(10))
    destination = tmp_path / "existing-bids"
    destination.mkdir()
    with pytest.raises(NeuralRecordingError, match="never overwrites"):
        recorder.export_bids_brainvision(destination)


def test_expired_recordings_are_pruned_but_active_and_invalid_files_remain(tmp_path) -> None:
    source = SyntheticNeuralSource(seed=7)
    source.start()
    now = datetime.now(UTC)
    active = EncryptedNeuralRecorder(
        destination=tmp_path / "active.neeg",
        descriptor=source.descriptor,
        consent=_consent(source),
        key=b"a" * 32,
    )
    expired_path = tmp_path / "expired.neeg"
    expired = EncryptedNeuralRecorder(
        destination=expired_path,
        descriptor=source.descriptor,
        consent=_consent(source),
        key=b"x" * 32,
    )
    header = json.loads(expired.destination.read_text(encoding="utf-8").splitlines()[0])
    header["consent"]["granted_at"] = (now - timedelta(days=2)).isoformat()
    header["consent"]["expires_at"] = (now - timedelta(days=1)).isoformat()
    header["consent"]["retention_days"] = 2
    expired_path.write_text(json.dumps(header) + "\n", encoding="utf-8")
    invalid = tmp_path / "invalid.neeg"
    invalid.write_text("not-json\n", encoding="utf-8")

    removed = prune_expired_neural_recordings(tmp_path, now=now)
    assert removed == (expired_path.resolve(),)
    assert not expired_path.exists()
    assert active.destination.exists()
    assert invalid.exists()
