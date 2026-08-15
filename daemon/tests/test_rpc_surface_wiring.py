"""Cross-language contracts for the desktop, neural sidecar, and local MCP RPC surfaces."""

from __future__ import annotations

import re
from pathlib import Path

from pilot.security.rpc_identity import MCP_LOCAL_METHODS, NEURAL_SIDECAR_METHODS

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_SOURCE = REPO_ROOT / "daemon" / "pilot" / "server.py"
UI_SOURCE = REPO_ROOT / "tauri-app" / "ui" / "src"
MCP_SOURCE = REPO_ROOT / "daemon" / "pilot" / "mcp_server.py"


def _server_methods() -> set[str]:
    source = SERVER_SOURCE.read_text(encoding="utf-8")
    return set(re.findall(r'^\s*"([a-z][a-z0-9_]*)":\s*self\._handle_[a-z0-9_]+,?$', source, re.MULTILINE))


def _literal_ui_calls() -> set[str]:
    methods: set[str] = set()
    for path in UI_SOURCE.rglob("*"):
        if path.suffix not in {".ts", ".svelte"} or ".test." in path.name:
            continue
        source = path.read_text(encoding="utf-8")
        methods.update(re.findall(r'\bcall(?:<[^;\n]+?>)?\(\s*["\']([a-z][a-z0-9_]*)["\']', source))
    return methods


def test_every_literal_desktop_rpc_call_has_a_daemon_handler():
    missing = sorted(_literal_ui_calls() - _server_methods())
    assert missing == [], f"UI calls missing daemon handlers: {missing}"


def test_role_scoped_rpc_allowlists_only_reference_real_handlers():
    methods = _server_methods()
    assert sorted(MCP_LOCAL_METHODS - methods) == []
    assert sorted(NEURAL_SIDECAR_METHODS - methods) == []


def test_local_mcp_bridge_only_calls_role_scoped_methods():
    source = MCP_SOURCE.read_text(encoding="utf-8")
    called = set(re.findall(r'daemon\.call\(\s*["\']([a-z][a-z0-9_]*)["\']', source))

    assert called
    assert sorted(called - MCP_LOCAL_METHODS) == []
