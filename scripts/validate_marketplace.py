"""Validate or refresh the GitHub plugin marketplace registry.

Usage:
    python scripts/validate_marketplace.py
    python scripts/validate_marketplace.py --write
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DAEMON_ROOT = REPO_ROOT / "daemon"
sys.path.insert(0, str(DAEMON_ROOT))

from pilot.plugins.marketplace import (  # noqa: E402
    SIGNATURE_METADATA_FILES,
    MarketplaceError,
    validate_catalog,
    validate_plugin_name,
)

REGISTRY_PATH = REPO_ROOT / "plugins" / "registry.json"
ALLOWED_IMPORT_ROOTS = frozenset(
    {
        "__future__",
        "json",
        "os",
        "typing",
        "urllib",
    }
)
BLOCKED_CALLS = frozenset({"compile", "eval", "exec", "__import__"})


def _validate_python(plugin_name: str, code_path: Path) -> None:
    source = code_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(code_path))
    except SyntaxError as exc:
        raise MarketplaceError(f"{plugin_name}: Python syntax error: {exc}") from exc

    has_handler = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
            for module in modules:
                root = module.split(".", 1)[0]
                if root not in ALLOWED_IMPORT_ROOTS:
                    raise MarketplaceError(
                        f"{plugin_name}: import {module!r} is not allowed in the MVP marketplace"
                    )
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in BLOCKED_CALLS:
                raise MarketplaceError(
                    f"{plugin_name}: direct {node.func.id}() calls are not allowed"
                )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            has_handler = has_handler or node.name == "handle_tool"
    if not has_handler:
        raise MarketplaceError(f"{plugin_name}: plugin.py must define handle_tool")


def _package_files(plugin_dir: Path) -> list[dict[str, str]]:
    files = []
    for path in sorted(candidate for candidate in plugin_dir.rglob("*") if candidate.is_file()):
        relative = path.relative_to(plugin_dir).as_posix()
        if path.name in SIGNATURE_METADATA_FILES or "__pycache__" in path.parts:
            continue
        if path.suffix not in {".json", ".py"}:
            raise MarketplaceError(
                f"{plugin_dir.name}: unsupported package file for MVP: {relative}"
            )
        files.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return files


def build_registry(current: dict) -> dict:
    plugins_root = REPO_ROOT / "plugins"
    entries_by_name = {
        str(entry.get("name")): entry for entry in current.get("plugins", [])
    }
    plugin_dirs = sorted(
        path for path in plugins_root.iterdir() if path.is_dir() and (path / "manifest.json").is_file()
    )
    discovered_names = {validate_plugin_name(path.name) for path in plugin_dirs}
    if discovered_names != set(entries_by_name):
        missing = sorted(discovered_names - set(entries_by_name))
        stale = sorted(set(entries_by_name) - discovered_names)
        raise MarketplaceError(
            f"Registry/package mismatch; missing entries={missing}, stale entries={stale}"
        )

    updated_entries = []
    for plugin_dir in plugin_dirs:
        name = validate_plugin_name(plugin_dir.name)
        manifest = json.loads((plugin_dir / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("name") != name:
            raise MarketplaceError(f"{name}: manifest name must match its directory")
        if manifest.get("runtime_type", "python") != "python":
            raise MarketplaceError(f"{name}: MVP marketplace only accepts Python plugins")
        entry_point = manifest.get("entry_point", "plugin.py")
        if entry_point != "plugin.py":
            raise MarketplaceError(f"{name}: entry_point must be plugin.py")
        _validate_python(name, plugin_dir / entry_point)

        entry = entries_by_name[name]
        for field_name in ("version", "description", "author", "tools"):
            if entry.get(field_name) != manifest.get(field_name):
                raise MarketplaceError(
                    f"{name}: registry {field_name} must exactly match manifest.json"
                )
        entry["package"] = {
            "path": f"plugins/{name}",
            "files": _package_files(plugin_dir),
        }
        updated_entries.append(entry)

    result = {
        "schema_version": current.get("schema_version"),
        "repository": current.get("repository"),
        "ref": current.get("ref"),
        "submission_url": current.get("submission_url"),
        "plugins": updated_entries,
    }
    return validate_catalog(result)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="Refresh package SHA-256 values in plugins/registry.json",
    )
    args = parser.parse_args()

    current = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    expected = build_registry(current)
    rendered = json.dumps(expected, indent=2, ensure_ascii=False) + "\n"
    current_rendered = REGISTRY_PATH.read_text(encoding="utf-8")
    if args.write:
        REGISTRY_PATH.write_text(rendered, encoding="utf-8")
        print(f"Updated {REGISTRY_PATH.relative_to(REPO_ROOT)}")
        return 0
    if current_rendered != rendered:
        print(
            "Marketplace registry is stale. Run: "
            "python scripts/validate_marketplace.py --write",
            file=sys.stderr,
        )
        return 1
    print(f"Marketplace valid: {len(expected['plugins'])} approved plugins")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
