"""Generate public changelog and machine-readable release feeds."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "daemon"))

from pilot.changelog import CHANGELOG, VERSION  # noqa: E402

SITE = "https://www.helioxos.dev"
REPOSITORY = "https://github.com/VyomKulshrestha/Heliox-OS"


def releases() -> list[dict[str, object]]:
    result = []
    for version, entry in CHANGELOG.items():
        features = [
            {"name": item["name"], "description": item["description"]}
            if isinstance(item, dict)
            else {"name": str(item), "description": ""}
            for item in entry["features"]
        ]
        result.append(
            {
                "version": version,
                "title": entry["title"],
                "date": entry["date"],
                "summary": entry["summary"],
                "features": features,
                "release_url": f"{REPOSITORY}/releases/tag/v{version}",
            }
        )
    return result


def render_markdown(items: list[dict[str, object]]) -> str:
    lines = [
        "---",
        "title: Heliox OS changelog",
        f"canonical_url: {SITE}/changelog.md",
        f"last_updated: {date.today().isoformat()}",
        "---",
        "",
        "# Heliox OS changelog",
        "",
        "This page is generated from the changelog shipped by the Heliox daemon. "
        "It describes released product milestones; current limitations remain in the proof center.",
        "",
    ]
    for item in items:
        lines.extend(
            [
                f"## {item['version']} — {item['title']}",
                "",
                f"Released: **{item['date']}**",
                "",
                str(item["summary"]),
                "",
            ]
        )
        for feature in item["features"]:
            lines.append(f"- **{feature['name']}** — {feature['description']}")
        lines.extend(["", f"[Release artifacts]({item['release_url']})", ""])
    lines.extend(
        [
            "## Current evidence",
            "",
            f"See [evidence and limitations]({SITE}/proof.md) and the "
            f"[machine-readable capability catalog]({SITE}/capabilities.json).",
            "",
        ]
    )
    return "\n".join(lines)


def render_json_feed(items: list[dict[str, object]]) -> dict[str, object]:
    return {
        "version": "https://jsonfeed.org/version/1.1",
        "title": "Heliox OS releases",
        "home_page_url": SITE,
        "feed_url": f"{SITE}/releases.feed.json",
        "description": "Verified release milestones generated from the Heliox daemon changelog.",
        "items": [
            {
                "id": f"heliox-{item['version']}",
                "url": item["release_url"],
                "title": f"Heliox OS {item['version']} — {item['title']}",
                "summary": item["summary"],
                "date_published": f"{item['date']}T00:00:00Z",
                "tags": ["release", "heliox-os"],
                "content_text": "\n".join(
                    f"{feature['name']}: {feature['description']}"
                    for feature in item["features"]
                ),
            }
            for item in items
        ],
    }


def render_rss(items: list[dict[str, object]]) -> bytes:
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    for tag, text in (
        ("title", "Heliox OS releases"),
        ("link", SITE),
        (
            "description",
            "Verified release milestones generated from the Heliox daemon changelog.",
        ),
        ("language", "en"),
    ):
        ET.SubElement(channel, tag).text = text
    for item in items:
        node = ET.SubElement(channel, "item")
        ET.SubElement(
            node, "title"
        ).text = f"Heliox OS {item['version']} — {item['title']}"
        ET.SubElement(node, "link").text = str(item["release_url"])
        ET.SubElement(
            node, "guid", {"isPermaLink": "false"}
        ).text = f"heliox-{item['version']}"
        published = datetime.fromisoformat(str(item["date"])).replace(
            tzinfo=timezone.utc
        )
        ET.SubElement(node, "pubDate").text = format_datetime(published)
        ET.SubElement(node, "description").text = str(item["summary"])
    ET.indent(rss, space="  ")
    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)


def write_outputs(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    items = releases()
    payload = {
        "schema_version": 1,
        "current_version": VERSION,
        "generated_from": "daemon/pilot/changelog.py",
        "releases": items,
    }
    (output_dir / "changelog.md").write_text(
        render_markdown(items), encoding="utf-8", newline="\n"
    )
    (output_dir / "releases.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output_dir / "releases.feed.json").write_text(
        json.dumps(render_json_feed(items), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output_dir / "releases.xml").write_bytes(render_rss(items))
    print(f"Generated {len(items)} releases in {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    args = parser.parse_args()
    write_outputs(args.output_dir.resolve())


if __name__ == "__main__":
    main()
