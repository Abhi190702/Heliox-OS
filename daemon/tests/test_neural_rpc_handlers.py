from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from pilot.config import PilotConfig
from pilot.security.rpc_identity import RpcClientRole
from pilot.server import PilotServer


@pytest.fixture
def server() -> tuple[PilotServer, MagicMock, MagicMock]:
    instance = PilotServer(PilotConfig())
    instance._neural_controller = MagicMock()
    instance._neural_controller.status = AsyncMock(
        return_value={"connected": False, "capabilities": {"physical_control": False}}
    )
    instance._neural_controller.connect = AsyncMock(return_value={"connected": True})
    instance._neural_controller.arm = AsyncMock(return_value={"state": "armed_safe_ui"})
    instance._neural_controller.commit = AsyncMock(return_value={"status": "committed"})
    instance._neural_controller.disarm = AsyncMock(return_value={"state": "observe_only"})
    ui = MagicMock()
    sidecar = MagicMock()
    instance._client_roles[ui] = RpcClientRole.UI
    instance._client_roles[sidecar] = RpcClientRole.NEURAL_SIDECAR
    return instance, ui, sidecar


@pytest.mark.asyncio
async def test_status_is_shared_but_physical_authority_is_explicitly_false(server) -> None:
    instance, ui, sidecar = server
    for client in (ui, sidecar):
        result = await instance._handle_neural_status({}, client)
        assert result["status"] == "ok"
        assert result["capabilities"]["physical_control"] is False


@pytest.mark.asyncio
async def test_connect_is_sidecar_only_and_strictly_parsed(server) -> None:
    instance, ui, sidecar = server
    descriptor = {
        "session_id": str(uuid.uuid4()),
        "source_id": "synthetic-test",
        "board_kind": "synthetic",
        "transport": "synthetic",
        "sample_rate_hz": 250,
        "channel_count": 2,
        "channel_names": ["O1", "Oz"],
        "reference": "synthetic-reference",
        "sequence_start": 0,
        "started_monotonic_ns": 1,
    }
    result = await instance._handle_neural_connect({"descriptor": descriptor}, sidecar)
    assert result["status"] == "ok"
    instance._neural_controller.connect.assert_awaited_once()

    with pytest.raises(PermissionError):
        await instance._handle_neural_connect({"descriptor": descriptor}, ui)
    rejected = await instance._handle_neural_connect({"descriptor": {**descriptor, "raw_eeg": [[1.0]]}}, sidecar)
    assert rejected["status"] == "rejected"


@pytest.mark.asyncio
async def test_arming_and_commit_require_ui_role_and_explicit_user_flag(server) -> None:
    instance, ui, sidecar = server
    session_id = str(uuid.uuid4())
    result = await instance._handle_neural_arm(
        {"session_id": session_id, "scope": "navigate", "user_authorized": True}, ui
    )
    assert result["status"] == "ok"
    assert instance._neural_controller.arm.await_args.kwargs["non_neural_authorized"] is True
    with pytest.raises(PermissionError):
        await instance._handle_neural_arm(
            {"session_id": session_id, "scope": "navigate", "user_authorized": True},
            sidecar,
        )

    commit = await instance._handle_neural_commit(
        {
            "preview_id": str(uuid.uuid4()),
            "expected_revision": 4,
            "world_model_approved": True,
        },
        ui,
    )
    assert commit["status"] == "committed"
    with pytest.raises(PermissionError):
        await instance._handle_neural_commit({"preview_id": str(uuid.uuid4()), "expected_revision": 4}, sidecar)


@pytest.mark.asyncio
async def test_disarm_is_available_to_both_roles_and_reason_is_bounded(server) -> None:
    instance, ui, sidecar = server
    await instance._handle_neural_disarm({"reason": "disconnect"}, sidecar)
    await instance._handle_neural_disarm({"reason": "x" * 1000}, ui)
    reasons = [call.kwargs["reason"] for call in instance._neural_controller.disarm.await_args_list]
    assert reasons[0] == "disconnect"
    assert len(reasons[1]) <= 120
