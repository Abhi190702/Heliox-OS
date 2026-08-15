from benchmarks.subscription_planning_suite import CASES, evaluate_action_types


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
    assert not evaluate_action_types(CASES["semantic_browser"], ["browser_navigate"], "")
    assert not evaluate_action_types(CASES["evidence_first_files"], ["file_list"], "planning failed")
    assert not evaluate_action_types(
        CASES["evidence_first_files"],
        ["file_list"],
        "",
        destructive_actions=1,
    )
