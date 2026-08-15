"""Contracts for the single production cognitive runtime."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_SOURCE = REPO_ROOT / "daemon" / "pilot" / "server.py"


def test_server_uses_canonical_cognitive_engine_without_legacy_hub():
    source = SERVER_SOURCE.read_text(encoding="utf-8")

    assert "from pilot.cognitive.cognitive_engine import CognitiveEngine" in source
    assert "from pilot.cognitive.hub import CognitiveHub" not in source
    assert "self._cognitive_hub =" not in source


def test_cognitive_engine_is_connected_to_live_consumers():
    source = SERVER_SOURCE.read_text(encoding="utf-8")

    assert "self._screen_vision._cognitive_engine = self._cognitive_engine" in source
    assert "StressGate(self._cognitive_engine)" in source
    assert "IntentPredictor(self._cognitive_engine)" in source
