"""Run the deterministic local Heliox approval demo and retain its evidence."""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = REPO_ROOT / "tauri-app" / "ui"


def _port_closed(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", port)) != 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Evidence directory (defaults under .codex-artifacts).")
    args = parser.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = (args.output or REPO_ROOT / ".codex-artifacts" / f"antler-approval-{stamp}").resolve()
    output.mkdir(parents=True, exist_ok=True)
    npm = shutil.which("npm")
    if npm is None:
        parser.error("npm is required; install the checked-in UI dependencies before running the demo")

    env = os.environ.copy()
    env["HELIOX_APPROVAL_ARTIFACT_DIR"] = str(output)
    env["HELIOX_PYTHON"] = sys.executable
    command = [npm, "run", "test:e2e:approval", "--", "--reporter=line"]
    completed = subprocess.run(command, cwd=UI_ROOT, env=env, check=False)

    cleanup = {port: _port_closed(port) for port in (1420, 8785)}
    summary = output / "claim-boundary.md"
    if summary.exists():
        with summary.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write("\n## Runner cleanup verification\n\n")
            stream.write(f"- Vite loopback port 1420 closed: `{cleanup[1420]}`.\n")
            stream.write(f"- Smoke WebSocket port 8785 closed: `{cleanup[8785]}`.\n")

    if completed.returncode != 0:
        print(f"Antler demo failed. Retained artifacts: {output}", file=sys.stderr)
        return completed.returncode
    if not all(cleanup.values()):
        print(f"Antler demo ran, but cleanup verification failed: {cleanup}", file=sys.stderr)
        return 1

    print(f"Antler demo passed. Evidence: {output}")
    print(f"Claim boundary: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
