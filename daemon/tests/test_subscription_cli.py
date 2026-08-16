import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from pilot.agents.planner import Planner
from pilot.config import PilotConfig, _config_to_dict, _merge_config, _validate_config_types
from pilot.models.router import ModelRouter
from pilot.models.subscription_cli import CLIResult, SubscriptionCLIClient, _serialize_messages
from pilot.server import PilotServer


def test_subscription_config_round_trips_and_is_validated():
    raw = {
        "model": {
            "provider": "subscription",
            "subscription_provider": "codex",
            "subscription_model": "gpt-test",
            "subscription_timeout_seconds": 90,
            "subscription_max_prompt_chars": 32000,
        }
    }

    _validate_config_types(raw)
    config = _merge_config(PilotConfig(), raw)

    assert config.model.provider == "subscription"
    assert config.model.subscription_provider == "codex"
    assert config.model.subscription_model == "gpt-test"
    assert _config_to_dict(config)["model"]["subscription_max_prompt_chars"] == 32000


def test_message_serialization_is_compact_and_deduplicates_system():
    serialized = _serialize_messages(
        [
            {"role": "system", "content": "Follow policy"},
            {"role": "user", "content": "Plan this"},
        ],
        "Follow policy",
    )

    assert serialized.count("Follow policy") == 1
    assert "USER\nPlan this" in serialized
    assert "Do not inspect files" in serialized


@pytest.mark.asyncio
async def test_codex_status_requires_chatgpt_subscription(monkeypatch):
    config = PilotConfig()
    client = SubscriptionCLIClient(config)
    monkeypatch.setattr(client, "_resolve_executable", lambda provider: "codex")
    client._run_process = AsyncMock(
        side_effect=[
            CLIResult(0, "codex-cli 1.0\n", ""),
            CLIResult(0, "Logged in using ChatGPT\n", ""),
        ]
    )

    status = await client.status("codex", refresh=True)

    assert status["installed"] is True
    assert status["authenticated"] is True
    assert status["subscription"] is True
    assert "ChatGPT" in status["message"]


@pytest.mark.asyncio
async def test_codex_api_key_login_is_not_mislabeled_as_subscription(monkeypatch):
    config = PilotConfig()
    client = SubscriptionCLIClient(config)
    monkeypatch.setattr(client, "_resolve_executable", lambda provider: "codex")
    client._run_process = AsyncMock(
        side_effect=[
            CLIResult(0, "codex-cli 1.0\n", ""),
            CLIResult(0, "Logged in using an API key\n", ""),
        ]
    )

    status = await client.status("codex", refresh=True)

    assert status["authenticated"] is True
    assert status["subscription"] is False


@pytest.mark.asyncio
async def test_claude_status_accepts_subscription_json(monkeypatch):
    config = PilotConfig()
    client = SubscriptionCLIClient(config)
    monkeypatch.setattr(client, "_resolve_executable", lambda provider: "claude")
    client._run_process = AsyncMock(
        side_effect=[
            CLIResult(0, "2.1.0\n", ""),
            CLIResult(0, json.dumps({"loggedIn": True, "authMethod": "claudeai"}), ""),
        ]
    )

    status = await client.status("claude", refresh=True)

    assert status["subscription"] is True
    assert "Claude Code" in status["message"]


@pytest.mark.asyncio
async def test_subscription_status_and_login_rpcs_delegate_to_selected_cli():
    server = PilotServer(PilotConfig())
    client = MagicMock()
    client.status = AsyncMock(return_value={"provider": "claude", "subscription": True})
    client.start_login = AsyncMock(return_value={"status": "started", "message": "Sign in"})
    server._planner = MagicMock()
    server._planner._model._subscription = client

    status = await server._handle_subscription_status(
        {"provider": "claude", "refresh": True},
        MagicMock(),
    )
    login = await server._handle_subscription_login({"provider": "claude"}, MagicMock())

    assert status["subscription"] is True
    assert login["status"] == "started"
    client.status.assert_awaited_once_with("claude", refresh=True)
    client.start_login.assert_awaited_once_with("claude")


