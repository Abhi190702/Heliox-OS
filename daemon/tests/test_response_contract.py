from pilot.actions import Action, ActionPlan, ActionResult, ActionType, SystemInfoParams, VerificationResult
from pilot.response_contract import partial_failure_message, success_message


def _action() -> Action:
    return Action(
        action_type=ActionType.SYSTEM_INFO,
        target="system",
        parameters=SystemInfoParams(),
    )


def test_success_message_reports_verified_execution_not_just_plan_intent():
    plan = ActionPlan(actions=[_action()], explanation="Inspect system information.")
    result = ActionResult(action=_action(), success=True, output="Windows")
    verification = VerificationResult(passed=True, details=["Action 0: VERIFIED"])

    assert success_message(plan, [result], verification, dry_run=False) == (
        "Completed and verified 1 action. Inspect system information."
    )


def test_dry_run_message_explicitly_says_no_changes_were_made():
    plan = ActionPlan(actions=[_action()], explanation="Change a setting.")
    verification = VerificationResult(passed=True)

    assert success_message(plan, [], verification, dry_run=True) == (
        "Dry run completed; no changes were made. Planned: Change a setting."
    )


def test_partial_failure_message_surfaces_real_error_instead_of_plan_intent():
    action = _action()
    result = ActionResult(action=action, success=False, error="Process exited with code 125")
    verification = VerificationResult(
        passed=False,
        details=["Action 0 (system_info): FAILED — Process exited with code 125"],
        failed_actions=[0],
    )

    message = partial_failure_message([result], verification)

    assert "1 of 1 action failed" in message
    assert "Process exited with code 125" in message
