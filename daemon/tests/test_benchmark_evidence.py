from __future__ import annotations

import json
from pathlib import Path


def test_committed_software_benchmark_bundle_has_truthful_passing_contracts() -> None:
    evidence_dir = Path(__file__).resolve().parents[2] / "docs" / "evidence"
    path = sorted(evidence_dir.glob("software-benchmarks-*.json"))[-1]
    report = json.loads(path.read_text(encoding="utf-8"))

    assert report["schema_version"] == "1.0.0"
    assert len(report["source_commit"]) == 40
    assert report["guarded_cpu_request"]["model_generate_calls"] == 0
    assert report["local_status_suite"]["model_generate_calls"] == 0
    assert report["intent_dispatch"]["failed"] == 0
    assert report["intent_dispatch"]["accuracy"] == 1.0
    world_model = report["learned_risk_world_model"]
    assert world_model["direction_checks_passed"] == len(world_model["direction_checks"])
    assert world_model["validation"]["disk_improvement_percent"] > 0
    assert world_model["validation"]["process_improvement_percent"] > 0
    assert "no claim" in report["claim_boundary"].lower()


def test_committed_subscription_planning_evidence_is_bounded_and_non_destructive() -> None:
    evidence_dir = Path(__file__).resolve().parents[2] / "docs" / "evidence"
    path = sorted(evidence_dir.glob("subscription-planning-*.json"))[-1]
    report = json.loads(path.read_text(encoding="utf-8"))

    assert report["schema_version"] == "1.0.0"
    assert len(report["source_commit"]) == 40
    assert report["passed"] == report["case_count"] == len(report["results"])
    assert report["scope"] == "side-effect-free planning only; no action was executed"
    assert all(result["passed"] for result in report["results"])
    assert all(result["destructive_actions"] == 0 for result in report["results"])
    assert "one developer-machine" in report["claim_boundary"].lower()
