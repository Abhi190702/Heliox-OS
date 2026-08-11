"""Bounded neural acquisition adapters for the isolated ``neurod`` sidecar.

This module is deliberately absent from Heliox's planner and action packages.
It owns high-rate samples and exposes only bounded windows to the decoder; the
rest of the application receives signed :class:`NeuralIntentV1` envelopes.
"""

from __future__ import annotations

import importlib
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from uuid import UUID, uuid4

import numpy as np
from numpy.typing import NDArray

from pilot.neural.protocol import NeuralStreamDescriptorV1, NeuralTransport

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]


class NeuralAcquisitionError(RuntimeError):
    """A source failed validation or could not produce a trustworthy window."""


@dataclass(frozen=True, slots=True)
class NeuralSampleWindow:
    """One immutable channel-by-sample block inside the sidecar boundary."""

    samples_uv: FloatArray
    timestamps_ns: IntArray
    sequence_start: int
    dropped_before: int = 0

    def __post_init__(self) -> None:
        samples = np.asarray(self.samples_uv, dtype=np.float64)
        timestamps = np.asarray(self.timestamps_ns, dtype=np.int64)
        if samples.ndim != 2 or samples.shape[0] < 1 or samples.shape[1] < 1:
            raise NeuralAcquisitionError("samples must have shape channels x samples")
        if timestamps.ndim != 1 or timestamps.shape[0] != samples.shape[1]:
            raise NeuralAcquisitionError("one timestamp is required for every sample")
        if not np.isfinite(samples).all():
            raise NeuralAcquisitionError("NaN and infinity are forbidden in neural samples")
        if timestamps[0] <= 0 or np.any(np.diff(timestamps) <= 0):
            raise NeuralAcquisitionError("sample timestamps must be positive and strictly increasing")
        if self.sequence_start < 0 or self.dropped_before < 0:
            raise NeuralAcquisitionError("sequence and drop counters cannot be negative")
        samples = np.array(samples, copy=True)
        timestamps = np.array(timestamps, copy=True)
        samples.setflags(write=False)
        timestamps.setflags(write=False)
        object.__setattr__(self, "samples_uv", samples)
        object.__setattr__(self, "timestamps_ns", timestamps)

    @property
    def sample_count(self) -> int:
        return int(self.samples_uv.shape[1])

    @property
    def channel_count(self) -> int:
        return int(self.samples_uv.shape[0])

    @property
    def sequence_end(self) -> int:
        return self.sequence_start + self.sample_count - 1


@dataclass(frozen=True, slots=True)
class NeuralBufferHealth:
    capacity_samples: int
    buffered_samples: int
    dropped_samples: int
    appended_windows: int
    last_sequence: int


