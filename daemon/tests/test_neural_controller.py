from __future__ import annotations

import asyncio
import time
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from pilot.actions import Action, ActionResult, ActionType, EmptyParams
from pilot.agents.destructive_critic import PlanRiskAssessment
from pilot.config import PilotConfig
from pilot.neural.controller import NeuralControlError, NeuralController
from pilot.neural.gate import NeuralIntentGate, NeuralIntentGateConfig, NeuralIntentSigner
from pilot.neural.goals import NeuralGoalDefinition, NeuralGoalError, NeuralGoalRegistry
from pilot.neural.protocol import (
    NeuralIntentClass,
    NeuralIntentV1,
    NeuralParadigm,
    NeuralScope,
    NeuralStreamDescriptorV1,
    NeuralTransport,
    SignalQuality,
)
from pilot.security.gateway import InvocationSource

CALIBRATION = "b" * 64
SUBJECT = "local-subject"


def _safe_assessment(*, requires_confirmation: bool = False) -> PlanRiskAssessment:
    score = 0.5 if requires_confirmation else 0.0
    return PlanRiskAssessment(
        heuristic_score=0.0,
        world_model_score=score,
        combined_score=score,
        reasons=["test warning"] if requires_confirmation else [],
        prediction_sources=["rules"],
        weights_loaded=False,
        model_version="rule-fallback-v1",
    )


async def _controller(scope: NeuralScope) -> tuple[NeuralController, NeuralIntentSigner, uuid.UUID, AsyncMock]:
    signer = NeuralIntentSigner(b"k" * 32)
    session_id = uuid.uuid4()
    goals = NeuralGoalRegistry()
    gate = NeuralIntentGate(
        signer=signer,
        safe_goals={command_id: command_id for command_id in goals.command_ids},
        config=NeuralIntentGateConfig(cancellation_window_ns=1, cooldown_ns=1),
    )
    executor = AsyncMock()
    controller = NeuralController(
        config=PilotConfig(),
        gate=gate,
        executor=executor,
        goals=goals,
    )
    descriptor = NeuralStreamDescriptorV1(
        session_id=session_id,
        source_id="synthetic-test",
        board_kind="synthetic",
        transport=NeuralTransport.SYNTHETIC,
        sample_rate_hz=250,
        channel_count=3,
        channel_names=("O1", "Oz", "O2"),
        reference="synthetic-common-reference",
        sequence_start=0,
        started_monotonic_ns=time.monotonic_ns(),
    )
    await controller.connect(descriptor)
    await controller.begin_calibration(session_id)
    await controller.finish_calibration(session_id, calibration_id=CALIBRATION, subject_key=SUBJECT)
    await controller.arm(session_id, scope=scope, non_neural_authorized=True)
    return controller, signer, session_id, executor


async def _intent(
    controller: NeuralController,
    signer: NeuralIntentSigner,
    session_id: uuid.UUID,
    *,
    intent_class: NeuralIntentClass,
    scope: NeuralScope,
    command_id: str | None = None,
) -> NeuralIntentV1:
    status = await controller.status()
    now = time.monotonic_ns()
    unsigned = NeuralIntentV1(
        session_id=session_id,
        intent_id=uuid.uuid4(),
        sequence=int(status["last_sequence"]) + 1,
        window_start_ns=now - 300_000_000,
        window_end_ns=now - 100_000_000,
        expires_at_ns=now + 2_000_000_000,
        paradigm=NeuralParadigm.SYNTHETIC,
        intent_class=intent_class,
        command_id=command_id,
        posterior_permille=950,
        margin_permille=400,
        signal_quality=SignalQuality.GOOD,
        dwell_windows=4,
        decoder_version="a" * 64,
        calibration_id=CALIBRATION,
        subject_key=SUBJECT,
        requested_scope=scope,
        state_revision=int(status["state_revision"]),
        signature="0" * 64,
    )
    return unsigned.model_copy(update={"signature": signer.sign(unsigned)})


def test_goal_registry_rejects_tier_two_or_dynamic_authority() -> None:
    with pytest.raises(NeuralGoalError, match="Tier 0/1"):
        NeuralGoalDefinition(
            "click",
            "Click",
            "Unsafe dynamic click",
            Action(action_type=ActionType.BROWSER_CLICK, target="anything", parameters=EmptyParams()),
        )
    registry = NeuralGoalRegistry()
    assert "system-overview" in registry.command_ids
    assert registry.resolve("system-overview").plan().actions[0].action_type == ActionType.SYSTEM_INFO


