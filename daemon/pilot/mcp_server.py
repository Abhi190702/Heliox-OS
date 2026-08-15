"""Local Model Context Protocol bridge for Heliox OS.

The MCP process is intentionally separate from the public documentation MCP.
It speaks MCP over stdio to a trusted local host, then uses a rotated,
least-privilege credential to call a small daemon RPC allow-list. It cannot
approve plans, edit configuration, read API keys, or invoke the daemon's raw
``execute`` method.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Protocol

import websockets
from mcp.server import MCPServer
from mcp_types import ToolAnnotations

from pilot import __version__
from pilot.config import RUNTIME_DIR, PilotConfig

logger = logging.getLogger("pilot.mcp")


def _package_version() -> str:
    """Return the source/package version used by the running MCP process."""
    return __version__


_READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
_MODEL_READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=True,
)
_SUBMIT = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
    openWorldHint=True,
)
_CANCEL = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


class DaemonRpcError(RuntimeError):
    """A safe, user-visible local daemon connection or RPC failure."""


class RpcClient(Protocol):
    async def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]: ...


class HelioxDaemonClient:
    """One-request authenticated client for the local Heliox WebSocket RPC."""

    def __init__(
        self,
        *,
        uri: str | None = None,
        token_file: str | Path | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        config = PilotConfig.load()
        host = config.server.host
        if host in {"0.0.0.0", "::", "[::]"}:
            host = "127.0.0.1"
        self._uri = uri or f"ws://{host}:{config.server.port}"
        self._token_file = Path(token_file) if token_file else RUNTIME_DIR / "mcp_auth_token"
        self._timeout_seconds = timeout_seconds

    def _read_token(self) -> str:
        try:
            token = self._token_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise DaemonRpcError("Cannot connect to Heliox OS. Start the desktop app or daemon first.") from exc
        if not token:
            raise DaemonRpcError("The local Heliox MCP credential is empty; restart the daemon.")
        return token

    async def _response_for(self, websocket: Any, request_id: str) -> dict[str, Any]:
        for _ in range(100):
            raw = await asyncio.wait_for(websocket.recv(), timeout=self._timeout_seconds)
            try:
                payload = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                continue
            if payload.get("id") != request_id:
                continue
            error = payload.get("error")
            if isinstance(error, dict):
                message = str(error.get("message") or "Heliox daemon RPC failed")
                raise DaemonRpcError(message)
            result = payload.get("result")
            if not isinstance(result, dict):
                raise DaemonRpcError("Heliox daemon returned an invalid RPC result.")
            return result
        raise DaemonRpcError("Heliox daemon did not return a matching RPC response.")

    async def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        token = self._read_token()
        auth_id = f"auth-{uuid.uuid4()}"
        request_id = f"mcp-{uuid.uuid4()}"
        try:
            async with websockets.connect(
                self._uri,
                open_timeout=self._timeout_seconds,
                close_timeout=2,
                max_size=4 * 1024 * 1024,
            ) as websocket:
                await websocket.send(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "method": "auth",
                            "params": {"token": token},
                            "id": auth_id,
                        }
                    )
                )
                auth = await self._response_for(websocket, auth_id)
                if auth.get("role") != "mcp_local":
                    raise DaemonRpcError("The daemon rejected the local MCP identity.")

                await websocket.send(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "method": method,
                            "params": params or {},
                            "id": request_id,
                        }
                    )
                )
                return await self._response_for(websocket, request_id)
        except DaemonRpcError:
            raise
        except (OSError, TimeoutError, websockets.exceptions.WebSocketException) as exc:
            raise DaemonRpcError("Cannot connect to the local Heliox daemon. Start Heliox OS and try again.") from exc


def create_mcp_server(client: RpcClient | None = None) -> MCPServer:
    """Build the local stdio MCP server, optionally with an injected test client."""

    daemon = client or HelioxDaemonClient()
    mcp = MCPServer(
        name="heliox-local",
        title="Heliox OS Local Control",
        description="Approval-gated local desktop automation through Heliox OS.",
        version=_package_version(),
        website_url="https://www.helioxos.dev",
        instructions=(
            "This server controls only the current user's local Heliox daemon. "
            "preview_heliox_task is advisory. submit_heliox_task returns before execution; "
            "the user must review every proposed action in the Heliox UI. Never claim a "
            "submitted task completed until get_heliox_task_status returns a terminal result. "
            "No MCP tool can approve a task."
        ),
    )

    @mcp.tool(
        title="Check Heliox health",
        description="Check whether the local Heliox daemon is reachable and healthy.",
        annotations=_READ_ONLY,
        structured_output=True,
    )
    async def heliox_health() -> dict[str, Any]:
        return await daemon.call("health")

    @mcp.tool(
        title="Get Heliox system status",
        description="Read the local daemon's current high-level system status.",
        annotations=_READ_ONLY,
        structured_output=True,
    )
    async def get_heliox_system_status() -> dict[str, Any]:
        return await daemon.call("system_status")

    @mcp.tool(
        title="List Heliox capabilities",
        description="List the action types and agents exposed by the running Heliox daemon.",
        annotations=_READ_ONLY,
        structured_output=True,
    )
    async def list_heliox_capabilities() -> dict[str, Any]:
        return await daemon.call("capabilities")

    @mcp.tool(
        title="Preview a Heliox task",
        description=(
            "Ask Heliox to produce a side-effect-free advisory plan. The submitted task is "
            "replanned later and every resulting action requires visible user approval."
        ),
        annotations=_MODEL_READ_ONLY,
        structured_output=True,
    )
    async def preview_heliox_task(input: str, session_id: str = "default") -> dict[str, Any]:
        return await daemon.call(
            "mcp_plan_task",
            {"input": input, "session_id": session_id},
        )

    @mcp.tool(
        title="Submit a Heliox task",
        description=(
            "Submit a task to the full Heliox planner, policy, approval, execution, and "
            "verification pipeline. Returns a task id; execution cannot proceed until the "
            "user approves every proposed action in the Heliox UI."
        ),
        annotations=_SUBMIT,
        structured_output=True,
    )
    async def submit_heliox_task(input: str, session_id: str = "default") -> dict[str, Any]:
        return await daemon.call(
            "mcp_submit_task",
            {"input": input, "session_id": session_id},
        )

    @mcp.tool(
        title="Get a Heliox task result",
        description=(
            "Read approval, execution, cancellation, and verified terminal result state for a "
            "task previously submitted through this local MCP."
        ),
        annotations=_READ_ONLY,
        structured_output=True,
    )
    async def get_heliox_task_status(task_id: str) -> dict[str, Any]:
        return await daemon.call("mcp_task_status", {"task_id": task_id})

    @mcp.tool(
        title="Cancel a Heliox task",
        description=(
            "Request safe cancellation of a task created through this local MCP. This tool "
            "cannot cancel tasks created directly in the Heliox UI."
        ),
        annotations=_CANCEL,
        structured_output=True,
    )
    async def cancel_heliox_task(task_id: str) -> dict[str, Any]:
        return await daemon.call("mcp_cancel_task", {"task_id": task_id})

    return mcp


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Heliox OS MCP server over stdio")
    parser.add_argument("--daemon-url", default=None, help="Override the local daemon WebSocket URL")
    parser.add_argument("--token-file", default=None, help="Override the rotated MCP token file")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    server = create_mcp_server(HelioxDaemonClient(uri=args.daemon_url, token_file=args.token_file))
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
