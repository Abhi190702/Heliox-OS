"""Benchmark multiple guarded, non-LLM local status actions.

Run from ``daemon``:
    python benchmarks/local_status_suite.py --iterations 30 --warmup 3 --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
from dataclasses import dataclass
from typing import Any

from benchmarks.react_latency import build_harness, run_once, summarize


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    query: str
    expected_action: str


SCENARIOS = (
    Scenario("cpu_usage", "What's my CPU usage?", "cpu_usage"),
    Scenario("memory_usage", "What's my memory usage?", "memory_usage"),
    Scenario("disk_usage", "What's my disk usage?", "disk_usage"),
    Scenario("system_information", "Show system information", "system_info"),
)


async def benchmark_suite(iterations: int, warmup: int) -> dict[str, Any]:
    if iterations < 1:
        raise ValueError("iterations must be at least one")
    if warmup < 0:
        raise ValueError("warmup cannot be negative")

    harness = await build_harness()
    try:
        results: dict[str, Any] = {}
        for scenario in SCENARIOS:
            for _ in range(warmup):
                await run_once(harness, scenario.query, scenario.expected_action)
            timings = [await run_once(harness, scenario.query, scenario.expected_action) for _ in range(iterations)]
            results[scenario.name] = {
                "query": scenario.query,
                "expected_action": scenario.expected_action,
                **summarize(timings),
            }

        return {
            "schema_version": "1.0.0",
            "benchmark": "guarded_local_status_suite",
            "scope": (
                "Ready-daemon local planning, routing, policy, real read-only execution, "
                "postcondition verification, and response shaping"
            ),
            "environment": {
                "operating_system": platform.system(),
                "operating_system_release": platform.release(),
                "python": platform.python_version(),
                "warmup_iterations_per_scenario": warmup,
            },
            "scenarios": results,
            "model_generate_calls": harness.model.generate_calls,
            "limitations": [
                "Measures four deterministic local status intents with in-memory transport.",
                "Does not measure model-backed planning, UI rendering, network, browser, voice, camera, TTS, or neural hardware.",
                "Host state and operating-system APIs affect timings.",
            ],
        }
    finally:
        await harness.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = asyncio.run(benchmark_suite(args.iterations, args.warmup))
    if args.json:
        print(json.dumps(report, indent=2))
        return
    for name, scenario in report["scenarios"].items():
        print(f"{name}: median={scenario['median_ms']}ms p95={scenario['p95_ms']}ms p99={scenario['p99_ms']}ms")
    print(f"model_generate_calls: {report['model_generate_calls']}")


if __name__ == "__main__":
    main()
