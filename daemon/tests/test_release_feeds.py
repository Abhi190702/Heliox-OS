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
    from pilot.changelog import CHANGELOG, PUBLIC_RELEASE_VERSION, VERSION

    payload = json.loads((ROOT / "releases.json").read_text(encoding="utf-8"))
    assert payload["current_version"] == VERSION
    assert payload["current_source_version"] == VERSION
    assert payload["latest_published_version"] == PUBLIC_RELEASE_VERSION
    assert [item["version"] for item in payload["releases"]] == list(CHANGELOG)
    statuses = {item["version"]: item["status"] for item in payload["releases"]}
    assert statuses[VERSION] == "draft-prerelease"
    assert statuses[PUBLIC_RELEASE_VERSION] == "published"
    feed = json.loads((ROOT / "releases.feed.json").read_text(encoding="utf-8"))
    assert feed["version"] == "https://jsonfeed.org/version/1.1"
    assert [item["id"] for item in feed["items"]] == [f"heliox-{PUBLIC_RELEASE_VERSION}"]
    xml = ET.parse(ROOT / "releases.xml")
    assert len(xml.findall("./channel/item")) == 1