class BoundedNeuralBuffer:
    """A whole-window ring with explicit overflow and sequence accounting."""

    def __init__(self, *, channel_count: int, capacity_samples: int) -> None:
        if not 1 <= channel_count <= 64:
            raise ValueError("channel_count must be between 1 and 64")
        if capacity_samples < 2:
            raise ValueError("capacity_samples must be at least 2")
        self._channel_count = channel_count
        self._capacity = capacity_samples
        self._windows: deque[NeuralSampleWindow] = deque()
        self._buffered = 0
        self._dropped = 0
        self._appended = 0
        self._last_sequence = -1
        self._last_timestamp = 0

    def append(self, window: NeuralSampleWindow) -> None:
        if window.channel_count != self._channel_count:
            raise NeuralAcquisitionError("window channel count changed during a session")
        expected = self._last_sequence + 1
        if self._last_sequence >= 0 and window.sequence_start < expected:
            raise NeuralAcquisitionError("sample sequence was replayed or reordered")
        if self._last_sequence >= 0 and window.sequence_start > expected:
            gap = window.sequence_start - expected
            self._dropped += gap
            window = NeuralSampleWindow(
                samples_uv=window.samples_uv,
                timestamps_ns=window.timestamps_ns,
                sequence_start=window.sequence_start,
                dropped_before=window.dropped_before + gap,
            )
        if self._last_timestamp and window.timestamps_ns[0] <= self._last_timestamp:
            raise NeuralAcquisitionError("sample clock rolled back")

        if window.sample_count > self._capacity:
            removed = window.sample_count - self._capacity
            window = NeuralSampleWindow(
                samples_uv=window.samples_uv[:, removed:],
                timestamps_ns=window.timestamps_ns[removed:],
                sequence_start=window.sequence_start + removed,
                dropped_before=window.dropped_before + removed,
            )
            self._dropped += removed

        while self._windows and self._buffered + window.sample_count > self._capacity:
            expired = self._windows.popleft()
            self._buffered -= expired.sample_count
            self._dropped += expired.sample_count

        self._windows.append(window)
        self._buffered += window.sample_count
        self._appended += 1
        self._last_sequence = window.sequence_end
        self._last_timestamp = int(window.timestamps_ns[-1])

    def latest(self, sample_count: int) -> NeuralSampleWindow:
        if sample_count < 1:
            raise ValueError("sample_count must be positive")
        if self._buffered < sample_count:
            raise NeuralAcquisitionError(f"only {self._buffered} samples are buffered; {sample_count} required")
        remaining = sample_count
        sample_parts: list[FloatArray] = []
        timestamp_parts: list[IntArray] = []
        selected_windows: list[NeuralSampleWindow] = []
        sequence_start = 0
        for window in reversed(self._windows):
            take = min(remaining, window.sample_count)
            start = window.sample_count - take
            sample_parts.append(window.samples_uv[:, start:])
            timestamp_parts.append(window.timestamps_ns[start:])
            selected_windows.append(window)
            sequence_start = window.sequence_start + start
            remaining -= take
            if remaining == 0:
                break
        return NeuralSampleWindow(
            samples_uv=np.concatenate(list(reversed(sample_parts)), axis=1),
            timestamps_ns=np.concatenate(list(reversed(timestamp_parts))),
            sequence_start=sequence_start,
            dropped_before=sum(window.dropped_before for window in selected_windows),
        )

    @property
    def health(self) -> NeuralBufferHealth:
        return NeuralBufferHealth(
            capacity_samples=self._capacity,
            buffered_samples=self._buffered,
            dropped_samples=self._dropped,
            appended_windows=self._appended,
            last_sequence=self._last_sequence,
        )


@runtime_checkable
class NeuralSource(Protocol):
    """Driver surface implemented by synthetic, playback, BrainFlow, and LSL."""

    @property
    def descriptor(self) -> NeuralStreamDescriptorV1: ...

    def start(self) -> None: ...

    def read(self, sample_count: int) -> NeuralSampleWindow: ...

    def stop(self) -> None: ...


@dataclass(frozen=True, slots=True)
class NeuralFaultPlan:
    """Deterministic source faults for crash, race, and recovery tests."""

    every_nth_read: int
    mode: str
    drop_samples: int = 1
    stale_by_ns: int = 10_000_000_000
    saturation_uv: float = 1_000.0

    def __post_init__(self) -> None:
        if self.every_nth_read < 1:
            raise ValueError("fault cadence must be positive")
        if self.mode not in {"crash", "drop", "stale", "saturate", "replay"}:
            raise ValueError("unsupported neural fault mode")
        if self.drop_samples < 1 or self.stale_by_ns < 1 or self.saturation_uv < 1:
            raise ValueError("fault parameters must be positive")


class FaultInjectingNeuralSource:
    """Wrap a source with registered, reproducible faults; never use in live mode."""

    def __init__(self, source: NeuralSource, plan: NeuralFaultPlan) -> None:
        self._source = source
        self._plan = plan
        self._read_count = 0
        self._previous: NeuralSampleWindow | None = None

    @property
    def descriptor(self) -> NeuralStreamDescriptorV1:
        return self._source.descriptor

    def start(self) -> None:
        self._read_count = 0
        self._previous = None
        self._source.start()

    def read(self, sample_count: int) -> NeuralSampleWindow:
        self._read_count += 1
        window = self._source.read(sample_count)
        if self._read_count % self._plan.every_nth_read:
            self._previous = window
            return window
        if self._plan.mode == "crash":
            raise NeuralAcquisitionError("injected neural source crash")
        if self._plan.mode == "replay" and self._previous is not None:
            return self._previous
        if self._plan.mode == "drop":
            dropped = min(self._plan.drop_samples, window.sample_count - 1)
            return NeuralSampleWindow(
                window.samples_uv[:, dropped:],
                window.timestamps_ns[dropped:],
                window.sequence_start + dropped,
                window.dropped_before + dropped,
            )
        if self._plan.mode == "stale":
            timestamps = window.timestamps_ns - self._plan.stale_by_ns
            if timestamps[0] <= 0:
                raise NeuralAcquisitionError("injected stale timestamp left the monotonic domain")
            return NeuralSampleWindow(
                window.samples_uv,
                timestamps,
                window.sequence_start,
                window.dropped_before,
            )
        if self._plan.mode == "saturate":
            samples = np.array(window.samples_uv, copy=True)
            samples[0, :] = self._plan.saturation_uv
            return NeuralSampleWindow(
                samples,
                window.timestamps_ns,
                window.sequence_start,
                window.dropped_before,
            )
        self._previous = window
        return window

    def stop(self) -> None:
        self._source.stop()


