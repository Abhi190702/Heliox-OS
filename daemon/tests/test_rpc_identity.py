from pilot.security.rpc_identity import (
    RpcClientRole,
    authenticate_rpc_client,
    rpc_method_allowed,
)


def test_rpc_tokens_create_distinct_roles_without_empty_fallback() -> None:
    assert authenticate_rpc_client("ui-secret", ui_token="ui-secret", neural_token="neural-secret") == RpcClientRole.UI
    assert (
        authenticate_rpc_client("neural-secret", ui_token="ui-secret", neural_token="neural-secret")
        == RpcClientRole.NEURAL_SIDECAR
    )
    assert authenticate_rpc_client("", ui_token="", neural_token="") is None
    assert authenticate_rpc_client(None, ui_token="ui", neural_token="neural") is None


def test_neural_sidecar_cannot_call_general_or_confirmation_methods() -> None:
    role = RpcClientRole.NEURAL_SIDECAR
    assert rpc_method_allowed(role, "neural_intent_preview") is True
    assert rpc_method_allowed(role, "execute") is False
    assert rpc_method_allowed(role, "confirm") is False
    assert rpc_method_allowed(role, "update_config") is False
    assert rpc_method_allowed(RpcClientRole.UI, "execute") is True
