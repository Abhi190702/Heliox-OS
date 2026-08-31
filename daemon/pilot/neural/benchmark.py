"""Reproducible no-hardware neural acquisition and decoder benchmarks."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.metrics import balanced_accuracy_score
from sklearn.model_selection import LeaveOneGroupOut, cross_val_predict
from sklearn.pipeline import Pipeline

from pilot.neural.acquisition import BrainFlowNeuralSource, NeuralAcquisitionError
from pilot.neural.evaluation import NeuralIntentTrial, evaluate_neural_intent_trials
from pilot.neural.protocol import NeuralIntentClass
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


@dataclass(frozen=True, slots=True)
class EEGBCIBenchmark:
    evidence_kind: str
    dataset: str
    subject: int
    runs: tuple[int, ...]
    epoch_count: int
    channel_count: int
    sample_rate_hz: float
    evaluation: str
    balanced_accuracy: float
    chance_level: float
    fold_count: int
    decoded_preview_actions: dict[str, int]
    classifier_to_preview_mapping_verified: bool


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


def motor_imagery_preview_action(label: int) -> NeuralIntentClass:
    """Map the two recorded EEGBCI classes to bounded navigation previews."""

    actions = {
        0: NeuralIntentClass.FOCUS_LEFT,
        1: NeuralIntentClass.FOCUS_RIGHT,
    }
    try:
        return actions[label]
    except KeyError as exc:
        raise ValueError("motor-imagery labels must be zero or one") from exc


def _load_eegbci_epochs(
    *,
    subject: int,
    runs: tuple[int, ...],
    data_dir: Path | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    try:
        import mne
        from mne.datasets import eegbci
    except ImportError as exc:
        raise RuntimeError("MNE is not installed; install pilot-daemon[neural]") from exc

    epoch_parts: list[np.ndarray] = []
    label_parts: list[np.ndarray] = []
    group_parts: list[np.ndarray] = []
    sample_rate = 0.0
    for run in runs:
        filenames = eegbci.load_data(
            subject,
            [run],
            path=str(data_dir.expanduser().resolve()) if data_dir else None,
            update_path=False,
            verbose=False,
        )
        if len(filenames) != 1:
            raise RuntimeError(f"EEGBCI run {run} did not resolve to one EDF recording")
        raw = mne.io.read_raw_edf(filenames[0], preload=True, verbose="ERROR")
        eegbci.standardize(raw)
        raw.annotations.rename({"T1": "hands", "T2": "feet"})
        raw.set_eeg_reference(projection=True, verbose="ERROR")
        raw.filter(7.0, 30.0, fir_design="firwin", skip_by_annotation="edge", verbose="ERROR")
        epochs = mne.Epochs(
            raw,
            event_id=["hands", "feet"],
            tmin=-1.0,
            tmax=4.0,
            proj=True,
            picks="eeg",
            baseline=None,
            preload=True,
            verbose="ERROR",
        ).crop(tmin=1.0, tmax=2.0)
        data = epochs.get_data(copy=True)
        feet_code = epochs.event_id["feet"]
        labels = (epochs.events[:, -1] == feet_code).astype(np.int64)
        epoch_parts.append(data)
        label_parts.append(labels)
        group_parts.append(np.full(len(labels), run, dtype=np.int64))
        sample_rate = float(epochs.info["sfreq"])
    return (
        np.concatenate(epoch_parts),
        np.concatenate(label_parts),
        np.concatenate(group_parts),
        sample_rate,
    )


def evaluate_motor_imagery_epochs(
    epochs: np.ndarray,
    labels: np.ndarray,
    groups: np.ndarray,
    *,
    subject: int,
    runs: tuple[int, ...],
    sample_rate_hz: float,
) -> EEGBCIBenchmark:
    try:
        from mne.decoding import CSP
        from mne.utils import use_log_level
    except ImportError as exc:
        raise RuntimeError("MNE is not installed; install pilot-daemon[neural]") from exc
    data = np.asarray(epochs, dtype=np.float64)
    targets = np.asarray(labels, dtype=np.int64)
    run_groups = np.asarray(groups, dtype=np.int64)
    if data.ndim != 3 or len(data) != len(targets) or len(targets) != len(run_groups):
        raise ValueError("motor-imagery epochs, labels, and run groups do not align")
    if set(np.unique(targets)) != {0, 1}:
        raise ValueError("motor-imagery benchmark requires both registered classes")
    unique_groups = np.unique(run_groups)
    if len(unique_groups) < 2:
        raise ValueError("recorded EEG evaluation requires at least two independent runs")
    classifier = Pipeline(
        [
            ("csp", CSP(n_components=4, reg=None, log=True, norm_trace=False)),
            ("lda", LinearDiscriminantAnalysis()),
        ]
    )
    splitter = LeaveOneGroupOut()
    with use_log_level("ERROR"):
        predictions = cross_val_predict(classifier, data, targets, groups=run_groups, cv=splitter, n_jobs=None)
    actions = [motor_imagery_preview_action(int(label)).value for label in predictions]
    action_counts = {action: actions.count(action) for action in sorted(set(actions))}
    class_counts = np.bincount(targets, minlength=2)
    return EEGBCIBenchmark(
        evidence_kind="recorded_eeg",
        dataset="PhysioNet EEG Motor Movement/Imagery Dataset (EEGBCI)",
        subject=subject,
        runs=runs,
        epoch_count=len(targets),
        channel_count=data.shape[1],
        sample_rate_hz=sample_rate_hz,
        evaluation="leave-one-run-out CSP plus LDA",
        balanced_accuracy=round(float(balanced_accuracy_score(targets, predictions)), 6),
        chance_level=round(float(np.max(class_counts) / len(targets)), 6),
        fold_count=len(unique_groups),
        decoded_preview_actions=action_counts,
        classifier_to_preview_mapping_verified=len(actions) == len(targets),
    )


def benchmark_eegbci(
    *,
    subject: int = 1,
    runs: tuple[int, ...] = (6, 10, 14),
    data_dir: Path | None = None,
) -> EEGBCIBenchmark:
    """Download and evaluate recorded EEGBCI motor imagery without hardware."""

    if not 1 <= subject <= 109:
        raise ValueError("EEGBCI subject must be between 1 and 109")
    if len(set(runs)) < 2 or any(run not in {4, 6, 8, 10, 12, 14} for run in runs):
        raise ValueError("use at least two EEGBCI motor-imagery runs")
    epochs, labels, groups, sample_rate = _load_eegbci_epochs(
        subject=subject,
        runs=runs,
        data_dir=data_dir,
    )
    return evaluate_motor_imagery_epochs(
        epochs,
        labels,
        groups,
        subject=subject,
        runs=runs,
        sample_rate_hz=sample_rate,
    )


def benchmark_control_trials(manifest: Path) -> dict[str, object]:
    """Evaluate independent full-control trials exported by a test operator."""

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    raw_trials = payload.get("trials") if isinstance(payload, dict) else None
    if not isinstance(raw_trials, list):
        raise ValueError("control-trial manifest must contain a trials array")
    trials: list[NeuralIntentTrial] = []
    for index, item in enumerate(raw_trials):
        if not isinstance(item, dict):
            raise ValueError(f"control trial {index} must be an object")
        unknown = set(item) - {
            "duration_seconds",
            "expected_intent",
            "predicted_intent",
            "committed",
            "latency_ms",
        }
        if unknown:
            raise ValueError(f"control trial {index} has unknown fields: {sorted(unknown)}")
        expected = item.get("expected_intent")
        predicted = item.get("predicted_intent")
        trials.append(
            NeuralIntentTrial(
                duration_seconds=float(item["duration_seconds"]),
                expected_intent=NeuralIntentClass(expected) if expected is not None else None,
                predicted_intent=NeuralIntentClass(predicted) if predicted is not None else None,
                committed=bool(item.get("committed", False)),
                latency_ms=float(item["latency_ms"]) if item.get("latency_ms") is not None else None,
            )
        )
    return {
        "evidence_kind": str(payload.get("evidence_kind", "operator_labeled_trials")),
        "evaluation": "full neural intent commit gate",
        **evaluate_neural_intent_trials(trials).to_dict(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Heliox no-hardware neural benchmarks")
    subparsers = parser.add_subparsers(dest="benchmark", required=True)
    brainflow = subparsers.add_parser(
        "brainflow-synthetic",
        help="exercise the real BrainFlow adapter with generated, non-biological data",
    )
    brainflow.add_argument("--seconds", type=float, default=2.0)
    eegbci = subparsers.add_parser(
        "eegbci",
        help="download and benchmark recorded PhysioNet EEGBCI motor-imagery runs",
    )
    eegbci.add_argument("--subject", type=int, default=1)
    eegbci.add_argument("--runs", type=int, nargs="+", default=[6, 10, 14])
    eegbci.add_argument("--data-dir", type=Path)
    control_trials = subparsers.add_parser(
        "control-trials",
        help="score operator-labeled active and no-control trials from JSON",
    )
    control_trials.add_argument("manifest", type=Path)
    args = parser.parse_args()
    if args.benchmark == "brainflow-synthetic":
        print(json.dumps(asdict(benchmark_brainflow_synthetic(seconds=args.seconds)), indent=2))
    elif args.benchmark == "eegbci":
        result = benchmark_eegbci(
            subject=args.subject,
            runs=tuple(args.runs),
            data_dir=args.data_dir,
        )
        print(json.dumps(asdict(result), indent=2))
    elif args.benchmark == "control-trials":
        print(json.dumps(benchmark_control_trials(args.manifest), indent=2))


if __name__ == "__main__":
    main()
