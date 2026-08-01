import httpx
import pytest

from pilot.config import PilotConfig
from pilot.models.cloud import CloudClient, safe_provider_error
from pilot.models.router import ModelRouter


class _Vault:
    async def get_key(self, provider: str) -> str | None:
        return "super-secret-api-key" if provider == "gemini" else None


class _BackupVault:
    async def get_key(self, provider: str) -> str | None:
        return {
            "gemini": "invalid-primary-key",
            "gemini_backup_1": "healthy-backup-key",
        }.get(provider)


def _http_error(status: int, *, body: str = "") -> httpx.HTTPStatusError:
    request = httpx.Request(
        "POST",
        "https://generativelanguage.googleapis.com/v1beta/models/demo:generateContent?key=super-secret-api-key",
    )
    response = httpx.Response(status, request=request, text=body)
    return httpx.HTTPStatusError("request failed", request=request, response=response)


def test_http_provider_error_never_contains_endpoint_or_api_key():
    message = safe_provider_error(_http_error(429), "gemini")

    assert message == "Gemini API unavailable (429): quota or rate limit reached."
    assert "super-secret" not in message
    assert "googleapis.com" not in message
    assert "?key=" not in message


def test_invalid_key_error_is_actionable_without_echoing_provider_body():
    message = safe_provider_error(
        _http_error(400, body='{"error":{"status":"API_KEY_INVALID","message":"API key not valid"}}'),
        "gemini",
    )

    assert message == "Gemini API unavailable (400): the configured API key is invalid."


@pytest.mark.asyncio
async def test_cloud_client_raises_sanitized_error_without_original_exception_chain():
    config = PilotConfig()
    config.model.cloud_provider = "gemini"
    client = CloudClient(config, _Vault())

    async def _fail(*args, **kwargs):
        raise _http_error(429)

    client._call_gemini_native = _fail

    with pytest.raises(RuntimeError) as raised:
        await client.generate("hello")

    assert str(raised.value) == "Gemini API unavailable (429): quota or rate limit reached."
    assert raised.value.__suppress_context__ is True
    await client.close()


@pytest.mark.asyncio
async def test_cloud_client_rotates_past_an_invalid_key():
    config = PilotConfig()
    config.model.cloud_provider = "gemini"
    client = CloudClient(config, _BackupVault())
    attempted_keys: list[str] = []

    async def _generate(api_key, *args, **kwargs):
        attempted_keys.append(api_key)
        if api_key == "invalid-primary-key":
            raise _http_error(400, body='{"error":{"status":"API_KEY_INVALID"}}')
        return "healthy response"

    client._call_gemini_native = _generate

    assert await client.generate("hello") == "healthy response"
    assert attempted_keys == ["invalid-primary-key", "healthy-backup-key"]
    await client.close()


def test_cloud_circuit_breaker_fails_fast_with_sanitized_reason():
    config = PilotConfig()
    config.model.cloud_provider = "gemini"
    router = ModelRouter(config, _Vault())
    router._open_cloud_circuit("Gemini API unavailable (429): quota or rate limit reached.")

    with pytest.raises(RuntimeError) as raised:
        router._raise_if_cloud_circuit_open()

    assert "Retry shortly" in str(raised.value)
    assert "key=" not in str(raised.value)