@pytest.mark.asyncio
async def test_codex_generation_uses_sterile_read_only_ephemeral_contract(monkeypatch):
    config = PilotConfig()
    config.model.provider = "subscription"
    config.model.subscription_provider = "codex"
    config.model.subscription_model = "gpt-test"
    client = SubscriptionCLIClient(config)
    monkeypatch.setattr(client, "_resolve_executable", lambda provider: "codex")
    client.status = AsyncMock(return_value={"subscription": True})
    client._status_cache["codex"] = (0.0, {"last_usage": {"input_tokens": 1}})
    stdout = "\n".join(
        [
            json.dumps({"type": "turn.started"}),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": '{"actions":[]}'},
                }
            ),
            json.dumps(
                {
                    "type": "turn.completed",
                    "usage": {"input_tokens": 123, "cached_input_tokens": 100, "output_tokens": 7},
                }
            ),
        ]
    )
    client._run_process = AsyncMock(return_value=CLIResult(0, stdout, "harmless warning"))

    response = await client.generate("Return a plan", json_mode=True)

    assert response == '{"actions":[]}'
    args = client._run_process.await_args.args[0]
    assert "--ephemeral" in args
    assert "--ignore-user-config" in args
    assert "--ignore-rules" in args
    assert args[args.index("--sandbox") + 1] == "read-only"
    assert args[args.index("--model") + 1] == "gpt-test"
    assert client.last_usage["cached_input_tokens"] == 100
    assert client.last_usage["uncached_input_tokens"] == 23
    assert client.last_usage["heliox_prompt_chars"] > 0
    assert client.generation_count == 1
    assert "codex" not in client._status_cache


@pytest.mark.asyncio
async def test_codex_generation_rejects_unexpected_tool_activity(monkeypatch):
    config = PilotConfig()
    client = SubscriptionCLIClient(config)
    monkeypatch.setattr(client, "_resolve_executable", lambda provider: "codex")
    client.status = AsyncMock(return_value={"subscription": True})
    stdout = json.dumps(
        {
            "type": "item.completed",
            "item": {"type": "command_execution", "command": "dir"},
        }
    )
    client._run_process = AsyncMock(return_value=CLIResult(0, stdout, ""))

    with pytest.raises(RuntimeError, match="attempted a tool call"):
        await client.generate("Do nothing")


@pytest.mark.asyncio
async def test_subscription_prompt_limit_fails_before_process_launch(monkeypatch):
    config = PilotConfig()
    config.model.subscription_max_prompt_chars = 1000
    client = SubscriptionCLIClient(config)
    monkeypatch.setattr(client, "_resolve_executable", lambda provider: "codex")
    client.status = AsyncMock(return_value={"subscription": True})
    client._run_process = AsyncMock()

    with pytest.raises(RuntimeError, match="exceeding the configured limit"):
        await client.generate("x" * 2000)

    client._run_process.assert_not_awaited()


@pytest.mark.asyncio
async def test_subscription_message_history_is_compacted_to_exact_character_cap(monkeypatch):
    config = PilotConfig()
    config.model.subscription_max_prompt_chars = 20_000
    client = SubscriptionCLIClient(config)
    monkeypatch.setattr(client, "_resolve_executable", lambda provider: "codex")
    client.status = AsyncMock(return_value={"subscription": True})
    stdout = "\n".join(
        [
            json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "ok"}}),
            json.dumps({"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 1}}),
        ]
    )
    client._run_process = AsyncMock(return_value=CLIResult(0, stdout, ""))
    prompt = [
        {"role": "system", "content": "policy " * 2_000},
        *({"role": "user", "content": f"old-{index} " * 2_000} for index in range(4)),
        {"role": "user", "content": "detail " * 2_000 + "LATEST-GOAL"},
    ]

    assert await client.generate(prompt) == "ok"

    sent_prompt = client._run_process.await_args.kwargs["stdin"]
    assert len(sent_prompt) <= config.model.subscription_max_prompt_chars
    assert "LATEST-GOAL" in sent_prompt
    assert "old-0" not in sent_prompt