@pytest.mark.asyncio
async def test_navigation_commit_never_reaches_executor() -> None:
    controller, signer, session_id, executor = await _controller(NeuralScope.NAVIGATE)
    intent = await _intent(
        controller,
        signer,
        session_id,
        intent_class=NeuralIntentClass.SELECT,
        scope=NeuralScope.NAVIGATE,
    )
    preview = await controller.preview(intent)
    await asyncio.sleep(0.02)
    result = await controller.commit(
        uuid.UUID(str(preview["preview_id"])),
        expected_revision=int(preview["state_revision"]),
        world_model_approved=False,
    )
    assert result["canonical_goal"] == "neural_ui.select"
    executor.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_safe_desktop_goal_rechecks_world_model_and_uses_neural_gateway() -> None:
    controller, signer, session_id, executor = await _controller(NeuralScope.SAFE_DESKTOP)
    intent = await _intent(
        controller,
        signer,
        session_id,
        intent_class=NeuralIntentClass.SAFE_GOAL,
        scope=NeuralScope.SAFE_DESKTOP,
        command_id="system-overview",
    )
    executor.execute.return_value = [
        ActionResult(
            action=NeuralGoalRegistry().resolve("system-overview").plan().actions[0],
            success=True,
            output="system data",
        )
    ]
    with patch("pilot.neural.controller.assess_plan_risk", return_value=_safe_assessment()) as assess:
        preview = await controller.preview(intent)
        await asyncio.sleep(0.02)
        result = await controller.commit(
            uuid.UUID(str(preview["preview_id"])),
            expected_revision=int(preview["state_revision"]),
            world_model_approved=False,
        )
    assert assess.call_count == 2
    assert result["status"] == "completed"
    kwargs = executor.execute.await_args.kwargs
    assert kwargs["invocation_source"] == InvocationSource.NEURAL
    assert kwargs["critic_already_reviewed"] is False
    assert kwargs["user_confirmed"] is False


@pytest.mark.asyncio
async def test_safe_desktop_select_resolves_only_the_daemon_owned_focused_goal() -> None:
    controller, signer, session_id, executor = await _controller(NeuralScope.SAFE_DESKTOP)
    focused = str((await controller.status())["focused_command_id"])
    intent = await _intent(
        controller,
        signer,
        session_id,
        intent_class=NeuralIntentClass.SELECT,
        scope=NeuralScope.SAFE_DESKTOP,
    )
    executor.execute.return_value = [
        ActionResult(
            action=NeuralGoalRegistry().resolve(focused).plan().actions[0],
            success=True,
            output="safe result",
        )
    ]
    with patch("pilot.neural.controller.assess_plan_risk", return_value=_safe_assessment()):
        preview = await controller.preview(intent)
        assert preview["resolved_command_id"] == focused
        await asyncio.sleep(0.02)
        result = await controller.commit(
            uuid.UUID(str(preview["preview_id"])),
            expected_revision=int(preview["state_revision"]),
            world_model_approved=False,
        )
    assert result["command_id"] == focused
    assert executor.execute.await_count == 1


@pytest.mark.asyncio
async def test_world_model_warning_requires_ui_approval_and_unavailable_model_disarms() -> None:
    controller, signer, session_id, executor = await _controller(NeuralScope.SAFE_DESKTOP)
    intent = await _intent(
        controller,
        signer,
        session_id,
        intent_class=NeuralIntentClass.SAFE_GOAL,
        scope=NeuralScope.SAFE_DESKTOP,
        command_id="battery-status",
    )
    with patch(
        "pilot.neural.controller.assess_plan_risk",
        return_value=_safe_assessment(requires_confirmation=True),
    ):
        preview = await controller.preview(intent)
        with pytest.raises(NeuralControlError, match="non-neural approval"):
            await controller.commit(
                uuid.UUID(str(preview["preview_id"])),
                expected_revision=int(preview["state_revision"]),
                world_model_approved=False,
            )
    executor.execute.assert_not_awaited()

    controller2, signer2, session2, _ = await _controller(NeuralScope.SAFE_DESKTOP)
    intent2 = await _intent(
        controller2,
        signer2,
        session2,
        intent_class=NeuralIntentClass.SAFE_GOAL,
        scope=NeuralScope.SAFE_DESKTOP,
        command_id="battery-status",
    )
    unavailable = _safe_assessment().to_dict()
    unavailable["model_version"] = "evaluation-error"
    with (
        patch(
            "pilot.neural.controller.assess_plan_risk",
            return_value=PlanRiskAssessment(
                **{key: value for key, value in unavailable.items() if key != "requires_confirmation"}
            ),
        ),
        pytest.raises(NeuralControlError, match="unavailable"),
    ):
        await controller2.preview(intent2)
    assert (await controller2.status())["armed_scope"] == "observe"
