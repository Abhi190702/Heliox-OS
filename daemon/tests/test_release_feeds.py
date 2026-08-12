"""Contracts for generated public release feeds."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "generate_release_feeds.py"


def _module():
    spec = importlib.util.spec_from_file_location("generate_release_feeds", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_outputs_are_fresh(tmp_path: Path):
    module = _module()
    module.write_outputs(tmp_path)
    for name in ("changelog.md", "releases.json", "releases.feed.json", "releases.xml"):
        assert (tmp_path / name).read_bytes() == (ROOT / name).read_bytes(), name


def test_release_feeds_match_shipped_version():
    from pilot.changelog import CHANGELOG, VERSION

    payload = json.loads((ROOT / "releases.json").read_text(encoding="utf-8"))
    assert payload["current_version"] == VERSION
    assert [item["version"] for item in payload["releases"]] == list(CHANGELOG)
    feed = json.loads((ROOT / "releases.feed.json").read_text(encoding="utf-8"))
    assert feed["version"] == "https://jsonfeed.org/version/1.1"
    assert len(feed["items"]) == len(CHANGELOG)
    xml = ET.parse(ROOT / "releases.xml")
    assert len(xml.findall("./channel/item")) == len(CHANGELOG)