class SyntheticNeuralSource:
    """Deterministic SSVEP-like fixture for CI, soak, and fault injection."""

    def __init__(
        self,
        *,
        sample_rate_hz: int = 250,
        channel_names: tuple[str, ...] = ("O1", "Oz", "O2"),
        target_hz: float | None = None,
        noise_uv: float = 1.5,
        amplitude_uv: float = 12.0,
        seed: int = 0,
        session_id: UUID | None = None,
    ) -> None:
        if not 1 <= sample_rate_hz <= 4096:
            raise ValueError("sample_rate_hz is out of range")
        if target_hz is not None and not 1.0 <= target_hz < sample_rate_hz / 2:
            raise ValueError("target_hz must be below Nyquist")
        if noise_uv < 0 or amplitude_uv < 0:
            raise ValueError("synthetic amplitudes cannot be negative")
        self._sample_rate = sample_rate_hz
        self._channels = channel_names
        self._target_hz = target_hz
        self._noise_uv = noise_uv
        self._amplitude_uv = amplitude_uv
        self._rng = np.random.default_rng(seed)
        self._sequence = 0
        self._started_ns = 0
        self._running = False
        self._descriptor = NeuralStreamDescriptorV1(
            session_id=session_id or uuid4(),
            source_id=f"synthetic-{seed}",
            board_kind="brainflow-synthetic",
            transport=NeuralTransport.SYNTHETIC,
            sample_rate_hz=sample_rate_hz,
            channel_count=len(channel_names),
            channel_names=channel_names,
            reference="synthetic-common-reference",
            sequence_start=0,
            started_monotonic_ns=time.monotonic_ns(),
        )

    @property
    def descriptor(self) -> NeuralStreamDescriptorV1:
        return self._descriptor

    def set_target(self, target_hz: float | None) -> None:
        if target_hz is not None and not 1.0 <= target_hz < self._sample_rate / 2:
            raise ValueError("target_hz must be below Nyquist")
        self._target_hz = target_hz

    def start(self) -> None:
        self._sequence = 0
        self._started_ns = time.monotonic_ns()
        self._running = True

    def read(self, sample_count: int) -> NeuralSampleWindow:
        if not self._running:
            raise NeuralAcquisitionError("synthetic source is not running")
        if not 1 <= sample_count <= self._sample_rate * 30:
            raise NeuralAcquisitionError("synthetic read must be between one sample and 30 seconds")
        indexes = np.arange(self._sequence, self._sequence + sample_count, dtype=np.float64)
        seconds = indexes / self._sample_rate
        samples = self._rng.normal(0.0, self._noise_uv, size=(len(self._channels), sample_count))
        if self._target_hz is not None:
            phases = np.linspace(0.0, np.pi / 3, len(self._channels), endpoint=True)
            samples += np.stack(
                [self._amplitude_uv * np.sin(2 * np.pi * self._target_hz * seconds + phase) for phase in phases]
            )
        interval_ns = 1_000_000_000 / self._sample_rate
        timestamps = self._started_ns + np.rint(indexes * interval_ns).astype(np.int64)
        window = NeuralSampleWindow(samples, timestamps, self._sequence)
        self._sequence += sample_count
        return window

    def stop(self) -> None:
        self._running = False


