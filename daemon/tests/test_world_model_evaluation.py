from __future__ import annotations

import pytest

from pilot.intelligence.world_model import RiskEvidence, WorldPrediction, WorldState
from pilot.intelligence.world_model_evaluation import (
    WorldModelTrial,
    evaluate_world_model_trials,
)


def _prediction(risk: float, *, uncertainty: float) -> WorldPrediction:
    evidence = (RiskEvidence("test", risk, "offline trial"),) if risk else ()
    return WorldPrediction(
        action_type="system_info",
        predicted_state=WorldState.empty(),
        expected_effects=(),
        uncertainty=uncertainty,
        risk_evidence=evidence,
        sources=("test",),
        model_version="test",
    )


def test_world_model_evaluation_scores_risk_transition_and_latency() -> None:
    report = evaluate_world_model_trials(
        [
            WorldModelTrial(_prediction(0.9, uncertainty=0.2), True, 0.8, 8.0),
            WorldModelTrial(_prediction(0.1, uncertainty=0.8), False, 0.6, 12.0),
            WorldModelTrial(_prediction(0.2, uncertainty=0.3), True, None, 10.0),
        ]
    )

    assert report.trials == 3
    assert report.failures == 2
    assert report.false_negative_rate == pytest.approx(0.5)
    assert report.mean_transition_match == pytest.approx(0.7)
    assert report.high_uncertainty_rate == pytest.approx(1 / 3)
    assert report.median_latency_ms == 10.0
    assert report.p95_latency_ms == 12.0


def test_world_model_evaluation_rejects_invalid_observations() -> None:
    with pytest.raises(ValueError, match="transition_match"):
        evaluate_world_model_trials([WorldModelTrial(_prediction(0.1, uncertainty=0.2), False, 1.1, 5.0)])


def test_world_model_evaluation_requires_trials() -> None:
    with pytest.raises(ValueError, match="at least one"):
        evaluate_world_model_trials([])
