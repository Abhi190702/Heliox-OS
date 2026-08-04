from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from pilot.system import window_mgr
from pilot.system.platform_detect import Platform


@pytest.mark.asyncio
async def test_windows_focus_uses_verified_app_activation(monkeypatch):
    run = AsyncMock(return_value=(0, "42", ""))
    monkeypatch.setattr(window_mgr, "CURRENT_PLATFORM", Platform.WINDOWS)
    monkeypatch.setattr(window_mgr, "run_powershell", run)

    result = await window_mgr.window_focus(title="Owner's Notepad")

    script = run.await_args.args[0]
    assert "$target = 'Owner''s Notepad'" in script
    assert "AppActivate([int]$p.Id)" in script
    assert "GetWindowThreadProcessId" in script
    assert "$foregroundPid -ne $p.Id" in script
    assert result == "Focused window: Owner's Notepad"


@pytest.mark.asyncio
async def test_windows_focus_rejects_unverified_activation(monkeypatch):
    monkeypatch.setattr(window_mgr, "CURRENT_PLATFORM", Platform.WINDOWS)
    monkeypatch.setattr(
        window_mgr,
        "run_powershell",
        AsyncMock(return_value=(1, "", "Window activation was rejected")),
    )

    with pytest.raises(RuntimeError, match="activation was rejected"):
        await window_mgr.window_focus(process_name="Notepad")