class PlaybackNeuralSource:
    """Deterministic local replay from a non-pickle NPZ or in-memory fixture."""

    _MAX_FILE_BYTES = 512 * 1024 * 1024

    def __init__(
        self,
        samples_uv: FloatArray,
        *,
        sample_rate_hz: int,
        channel_names: tuple[str, ...],
        reference: str,
        timestamps_ns: IntArray | None = None,
        source_id: str = "local-playback",
        session_id: UUID | None = None,
    ) -> None:
        samples = np.asarray(samples_uv, dtype=np.float64)
        if samples.ndim != 2 or samples.shape[0] != len(channel_names) or samples.shape[1] < 2:
            raise NeuralAcquisitionError("playback samples must match channel metadata")
        if not np.isfinite(samples).all():
            raise NeuralAcquisitionError("playback contains NaN or infinity")
        if timestamps_ns is None:
            interval = 1_000_000_000 / sample_rate_hz
            timestamps = np.rint(np.arange(samples.shape[1]) * interval).astype(np.int64) + 1
        else:
            timestamps = np.asarray(timestamps_ns, dtype=np.int64)
        # Reuse the window validator before retaining the immutable arrays.
        checked = NeuralSampleWindow(samples, timestamps, 0)
        self._samples = checked.samples_uv
        self._timestamps = checked.timestamps_ns
        self._cursor = 0
        self._timestamp_offset = 0
        self._running = False
        self._descriptor = NeuralStreamDescriptorV1(
            session_id=session_id or uuid4(),
            source_id=source_id,
            board_kind="local-npz-playback",
            transport=NeuralTransport.PLAYBACK,
            sample_rate_hz=sample_rate_hz,
            channel_count=len(channel_names),
            channel_names=channel_names,
            reference=reference,
            sequence_start=0,
            started_monotonic_ns=time.monotonic_ns(),
        )

    @classmethod
    def from_npz(cls, path: Path) -> PlaybackNeuralSource:
        resolved = path.expanduser().resolve()
        if resolved.suffix.casefold() != ".npz":
            raise NeuralAcquisitionError("playback must use a .npz container")
        if not resolved.is_file() or resolved.stat().st_size > cls._MAX_FILE_BYTES:
            raise NeuralAcquisitionError("playback file is missing or exceeds 512 MiB")
        try:
            with np.load(resolved, allow_pickle=False) as archive:
                required = {"samples_uv", "sample_rate_hz", "channel_names", "reference"}
                if not required.issubset(archive.files):
                    raise NeuralAcquisitionError("playback metadata is incomplete")
                names = tuple(str(value) for value in archive["channel_names"].tolist())
                reference_value = archive["reference"].tolist()
                reference = str(reference_value)
                timestamps = archive.get("timestamps_ns", None)
                return cls(
                    archive["samples_uv"],
                    sample_rate_hz=int(archive["sample_rate_hz"].item()),
                    channel_names=names,
                    reference=reference,
                    timestamps_ns=timestamps,
                    source_id=f"playback-{resolved.stem}",
                )
        except NeuralAcquisitionError:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise NeuralAcquisitionError(f"invalid playback file: {exc}") from exc

    @property
    def descriptor(self) -> NeuralStreamDescriptorV1:
        return self._descriptor

    def start(self) -> None:
        self._cursor = 0
        self._timestamp_offset = time.monotonic_ns() - int(self._timestamps[0])
        self._running = True

    def read(self, sample_count: int) -> NeuralSampleWindow:
        if not self._running:
            raise NeuralAcquisitionError("playback source is not running")
        if sample_count < 1:
            raise ValueError("sample_count must be positive")
        end = self._cursor + sample_count
        if end > self._samples.shape[1]:
            raise EOFError("playback is exhausted")
        window = NeuralSampleWindow(
            self._samples[:, self._cursor : end],
            self._timestamps[self._cursor : end] + self._timestamp_offset,
            self._cursor,
        )
        self._cursor = end
        return window

    def stop(self) -> None:
        self._running = False


