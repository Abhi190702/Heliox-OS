from __future__ import annotations

import json
from pathlib import Path


def test_committed_software_benchmark_bundle_has_truthful_passing_contracts() -> None:
    path = Path(__file__).resolve().parents[2] / "docs" / "evidence" / "software-benchmarks-2026-08-13.json"
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
