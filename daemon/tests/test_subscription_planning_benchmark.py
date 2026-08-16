from argparse import Namespace
from unittest.mock import AsyncMock, patch

from benchmarks.subscription_planning_suite import CASES, evaluate_action_types, main


def test_benchmark_accepts_required_read_only_actions():
    assert evaluate_action_types(
        CASES["health_review"],
        ["system_health_review"],
        "",
    )


def test_benchmark_rejects_forbidden_or_incomplete_plans():
    assert not evaluate_action_types(
        CASES["health_review"],
        ["system_health_review", "shell_command"],
        "",
    )


def test_main_writes_machine_readable_evidence(tmp_path):
    output = tmp_path / "subscription.json"
    report = {
        "schema_version": "1.0.0",
        "scope": "side-effect-free planning only; no action was executed",
        "provider": "codex",
        "results": [],
    }
    with (
        patch(
            "benchmarks.subscription_planning_suite._parse_args",
            return_value=Namespace(provider="codex", model="", cases=None, output=output),
        ),
        patch("benchmarks.subscription_planning_suite.benchmark", new=AsyncMock(return_value=report)),
    ):
        main()

    assert output.read_text(encoding="utf-8").endswith("\n")
    assert '"provider": "codex"' in output.read_text(encoding="utf-8")
    assert not evaluate_action_types(CASES["semantic_browser"], ["browser_navigate"], "")
    assert not evaluate_action_types(CASES["evidence_first_files"], ["file_list"], "planning failed")
    assert not evaluate_action_types(
        CASES["evidence_first_files"],
        ["file_list"],
        "",
        destructive_actions=1,
    )


def test_evidence_case_accepts_a_read_only_script_plan():
    assert evaluate_action_types(
        CASES["evidence_first_files"],
        ["shell_script"],
        "",
        destructive_actions=0,
    )