class BrainFlowNeuralSource:
    """Optional BrainFlow board adapter loaded only inside ``neurod``."""

    _PARAMETER_FIELDS = {
        "serial_port",
        "mac_address",
        "ip_address",
        "ip_port",
        "timeout",
        "serial_number",
        "file",
        "master_board",
        "ip_protocol",
        "other_info",
    }

    def __init__(
        self,
        *,
        board_id: int,
        channel_names: tuple[str, ...],
        reference: str,
        input_parameters: dict[str, str | int] | None = None,
        source_id: str | None = None,
        session_id: UUID | None = None,
    ) -> None:
        unknown = set(input_parameters or {}) - self._PARAMETER_FIELDS
        if unknown:
            raise ValueError(f"unknown BrainFlow parameters: {sorted(unknown)}")
        self._board_id = int(board_id)
        self._channel_names = channel_names
        self._reference = reference
        self._parameters = dict(input_parameters or {})
        self._source_id = source_id or f"brainflow-board-{board_id}"
        self._session_id = session_id or uuid4()
        self._board: Any = None
        self._eeg_channels: list[int] = []
        self._sample_rate = 0
        self._sequence = 0
        self._last_timestamp_ns = 0
        self._descriptor: NeuralStreamDescriptorV1 | None = None

    @property
    def descriptor(self) -> NeuralStreamDescriptorV1:
        if self._descriptor is None:
            raise NeuralAcquisitionError("BrainFlow source has not started")
        return self._descriptor

    def start(self) -> None:
        if self._board is not None:
            raise NeuralAcquisitionError("BrainFlow source is already running")
        try:
            module = importlib.import_module("brainflow.board_shim")
        except ImportError as exc:
            raise NeuralAcquisitionError("BrainFlow is not installed; install pilot-daemon[neural]") from exc
        params = module.BrainFlowInputParams()
        for name, value in self._parameters.items():
            setattr(params, name, value)
        board = module.BoardShim(self._board_id, params)
        try:
            eeg_channels = list(module.BoardShim.get_eeg_channels(self._board_id))
            sample_rate = int(module.BoardShim.get_sampling_rate(self._board_id))
            if len(eeg_channels) != len(self._channel_names):
                raise NeuralAcquisitionError("configured channel names do not match BrainFlow EEG channels")
            board.prepare_session()
            board.start_stream(sample_rate * 30)
        except Exception:
            try:
                if board.is_prepared():
                    board.release_session()
            finally:
                raise
        self._board = board
        self._eeg_channels = eeg_channels
        self._sample_rate = sample_rate
        self._sequence = 0
        self._last_timestamp_ns = 0
        self._descriptor = NeuralStreamDescriptorV1(
            session_id=self._session_id,
            source_id=self._source_id,
            board_kind=f"brainflow-{self._board_id}",
            transport=NeuralTransport.BRAINFLOW,
            sample_rate_hz=sample_rate,
            channel_count=len(eeg_channels),
            channel_names=self._channel_names,
            reference=self._reference,
            sequence_start=0,
            started_monotonic_ns=time.monotonic_ns(),
        )

    def read(self, sample_count: int) -> NeuralSampleWindow:
        if self._board is None:
            raise NeuralAcquisitionError("BrainFlow source is not running")
        if not 1 <= sample_count <= self._sample_rate * 30:
            raise NeuralAcquisitionError("BrainFlow read exceeds the bounded window")
        if int(self._board.get_board_data_count()) < sample_count:
            raise NeuralAcquisitionError("BrainFlow has not buffered the requested samples")
        # Consume samples so a fast caller cannot decode the same board tail twice.
        data = np.asarray(self._board.get_board_data(sample_count), dtype=np.float64)
        if data.ndim != 2 or data.shape[1] < sample_count:
            raise NeuralAcquisitionError("BrainFlow has not buffered the requested samples")
        samples = data[self._eeg_channels, -sample_count:]
        interval_ns = 1_000_000_000 / self._sample_rate
        minimum_end = self._last_timestamp_ns + round(sample_count * interval_ns)
        end_ns = max(time.monotonic_ns(), minimum_end)
        timestamps = end_ns - np.rint(np.arange(sample_count - 1, -1, -1) * interval_ns).astype(np.int64)
        window = NeuralSampleWindow(samples, timestamps, self._sequence)
        self._sequence += sample_count
        self._last_timestamp_ns = int(timestamps[-1])
        return window

    def stop(self) -> None:
        board, self._board = self._board, None
        if board is None:
            return
        try:
            board.stop_stream()
        finally:
            board.release_session()


