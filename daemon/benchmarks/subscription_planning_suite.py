"""Opt-in, side-effect-free evaluation for subscription-backed Heliox planning.

This benchmark invokes the selected official CLI and therefore consumes that
account's subscription allowance. It only asks the Planner for JSON plans; it
never validates, approves, or executes an action.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pilot.agents.planner import Planner
from pilot.config import PilotConfig
from pilot.models.subscription_cli import SubscriptionCLIClient

REPO_ROOT = Path(__file__).resolve().parents[2]

CASES: dict[str, dict[str, Any]] = {
    "health_review": {
        "prompt": (
            "Perform a read-only system health review: collect CPU, memory, disk, battery, "
            "and running-process evidence, then report two prioritized observations. Do not modify anything."
        ),
        "required_any": {"system_health_review", "system_info"},
        "forbidden": {"shell_command", "shell_script", "code_execute"},
    },
    "semantic_browser": {
        "prompt": (
            "Open https://example.com in the controllable browser, inspect the visible page, choose the link that "
            "best explains the site even if I do not know its label, click it, and report the destination title."
        ),
        "required_any": {"browser_click", "browser_click_text", "mouse_click"},
        "required_all": {"browser_navigate", "browser_page_info"},
        "forbidden": {"browser_execute_js", "code_execute"},
    },
    "evidence_first_files": {
        "prompt": (
            "Find the five largest files under C:\\Users\\Public, hash each result, and prepare a concise report. "
            "Do not delete, move, rewrite, or execute any file."
        ),
        "required_any": {"file_list", "file_search", "directory_summary", "shell_command", "shell_script"},
        "forbidden": {"file_delete", "file_move", "file_write", "code_execute"},
    },
}


class EmptyMemory:
    async def get_context(self, *args: Any, **kwargs: Any) -> str:
        return ""

    async def get_history(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return []


class SubscriptionRouter:
    """Small Planner-compatible adapter that excludes execution and caching."""

    def __init__(self, config: PilotConfig) -> None:
        self._config = config
        self.client = SubscriptionCLIClient(config)

    async def generate(self, prompt: Any, **kwargs: Any) -> str:
        return await self.client.generate(prompt, **kwargs)


@dataclass
class CaseResult:
    name: str
    passed: bool
    latency_seconds: float
    model_calls: int
    action_types: list[str]
    explanation: str
    error: str
    usage: dict[str, int]
    destructive_actions: int


def _usage_delta(after: dict[str, int], before: dict[str, int]) -> dict[str, int]:
    return {key: after.get(key, 0) - before.get(key, 0) for key in sorted(set(before) | set(after))}


def evaluate_action_types(
    case: dict[str, Any],
    action_types: list[str],
    error: str,
    *,
    destructive_actions: int = 0,
) -> bool:
    if error:
        return False
    actions = set(action_types)
    required_any = set(case.get("required_any", set()))
    required_all = set(case.get("required_all", set()))
    forbidden = set(case.get("forbidden", set()))
    return (
        (not required_any or bool(actions & required_any))
        and required_all.issubset(actions)
        and not bool(actions & forbidden)
        and destructive_actions == 0
    )


async def run_case(name: str, case: dict[str, Any], planner: Planner, router: SubscriptionRouter) -> CaseResult:
    usage_before = dict(router.client.total_usage)
    generations_before = router.client.generation_count
    started = time.perf_counter()
    plan = await planner.plan(case["prompt"], session_id=f"subscription-benchmark:{name}", force_model=True)
    latency = time.perf_counter() - started
    action_types = [action.action_type.value for action in plan.actions]
    destructive_actions = sum(bool(action.destructive or action.is_irreversible) for action in plan.actions)
    error = plan.error or ""
    usage = _usage_delta(router.client.total_usage, usage_before)
    usage.update(
        {
            key: router.client.last_usage[key]
            for key in ("heliox_prompt_chars", "heliox_estimated_prompt_tokens")
            if key in router.client.last_usage
        }
    )
    return CaseResult(
        name=name,
        passed=evaluate_action_types(case, action_types, error, destructive_actions=destructive_actions),
        latency_seconds=round(latency, 3),
        model_calls=router.client.generation_count - generations_before,
        action_types=action_types,
        explanation=plan.explanation,
        error=error,
        usage=usage,
        destructive_actions=destructive_actions,
    )


async def benchmark(provider: str, model: str, selected_cases: list[str]) -> dict[str, Any]:
    config = PilotConfig()
    config.model.provider = "subscription"
    config.model.subscription_provider = provider
    config.model.subscription_model = model
    router = SubscriptionRouter(config)
    status = await router.client.status(provider, refresh=True)
    if not status.get("subscription"):
        raise RuntimeError(status.get("message") or "Subscription login is unavailable.")
    planner = Planner(router, EmptyMemory())
    results = [await run_case(name, CASES[name], planner, router) for name in selected_cases]
    latencies = [item.latency_seconds for item in results]
    return {
        "schema_version": "1.0.0",
        "captured_at": datetime.now(UTC).isoformat(),
        "source_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "scope": "side-effect-free planning only; no action was executed",
        "claim_boundary": (
            "One developer-machine subscription planning sample. It does not measure action execution, "
            "provider availability for other accounts, universal latency, plan correctness outside the fixed cases, "
            "or Claude Code because that CLI was not installed for this capture."
        ),
        "provider": provider,
        "provider_cli_version": status.get("version", ""),
        "model": model or "provider-default",
        "case_count": len(results),
        "passed": sum(item.passed for item in results),
        "median_latency_seconds": round(statistics.median(latencies), 3) if latencies else 0,
        "total_usage": dict(router.client.total_usage),
        "results": [asdict(item) for item in results],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("codex", "claude"), default="codex")
    parser.add_argument("--model", default="", help="Blank uses the official CLI default")
    parser.add_argument("--output", type=Path, help="Write the JSON report to this path instead of stdout")
    parser.add_argument(
        "--case",
        action="append",
        choices=tuple(CASES),
        dest="cases",
        help="Run one named case; repeat for multiple cases. Default: all cases.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    selected = args.cases or list(CASES)
    report = asyncio.run(benchmark(args.provider, args.model, selected))
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"Wrote subscription planning evidence to {args.output}")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
