import pytest

from pilot.actions import Action, ActionType, CodeExecParams
from pilot.agents.executor import Executor, _code_execution_error
from pilot.config import PilotConfig


def test_nonzero_exit_code_is_a_failure_even_with_stdout():
    error = _code_execution_error("hello\n[STDERR]\ndocker failed\n[EXIT CODE: 125]")

    assert error is not None
    assert "exited with code 125" in error
    assert "docker failed" in error


def test_explicit_backend_error_is_a_failure():
    assert _code_execution_error("ERROR: Sandbox timed out after 30s") == "ERROR: Sandbox timed out after 30s"


def test_stderr_without_nonzero_exit_is_not_misreported_as_failure():
    assert _code_execution_error("done\n[STDERR]\nwarning only") is None


def test_zero_exit_marker_is_not_a_failure():
    assert _code_execution_error("done\n[EXIT CODE: 0]") is None


@pytest.mark.asyncio
async def test_code_execute_nonzero_exit_becomes_failed_action(monkeypatch):
    async def _failed_execute(*args, **kwargs):
        return "[STDERR]\nunknown flag: --no-new-privileges\n[EXIT CODE: 125]"

    class _Model:
        async def generate(self, *args, **kwargs):
            return "print('retry')"

    monkeypatch.setattr("pilot.system.code_exec.execute_code", _failed_execute)
    executor = object.__new__(Executor)
    executor._config = PilotConfig()
    executor._model = _Model()
    executor._last_output = ""
    executor._largest_output = ""
    executor._stress_gate = None
    executor._dispatch_table = {ActionType.CODE_EXECUTE: executor._exec_code_execute}
    action = Action(
        action_type=ActionType.CODE_EXECUTE,
        target="python",
        parameters=CodeExecParams(code="print('hello')", language="python"),
    )

    result = await executor._execute_single(action, snapshot_id=None)

    assert result.success is False
    assert "exited with code 125" in (result.error or "")
