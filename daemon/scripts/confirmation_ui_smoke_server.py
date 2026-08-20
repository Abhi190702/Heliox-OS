"""Deterministic daemon used for the manual Svelte confirmation smoke test."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from urllib.request import urlopen

import websockets

from pilot.actions import Action, ActionPlan, ActionType, BrowserParams
from pilot.agents.executor import Executor
from pilot.config import PilotConfig
from pilot.security.audit import AuditLogger
from pilot.security.permissions import PermissionChecker
from pilot.security.validator import ActionValidator
from pilot.server import PilotServer
from pilot.system.browser import browser_close, browser_get_page_info


def _record(path: Path, payload: dict) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, sort_keys=True) + "\n")


async def run(evidence_path: Path, token: str, target_url: str) -> None:
    config = PilotConfig()
    config.server.auth_token = token
    server = PilotServer(config)
    executor = Executor(
        config,
        ActionValidator(config),
        PermissionChecker(config),
        AuditLogger(evidence_path.with_suffix(".audit.jsonl")),
    )
    command_number = 0
    browser_execute_count = 0

    async def execute(params, ws):
        nonlocal browser_execute_count, command_number
        command_number += 1
        plan_id = f"ui-smoke-{command_number}"
        action = Action(
            action_type=ActionType.BROWSER_NAVIGATE,
            target=target_url,
            parameters=BrowserParams(url=target_url),
        )
        plan = ActionPlan(
            actions=[action],
            explanation="Navigate the controlled browser to the local Heliox smoke page",
            raw_input=str(params.get("input", "")),
        )
        confirmed, approved, required = await server._wait_for_confirmation(
            plan_id,
            plan,
            ws,
            reason="Live UI-to-daemon browser-command smoke test.",
            force_all_actions=True,
        )
        if not confirmed or approved != required:
            _record(
                evidence_path,
                {
                    "browser_execute_count": browser_execute_count,
                    "decision": "denied",
                    "executed": False,
                    "plan_id": plan_id,
                },
            )
            return {"status": "cancelled", "message": f"DENIED {plan_id}: browser command did not run"}

        results = await executor.execute(plan, plan_id=plan_id, user_confirmed=True)
        result = results[0]
        if result.success:
            browser_execute_count += 1
        page_info = json.loads(await browser_get_page_info()) if result.success else None
        _record(
            evidence_path,
            {
                "browser_execute_count": browser_execute_count,
                "browser_page": page_info,
                "decision": "approved",
                "executed": result.success,
                "output": result.output,
                "plan_id": plan_id,
            },
        )
        return {
            "status": "success" if result.success else "error",
            "message": (
                f"APPROVED {plan_id}: browser command executed; page={page_info}"
                if result.success
                else f"APPROVED {plan_id}: browser command failed: {result.error}"
            ),
        }

    server._handlers = {"execute": execute, "confirm": server._handle_confirm}
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.unlink(missing_ok=True)
    _record(evidence_path, {"event": "ready", "target_url": target_url})
    try:
        async with websockets.serve(server._handle_connection, "127.0.0.1", 8785):
            await asyncio.Future()
    finally:
        await browser_close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--token")
    parser.add_argument("--target-url", default="http://127.0.0.1:1420/")
    args = parser.parse_args()
    token = args.token
    if not token:
        with urlopen(  # noqa: S310 - fixed loopback smoke endpoint
            "http://127.0.0.1:1420/api/auth_token",
            timeout=5,
        ) as response:
            token = response.read().decode("utf-8").strip()
    if not token:
        parser.error("the resolved token is empty")
    asyncio.run(run(args.evidence, token, args.target_url))


if __name__ == "__main__":
    main()
