"""Role-separated authentication policy for local daemon WebSocket clients."""

from __future__ import annotations

import hmac
from enum import StrEnum


class RpcClientRole(StrEnum):
    UI = "ui"
    NEURAL_SIDECAR = "neural_sidecar"


NEURAL_SIDECAR_METHODS = frozenset(
    {
        "neural_status",
        "neural_connect",
        "neural_finish_calibration",
        "neural_intent_preview",
        "neural_disarm",
    }
)


def authenticate_rpc_client(
    provided_token: object,
    *,
    ui_token: str,
    neural_token: str,
) -> RpcClientRole | None:
    """Classify a token in constant time without allowing empty credentials."""

    if not isinstance(provided_token, str) or not provided_token:
        return None
    ui_match = bool(ui_token) and hmac.compare_digest(provided_token, ui_token)
    neural_match = bool(neural_token) and hmac.compare_digest(provided_token, neural_token)
    if ui_match:
        return RpcClientRole.UI
    if neural_match:
        return RpcClientRole.NEURAL_SIDECAR
    return None


def rpc_method_allowed(role: RpcClientRole, method: str) -> bool:
    """The UI retains its existing API; neurod receives an explicit allow-list."""

    return role == RpcClientRole.UI or method in NEURAL_SIDECAR_METHODS
