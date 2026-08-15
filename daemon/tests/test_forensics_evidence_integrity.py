import json
from pathlib import Path

import pytest

from pilot.actions import Action, ActionType, LogAnalyzeParams
from pilot.agents.executor import Executor
from pilot.security.audit import AuditLogger
from pilot.security.permissions import PermissionChecker
from pilot.security.validator import ActionValidator


def _executor(default_config, tmp_path: Path) -> Executor:
    return Executor(
        default_config,
        ActionValidator(default_config),
        PermissionChecker(default_config),
        AuditLogger(audit_file=tmp_path / "audit.log"),
    )


def _action(path: Path) -> Action:
    return Action(
        action_type=ActionType.LOG_ANALYZE,
        parameters=LogAnalyzeParams(log_path=str(path), llm_contextual=False),
    )


async def test_missing_log_fails_without_manufacturing_evidence(default_config, tmp_path):
    missing = tmp_path / "missing.log"

    with pytest.raises(FileNotFoundError, match="Log source was not found"):
        await _executor(default_config, tmp_path)._exec_log_analyze(_action(missing))

    assert missing.exists() is False


async def test_real_log_is_analyzed_and_reported_as_real_evidence(default_config, tmp_path):
    log = tmp_path / "auth.log"
    log.write_text(
        "May 25 14:03:15 server sshd[1235]: Failed password for admin from 192.0.2.10 port 49152 ssh2\n",
        encoding="utf-8",
    )

    raw = await _executor(default_config, tmp_path)._exec_log_analyze(_action(log))
    report = json.loads(raw)

    assert report["summary"].startswith("Log analysis completed")
    assert report["timeline"]
    assert "192.0.2.10" in report["timeline"][0]


async def test_binary_windows_event_log_requires_explicit_export(default_config, tmp_path):
    evtx = tmp_path / "Security.evtx"
    evtx.write_bytes(b"ElfFile\x00binary")

    with pytest.raises(ValueError, match="export the Event Viewer log"):
        await _executor(default_config, tmp_path)._exec_log_analyze(_action(evtx))
