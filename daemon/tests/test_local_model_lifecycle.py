from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pilot.config import PilotConfig
from pilot.models.ollama import OllamaClient
from pilot.models.router import ModelRouter


class _StreamingResponse:
    status_code = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def raise_for_status(self):
        return None

    async def aiter_lines(self):
        yield '{"response":"ready"}'


@pytest.mark.asyncio
async def test_ollama_applies_configured_idle_timeout_to_every_request_path():
    config = PilotConfig()
    config.model.idle_unload_seconds = 37
    transport = MagicMock()
    response = MagicMock(status_code=200)
    response.json.side_effect = [
        {"response": "generated"},
        {"message": {"content": "chatted"}},
    ]
    transport.post = AsyncMock(return_value=response)
    transport.stream.return_value = _StreamingResponse()

    with patch("pilot.models.ollama.create_httpx_client", return_value=transport):
        client = OllamaClient(config=config)

    assert await client.generate("model", "prompt") == "generated"
    assert await client.generate("model", "prompt", stream_callback=AsyncMock()) == "ready"
    assert await client.generate("model", [{"role": "user", "content": "hello"}]) == "chatted"

    assert transport.post.await_args_list[0].kwargs["json"]["keep_alive"] == 37
    assert transport.stream.call_args.kwargs["json"]["keep_alive"] == 37
    assert transport.post.await_args_list[1].kwargs["json"]["keep_alive"] == 37


@pytest.mark.asyncio
async def test_llamacpp_unloads_after_configured_idle_period():
    config = PilotConfig()
    config.model.idle_unload_seconds = 0
    client = MagicMock()
    client.generate = AsyncMock(return_value="complete")
    router = object.__new__(ModelRouter)
    router._config = config
    router._llamacpp = client
    router._llamacpp_active_calls = 0
    router._llamacpp_idle_task = None

    assert await router._llamacpp_generate("prompt") == "complete"
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    client.unload.assert_called_once_with()
    await router._cancel_llamacpp_idle_unload()


@pytest.mark.asyncio
async def test_llamacpp_stays_loaded_until_all_concurrent_calls_finish():
    config = PilotConfig()
    config.model.idle_unload_seconds = 0
    first_started = asyncio.Event()
    release_first = asyncio.Event()

    async def generate(prompt, **_kwargs):
        if prompt == "first":
            first_started.set()
            await release_first.wait()
        return prompt

    client = MagicMock()
    client.generate = AsyncMock(side_effect=generate)
    router = object.__new__(ModelRouter)
    router._config = config
    router._llamacpp = client
    router._llamacpp_active_calls = 0
    router._llamacpp_idle_task = None

    first = asyncio.create_task(router._llamacpp_generate("first"))
    await first_started.wait()
    assert await router._llamacpp_generate("second") == "second"
    await asyncio.sleep(0)
    client.unload.assert_not_called()

    release_first.set()
    assert await first == "first"
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    client.unload.assert_called_once_with()
    await router._cancel_llamacpp_idle_unload()


@pytest.mark.asyncio
async def test_model_router_closes_every_provider_and_unloads_embedded_model():
    router = object.__new__(ModelRouter)
    router._llamacpp_idle_task = None
    router._llamacpp = MagicMock()
    router._subscription = MagicMock(close=AsyncMock())
    router._cache = MagicMock(close=AsyncMock())
    router._ollama = MagicMock(close=AsyncMock())
    router._cloud = MagicMock(close=AsyncMock())

    await router.close()

    router._subscription.close.assert_awaited_once_with()
    router._cache.close.assert_awaited_once_with()
    router._ollama.close.assert_awaited_once_with()
    router._cloud.close.assert_awaited_once_with()