class LSLNeuralSource:
    """Optional local LSL inlet with a bounded pull size and monotonic rebasing."""

    def __init__(
        self,
        *,
        stream_name: str,
        channel_names: tuple[str, ...],
        sample_rate_hz: int,
        reference: str,
        source_id: str | None = None,
        resolve_timeout_seconds: float = 3.0,
        session_id: UUID | None = None,
    ) -> None:
        self._stream_name = stream_name
        self._channel_names = channel_names
        self._sample_rate = sample_rate_hz
        self._reference = reference
        self._source_id = source_id or f"lsl-{stream_name}"
        self._resolve_timeout = resolve_timeout_seconds
        self._session_id = session_id or uuid4()
        self._inlet: Any = None
        self._sequence = 0
        self._lsl_anchor = 0.0
        self._monotonic_anchor = 0
        self._descriptor: NeuralStreamDescriptorV1 | None = None

    @property
    def descriptor(self) -> NeuralStreamDescriptorV1:
        if self._descriptor is None:
            raise NeuralAcquisitionError("LSL source has not started")
        return self._descriptor

    def start(self) -> None:
        try:
            pylsl = importlib.import_module("pylsl")
        except ImportError as exc:
            raise NeuralAcquisitionError("pylsl is not installed") from exc
        streams = pylsl.resolve_byprop("name", self._stream_name, minimum=1, timeout=self._resolve_timeout)
        if len(streams) != 1:
            raise NeuralAcquisitionError("LSL stream name must resolve to exactly one source")
        info = streams[0]
        if int(info.channel_count()) != len(self._channel_names):
            raise NeuralAcquisitionError("LSL channel count does not match configured metadata")
        nominal_rate = float(info.nominal_srate())
        if nominal_rate and abs(nominal_rate - self._sample_rate) > 0.01:
            raise NeuralAcquisitionError("LSL sample rate does not match configured metadata")
        self._inlet = pylsl.StreamInlet(
            info,
            max_buflen=30,
            max_chunklen=min(self._sample_rate * 5, 4096),
            recover=False,
        )
        self._sequence = 0
        self._lsl_anchor = float(pylsl.local_clock())
        self._monotonic_anchor = time.monotonic_ns()
        self._descriptor = NeuralStreamDescriptorV1(
            session_id=self._session_id,
            source_id=self._source_id,
            board_kind="lsl-local-stream",
            transport=NeuralTransport.LSL,
            sample_rate_hz=self._sample_rate,
            channel_count=len(self._channel_names),
            channel_names=self._channel_names,
            reference=self._reference,
            sequence_start=0,
            started_monotonic_ns=self._monotonic_anchor,
        )

    def read(self, sample_count: int) -> NeuralSampleWindow:
        if self._inlet is None:
            raise NeuralAcquisitionError("LSL source is not running")
        if not 1 <= sample_count <= self._sample_rate * 30:
            raise NeuralAcquisitionError("LSL read exceeds the bounded window")
        deadline = time.monotonic() + max(1.0, sample_count / self._sample_rate * 2)
        samples: list[list[float]] = []
        timestamps: list[float] = []
        while len(samples) < sample_count:
            remaining_seconds = deadline - time.monotonic()
            if remaining_seconds <= 0:
                raise NeuralAcquisitionError("LSL did not return the complete requested window")
            chunk, chunk_timestamps = self._inlet.pull_chunk(
                timeout=remaining_seconds,
                max_samples=sample_count - len(samples),
            )
            if len(chunk) != len(chunk_timestamps):
                raise NeuralAcquisitionError("LSL returned mismatched sample/timestamp counts")
            samples.extend(chunk)
            timestamps.extend(chunk_timestamps)
        matrix = np.asarray(samples, dtype=np.float64).T
        monotonic = self._monotonic_anchor + np.rint(
            (np.asarray(timestamps, dtype=np.float64) - self._lsl_anchor) * 1_000_000_000
        ).astype(np.int64)
        window = NeuralSampleWindow(matrix, monotonic, self._sequence)
        self._sequence += sample_count
        return window

    def stop(self) -> None:
        inlet, self._inlet = self._inlet, None
        if inlet is not None:
            inlet.close_stream()
