"""Tests for outcome-based replay and evaluation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from pilot.intelligence.experience import (
    ExperienceEventType,
    ExperienceLedger,
    PrivacyClass,
    experience_scope,
)
from pilot.testing.evaluation import (
    CompositeEnvironmentProbe,
    EnvironmentSnapshot,
    EvaluationScenario,
    ExperienceTrace,
    ExperienceTraceReplayer,
    FileEnvironmentProbe,
    MappingEnvironmentProbe,
    OutcomeEvaluationHarness,
    StateAssertion,
    StateOperator,
    TraceEvaluator,
    default_release_scenarios,
)


@pytest_asyncio.fixture
async def ledger(tmp_path):
    instance = ExperienceLedger(tmp_path / "experience.db")
    await instance.initialize()
    yield instance
    await instance.close()


async def _valid_success_trace(ledger: ExperienceLedger, task_id: str = "task-1") -> ExperienceTrace:
    started = datetime.now(timezone.utc)
    with experience_scope(session_id="session-1", task_id=task_id):
        intent = await ledger.append(
            ExperienceEventType.INTENT,
            idempotency_key=f"{task_id}:intent",
            payload={"input": "write the report"},
            occurred_at=started.isoformat(),
        )
        plan = await ledger.append(
            ExperienceEventType.PLAN_CREATED,
            idempotency_key=f"{task_id}:plan",
            plan_id="plan-1",
            parent_event_id=intent.event_id,
            payload={"action_count": 1},
            occurred_at=(started + timedelta(milliseconds=10)).isoformat(),
        )
        await ledger.append(
            ExperienceEventType.CANDIDATE_ACTION,
            idempotency_key=f"{task_id}:candidate",
            plan_id="plan-1",
            action_id="action-1",
            parent_event_id=plan.event_id,
            payload={"action_idempotency_key": "action-1"},
            occurred_at=(started + timedelta(milliseconds=20)).isoformat(),
        )
        await ledger.append(
            ExperienceEventType.ACTION_STARTED,
            idempotency_key=f"{task_id}:started",
            plan_id="plan-1",
            action_id="action-1",
            occurred_at=(started + timedelta(milliseconds=30)).isoformat(),
        )
        await ledger.append(
            ExperienceEventType.ACTION_COMPLETED,
            idempotency_key=f"{task_id}:completed",
            plan_id="plan-1",
            action_id="action-1",
            payload={"success": True, "callback_observed": True},
            occurred_at=(started + timedelta(milliseconds=40)).isoformat(),
        )
        await ledger.append(
            ExperienceEventType.OUTCOME_VERIFIED,
            idempotency_key=f"{task_id}:verified",
            plan_id="plan-1",
            payload={"passed": True},
            occurred_at=(started + timedelta(milliseconds=45)).isoformat(),
        )
        await ledger.append(
            ExperienceEventType.OUTCOME_VERIFIED,
            idempotency_key=f"{task_id}:terminal",
            plan_id="plan-1",
            payload={"status": "success", "duration_ms": 50},
            occurred_at=(started + timedelta(milliseconds=50)).isoformat(),
        )
    return await ExperienceTrace.from_ledger(ledger, task_id)


@pytest.mark.asyncio
async def test_trace_export_round_trip_preserves_typed_events(ledger, tmp_path):
    trace = await _valid_success_trace(ledger)
    path = tmp_path / "trace.json"

    trace.save(path)
    loaded = ExperienceTrace.load(path)

    assert loaded == trace
    assert loaded.schema_version == 1
    assert loaded.events[0].privacy_class == PrivacyClass.INTERNAL


@pytest.mark.asyncio
async def test_replayer_reconstructs_action_lifecycle_without_side_effects(ledger):
    trace = await _valid_success_trace(ledger)

    replay = ExperienceTraceReplayer().replay(trace)

    assert replay.terminal_status == "success"
    assert replay.duration_ms == 50
    assert replay.candidate_action_ids == ("action-1",)
    assert replay.started_action_ids == ("action-1",)
    assert replay.completed_action_ids == ("action-1",)
    assert replay.violations == ()


@pytest.mark.asyncio
async def test_replayer_flags_action_after_denied_approval(ledger):
    with experience_scope(task_id="denied-task"):
        await ledger.append(
            ExperienceEventType.CANDIDATE_ACTION,
            idempotency_key="denied:candidate",
            action_id="action-denied",
        )
        await ledger.append(
            ExperienceEventType.APPROVAL_RESOLVED,
            idempotency_key="denied:approval",
            payload={"decision": "denied"},
        )
        await ledger.append(
            ExperienceEventType.ACTION_STARTED,
            idempotency_key="denied:started",
            action_id="action-denied",
        )
        await ledger.append(
            ExperienceEventType.OUTCOME_VERIFIED,
            idempotency_key="denied:terminal",
            payload={"status": "cancelled"},
        )

    trace = await ExperienceTrace.from_ledger(ledger, "denied-task")
    replay = ExperienceTraceReplayer().replay(trace)

    assert "action started after approval was denied or expired" in replay.violations


@pytest.mark.parametrize(
    ("assertion", "passed"),
    [
        (StateAssertion(("file", "exists"), StateOperator.EQUALS, True), True),
        (StateAssertion(("file", "size"), StateOperator.GREATER_THAN_OR_EQUAL, 10), True),
        (StateAssertion(("file", "size"), StateOperator.LESS_THAN_OR_EQUAL, 11), True),
        (StateAssertion(("file", "tags"), StateOperator.CONTAINS, "verified"), True),
        (StateAssertion(("file", "missing"), StateOperator.NOT_EXISTS), True),
        (StateAssertion(("file", "size"), StateOperator.NOT_EQUALS, 10), False),
    ],
)
def test_state_assertions_grade_normalized_environment(assertion, passed):
    snapshot = EnvironmentSnapshot({"file": {"exists": True, "size": 10, "tags": ["verified"]}})
    result, _detail = assertion.evaluate(snapshot)
    assert result is passed


@pytest.mark.asyncio
async def test_evaluator_fails_successful_chat_when_actual_state_is_wrong(ledger):
    trace = await _valid_success_trace(ledger)
    scenario = EvaluationScenario(
        scenario_id="actual-state",
        description="The file must really exist.",
        expected_terminal_statuses=("success",),
        state_assertions=(
            StateAssertion(
                ("files", "report.txt", "exists"),
                StateOperator.EQUALS,
                True,
            ),
        ),
    )

    report = TraceEvaluator().evaluate(
        scenario,
        trace,
        EnvironmentSnapshot({"files": {"report.txt": {"exists": False}}}),
        EnvironmentSnapshot({"files": {"report.txt": {"exists": False}}}),
    )

    assert report.passed is False
    assert report.dimension_scores["outcome"] == 0.5
    assert any("got False" in violation for violation in report.violations)


@pytest.mark.asyncio
async def test_evaluator_penalizes_duplicate_action_attempts(ledger):
    trace = await _valid_success_trace(ledger)
    with experience_scope(task_id=trace.task_id):
        await ledger.append(
            ExperienceEventType.ACTION_STARTED,
            idempotency_key="duplicate:start",
            action_id="action-1",
        )
        await ledger.append(
            ExperienceEventType.ACTION_COMPLETED,
            idempotency_key="duplicate:complete",
            action_id="action-1",
            payload={"success": True, "callback_observed": True},
        )
    trace = await ExperienceTrace.from_ledger(ledger, trace.task_id)
    scenario = EvaluationScenario(
        "no-duplicates",
        "Actions execute once.",
        ("success",),
        max_repeated_action_starts=1,
    )

    report = TraceEvaluator().evaluate(
        scenario,
        trace,
        EnvironmentSnapshot({}),
        EnvironmentSnapshot({}),
    )

    assert report.dimension_scores["efficiency"] == 0.5
    assert any("repeated action" in violation for violation in report.violations)


@pytest.mark.asyncio
async def test_harness_captures_before_and_after_real_state(ledger):
    state = {"files": {"report.txt": {"exists": False}}}
    probe = MappingEnvironmentProbe(lambda: state)
    scenario = EvaluationScenario(
        "write-file",
        "Driver must change actual state.",
        ("success",),
        state_assertions=(
            StateAssertion(
                ("files", "report.txt", "exists"),
                StateOperator.EQUALS,
                True,
            ),
        ),
    )

    async def driver():
        state["files"]["report.txt"]["exists"] = True
        with experience_scope(task_id="harness-task"):
            await ledger.append(
                ExperienceEventType.OUTCOME_VERIFIED,
                idempotency_key="harness:terminal",
                payload={"status": "success", "duration_ms": 25},
            )

    report = await OutcomeEvaluationHarness(ledger).run(
        scenario,
        task_id="harness-task",
        driver=driver,
        probe=probe,
    )

    assert report.passed is True
    assert report.before.values["files"]["report.txt"]["exists"] is False
    assert report.after.values["files"]["report.txt"]["exists"] is True


@pytest.mark.asyncio
async def test_correction_requires_a_later_revised_plan(ledger):
    with experience_scope(task_id="correction-task"):
        await ledger.append(
            ExperienceEventType.PLAN_CREATED,
            idempotency_key="correction:plan",
        )
        await ledger.append(
            ExperienceEventType.USER_CORRECTION,
            idempotency_key="correction:user",
        )
        await ledger.append(
            ExperienceEventType.OUTCOME_VERIFIED,
            idempotency_key="correction:terminal",
            payload={"status": "cancelled"},
        )

    trace = await ExperienceTrace.from_ledger(ledger, "correction-task")
    replay = ExperienceTraceReplayer().replay(trace)

    assert "user correction was not followed by a revised plan" in replay.violations


def test_default_release_suite_covers_every_required_scenario():
    scenarios = default_release_scenarios()

    assert set(scenarios) == {
        "delayed_approval",
        "denied_approval",
        "expired_or_disconnected_approval",
        "daemon_restart_during_task",
        "cancellation_during_phases",
        "simple_browser_navigation",
        "ambiguous_ui_target",
        "long_multi_application_task",
        "voice_barge_in_and_correction",
        "gaze_gesture_cursor_coexistence",
        "no_hand_false_positive",
        "world_model_policy_precedence",
        "offline_no_gpu_fallback",
        "malicious_plugin_or_prompt_injection",
    }
    assert all(scenario.description for scenario in scenarios.values())


@pytest.mark.asyncio
async def test_trace_export_paginates_beyond_one_sqlite_page(ledger):
    with experience_scope(task_id="long-trace"):
        for index in range(1005):
            await ledger.append(
                ExperienceEventType.OBSERVATION,
                idempotency_key=f"long:{index}",
                payload={"index": index},
            )

    trace = await ExperienceTrace.from_ledger(ledger, "long-trace")

    assert len(trace.events) == 1005
    assert trace.events[-1].payload["index"] == 1004


@pytest.mark.asyncio
async def test_file_and_composite_probes_capture_real_final_state(tmp_path):
    target = tmp_path / "artifact.txt"
    target.write_text("verified artifact", encoding="utf-8")
    file_probe = FileEnvironmentProbe((target,))
    composite = CompositeEnvironmentProbe({"workspace": file_probe})

    snapshot = await composite.capture()
    file_state = snapshot.values["workspace"]["files"][str(target.resolve())]

    assert file_state["exists"] is True
    assert file_state["size"] == len("verified artifact")
    assert len(file_state["sha256"]) == 64
    assert snapshot.provenance["workspace"]["probe"] == "FileEnvironmentProbe"


@pytest.mark.asyncio
async def test_harness_records_driver_failure_and_still_captures_after_state(ledger):
    captures = 0

    async def capture():
        nonlocal captures
        captures += 1
        return {"capture": captures}

    async def driver():
        raise RuntimeError("trial failed")

    scenario = EvaluationScenario("driver-error", "Capture failures.", ("error",))
    report = await OutcomeEvaluationHarness(ledger).run(
        scenario,
        task_id="driver-error-task",
        driver=driver,
        probe=MappingEnvironmentProbe(capture),
    )

    assert report.passed is False
    assert report.driver_error == "RuntimeError: trial failed"
    assert report.before.values == {"capture": 1}
    assert report.after.values == {"capture": 2}
    assert any("driver failed" in violation for violation in report.violations)
