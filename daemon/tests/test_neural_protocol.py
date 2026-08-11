from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from pilot.neural.protocol import (
    NeuralIntentClass,
    NeuralIntentV1,
    NeuralParadigm,
    NeuralScope,
    NeuralStreamDescriptorV1,
    NeuralTransport,
    SignalQuality,
)


def _descriptor(**updates: object) -> NeuralStreamDescriptorV1:
    values = {
        "session_id": uuid.uuid4(),
        "source_id": "synthetic-1",
        "board_kind": "brainflow-synthetic",
        "transport": NeuralTransport.SYNTHETIC,
        "sample_rate_hz": 250,
        "channel_count": 3,
        "channel_names": ("O1", "Oz", "O2"),
        "reference": "linked-mastoids",
        "sequence_start": 1,
        "started_monotonic_ns": 1_000_000,
    }
    values.update(updates)
    return NeuralStreamDescriptorV1(**values)


def _intent(**updates: object) -> NeuralIntentV1:
    values = {
        "session_id": uuid.uuid4(),
        "intent_id": uuid.uuid4(),
        "sequence": 1,
        "window_start_ns": 1_000_000,
        "window_end_ns": 2_000_000,
        "expires_at_ns": 3_000_000,
        "paradigm": NeuralParadigm.SSVEP,
        "intent_class": NeuralIntentClass.SELECT,
        "posterior_permille": 850,
        "margin_permille": 300,
        "signal_quality": SignalQuality.GOOD,
        "dwell_windows": 3,
        "decoder_version": "a" * 64,
        "calibration_id": "b" * 64,
        "subject_key": "local-subject",
        "requested_scope": NeuralScope.NAVIGATE,
        "state_revision": 2,
        "signature": "0" * 64,
    }
    values.update(updates)
    return NeuralIntentV1(**values)


def test_stream_descriptor_requires_exact_unique_channel_metadata() -> None:
    assert _descriptor().channel_names == ("O1", "Oz", "O2")
    with pytest.raises(ValidationError, match="channel_count"):
        _descriptor(channel_count=2)
    with pytest.raises(ValidationError, match="unique"):
        _descriptor(channel_names=("O1", "o1", "O2"))


def test_contracts_reject_unknown_fields_and_coercion() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        _descriptor(raw_eeg=[[1.0]])
    with pytest.raises(ValidationError):
        _descriptor(sample_rate_hz="250")


def test_intent_requires_safe_goal_identifier_only_for_safe_goal() -> None:
    with pytest.raises(ValidationError, match="require command_id"):
        _intent(intent_class=NeuralIntentClass.SAFE_GOAL, requested_scope=NeuralScope.SAFE_DESKTOP)
    with pytest.raises(ValidationError, match="valid only"):
        _intent(command_id="open-calendar")


def test_intent_accepts_wire_class_alias_and_has_stable_signing_payload() -> None:
    base = _intent().model_dump(mode="json", by_alias=True)
    assert base["class"] == "select"
    reconstructed = NeuralIntentV1.model_validate(base)
    assert reconstructed.model_dump(mode="json", by_alias=True) == base
    assert b'"class":"select"' in reconstructed.signing_payload()
    assert b"signature" not in reconstructed.signing_payload()


def test_wire_contract_accepts_json_shapes_but_rejects_numeric_coercion() -> None:
    base = _descriptor().model_dump(mode="json")
    assert NeuralStreamDescriptorV1.model_validate(base).channel_names == ("O1", "Oz", "O2")
    base["sample_rate_hz"] = "250"
    with pytest.raises(ValidationError):
        NeuralStreamDescriptorV1.model_validate(base)


def test_intent_rejects_invalid_temporal_and_confidence_relationships() -> None:
    with pytest.raises(ValidationError, match="window_end_ns"):
        _intent(window_start_ns=5, window_end_ns=4, expires_at_ns=6)
    with pytest.raises(ValidationError, match="margin_permille"):
        _intent(posterior_permille=200, margin_permille=300)
