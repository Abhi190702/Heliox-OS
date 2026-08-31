"""Dataset-neutral offline evaluation for world-model predictions."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from statistics import fmean, median

from pilot.intelligence.world_model import WorldPrediction


@dataclass(frozen=True, slots=True)
class WorldModelTrial:
    """One pre-action prediction paired with a post-action observation."""

    prediction: WorldPrediction
    observed_failure: bool
    transition_match: float | None = None
    latency_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class WorldModelEvaluation:
    trials: int
    failures: int
    risk_brier_score: float
    risk_calibration_error: float
    false_negative_rate: float
    transition_trials: int
    mean_transition_match: float | None
    high_uncertainty_rate: float
    median_latency_ms: float
    p95_latency_ms: float

    def to_dict(self) -> dict[str, int | float | None]:
        return asdict(self)


def _risk_score(prediction: WorldPrediction) -> float:
    return max((item.score for item in prediction.risk_evidence), default=0.0)


def _quantile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]


def evaluate_world_model_trials(
    trials: list[WorldModelTrial],
    *,
    risk_threshold: float = 0.5,
    calibration_bins: int = 10,
) -> WorldModelEvaluation:
    """Score risk calibration, transition fidelity, uncertainty, and latency."""
    if not trials:
        raise ValueError("at least one world-model trial is required")
    if not 0.0 <= risk_threshold <= 1.0:
        raise ValueError("risk_threshold must be between 0 and 1")
    if calibration_bins < 2:
        raise ValueError("calibration_bins must be at least 2")

    risks: list[float] = []
    outcomes: list[float] = []
    transitions: list[float] = []
    latencies: list[float] = []
    for trial in trials:
        risk = _risk_score(trial.prediction)
        if not math.isfinite(risk) or not 0.0 <= risk <= 1.0:
            raise ValueError("prediction risk evidence must be finite and between 0 and 1")
        if not math.isfinite(trial.prediction.uncertainty) or not 0.0 <= trial.prediction.uncertainty <= 1.0:
            raise ValueError("prediction uncertainty must be finite and between 0 and 1")
        if not math.isfinite(trial.latency_ms) or trial.latency_ms < 0.0:
            raise ValueError("latency_ms must be finite and non-negative")
        if trial.transition_match is not None:
            if not math.isfinite(trial.transition_match) or not 0.0 <= trial.transition_match <= 1.0:
                raise ValueError("transition_match must be finite and between 0 and 1")
            transitions.append(trial.transition_match)
        risks.append(risk)
        outcomes.append(float(trial.observed_failure))
        latencies.append(trial.latency_ms)

    brier = fmean((risk - outcome) ** 2 for risk, outcome in zip(risks, outcomes))
    calibration_error = 0.0
    for bin_index in range(calibration_bins):
        lower = bin_index / calibration_bins
        upper = (bin_index + 1) / calibration_bins
        members = [
            index
            for index, risk in enumerate(risks)
            if lower <= risk < upper or (bin_index == calibration_bins - 1 and risk == 1.0)
        ]
        if members:
            weight = len(members) / len(trials)
            calibration_error += weight * abs(
                fmean(risks[index] for index in members) - fmean(outcomes[index] for index in members)
            )

    failure_indices = [index for index, outcome in enumerate(outcomes) if outcome == 1.0]
    false_negatives = sum(risks[index] < risk_threshold for index in failure_indices)
    false_negative_rate = false_negatives / len(failure_indices) if failure_indices else 0.0
    high_uncertainty_rate = sum(trial.prediction.uncertainty >= 0.75 for trial in trials) / len(trials)

    return WorldModelEvaluation(
        trials=len(trials),
        failures=len(failure_indices),
        risk_brier_score=brier,
        risk_calibration_error=calibration_error,
        false_negative_rate=false_negative_rate,
        transition_trials=len(transitions),
        mean_transition_match=fmean(transitions) if transitions else None,
        high_uncertainty_rate=high_uncertainty_rate,
        median_latency_ms=median(latencies),
        p95_latency_ms=_quantile(latencies, 0.95),
    )
