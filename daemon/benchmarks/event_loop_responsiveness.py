"""Measure scheduler responsiveness during a real one-second CPU monitor sample.

Run from ``daemon``:
    python benchmarks/event_loop_responsiveness.py --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import statistics
import time
from typing import Any

from benchmarks.react_latency import _percentile
from pilot.agents.background import BackgroundTaskManager


async def benchmark(heartbeat_interval_ms: float = 10.0) -> dict[str, Any]:
    if heartbeat_interval_ms <= 0:
        raise ValueError("heartbeat interval must be positive")

    interval_seconds = heartbeat_interval_ms / 1000
    gaps_ms: list[float] = []
    started = time.perf_counter()
    previous = started
    sample_task = asyncio.create_task(BackgroundTaskManager._cpu_check())

    while not sample_task.done():
        await asyncio.sleep(interval_seconds)
        now = time.perf_counter()
        gaps_ms.append((now - previous) * 1000)
        previous = now

    sample = await sample_task
    elapsed_ms = (time.perf_counter() - started) * 1000
    if not gaps_ms:
        raise RuntimeError("CPU sample completed without a scheduler heartbeat")

    max_gap_ms = max(gaps_ms)
    return {
        "schema_version": "1.0.0",
        "benchmark": "event_loop_responsiveness_during_cpu_monitor",
        "scope": "Real psutil one-second CPU monitor sample with a concurrent asyncio heartbeat",
        "environment": {
            "operating_system": platform.system(),
            "operating_system_release": platform.release(),
            "python": platform.python_version(),
            "target_heartbeat_ms": heartbeat_interval_ms,
        },
        "sample_duration_ms": round(elapsed_ms, 3),
        "cpu_percent": sample["cpu_percent"],
        "heartbeat_ticks": len(gaps_ms),
        "heartbeat_median_ms": round(statistics.median(gaps_ms), 3),
        "heartbeat_p95_ms": round(_percentile(gaps_ms, 0.95), 3),
        "heartbeat_max_ms": round(max_gap_ms, 3),
        "max_scheduler_delay_ms": round(max(0.0, max_gap_ms - heartbeat_interval_ms), 3),
        "limitations": [
            "Measures scheduler availability, not CPU-monitor completion latency.",
            "Windows timer granularity and host load affect heartbeat intervals.",
            "Does not measure UI rendering or hardware input latency.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--heartbeat-ms", type=float, default=10.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = asyncio.run(benchmark(args.heartbeat_ms))
    if args.json:
        print(json.dumps(report, indent=2))
        return
    for key, value in report.items():
        if key not in {"environment", "limitations"}:
            print(f"{key}: {value}")


if __name__ == "__main__":
    main()
