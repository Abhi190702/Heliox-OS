"""Learned Risk Gate — ties Layers 1/3/4/5 together for a whole plan.

Mirrors Ferrum-OS's cognitive/world_model/mod.rs's evaluate_action(), which
composes the encoder/transition/safety layers for one proposed action.
Heliox's RiskGate.evaluate_plan() captures one OS snapshot, runs every
action through both learned and deterministic transitions, scores the
riskier result, and advances a conservative simulated state. This preserves
the "one bad action anywhere in the plan is enough" rule while also catching
resource impact that compounds across actions already present in the plan.

Strictly additive: if no weights are staged, evaluate_plan() still runs
using deterministic transitions. When a learned model is staged, a learned
prediction can add caution but cannot replace a stronger rule prediction.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pilot.security.risk_model import EMBEDDING_SIZE, LEARNABLE_ACTION_TYPES, RiskTransitionModel
from pilot.security.risk_observation import NOMINAL_PROC_CAPACITY, capture_os_snapshot
from pilot.security.risk_safety import score_outcome

if TYPE_CHECKING:
    from pilot.actions import ActionPlan
    from pilot.config import PilotConfig


class RiskGate:
    """Owns the (optional) learned transition model and evaluates whole
    plans against it. One instance is enough for the daemon's lifetime —
    see get_risk_gate() below; construct your own only in tests."""

    def __init__(self, weights_path: str | None = None) -> None:
        self._transition = RiskTransitionModel(weights_path)
        self._last_evaluation: dict[str, object] | None = None

    @property
    def available(self) -> bool:
        """True once a learned transition model is actually staged — the
        rule-based fallback runs regardless, so this only reports whether
        predictions for LEARNABLE_ACTION_TYPES come from real training or
        the honest rule-table default."""
        return self._transition.is_loaded

    @property
    def last_evaluation(self) -> dict[str, object] | None:
        """Return a defensive copy of the latest plan assessment."""
        return dict(self._last_evaluation) if self._last_evaluation is not None else None

    def status(self, enabled: bool) -> dict[str, object]:
        """Return user-safe runtime/model metadata for Settings."""
        return {
            "enabled": enabled,
            "weights_loaded": self.available,
            "model_version": self._transition.model_version,
            "training_samples": self._transition.training_samples,
            "embedding_size": EMBEDDING_SIZE,
            "learnable_action_types": sorted(action_type.value for action_type in LEARNABLE_ACTION_TYPES),
            "last_evaluation": self._last_evaluation,
        }

    def evaluate_plan(self, plan: ActionPlan, config: PilotConfig) -> tuple[float, list[str]]:
        """Returns (worst risk in [0,1] seen across the plan's actions,
        the reasons that fired for that worst action — empty if none)."""
        if not plan.actions:
            self._last_evaluation = {
                "evaluated_at": datetime.now(UTC).isoformat(),
                "action_count": 0,
                "risk_score": 0.0,
                "reasons": [],
                "worst_action_type": None,
                "prediction_sources": [],
            }
            return 0.0, []

        # One snapshot for the whole plan: this runs before execution
        # (predicting what WOULD happen), not interleaved with it, so OS
        # state isn't expected to shift meaningfully action-to-action —
        # and psutil calls aren't free, so one call beats N.
        snapshot = capture_os_snapshot()

        simulated = snapshot
        cumulative_proc_delta = 0.0
        worst_risk = 0.0
        worst_reasons: list[str] = []
        worst_action_type: str | None = None
        worst_sources: list[str] = []
        for action in plan.actions:
            learned_or_rule = self._transition.predict(simulated, action)
            deterministic = self._transition.predict_rule(simulated, action)
            candidates = [learned_or_rule]
            if learned_or_rule.source != "rule":
                candidates.append(deterministic)

            step_proc_delta = max(
                (outcome.proc_count_delta_normalized for outcome in candidates),
                key=abs,
            )
            cumulative_proc_delta += step_proc_delta

            for outcome in candidates:
                cumulative_outcome = replace(outcome, proc_count_delta_normalized=cumulative_proc_delta)
                risk, reasons = score_outcome(action, cumulative_outcome, config)
                if risk > worst_risk or worst_action_type is None:
                    worst_risk = risk
                    worst_reasons = reasons
                    worst_action_type = action.action_type.value
                    worst_sources = sorted({candidate.source for candidate in candidates})

            simulated = replace(
                simulated,
                disk_usage_fraction=max(outcome.disk_usage_after for outcome in candidates),
                proc_count=max(
                    0,
                    round(snapshot.proc_count + cumulative_proc_delta * NOMINAL_PROC_CAPACITY),
                ),
            )

        self._last_evaluation = {
            "evaluated_at": datetime.now(UTC).isoformat(),
            "action_count": len(plan.actions),
            "risk_score": worst_risk,
            "reasons": worst_reasons,
            "worst_action_type": worst_action_type,
            "prediction_sources": worst_sources,
        }
        return worst_risk, worst_reasons


_gate: RiskGate | None = None


def get_risk_gate() -> RiskGate:
    """Lazily-constructed process-wide singleton — the learned weights (if
    any) only need loading once per daemon lifetime."""
    global _gate
    if _gate is None:
        _gate = RiskGate()
    return _gate
