"""Public evidence must stay generated from current repository authorities."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _generate(repo_root: Path, output: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "generate_public_proof.py"),
            "--output",
            str(output),
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def test_public_proof_exposes_evidence_boundaries(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    output = tmp_path / "proof.md"
    _generate(repo_root, output)
    text = output.read_text(encoding="utf-8")

    assert "157" in text
    assert "executor result without an independent post-condition" in text
    assert "not proven live brain control" in text
    assert "result is intentionally linked rather than copied as “green”" in text
    assert "f2df192" in text
    assert "59/59 cases" in text
    assert "36,000 training" in text
    assert "Event-loop responsiveness" in text
    assert "software-benchmarks-2026-08-13.json" in text


def test_committed_public_proof_is_current(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    output = tmp_path / "proof.md"
    _generate(repo_root, output)
    assert output.read_bytes() == (repo_root / "proof.md").read_bytes()
