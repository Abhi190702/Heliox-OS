"""Heliox-side neural preview and guarded execution controller."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from uuid import UUID

from pilot.actions import ActionPlan, PermissionTier
from pilot.agents.destructive_critic import PlanRiskAssessment, assess_plan_risk
from pilot.config import PilotConfig
from pilot.neural.gate import NeuralCommit, NeuralIntentGate, NeuralPreview
from pilot.neural.goals import NeuralGoalRegistry
from pilot.neural.protocol import NeuralIntentV1, NeuralScope, NeuralStreamDescriptorV1
from pilot.security.gateway import (
    DEFAULT_SOURCE_PROFILES,
    InvocationSource,
    TaskScopeOverride,
)


class NeuralControlError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PendingNeuralExecution:
    preview: NeuralPreview
    plan: ActionPlan | None
    world_model: PlanRiskAssessment | None


class NeuralController:
    """Convert a committed neural preview into UI navigation or one fixed plan."""

    def __init__(
        self,
        *,
        config: PilotConfig,
        gate: NeuralIntentGate,
        executor: Any,
        goals: NeuralGoalRegistry | None = None,
        broadcast: Callable[[str, Any], Awaitable[None]] | None = None,
    ) -> None:
        self._config = config
        self._gate = gate
        self._executor = executor
        self._goals = goals or NeuralGoalRegistry()
        self._broadcast = broadcast
        self._pending: PendingNeuralExecution | None = None
        self._lock = asyncio.Lock()

    async def connect(self, descriptor: NeuralStreamDescriptorV1) -> dict[str, object]:
        async with self._lock:
            self._pending = None
            status = await self._gate.connect(descriptor)
            await self._emit("neural_status", status)
            return status

    async def begin_calibration(self, session_id: UUID) -> dict[str, object]:
        async with self._lock:
            self._pending = None
            status = await self._gate.begin_calibration(session_id)
            await self._emit("neural_status", status)
            return status

    async def finish_calibration(self, session_id: UUID, *, calibration_id: str, subject_key: str) -> dict[str, object]:
        async with self._lock:
            status = await self._gate.finish_calibration(
                session_id,
                calibration_id=calibration_id,
                subject_key=subject_key,
            )
            await self._emit("neural_status", status)
            return status

    async def arm(
        self,
        session_id: UUID,
        *,
        scope: NeuralScope,
        non_neural_authorized: bool,
    ) -> dict[str, object]:
        async with self._lock:
            self._pending = None
            status = await self._gate.arm(
                session_id,
                scope=scope,
                non_neural_authorized=non_neural_authorized,
            )
            await self._emit("neural_status", status)
            return status

    async def preview(self, intent: NeuralIntentV1) -> dict[str, object]:
        async with self._lock:
            preview = await self._gate.preview(intent)
            if preview is None:
                self._pending = None
                status = await self._gate.status()
                await self._emit("neural_disarmed", {**status, "reason": "neural_cancel"})
                return {"status": "cancelled", **status}

            plan: ActionPlan | None = None
            world_model: PlanRiskAssessment | None = None
            try:
                if preview.command_id:
                    plan = self._goals.resolve(preview.command_id).plan()
                    world_model = self._assess_world_model(plan)
            except Exception:
                self._pending = None
                await self._gate.disarm(reason="preview_safety_failure")
                raise

            self._pending = PendingNeuralExecution(preview, plan, world_model)
            payload = self._preview_payload(self._pending)
            await self._emit("neural_preview", payload)
            return payload

    async def commit(
        self,
        preview_id: UUID,
        *,
        expected_revision: int,
        world_model_approved: bool,
    ) -> dict[str, object]:
        async with self._lock:
            pending = self._pending
            if pending is None or pending.preview.preview_id != preview_id:
                raise NeuralControlError("preview is missing or no longer current")
            plan = pending.plan
            assessment = pending.world_model
            if plan is not None:
                assessment = self._assess_world_model(plan)
                if assessment.requires_confirmation and not world_model_approved:
                    raise NeuralControlError("world-model warning requires a non-neural approval")
                effect_tier = int(plan.max_tier)
            else:
                effect_tier = int(PermissionTier.READ_ONLY)

            commit = await self._gate.commit(
                preview_id,
                expected_revision=expected_revision,
                effect_tier=effect_tier,
            )
            self._pending = None
            if plan is None:
                payload = self._navigation_commit_payload(commit)
                await self._emit("neural_navigation", payload)
                return payload

            plan_id = f"neural-{commit.intent_id}"
            profile = self._config.gateway.source_profiles.get("neural", DEFAULT_SOURCE_PROFILES["neural"])
            results = await self._executor.execute(
                plan,
                plan_id=plan_id,
                invocation_source=InvocationSource.NEURAL,
                scope_override=TaskScopeOverride(
                    max_tier=profile.max_tier,
                    deny_action_types=profile.deny_action_types,
                    allow_root=profile.allow_root,
                ),
                critic_already_reviewed=False,
                user_confirmed=bool(assessment and assessment.requires_confirmation and world_model_approved),
            )
            payload = {
                "status": "completed" if results and all(result.success for result in results) else "failed",
                "preview_id": str(commit.preview_id),
                "intent_id": str(commit.intent_id),
                "plan_id": plan_id,
                "canonical_goal": commit.canonical_goal,
                "world_model": assessment.to_dict() if assessment else None,
                "results": [result.model_dump(mode="json") for result in results],
                "retry_allowed": False,
            }
            await self._emit("neural_result", payload)
            return payload

    async def disarm(self, *, reason: str) -> dict[str, object]:
        async with self._lock:
            self._pending = None
            status = await self._gate.disarm(reason=reason)
            await self._emit("neural_disarmed", status)
            return status

    async def status(self) -> dict[str, object]:
        status = await self._gate.status()
        return {
            **status,
            "capabilities": {
                "observe": True,
                "calibrate": True,
                "ui_navigation": True,
                "safe_desktop": True,
                "physical_control": False,
                "destructive_approval": False,
            },
            "safe_goals": self._goals.public_summaries(),
        }

    def _assess_world_model(self, plan: ActionPlan) -> PlanRiskAssessment:
        if not self._config.gateway.risk_gate_enabled:
            raise NeuralControlError("world model is disabled; neural desktop control fails closed")
        assessment = assess_plan_risk(plan, self._config)
        if assessment.model_version in {"disabled", "evaluation-error"}:
            raise NeuralControlError("world model is unavailable; neural desktop control fails closed")
        return assessment

    @staticmethod
    def _preview_payload(pending: PendingNeuralExecution) -> dict[str, object]:
        preview = pending.preview
        assessment = pending.world_model
        return {
            "status": "previewed",
            "preview_id": str(preview.preview_id),
            "intent_id": str(preview.intent_id),
            "intent_class": preview.intent_class.value,
            "command_id": preview.command_id,
            "canonical_goal": preview.canonical_goal,
            "requested_scope": preview.requested_scope.value,
            "state_revision": preview.state_revision,
            "created_at_ns": preview.created_at_ns,
            "eligible_at_ns": preview.eligible_at_ns,
            "expires_at_ns": preview.expires_at_ns,
            "world_model": assessment.to_dict() if assessment else None,
            "requires_non_neural_approval": bool(assessment and assessment.requires_confirmation),
        }

    @staticmethod
    def _navigation_commit_payload(commit: NeuralCommit) -> dict[str, object]:
        return {
            "status": "committed",
            "preview_id": str(commit.preview_id),
            "intent_id": str(commit.intent_id),
            "canonical_goal": commit.canonical_goal,
            "requested_scope": commit.requested_scope.value,
            "committed_at_ns": commit.committed_at_ns,
        }

    async def _emit(self, method: str, payload: dict[str, object]) -> None:
        if self._broadcast is not None:
            await self._broadcast(method, payload)
