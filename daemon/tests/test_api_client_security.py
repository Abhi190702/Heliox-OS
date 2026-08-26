from __future__ import annotations

from types import SimpleNamespace

import pytest

from pilot.system import api_client


class _ClientContext:
    def __init__(self, client: object) -> None:
        self._client = client

    async def __aenter__(self) -> object:
        return self._client

    async def __aexit__(self, *_args: object) -> None:
        return None


@pytest.mark.asyncio
async def test_api_request_never_retries_without_tls_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    class _FailingClient:
        async def request(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("CERTIFICATE_VERIFY_FAILED")

    def _client_factory(*_args: object, **kwargs: object) -> _ClientContext:
        calls.append(kwargs)
        return _ClientContext(_FailingClient())

    monkeypatch.setattr(api_client.PilotConfig, "load", lambda: object())
    monkeypatch.setattr(api_client, "create_httpx_client", _client_factory)

    with pytest.raises(RuntimeError, match="CERTIFICATE_VERIFY_FAILED"):
        await api_client.api_request("GET", "https://example.com")

    assert len(calls) == 1
    assert calls[0]["verify"] is True


@pytest.mark.asyncio
async def test_scrape_url_keeps_tls_verification_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    class _ScrapeClient:
        async def get(self, _url: str) -> object:
            return SimpleNamespace(text="<html><body>secure</body></html>")

    def _client_factory(*_args: object, **kwargs: object) -> _ClientContext:
        calls.append(kwargs)
        return _ClientContext(_ScrapeClient())

    monkeypatch.setattr(api_client.PilotConfig, "load", lambda: object())
    monkeypatch.setattr(api_client, "create_httpx_client", _client_factory)

    assert await api_client.scrape_url("https://example.com") == "secure"
    assert len(calls) == 1
    assert calls[0]["verify"] is True
