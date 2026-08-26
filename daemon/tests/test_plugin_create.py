from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import pilot.plugins
import pilot.server as server_module
from pilot.config import PilotConfig
from pilot.server import PilotServer


@pytest.mark.asyncio
async def test_plugin_create_rejects_placeholder_or_invalid_implementations(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server_module, "PLUGINS_DIR", tmp_path)
    server = PilotServer(PilotConfig())

    missing_code = await server._handle_plugin_create(
        {"name": "missing-code", "tools": [{"name": "run"}], "code": ""},
        MagicMock(),
    )
    invalid_code = await server._handle_plugin_create(
        {"name": "invalid-code", "tools": [{"name": "run"}], "code": "def nope(:"},
        MagicMock(),
    )
    missing_handler = await server._handle_plugin_create(
        {"name": "missing-handler", "tools": [{"name": "run"}], "code": "def other():\n    pass"},
        MagicMock(),
    )

    assert "placeholder" in missing_code["error"]
    assert "invalid Python" in invalid_code["error"]
    assert "handle_tool" in missing_handler["error"]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_plugin_create_removes_partial_directory_when_signing_fails(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server_module, "PLUGINS_DIR", tmp_path)
    monkeypatch.setattr(pilot.plugins, "sign_plugin_directory", MagicMock(side_effect=RuntimeError("signing failed")))
    server = PilotServer(PilotConfig())

    result = await server._handle_plugin_create(
        {
            "name": "unsigned-plugin",
            "tools": [{"name": "run", "description": "Run the tool", "inputs": []}],
            "code": "def handle_tool(tool_name, params):\n    return {'status': 'ok'}",
        },
        MagicMock(),
    )

    assert "signing failed" in result["error"]
    assert not (tmp_path / "unsigned-plugin").exists()
