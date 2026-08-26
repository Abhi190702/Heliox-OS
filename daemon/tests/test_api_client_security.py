from __future__ import annotations

import socket
from unittest.mock import AsyncMock

import pytest

from pilot.actions import Action, ActionType, ApiRequestParams
from pilot.agents.executor import Executor
from pilot.system import api_client


class _ClientContext:
    def __init__(self, client: object) -> None:
        self._client = client

    async def __aenter__(self) -> object:
        return self._client

    async def __aexit__(self, *_args: object) -> None:
        return None


class _Response:
    def __init__(
        self,
        *,
        url: str,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        text: str = "ok",
    ) -> None:
        self.url = url
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text

    def json(self) -> object:
        raise ValueError("not json")


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
        await api_client.api_request("GET", "https://8.8.8.8")

    assert len(calls) == 1
    assert calls[0]["verify"] is True


@pytest.mark.asyncio
async def test_api_request_rejects_unsupported_method_before_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _unexpected_client(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network client must not be constructed")

    monkeypatch.setattr(api_client, "create_httpx_client", _unexpected_client)

    with pytest.raises(ValueError, match="Unsupported HTTP method"):
        await api_client.api_request("CONNECT", "https://example.com")


@pytest.mark.asyncio
async def test_scrape_url_keeps_tls_verification_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    class _ScrapeClient:
        async def request(self, _method: str, url: str, **_kwargs: object) -> object:
            return _Response(url=url, text="<html><body>secure</body></html>")

    def _client_factory(*_args: object, **kwargs: object) -> _ClientContext:
        calls.append(kwargs)
        return _ClientContext(_ScrapeClient())

    monkeypatch.setattr(api_client.PilotConfig, "load", lambda: object())
    monkeypatch.setattr(api_client, "create_httpx_client", _client_factory)

    assert await api_client.scrape_url("https://8.8.8.8") == "secure"
    assert len(calls) == 1
    assert calls[0]["verify"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/admin",
        "http://127.0.0.1/admin",
        "http://[::1]/admin",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.8/internal",
    ],
)
async def test_api_request_blocks_private_network_by_default(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    requests: list[str] = []

    class _Client:
        async def request(self, _method: str, request_url: str, **_kwargs: object) -> object:
            requests.append(request_url)
            return _Response(url=request_url)

    monkeypatch.setattr(api_client.PilotConfig, "load", lambda: object())
    monkeypatch.setattr(api_client, "create_httpx_client", lambda *_args, **_kwargs: _ClientContext(_Client()))

    with pytest.raises(ValueError, match="Private-network URL blocked"):
        await api_client.api_request("GET", url)

    assert requests == []


@pytest.mark.asyncio
async def test_api_request_blocks_hostname_resolving_to_private_address(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[str] = []

    class _Client:
        async def request(self, _method: str, request_url: str, **_kwargs: object) -> object:
            requests.append(request_url)
            return _Response(url=request_url)

    monkeypatch.setattr(api_client.PilotConfig, "load", lambda: object())
    monkeypatch.setattr(api_client, "create_httpx_client", lambda *_args, **_kwargs: _ClientContext(_Client()))
    monkeypatch.setattr(
        api_client.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 80))],
    )

    with pytest.raises(ValueError, match="Private-network URL blocked"):
        await api_client.api_request("GET", "http://metadata.internal/latest")

    assert requests == []


@pytest.mark.asyncio
async def test_api_request_allows_approved_private_network(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Client:
        async def request(self, _method: str, url: str, **_kwargs: object) -> object:
            return _Response(url=url, text="private response")

    monkeypatch.setattr(api_client.PilotConfig, "load", lambda: object())
    monkeypatch.setattr(api_client, "create_httpx_client", lambda *_args, **_kwargs: _ClientContext(_Client()))

    result = await api_client.api_request(
        "GET",
        "http://127.0.0.1:8080/status",
        allow_private_network=True,
    )

    assert "private response" in result


@pytest.mark.asyncio
async def test_redirect_to_private_network_is_blocked_before_following(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[str] = []

    class _Client:
        async def request(self, _method: str, url: str, **_kwargs: object) -> object:
            requests.append(url)
            return _Response(
                url=url,
                status_code=302,
                headers={"location": "http://127.0.0.1/admin"},
            )

    monkeypatch.setattr(api_client.PilotConfig, "load", lambda: object())
    monkeypatch.setattr(api_client, "create_httpx_client", lambda *_args, **_kwargs: _ClientContext(_Client()))

    with pytest.raises(ValueError, match="Private-network URL blocked"):
        await api_client.api_request("GET", "https://8.8.8.8/start")

    assert requests == ["https://8.8.8.8/start"]


@pytest.mark.asyncio
async def test_cross_origin_redirect_strips_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[tuple[str, dict[str, object]]] = []

    class _Client:
        async def request(self, _method: str, url: str, **kwargs: object) -> object:
            requests.append((url, kwargs))
            if len(requests) == 1:
                return _Response(url=url, status_code=302, headers={"location": "https://1.1.1.1/next"})
            return _Response(url=url)

    monkeypatch.setattr(api_client.PilotConfig, "load", lambda: object())
    monkeypatch.setattr(api_client, "create_httpx_client", lambda *_args, **_kwargs: _ClientContext(_Client()))

    await api_client.api_request(
        "GET",
        "https://8.8.8.8/start",
        headers={"Authorization": "Bearer secret", "Cookie": "session=secret", "Accept": "application/json"},
        auth=("user", "secret"),
    )

    assert len(requests) == 2
    redirected_kwargs = requests[1][1]
    assert "auth" not in redirected_kwargs
    assert redirected_kwargs["headers"] == {"Accept": "application/json"}


@pytest.mark.asyncio
async def test_executor_forwards_private_network_approval_to_api_request(monkeypatch: pytest.MonkeyPatch) -> None:
    request = AsyncMock(return_value="ok")
    monkeypatch.setattr(api_client, "api_request", request)
    action = Action(
        action_type=ActionType.API_REQUEST,
        parameters=ApiRequestParams(
            method="GET",
            url="http://127.0.0.1:8080/status",
            allow_private_network=True,
        ),
    )

    result = await Executor._exec_api_request(object.__new__(Executor), action)

    assert result == "ok"
    request.assert_awaited_once_with(
        "GET",
        "http://127.0.0.1:8080/status",
        None,
        None,
        None,
        timeout=30,
        allow_private_network=True,
    )


@pytest.mark.asyncio
async def test_executor_forwards_private_network_approval_to_scraper(monkeypatch: pytest.MonkeyPatch) -> None:
    scrape = AsyncMock(return_value="ok")
    monkeypatch.setattr(api_client, "scrape_url", scrape)
    action = Action(
        action_type=ActionType.API_SCRAPE,
        parameters=ApiRequestParams(
            url="http://127.0.0.1:8080/status",
            selector="main",
            extract="text",
            allow_private_network=True,
        ),
    )

    result = await Executor._exec_api_scrape(object.__new__(Executor), action)

    assert result == "ok"
    scrape.assert_awaited_once_with(
        "http://127.0.0.1:8080/status",
        "main",
        "text",
        allow_private_network=True,
    )
