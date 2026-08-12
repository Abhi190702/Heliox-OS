"""Evaluate deterministic intent routing accuracy and latency.

This suite never executes an action. It checks whether bounded local utterances
select the intended action and whether ambiguous workflow language correctly
falls through to model-backed planning.

Run from ``daemon``:
    python benchmarks/intent_dispatch_suite.py --json
"""

from __future__ import annotations

import argparse
import json
import platform
import time
from dataclasses import dataclass
from typing import Any

from benchmarks.react_latency import summarize
from pilot.agents.planner import Planner


@dataclass(frozen=True, slots=True)
class IntentCase:
    category: str
    utterance: str
    expected_actions: tuple[str, ...]


def _case(category: str, utterance: str, *actions: str) -> IntentCase:
    return IntentCase(category, utterance, actions)


CASES = (
    _case("url", "open https://example.com", "browser_navigate"),
    _case("url", "visit github.com", "browser_navigate"),
    _case("url", "go to docs.python.org/3/", "browser_navigate"),
    _case("url", "navigate to https://helioxos.dev", "browser_navigate"),
    _case("url", "launch wikipedia.org", "browser_navigate"),
    _case("url", "browse https://example.org/path", "browser_navigate"),
    _case("browser_click", "click Launch", "browser_click_text"),
    _case("browser_click", "click on Launch on the website", "browser_click_text"),
    _case("browser_click", "press the Continue button", "browser_click_text"),
    _case("browser_click", "choose Learn more on the page", "browser_click_text"),
    _case("browser_click", "select Sign in", "browser_click_text"),
    _case("browser_click", "click the Download option on the webpage", "browser_click_text"),
    _case("screen", "screenshot", "screenshot"),
    _case("screen", "take a screenshot", "screenshot"),
    _case("screen", "screenshot and describe it", "screen_analyze"),
    _case("screen", "take a screenshot and describe it", "screen_analyze"),
    _case("screen", "what is this on my screen?", "screen_analyze"),
    _case("screen", "what am I looking at?", "screen_analyze"),
    _case("screen", "inspect my screen", "screen_analyze"),
    _case("screen", "analyze the screen", "screen_analyze"),
    _case("system_info", "show system info", "system_info"),
    _case("system_info", "true system information", "system_info"),
    _case("system_info", "display my system specs", "system_info"),
    _case("system_info", "tell me the system details", "system_info"),
    _case("usage", "what's my CPU usage?", "cpu_usage"),
    _case("usage", "show cpu usage", "cpu_usage"),
    _case("usage", "tell me my CPU usage", "cpu_usage"),
    _case("usage", "what is my memory usage?", "memory_usage"),
    _case("usage", "check RAM usage", "memory_usage"),
    _case("usage", "show my memory usage", "memory_usage"),
    _case("usage", "what's my disk usage?", "disk_usage"),
    _case("usage", "check disk usage", "disk_usage"),
    _case("usage", "tell me my disk usage", "disk_usage"),
    _case("application", "open notepad", "open_application"),
    _case("application", "launch Visual Studio Code", "open_application"),
    _case("application", "start calculator", "open_application"),
    _case("application", "run Hermes", "open_application"),
    _case("application", "open Antigravity", "open_application"),
    _case("application", "launch file explorer", "open_application"),
    _case("file_read", r"read C:\Temp\status.txt", "file_read"),
    _case("file_read", r"show contents of C:\Logs\pilot.log", "file_read"),
    _case("file_read", "inspect /var/log/syslog", "file_read"),
    _case("forensics", "analyze auth logs", "log_analyze"),
    _case("forensics", "inspect syslog for anomalies", "log_analyze"),
    _case("forensics", "review the event log for suspicious activity", "log_analyze"),
    _case("forensics", "scan nginx logs for failed logins", "log_analyze"),
    _case(
        "browser_workflow",
        "Open https://example.com, click the link labeled Learn More, then report the title and first paragraph",
        "browser_navigate",
        "browser_click_text",
        "browser_page_info",
        "browser_extract",
    ),
    _case("fallback", "run the tests"),
    _case("fallback", "start a backup"),
    _case("fallback", "open the project"),
    _case("fallback", "launch a workflow"),
    _case("fallback", "open my report"),
    _case("fallback", "open the downloads folder"),
    _case("fallback", "run a security scan"),
    _case("fallback", "start the deployment"),
    _case("fallback", "run this task"),
    _case("fallback", "open README and summarize it"),
    _case("fallback", "What is the latest world news?"),
    _case("fallback", "research system information formats and compare them"),
)


def benchmark() -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    timings_ms: list[float] = []
    category_totals: dict[str, int] = {}
    category_passes: dict[str, int] = {}

    for case in CASES:
        started = time.perf_counter_ns()
        plan = Planner._try_fast_path(case.utterance)
        timings_ms.append((time.perf_counter_ns() - started) / 1_000_000)
        actual = tuple(action.action_type.value for action in plan.actions) if plan is not None else ()
        passed = actual == case.expected_actions
        category_totals[case.category] = category_totals.get(case.category, 0) + 1
        category_passes[case.category] = category_passes.get(case.category, 0) + int(passed)
        if not passed:
            failures.append(
                {
                    "category": case.category,
                    "utterance": case.utterance,
                    "expected_actions": list(case.expected_actions),
                    "actual_actions": list(actual),
                }
            )

    passed_count = len(CASES) - len(failures)
    return {
        "schema_version": "1.0.0",
        "benchmark": "deterministic_intent_dispatch",
        "scope": "Curated bounded local intents and ambiguous fall-through controls; planning only, no execution",
        "environment": {
            "operating_system": platform.system(),
            "python": platform.python_version(),
        },
        "case_count": len(CASES),
        "passed": passed_count,
        "failed": len(failures),
        "accuracy": round(passed_count / len(CASES), 6),
        "categories": {
            name: {
                "passed": category_passes.get(name, 0),
                "total": total,
                "accuracy": round(category_passes.get(name, 0) / total, 6),
            }
            for name, total in category_totals.items()
        },
        "latency": summarize(timings_ms),
        "failures": failures,
        "limitations": [
            "The fixed corpus is a regression set, not a population-level language-understanding benchmark.",
            "Passing fall-through cases means model planning is required; it does not grade the model's later answer.",
            "Application cases grade routing only and do not prove the application is installed or launched.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = benchmark()
    if args.json:
        print(json.dumps(report, indent=2))
        return
    print(f"accuracy: {report['passed']}/{report['case_count']} ({report['accuracy']:.1%})")
    print(f"median_ms: {report['latency']['median_ms']}")
    for failure in report["failures"]:
        print(f"FAIL {failure['utterance']!r}: expected {failure['expected_actions']}, got {failure['actual_actions']}")


if __name__ == "__main__":
    main()
