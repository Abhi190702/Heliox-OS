"""Dataset-neutral neural-intent evaluation focused on control safety."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import median

import numpy as np

from pilot.neural.protocol import NeuralIntentClass


@dataclass(frozen=True, slots=True)
class NeuralIntentTrial:
    """One independent active or no-control evaluation trial."""

    duration_seconds: float
    expected_intent: NeuralIntentClass | None
    predicted_intent: NeuralIntentClass | None = None
    committed: bool = False
    latency_ms: float | None = None

    def __post_init__(self) -> None:
        if not np.isfinite(self.duration_seconds) or self.duration_seconds <= 0:
            raise ValueError("trial duration must be finite and positive")
        if self.committed and self.predicted_intent is None:
            raise ValueError("a committed trial requires a predicted intent")
        if self.latency_ms is not None and (not np.isfinite(self.latency_ms) or self.latency_ms < 0):
            raise ValueError("trial latency must be finite and non-negative")
        if self.latency_ms is not None and not self.committed:
            raise ValueError("latency belongs only to committed trials")


@dataclass(frozen=True, slots=True)
class NeuralIntentEvaluation:
    trial_count: int
    active_trials: int
    idle_trials: int
    committed_trials: int
    correct_commits: int
    false_commits: int
    missed_active_trials: int
    precision: float
    recall: float
    f1: float
    idle_abstention_rate: float
    false_commits_per_idle_hour: float
    median_commit_latency_ms: float | None
    p95_commit_latency_ms: float | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def evaluate_neural_intent_trials(
    trials: tuple[NeuralIntentTrial, ...] | list[NeuralIntentTrial],
) -> NeuralIntentEvaluation:
    """Score exact committed intents and no-control false activations.

    A prediction that never crosses the commit gate is an abstention, not an
    action. Wrong-class commits and any commit during an idle trial are false
    commits. This intentionally evaluates the full control decision rather
    than presenting classifier accuracy as product reliability.
    """

    if not trials:
        raise ValueError("at least one independent neural-intent trial is required")
    active = [trial for trial in trials if trial.expected_intent is not None]
    idle = [trial for trial in trials if trial.expected_intent is None]
    committed = [trial for trial in trials if trial.committed]
    correct = [
        trial
        for trial in committed
        if trial.expected_intent is not None and trial.predicted_intent == trial.expected_intent
    ]
    false = [trial for trial in committed if trial not in correct]
    correct_ids = {id(trial) for trial in correct}
    missed = [trial for trial in active if id(trial) not in correct_ids]

    precision = len(correct) / len(committed) if committed else 0.0
    recall = len(correct) / len(active) if active else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    idle_abstentions = sum(not trial.committed for trial in idle)
    idle_seconds = sum(trial.duration_seconds for trial in idle)
    idle_false_commits = sum(trial.committed for trial in idle)
    latencies = sorted(float(trial.latency_ms) for trial in committed if trial.latency_ms is not None)

    return NeuralIntentEvaluation(
        trial_count=len(trials),
        active_trials=len(active),
        idle_trials=len(idle),
        committed_trials=len(committed),
        correct_commits=len(correct),
        false_commits=len(false),
        missed_active_trials=len(missed),
        precision=round(precision, 6),
        recall=round(recall, 6),
        f1=round(f1, 6),
        idle_abstention_rate=round(idle_abstentions / len(idle), 6) if idle else 0.0,
        false_commits_per_idle_hour=round(idle_false_commits / (idle_seconds / 3600), 6) if idle_seconds else 0.0,
        median_commit_latency_ms=round(median(latencies), 3) if latencies else None,
        p95_commit_latency_ms=round(float(np.percentile(latencies, 95)), 3) if latencies else None,
    )
