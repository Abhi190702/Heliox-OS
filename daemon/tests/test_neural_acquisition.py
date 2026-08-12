from __future__ import annotations

import sys
import time
import types
from pathlib import Path

import numpy as np
import pytest

from pilot.neural.acquisition import (
    BoundedNeuralBuffer,
    BrainFlowNeuralSource,
    FaultInjectingNeuralSource,
    LSLNeuralSource,
    NeuralAcquisitionError,
    NeuralFaultPlan,
    NeuralSampleWindow,
    PlaybackNeuralSource,
    SyntheticNeuralSource,
)


def _window(sequence: int, count: int, *, channels: int = 2, start_ns: int = 1) -> NeuralSampleWindow:
    return NeuralSampleWindow(
        np.arange(channels * count, dtype=np.float64).reshape(channels, count),
        np.arange(start_ns, start_ns + count, dtype=np.int64),
        sequence,
    )


def test_sample_windows_are_immutable_and_reject_invalid_values() -> None:
    original = np.ones((2, 3))
    window = NeuralSampleWindow(original, np.array([1, 2, 3]), 0)
    original[0, 0] = 99
    assert window.samples_uv[0, 0] == 1
    with pytest.raises(ValueError):
        window.samples_uv[0, 0] = 2
    with pytest.raises(NeuralAcquisitionError, match="NaN"):
        NeuralSampleWindow(np.array([[np.nan]]), np.array([1]), 0)
    with pytest.raises(NeuralAcquisitionError, match="strictly increasing"):
        NeuralSampleWindow(np.ones((1, 2)), np.array([2, 2]), 0)


def test_bounded_buffer_tracks_overflow_gaps_and_rejects_replay() -> None:
    buffer = BoundedNeuralBuffer(channel_count=2, capacity_samples=5)
    buffer.append(_window(0, 3, start_ns=1))
    buffer.append(_window(5, 3, start_ns=4))
    assert buffer.health.buffered_samples == 3
    assert buffer.health.dropped_samples == 5  # two missing + three evicted
    assert buffer.latest(2).sequence_start == 6
    with pytest.raises(NeuralAcquisitionError, match="replayed"):
        buffer.append(_window(7, 1, start_ns=8))


def test_synthetic_source_is_deterministic_and_frequency_tagged() -> None:
    first = SyntheticNeuralSource(target_hz=12.0, noise_uv=0.0, seed=4)
    second = SyntheticNeuralSource(target_hz=12.0, noise_uv=0.0, seed=4)
    first.start()
    second.start()
    a = first.read(250)
    b = second.read(250)
    assert np.allclose(a.samples_uv, b.samples_uv)
    spectrum = np.abs(np.fft.rfft(a.samples_uv[0]))
    frequencies = np.fft.rfftfreq(250, d=1 / 250)
    assert frequencies[np.argmax(spectrum[1:]) + 1] == 12.0
    assert first.read(10).sequence_start == 250
    assert a.timestamps_ns[-1] <= time.monotonic_ns()


def test_playback_npz_is_safe_bounded_and_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "session.npz"
    np.savez(
        path,
        samples_uv=np.arange(20, dtype=np.float64).reshape(2, 10),
        sample_rate_hz=np.array(250),
        channel_names=np.array(["O1", "Oz"]),
        reference=np.array("linked-mastoids"),
    )
    source = PlaybackNeuralSource.from_npz(path)
    source.start()
    first = source.read(4)
    assert first.sequence_start == 0
    assert first.timestamps_ns[0] > 1_000_000_000
    assert source.read(6).sequence_end == 9
    with pytest.raises(EOFError):
        source.read(1)


def test_playback_rejects_pickle_and_incomplete_archives(tmp_path: Path) -> None:
    incomplete = tmp_path / "incomplete.npz"
    np.savez(incomplete, samples_uv=np.ones((2, 4)))
    with pytest.raises(NeuralAcquisitionError, match="incomplete"):
        PlaybackNeuralSource.from_npz(incomplete)

    pickled = tmp_path / "pickled.npz"
    np.savez(
        pickled,
        samples_uv=np.ones((1, 3)),
        sample_rate_hz=np.array(250),
        channel_names=np.array([object()], dtype=object),
        reference=np.array("ref"),
    )
    with pytest.raises(NeuralAcquisitionError, match="invalid playback"):
        PlaybackNeuralSource.from_npz(pickled)


