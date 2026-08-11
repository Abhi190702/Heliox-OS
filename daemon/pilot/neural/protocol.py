"""Strict, versioned contracts at the neural acquisition boundary."""

from __future__ import annotations

import json
import math
from enum import StrEnum
from typing import Annotated, Self
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, StringConstraints, model_validator

Identifier = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._:-]{1,128}$")]
ArtifactHash = Annotated[str, StringConstraints(pattern=r"^[A-Fa-f0-9]{8,128}$")]
SignatureHex = Annotated[str, StringConstraints(pattern=r"^[A-Fa-f0-9]{64}$")]
SchemaVersion = Annotated[int, Field(strict=True, ge=1, le=1)]
SequenceNumber = Annotated[int, Field(strict=True, ge=0)]
MonotonicTimestamp = Annotated[int, Field(strict=True, gt=0)]
Permille = Annotated[int, Field(strict=True, ge=0, le=1000)]


class NeuralTransport(StrEnum):
    BRAINFLOW = "brainflow"
    LSL = "lsl"
    PLAYBACK = "playback"
    SYNTHETIC = "synthetic"


class NeuralParadigm(StrEnum):
    SSVEP = "ssvep"
    P300 = "p300"
    MOTOR_IMAGERY = "motor_imagery"
    EOG = "eog"
    EMG = "emg"
    SYNTHETIC = "synthetic"


class NeuralIntentClass(StrEnum):
    CANCEL = "cancel"
    FOCUS_LEFT = "focus_left"
    FOCUS_RIGHT = "focus_right"
    SELECT = "select"
    SAFE_GOAL = "safe_goal"


class NeuralScope(StrEnum):
    OBSERVE = "observe"
    NAVIGATE = "navigate"
    SAFE_DESKTOP = "safe_desktop"
    PHYSICAL_GOAL = "physical_goal"


class SignalQuality(StrEnum):
    GOOD = "good"
    DEGRADED = "degraded"
    REJECT = "reject"


class ArtifactFlag(StrEnum):
    BLINK = "blink"
    MUSCLE = "muscle"
    SATURATION = "saturation"
    CONTACT = "contact"
    MOTION = "motion"
    LINE_NOISE = "line_noise"
    FLAT_CHANNEL = "flat_channel"
    PACKET_LOSS = "packet_loss"
    CLOCK = "clock"


class NeuralStreamDescriptorV1(BaseModel):
    """Metadata for one bounded acquisition session, never sample payloads."""

    # UUIDs, enums, and tuples must parse from their JSON string/list forms.
    # Numeric fields remain explicitly strict so values such as "250" cannot
    # silently cross this authority boundary.
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: SchemaVersion = 1
    session_id: UUID
    source_id: Identifier
    board_kind: Identifier
    transport: NeuralTransport
    sample_rate_hz: Annotated[int, Field(strict=True, ge=1, le=4096)]
    channel_count: Annotated[int, Field(strict=True, ge=1, le=64)]
    channel_names: tuple[Identifier, ...] = Field(min_length=1, max_length=64)
    units: str = Field(default="microvolts", pattern=r"^microvolts$")
    reference: str = Field(min_length=1, max_length=256)
    calibration_id: ArtifactHash | None = None
    sequence_start: SequenceNumber
    started_monotonic_ns: MonotonicTimestamp

    @model_validator(mode="after")
    def validate_channels(self) -> Self:
        if len(self.channel_names) != self.channel_count:
            raise ValueError("channel_count must equal the number of channel_names")
        normalized = [name.casefold() for name in self.channel_names]
        if len(set(normalized)) != len(normalized):
            raise ValueError("channel_names must be unique")
        return self


class NeuralIntentV1(BaseModel):
    """One signed, expiring, decoder-derived intent candidate.

    ``command_id`` refers only to a goal compiled into the local allow-list.
    It is never shell text or a natural-language instruction supplied by the
    gateway.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    schema_version: SchemaVersion = 1
    session_id: UUID
    intent_id: UUID
    sequence: SequenceNumber
    window_start_ns: MonotonicTimestamp
    window_end_ns: MonotonicTimestamp
    expires_at_ns: MonotonicTimestamp
    paradigm: NeuralParadigm
    intent_class: NeuralIntentClass = Field(
        validation_alias=AliasChoices("intent_class", "class"),
        serialization_alias="class",
    )
    command_id: Identifier | None = None
    posterior_permille: Permille
    margin_permille: Permille
    signal_quality: SignalQuality
    artifact_flags: tuple[ArtifactFlag, ...] = Field(default=(), max_length=16)
    dwell_windows: Annotated[int, Field(strict=True, ge=1, le=64)]
    decoder_version: ArtifactHash
    calibration_id: ArtifactHash
    subject_key: Identifier
    requested_scope: NeuralScope
    state_revision: SequenceNumber
    signature: SignatureHex

    @model_validator(mode="after")
    def validate_semantics(self) -> Self:
        if self.window_end_ns < self.window_start_ns:
            raise ValueError("window_end_ns must not precede window_start_ns")
        if self.expires_at_ns < self.window_end_ns:
            raise ValueError("expires_at_ns must not precede the evidence window")
        if self.margin_permille > self.posterior_permille:
            raise ValueError("margin_permille cannot exceed posterior_permille")
        if len(set(self.artifact_flags)) != len(self.artifact_flags):
            raise ValueError("artifact_flags must not contain duplicates")
        if self.intent_class == NeuralIntentClass.SAFE_GOAL and not self.command_id:
            raise ValueError("safe_goal intents require command_id")
        if self.intent_class != NeuralIntentClass.SAFE_GOAL and self.command_id is not None:
            raise ValueError("command_id is valid only for safe_goal intents")
        return self

    def signing_payload(self) -> bytes:
        """Return a stable JSON representation excluding the signature."""

        data = self.model_dump(mode="json", by_alias=True, exclude={"signature"})
        if not all(math.isfinite(value) for value in (self.posterior_permille, self.margin_permille)):
            raise ValueError("non-finite confidence values are forbidden")
        return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