@pytest.mark.asyncio
async def test_claude_generation_disables_tools_and_persistence(monkeypatch):
    config = PilotConfig()
    config.model.subscription_provider = "claude"
    client = SubscriptionCLIClient(config)
    monkeypatch.setattr(client, "_resolve_executable", lambda provider: "claude")
    client.status = AsyncMock(return_value={"subscription": True})
    client._run_process = AsyncMock(
        return_value=CLIResult(
            0,
            json.dumps(
                {
                    "result": "ignored",
                    "structured_output": {"actions": []},
                    "usage": {"input_tokens": 40, "output_tokens": 5},
                }
            ),
            "",
        )
    )

    response = await client.generate("Return a plan", json_mode=True)

    assert response == '{"actions":[]}'
    args = client._run_process.await_args.args[0]
    assert "--bare" in args
    assert "--no-session-persistence" in args
    assert args[args.index("--tools") + 1] == ""
    assert args[args.index("--max-turns") + 1] == "1"
    sent_prompt = client._run_process.await_args.kwargs["stdin"]
    assert "Do not inspect files" not in sent_prompt
    assert args[args.index("--system-prompt") + 1].startswith("You are a text-only")
    assert client.last_usage["heliox_estimated_prompt_tokens"] > 0


@pytest.mark.asyncio
async def test_claude_plain_text_fallback_never_reuses_previous_usage(monkeypatch):
    config = PilotConfig()
    config.model.subscription_provider = "claude"
    client = SubscriptionCLIClient(config)
    client.last_usage = {"input_tokens": 9_999}
    monkeypatch.setattr(client, "_resolve_executable", lambda provider: "claude")
    client.status = AsyncMock(return_value={"subscription": True})
    client._run_process = AsyncMock(return_value=CLIResult(0, "plain response", ""))

    assert await client.generate("Respond plainly") == "plain response"

    assert "input_tokens" not in client.last_usage
    assert client.last_usage["heliox_prompt_chars"] > 0


@pytest.mark.asyncio
async def test_model_router_dispatches_selected_subscription_before_local_fallback():
    config = PilotConfig()
    config.model.provider = "subscription"
    config.model.subscription_provider = "codex"
    router = ModelRouter(config, MagicMock())
    router._cache.get = AsyncMock(return_value=None)
    router._cache.set = AsyncMock()
    router._rate_limiter.acquire = AsyncMock()
    router._subscription.generate = AsyncMock(return_value="subscription result")
    router._ollama.is_available = AsyncMock(return_value=True)

    result = await router._generate_with_cache("task")

    assert result == "subscription result"
    router._subscription.generate.assert_awaited_once()
    router._cache.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_model_router_records_actual_subscription_usage_and_skips_cached_usage():
    config = PilotConfig()
    config.model.provider = "subscription"
    config.model.subscription_provider = "codex"
    router = ModelRouter(config, MagicMock())
    router._cache.get = AsyncMock(side_effect=[None, "cached result"])
    router._cache.set = AsyncMock()
    router._rate_limiter.acquire = AsyncMock()
    tracker = MagicMock()
    tracker.record_usage = AsyncMock()
    router.set_budget_tracker(tracker)

    async def generated(*args, **kwargs):
        router._subscription.last_usage = {"input_tokens": 321, "output_tokens": 17}
        router._subscription.generation_count += 1
        router._subscription._request_usage[asyncio.current_task()] = dict(router._subscription.last_usage)
        return "fresh result"

    router._subscription.generate = generated

    assert await router.generate("task") == "fresh result"
    await asyncio.sleep(0)
    tracker.record_usage.assert_awaited_once_with("subscription:codex", "cli-default", 321, 17)

    tracker.record_usage.reset_mock()
    assert await router.generate("task") == "cached result"
    await asyncio.sleep(0)
    tracker.record_usage.assert_not_awaited()


@pytest.mark.asyncio
async def test_planner_compacts_subscription_history_before_cli_limit():
    config = PilotConfig()
    config.model.provider = "subscription"
    config.model.subscription_max_prompt_chars = 20_000
    captured: list[dict] = []

    class FakeRouter:
        _config = config

        async def generate(self, prompt, **kwargs):
            captured.extend(prompt)
            return '{"explanation":"Read status","actions":[{"action_type":"system_info","target":"system","parameters":{}}]}'

    class FakeMemory:
        async def get_context(self, *args, **kwargs):
            return "context " * 5_000

        async def get_history(self, *args, **kwargs):
            return [{"user_input": "old request " * 800, "explanation": "old response " * 800} for _ in range(10)]

    plan = await Planner(FakeRouter(), FakeMemory()).plan(
        "Inspect the current system safely",
        force_model=True,
    )

    assert plan.error is None
    assert len(captured) < 22
