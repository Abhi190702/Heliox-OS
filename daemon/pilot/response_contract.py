"""Truthful, user-facing summaries for terminal execution states.

Planning text describes intent.  These helpers describe what actually happened
after execution and verification, so callers never reuse a proposed plan as a
success or failure result.
"""

from __future__ import annotations

from collections.abc import Sequence

from pilot.actions import ActionPlan, ActionResult, VerificationResult


def success_message(
    plan: ActionPlan,
    results: Sequence[ActionResult],
    verification: VerificationResult,
    *,
    dry_run: bool,
) -> str:
    """Build a terminal success message from verified execution state."""
    if dry_run:
        intent = _clean(plan.explanation)
        return (
            f"Dry run completed; no changes were made. Planned: {intent}"
            if intent
            else "Dry run completed; no changes were made."
        )

    count = len(results)
    noun = "action" if count == 1 else "actions"
    intent = _clean(plan.explanation)
    prefix = f"Completed and verified {count} {noun}."
    if intent:
        return f"{prefix} {intent}"
    if verification.details:
        return f"{prefix} {_clean(verification.details[0])}"
    return prefix


def partial_failure_message(
    results: Sequence[ActionResult],
    verification: VerificationResult | None,
) -> str:
    """Build a failure summary without presenting the original intent as fact."""
    total = len(results)
    failed_indices = set(verification.failed_actions if verification else [])
    failed_indices.update(i for i, result in enumerate(results) if not result.success)
    failed = len(failed_indices)

    if total:
        noun = "action" if total == 1 else "actions"
        prefix = (
            f"Task did not complete successfully: {failed or total} of {total} {noun} failed or could not be verified."
        )
    else:
        prefix = "Task did not complete successfully: no action result was verified."

    issues = [result.error for result in results if result.error]
    if verification:
        issues.extend(
            detail
            for detail in verification.details
            if "FAILED" in detail or "MISMATCH" in detail or "error" in detail.lower()
        )
    first_issue = next((_clean(issue) for issue in issues if _clean(issue)), "")
    return f"{prefix} {first_issue}" if first_issue else prefix


def _clean(value: object) -> str:
    return " ".join(str(value).split())
