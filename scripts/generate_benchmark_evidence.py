"""Generate one reproducible, machine-readable Heliox software benchmark bundle."""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
DAEMON_ROOT = REPO_ROOT / "daemon"
sys.path.insert(0, str(DAEMON_ROOT))

from benchmarks.event_loop_responsiveness import benchmark as benchmark_event_loop  # noqa: E402
from benchmarks.intent_dispatch_suite import benchmark as benchmark_intents  # noqa: E402
from benchmarks.local_status_suite import benchmark_suite as benchmark_status  # noqa: E402
from benchmarks.react_latency import benchmark_report as benchmark_guarded_request  # noqa: E402
from benchmarks.world_model_suite import benchmark as benchmark_world_model  # noqa: E402


def _commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


async def build_bundle() -> dict:
    captured_at = datetime.now(ZoneInfo("Asia/Kolkata"))
    return {
        "schema_version": "1.0.0",
        "captured_at": captured_at.isoformat(),
        "captured_on": captured_at.date().isoformat(),
        "source_commit": _commit(),
        "claim_boundary": (
            "Local software benchmark bundle; no claim of model-provider, network, browser page-load, "
            "microphone, camera, speaker, gaze, gesture, EEG, or human accuracy"
        ),
        "guarded_cpu_request": await benchmark_guarded_request(
            iterations=100, warmup=10
        ),
        "local_status_suite": await benchmark_status(iterations=50, warmup=5),
        "event_loop_responsiveness": await benchmark_event_loop(
            heartbeat_interval_ms=10.0
        ),
        "intent_dispatch": benchmark_intents(),
        "learned_risk_world_model": benchmark_world_model(iterations=1000),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "docs" / "evidence" / "software-benchmarks-2026-08-13.json",
    )
    args = parser.parse_args()
    report = asyncio.run(build_bundle())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"Wrote benchmark evidence to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
