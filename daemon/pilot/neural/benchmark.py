"""Reproducible no-hardware neural acquisition and decoder benchmarks."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass

from pilot.neural.acquisition import BrainFlowNeuralSource, NeuralAcquisitionError
from pilot.neural.quality import NeuralSignalQualityAnalyzer


@dataclass(frozen=True, slots=True)
class BrainFlowSyntheticBenchmark:
    evidence_kind: str
    board_kind: str
    sample_rate_hz: int
    channel_names: tuple[str, ...]
    sample_count: int
    acquisition_seconds: float
    realtime_ratio: float
    signal_quality: str
    artifact_flags: tuple[str, ...]


def benchmark_brainflow_synthetic(*, seconds: float = 2.0) -> BrainFlowSyntheticBenchmark:
    """Acquire a bounded window from BrainFlow's synthetic board.

    This validates the real BrainFlow adapter without presenting generated
    waveforms as biological EEG or as classifier-accuracy evidence.
    """

    if not 0.25 <= seconds <= 30:
        raise ValueError("benchmark duration must be between 0.25 and 30 seconds")
    source = BrainFlowNeuralSource(
        board_id=-1,
        channel_names=("C3", "Cz", "C4", "Oz"),
        reference="brainflow-synthetic-reference",
        source_id="brainflow-synthetic-benchmark",
    )
    source.start()
    try:
        descriptor = source.descriptor
        sample_count = round(seconds * descriptor.sample_rate_hz)
        started = time.perf_counter()
        deadline = started + seconds + 5.0
        while True:
            try:
                window = source.read(sample_count)
                break
            except NeuralAcquisitionError as exc:
                if "not buffered" not in str(exc).casefold() or time.perf_counter() >= deadline:
                    raise
                time.sleep(0.01)
        elapsed = time.perf_counter() - started
        quality = NeuralSignalQualityAnalyzer().analyze(
            window,
            sample_rate_hz=descriptor.sample_rate_hz,
            channel_names=descriptor.channel_names,
        )
        return BrainFlowSyntheticBenchmark(
            evidence_kind=descriptor.evidence_kind.value,
            board_kind=descriptor.board_kind,
            sample_rate_hz=descriptor.sample_rate_hz,
            channel_names=descriptor.channel_names,
            sample_count=window.sample_count,
            acquisition_seconds=round(elapsed, 6),
            realtime_ratio=round((window.sample_count / descriptor.sample_rate_hz) / max(elapsed, 1e-9), 6),
            signal_quality=quality.quality.value,
            artifact_flags=tuple(flag.value for flag in quality.artifact_flags),
        )
    finally:
        source.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Heliox no-hardware neural benchmarks")
    subparsers = parser.add_subparsers(dest="benchmark", required=True)
    brainflow = subparsers.add_parser(
        "brainflow-synthetic",
        help="exercise the real BrainFlow adapter with generated, non-biological data",
    )
    brainflow.add_argument("--seconds", type=float, default=2.0)
    args = parser.parse_args()
    if args.benchmark == "brainflow-synthetic":
        print(json.dumps(asdict(benchmark_brainflow_synthetic(seconds=args.seconds)), indent=2))


if __name__ == "__main__":
    main()
