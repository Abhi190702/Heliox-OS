import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from pilot.config import PilotConfig, _config_to_dict, _merge_config, _validate_config_types
from pilot.models.router import ModelRouter
from pilot.models.subscription_cli import CLIResult, SubscriptionCLIClient, _serialize_messages


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
async def test_codex_generation_uses_sterile_read_only_ephemeral_contract(monkeypatch):
    config = PilotConfig()
    config.model.provider = "subscription"
    config.model.subscription_provider = "codex"
    config.model.subscription_model = "gpt-test"
    client = SubscriptionCLIClient(config)
    monkeypatch.setattr(client, "_resolve_executable", lambda provider: "codex")
    client.status = AsyncMock(return_value={"subscription": True})
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

