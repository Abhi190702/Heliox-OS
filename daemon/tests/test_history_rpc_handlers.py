import pytest

from pilot.config import PilotConfig
from pilot.server import PilotServer


class _MemoryHistory:
    async def get_history(self, *, limit: int, offset: int):
        return [{"id": 1, "user_input": "inspect system", "success": True}]


class _PlanHistory:
    async def get_list(self, *, limit: int, offset: int, status_filter: str | None):
        return [{"plan_id": "plan-1", "execution_status": "success"}]


@pytest.mark.asyncio
async def test_activity_history_has_explicit_success_status():
    server = PilotServer(PilotConfig())
    server._memory = _MemoryHistory()

    result = await server._handle_get_history({"limit": 10, "offset": 0}, ws=None)

    assert result["status"] == "ok"
    assert result["entries"][0]["success"] is True


@pytest.mark.asyncio
async def test_plan_history_has_explicit_success_status():
    server = PilotServer(PilotConfig())
    server._plan_history = _PlanHistory()

    result = await server._handle_get_plan_history({"limit": 10, "offset": 0}, ws=None)

    assert result["status"] == "ok"
    assert result["plans"][0]["plan_id"] == "plan-1"


@pytest.mark.asyncio
async def test_unavailable_plan_history_has_explicit_error_status():
    server = PilotServer(PilotConfig())
    server._plan_history = None

    result = await server._handle_get_plan_history({}, ws=None)

    assert result["status"] == "error"
    assert result["plans"] == []