def test_brainflow_adapter_validates_metadata_and_releases_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class Params:
        pass

    class Board:
        def __init__(self, board_id: int, params: Params) -> None:
            assert board_id == 99

        @staticmethod
        def get_eeg_channels(board_id: int) -> list[int]:
            return [0, 1]

        @staticmethod
        def get_sampling_rate(board_id: int) -> int:
            return 250

        @staticmethod
        def get_eeg_names(board_id: int) -> list[str]:
            return ["O1", "Oz"]

        def prepare_session(self) -> None:
            calls.append("prepare")

        def start_stream(self, capacity: int) -> None:
            assert capacity == 7500
            calls.append("start")

        def get_board_data(self, count: int) -> np.ndarray:
            return np.arange(2 * count, dtype=np.float64).reshape(2, count)

        def get_board_data_count(self) -> int:
            return 1000

        def stop_stream(self) -> None:
            calls.append("stop")

        def release_session(self) -> None:
            calls.append("release")

    package = types.ModuleType("brainflow")
    module = types.ModuleType("brainflow.board_shim")
    module.BrainFlowInputParams = Params
    module.BoardShim = Board
    monkeypatch.setitem(sys.modules, "brainflow", package)
    monkeypatch.setitem(sys.modules, "brainflow.board_shim", module)

    source = BrainFlowNeuralSource(
        board_id=99,
        channel_names=("O1", "Oz"),
        reference="linked-mastoids",
    )
    source.start()
    assert source.descriptor.sample_rate_hz == 250
    assert source.read(25).sample_count == 25
    source.stop()
    assert calls == ["prepare", "start", "stop", "release"]


def test_brainflow_adapter_selects_named_subset_and_labels_synthetic_board(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Params:
        pass

    class Board:
        def __init__(self, board_id: int, params: Params) -> None:
            assert board_id == -1

        @staticmethod
        def get_eeg_channels(board_id: int) -> list[int]:
            return [1, 2, 3, 4]

        @staticmethod
        def get_eeg_names(board_id: int) -> list[str]:
            return ["C3", "Cz", "C4", "Oz"]

        @staticmethod
        def get_sampling_rate(board_id: int) -> int:
            return 250

        def prepare_session(self) -> None:
            pass

        def start_stream(self, capacity: int) -> None:
            pass

        def get_board_data(self, count: int) -> np.ndarray:
            data = np.zeros((5, count), dtype=np.float64)
            for index in range(1, 5):
                data[index, :] = index
            return data

        def get_board_data_count(self) -> int:
            return 1000

        def stop_stream(self) -> None:
            pass

        def release_session(self) -> None:
            pass

    package = types.ModuleType("brainflow")
    module = types.ModuleType("brainflow.board_shim")
    module.BrainFlowInputParams = Params
    module.BoardShim = Board
    monkeypatch.setitem(sys.modules, "brainflow", package)
    monkeypatch.setitem(sys.modules, "brainflow.board_shim", module)

    source = BrainFlowNeuralSource(
        board_id=-1,
        channel_names=("C3", "C4"),
        reference="synthetic-common-reference",
    )
    source.start()
    try:
        assert source.descriptor.evidence_kind.value == "synthetic"
        assert source.read(5).samples_uv[:, 0].tolist() == [1.0, 3.0]
    finally:
        source.stop()


def test_lsl_adapter_accumulates_partial_chunks_without_dropping_samples(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[float, int]] = []

    class Info:
        @staticmethod
        def channel_count() -> int:
            return 2

        @staticmethod
        def nominal_srate() -> float:
            return 250.0

    class Inlet:
        def __init__(self, info: Info, **kwargs: object) -> None:
            assert kwargs["recover"] is False
            self._chunks = [
                ([[1.0, 2.0], [3.0, 4.0]], [100.001, 100.002]),
                ([[5.0, 6.0]], [100.003]),
            ]

        def pull_chunk(self, *, timeout: float, max_samples: int):
            calls.append((timeout, max_samples))
            return self._chunks.pop(0)

        def close_stream(self) -> None:
            pass

    module = types.ModuleType("pylsl")
    module.resolve_byprop = lambda *args, **kwargs: [Info()]
    module.local_clock = lambda: 100.0
    module.StreamInlet = Inlet
    monkeypatch.setitem(sys.modules, "pylsl", module)

    source = LSLNeuralSource(
        stream_name="HelioxEEG",
        channel_names=("O1", "Oz"),
        sample_rate_hz=250,
        reference="linked-mastoids",
    )
    source.start()
    window = source.read(3)
    source.stop()

    assert window.samples_uv.tolist() == [[1.0, 3.0, 5.0], [2.0, 4.0, 6.0]]
    assert window.sequence_start == 0
    assert [max_samples for _, max_samples in calls] == [3, 1]


def test_fault_injection_replays_and_saturates_deterministically() -> None:
    replay = FaultInjectingNeuralSource(
        SyntheticNeuralSource(seed=8),
        NeuralFaultPlan(every_nth_read=2, mode="replay"),
    )
    replay.start()
    first = replay.read(20)
    assert replay.read(20).sequence_start == first.sequence_start
    replay.stop()

    saturated = FaultInjectingNeuralSource(
        SyntheticNeuralSource(seed=9),
        NeuralFaultPlan(every_nth_read=1, mode="saturate"),
    )
    saturated.start()
    assert np.all(saturated.read(20).samples_uv[0] == 1_000.0)
    saturated.stop()
