"""Tests for the repository-wide release metadata gate."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_release.py"
SPEC = importlib.util.spec_from_file_location("check_release", SCRIPT)
assert SPEC and SPEC.loader
check_release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_release)


def test_current_repository_release_versions_are_synchronized():
    assert check_release.validate_release(ROOT, "v0.10.0") == "0.10.0"


def test_release_gate_rejects_version_mismatch(monkeypatch):
    monkeypatch.setattr(
        check_release,
        "collect_versions",
        lambda _root: {"daemon": "0.10.0", "desktop": "0.9.0"},
    )

    with pytest.raises(ValueError, match="inconsistent"):
        check_release.validate_release(ROOT)


def test_release_gate_rejects_wrong_tag(monkeypatch):
    monkeypatch.setattr(
        check_release,
        "collect_versions",
        lambda _root: {"daemon": "0.10.0", "desktop": "0.10.0"},
    )

    with pytest.raises(ValueError, match="does not match"):
        check_release.validate_release(ROOT, "v0.10.1")
