"""Least-privileged neural sidecar runtime: acquire, inspect, decode, sign."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Protocol
from uuid import uuid4

from pilot.neural.acquisition import (
    BoundedNeuralBuffer,
    NeuralAcquisitionError,
    NeuralBufferHealth,
    NeuralSampleWindow,
    NeuralSource,
)
from pilot.neural.decoder import DecodedNeuralCandidate, SSVEPDecoder
from pilot.neural.gate import NeuralIntentSigner
from pilot.neural.protocol import (
    NeuralIntentV1,
    NeuralScope,
    NeuralStimulusMarkerV1,
    NeuralStreamDescriptorV1,
    SignalQuality,
)
from pilot.neural.quality import NeuralSignalQualityAnalyzer, SignalQualitySummary


@dataclass(frozen=True, slots=True)
class NeuralObservation:
    quality: SignalQualitySummary
    candidate: DecodedNeuralCandidate | None
    intent: NeuralIntentV1 | None
    abstention_reason: str | None


class NeuralWindowRecorder(Protocol):
    def append(self, window: NeuralSampleWindow) -> None: ...

    def append_marker(self, marker: NeuralStimulusMarkerV1) -> None: ...


class NeuralDecoderService:
    """Keep raw windows local and return only bounded derived observations."""

    def __init__(
        self,
        *,
        source: NeuralSource,
        decoder: SSVEPDecoder,
        signer: NeuralIntentSigner,
        window_seconds: float = 2.0,
        step_seconds: float = 0.5,
        validity_seconds: float = 3.0,
        minimum_decoder_posterior_permille: int = 500,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        recorder: NeuralWindowRecorder | None = None,
        recorder_factory: Callable[[NeuralStreamDescriptorV1], NeuralWindowRecorder] | None = None,
    ) -> None:
        self._source = source
        self._decoder = decoder
        self._signer = signer
        self._quality = NeuralSignalQualityAnalyzer()
        if window_seconds <= 0 or step_seconds <= 0 or step_seconds > window_seconds:
            raise ValueError("invalid neural window/step duration")
        self._window_seconds = window_seconds
        self._step_seconds = step_seconds
        self._window_samples = 0
        self._step_samples = 0
        self._validity_ns = round(validity_seconds * 1_000_000_000)
        if self._validity_ns <= 0:
            raise ValueError("intent validity must be positive")
        if not 0 <= minimum_decoder_posterior_permille <= 1000:
            raise ValueError("decoder posterior threshold must be permille")
        self._minimum_posterior = minimum_decoder_posterior_permille
        self._monotonic_ns = monotonic_ns
        self._recorder = recorder
        self._recorder_factory = recorder_factory
        if recorder is not None and recorder_factory is not None:
            raise ValueError("provide a neural recorder or recorder factory, not both")
        self._buffer: BoundedNeuralBuffer | None = None
        self._sequence = 0
        self._last_target: str | None = None
        self._dwell = 0
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._source.start()
        try:
            descriptor = self._source.descriptor
            if self._recorder_factory is not None:
                self._recorder = self._recorder_factory(descriptor)
            if descriptor.sample_rate_hz != self._decoder.artifact.sample_rate_hz:
                raise ValueError("source sample rate does not match calibration")
            if descriptor.channel_names != self._decoder.artifact.channel_names:
                raise ValueError("source channels do not match calibration")
            if descriptor.reference != self._decoder.artifact.reference:
                raise ValueError("source reference does not match calibration")
            self._window_samples = round(self._window_seconds * descriptor.sample_rate_hz)
            self._step_samples = round(self._step_seconds * descriptor.sample_rate_hz)
            if self._window_samples < 64 or not 1 <= self._step_samples <= self._window_samples:
                raise ValueError("invalid neural window/step duration")
            if self._window_samples != self._decoder.artifact.window_samples:
                raise ValueError("runtime window length does not match calibration")
            self._buffer = BoundedNeuralBuffer(
                channel_count=descriptor.channel_count,
                capacity_samples=max(self._window_samples * 3, descriptor.sample_rate_hz * 10),
            )
            self._sequence = descriptor.sequence_start
            self._running = True
            warmup_deadline = time.monotonic() + 10.0
            while self._buffer.health.buffered_samples < self._window_samples:
                needed = self._window_samples - self._buffer.health.buffered_samples
                try:
                    # Request the complete missing warm-up span. Synthetic and
                    # playback sources can fill it immediately with a window
                    # ending at the current clock; live adapters wait/fail
                    # closed until that many real samples are buffered.
                    self._buffer.append(self._read_source(needed))
                except NeuralAcquisitionError as exc:
                    # A live board may need a short warm-up before its first
                    # complete chunk. Never spin forever or hide other errors.
                    if "not buffered" not in str(exc).casefold():
                        raise
                    if time.monotonic() >= warmup_deadline:
                        raise NeuralAcquisitionError(
                            "neural source did not buffer a complete window within 10 seconds"
                        ) from exc
                    time.sleep(min(self._step_seconds / 4, 0.05))
        except Exception:
            self._source.stop()
            self._running = False
            raise

    def stop(self) -> None:
        self._source.stop()
        self._running = False
        self._buffer = None
        self._last_target = None
        self._dwell = 0

    @property
    def recorder(self) -> NeuralWindowRecorder | None:
        return self._recorder

    def observe_once(
        self,
        *,
        state_revision: int,
        requested_scope: NeuralScope,
    ) -> NeuralObservation:
        if not self._running or self._buffer is None:
            raise RuntimeError("neural decoder service is not running")
        self._buffer.append(self._read_source(self._step_samples))
        window = self._buffer.latest(self._window_samples)
        descriptor = self._source.descriptor
        quality = self._quality.analyze(
            window,
            sample_rate_hz=descriptor.sample_rate_hz,
            channel_names=descriptor.channel_names,
        )
        if quality.quality != SignalQuality.GOOD or quality.artifact_flags:
            self._last_target = None
            self._dwell = 0
            return NeuralObservation(quality, None, None, "signal_quality")

        candidate = self._decoder.decode(window, quality=quality)
        if candidate.posterior_permille < self._minimum_posterior:
            self._last_target = None
            self._dwell = 0
            return NeuralObservation(quality, candidate, None, "decoder_uncertain")
        if candidate.target_id == self._last_target:
            self._dwell = min(self._dwell + 1, 64)
        else:
            self._last_target = candidate.target_id
            self._dwell = 1

        now = self._monotonic_ns()
        unsigned = NeuralIntentV1(
            session_id=descriptor.session_id,
            intent_id=uuid4(),
            sequence=self._sequence,
            window_start_ns=int(window.timestamps_ns[0]),
            window_end_ns=int(window.timestamps_ns[-1]),
            expires_at_ns=max(now, int(window.timestamps_ns[-1])) + self._validity_ns,
            paradigm=self._decoder.artifact.paradigm,
            intent_class=candidate.intent_class,
            command_id=candidate.command_id,
            posterior_permille=candidate.posterior_permille,
            margin_permille=candidate.margin_permille,
            signal_quality=quality.quality,
            artifact_flags=quality.artifact_flags,
            dwell_windows=self._dwell,
            decoder_version=self._decoder.artifact.decoder_version,
            calibration_id=self._decoder.artifact.calibration_id,
            subject_key=self._decoder.artifact.subject_key,
            requested_scope=requested_scope,
            state_revision=state_revision,
            signature="0" * 64,
        )
        self._sequence += 1
        intent = unsigned.model_copy(update={"signature": self._signer.sign(unsigned)})
        return NeuralObservation(quality, candidate, intent, None)

    def record_stimulus_marker(self, marker: NeuralStimulusMarkerV1) -> None:
        if not self._running:
            raise RuntimeError("neural decoder service is not running")
        if marker.session_id != self._source.descriptor.session_id:
            raise ValueError("stimulus marker does not match the acquisition session")
        if self._recorder is not None:
            self._recorder.append_marker(marker)

    @property
    def descriptor(self) -> NeuralStreamDescriptorV1:
        return self._source.descriptor

    @property
    def buffer_health(self) -> NeuralBufferHealth:
        if self._buffer is None:
            raise RuntimeError("neural decoder service is not running")
        return self._buffer.health

    def _read_source(self, sample_count: int) -> NeuralSampleWindow:
        window = self._source.read(sample_count)
        if self._recorder is not None:
            self._recorder.append(window)
        return window
