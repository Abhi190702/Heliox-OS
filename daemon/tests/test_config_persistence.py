from __future__ import annotations

import tomllib

import pytest

import pilot.config as config_module
from pilot.config import PilotConfig


def _redirect_config_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config_module, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_module, "CONFIG_FILE", tmp_path / "config.toml")
    monkeypatch.setattr(config_module, "RESTRICTIONS_FILE", tmp_path / "restrictions.toml")


def test_save_replaces_complete_config_files_without_leaving_temporary_files(tmp_path, monkeypatch):
    _redirect_config_files(tmp_path, monkeypatch)
    config = PilotConfig()
    config.voice.tts_engine = "os_native"

    config.save()

    assert tomllib.loads(config_module.CONFIG_FILE.read_text(encoding="utf-8"))["voice"]["tts_engine"] == "os_native"
    assert tomllib.loads(config_module.RESTRICTIONS_FILE.read_text(encoding="utf-8"))
    assert list(tmp_path.glob(".*.tmp")) == []


def test_failed_atomic_replace_preserves_previous_config(tmp_path, monkeypatch):
    _redirect_config_files(tmp_path, monkeypatch)
    config = PilotConfig()
    config.save()
    original = config_module.CONFIG_FILE.read_bytes()
    real_replace = config_module.os.replace

    def fail_config_replace(source, destination):
        if destination == config_module.CONFIG_FILE:
            raise OSError("simulated replace failure")
        real_replace(source, destination)

    config.voice.tts_engine = "os_native"
    monkeypatch.setattr(config_module.os, "replace", fail_config_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        config.save()

    assert config_module.CONFIG_FILE.read_bytes() == original
    assert list(tmp_path.glob(".*.tmp")) == []


def test_malformed_restrictions_fall_back_to_built_in_safety_defaults(tmp_path, monkeypatch, caplog):
    _redirect_config_files(tmp_path, monkeypatch)
    config_module.RESTRICTIONS_FILE.write_text("not = [valid", encoding="utf-8")

    loaded = PilotConfig.load()

    assert loaded.restrictions == config_module.Restrictions()
    assert "Failed to load restrictions.toml" in caplog.text
