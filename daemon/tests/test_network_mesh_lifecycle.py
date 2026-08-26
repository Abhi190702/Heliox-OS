import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from pilot.network.mesh import HelioxMesh


def _mesh() -> HelioxMesh:
    config = SimpleNamespace(
        port=8786,
        collab_exec_enabled=False,
        skill_sync_enabled=False,
    )
    plugin_manager = SimpleNamespace(list_plugins=lambda: [])
    return HelioxMesh(config, MagicMock(), plugin_manager)


@pytest.mark.asyncio
async def test_mesh_stop_cancels_owned_background_tasks():
    mesh = _mesh()
    stopped = False

    async def long_running_task() -> None:
        nonlocal stopped
        try:
            await asyncio.sleep(60)
        finally:
            stopped = True

    mesh._running = True
    mesh._spawn(long_running_task())

    await asyncio.sleep(0)
    await mesh.stop()

    assert stopped is True
    assert mesh._tasks == set()
    assert mesh._running is False


@pytest.mark.asyncio
async def test_peer_discovered_after_stop_does_not_start_connection():
    mesh = _mesh()
    mesh._connect_to_peer = AsyncMock()

    mesh._on_peer_found(SimpleNamespace(peer_id="peer-1"))
    await asyncio.sleep(0)

    mesh._connect_to_peer.assert_not_awaited()
