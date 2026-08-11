"""Role-separated authentication policy for local daemon WebSocket clients."""

from __future__ import annotations

import hashlib
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
        "neural_observation",
        "neural_disarm",
        "neural_stimulus_markers",
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


def derive_neural_signing_key(neural_token: str) -> bytes:
    """Derive a domain-separated intent MAC key without sharing the UI token."""

    if len(neural_token) < 32:
        raise ValueError("neural sidecar token is too short")
    return hmac.new(
        neural_token.encode("utf-8"),
        b"heliox-neural-intent-signing-v1",
        hashlib.sha256,
    ).digest()
