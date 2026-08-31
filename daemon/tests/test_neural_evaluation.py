from __future__ import annotations

import pytest

from pilot.neural.evaluation import NeuralIntentTrial, evaluate_neural_intent_trials
from pilot.neural.protocol import NeuralIntentClass


def test_neural_evaluation_scores_commits_abstentions_and_latency() -> None:
    trials = [
        NeuralIntentTrial(2, NeuralIntentClass.SELECT, NeuralIntentClass.SELECT, True, 800),
        NeuralIntentTrial(2, NeuralIntentClass.CANCEL, NeuralIntentClass.CANCEL, True, 600),
        NeuralIntentTrial(2, NeuralIntentClass.FOCUS_LEFT, NeuralIntentClass.FOCUS_RIGHT, True, 700),
        NeuralIntentTrial(2, NeuralIntentClass.FOCUS_RIGHT),
        NeuralIntentTrial(1800, None),
        NeuralIntentTrial(1800, None, NeuralIntentClass.SELECT, True, 900),
    ]

    report = evaluate_neural_intent_trials(trials)

    assert report.active_trials == 4
    assert report.correct_commits == 2
    assert report.false_commits == 2
    assert report.missed_active_trials == 2
    assert report.precision == 0.5
    assert report.recall == 0.5
    assert report.f1 == 0.5
    assert report.idle_abstention_rate == 0.5
    assert report.false_commits_per_idle_hour == 1.0
    assert report.median_commit_latency_ms == 750.0
    assert report.p95_commit_latency_ms == 885.0


def test_neural_evaluation_rejects_invalid_trials_and_empty_input() -> None:
    with pytest.raises(ValueError, match="finite and positive"):
        NeuralIntentTrial(0, None)
    with pytest.raises(ValueError, match="requires a predicted intent"):
        NeuralIntentTrial(1, None, committed=True)
    with pytest.raises(ValueError, match="only to committed"):
        NeuralIntentTrial(1, NeuralIntentClass.SELECT, latency_ms=10)
    with pytest.raises(ValueError, match="at least one"):
        evaluate_neural_intent_trials([])
