"""Generate the public Heliox evidence and limitations page."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_URL = "https://github.com/VyomKulshrestha/Heliox-OS"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _matrix_values(workflow: str, key: str) -> list[str]:
    match = re.search(rf"^\s*{re.escape(key)}:\s*\[([^\]]+)]", workflow, re.MULTILINE)
    if not match:
        raise ValueError(f"Unable to locate {key!r} matrix in CI workflow")
    return [item.strip().strip("'\"") for item in match.group(1).split(",")]


def _percent_reduction(before: float, after: float) -> float:
    return round((before - after) / before * 100, 1)


def build_proof() -> str:
    capabilities = _load_json(REPO_ROOT / "capabilities.json")
    latency = _load_json(
        REPO_ROOT / "docs" / "evidence" / "react-latency-2026-08-12.json"
    )
    ci_workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    ci_operating_systems = _matrix_values(ci_workflow, "os")
    python_versions = _matrix_values(ci_workflow, "python-version")

    summary = capabilities["summary"]
    action_total = summary["action_types"]
    independent_total = summary["independent_postcondition_verifiers"]
    executor_only = action_total - independent_total
    before = latency["before"]
    after = latency["after"]
    mean_reduction = _percent_reduction(before["mean_ms"], after["mean_ms"])
    median_reduction = _percent_reduction(before["median_ms"], after["median_ms"])

    return f"""# Heliox OS Evidence and Limitations

> This page separates reproducible software evidence, live CI status, developer-run hardware observations, and claims that have not yet been established. It is an evidence index, not a promise that every feature works on every computer.

Evidence snapshot date: **{latency["captured_on"]}**  
Product version: **{capabilities["product"]["version"]}**

## Capability and routing evidence

- **{action_total}** declared action types are generated from `daemon/pilot/actions.py`.
- **{summary["mesh"]["specialists"]}** executable specialists register providers for all **{summary["mesh"]["registered_action_types"]}** action types.
- Mesh coverage is **{"complete" if summary["mesh"]["coverage_complete"] else "incomplete"}**; uncovered action types: **{len(summary["mesh"]["uncovered_action_types"])}**.
- **{independent_total}** action types have a separate observed post-condition verifier.
- **{executor_only}** action types currently rely on the executor result without an independent post-condition check.
- **{summary["plugins"]}** plugin manifests are represented in the generated catalog.

Source: [machine-readable capability catalog]({REPOSITORY_URL}/blob/main/capabilities.json). Platform declarations describe product targets; host tools, credentials, permissions, hardware, and integrations still determine runtime availability.

## Continuous-integration coverage

The committed CI workflow currently defines:

| Gate | Coverage | Live result |
| --- | --- | --- |
| Python | Ruff and Pytest on {", ".join(ci_operating_systems)} with Python {", ".join(python_versions)} | [CI workflow]({REPOSITORY_URL}/actions/workflows/ci.yml) |
| Frontend | Prettier, Svelte type checking, dependency audit, static/unit tests, and Vite build | [CI workflow]({REPOSITORY_URL}/actions/workflows/ci.yml) |
| Visual regression | Chromium snapshots on {", ".join(ci_operating_systems)} | [CI workflow]({REPOSITORY_URL}/actions/workflows/ci.yml) |
| Rust desktop shell | Formatting, Clippy with warnings denied, and tests | [CI workflow]({REPOSITORY_URL}/actions/workflows/ci.yml) |
| Marketplace | Manifest, hash, and moderation validation | [Marketplace workflow]({REPOSITORY_URL}/actions/workflows/marketplace.yml) |
| Installers | Separate gated Windows, macOS, and Linux release jobs | [Release workflow]({REPOSITORY_URL}/actions/workflows/release.yml) |
| Windows signing | SignPath test-policy signing and Authenticode signer-presence verification for the EXE, MSI, and embedded application | [SignPath test workflow]({REPOSITORY_URL}/actions/workflows/signpath-test.yml) |

The result is intentionally linked rather than copied as “green”: CI status can change after this file is generated.

## Measured local request latency

Command:

```text
cd daemon
python benchmarks/react_latency.py --iterations {latency["environment"]["iterations"]}
```

Scope: {latency["scope"]}. Environment: {latency["environment"]["operating_system"]}, Python {latency["environment"]["python"]}.

| Metric | Before | After `f2df192` | Change |
| --- | ---: | ---: | ---: |
| Mean | {before["mean_ms"]:.2f} ms | {after["mean_ms"]:.2f} ms | {mean_reduction:.1f}% lower |
| Median | {before["median_ms"]:.2f} ms | {after["median_ms"]:.2f} ms | {median_reduction:.1f}% lower |
| Minimum | {before["min_ms"]:.2f} ms | {after["min_ms"]:.2f} ms | — |
| Maximum | {before["max_ms"]:.2f} ms | {after["max_ms"]:.2f} ms | — |

- The maximum retains the real first-use thread-pool cold start.
- The benchmark makes zero model calls and therefore does not measure provider or network latency.
- It does not measure VLM analysis, browser page loading, microphone capture, TTS playback, camera inference, or neural hardware.
- This is a local reproducibility snapshot, not a universal performance guarantee.

Raw evidence: [`react-latency-2026-08-12.json`]({REPOSITORY_URL}/blob/main/docs/evidence/react-latency-2026-08-12.json).

## Platform and hardware evidence

| Feature | Automated/software evidence | Physical evidence status | Permitted claim |
| --- | --- | --- | --- |
| Typed plans and action routing | Schema, permission, executor, provider-coverage, and result-contract tests | No special hardware required | Software path is tested; individual host actions still depend on platform adapters and permissions. |
| Browser automation | Unit/integration and visual-browser contracts | Site behavior and browser versions vary | Supported through guarded browser actions; no claim of universal website compatibility. |
| Voice recognition | Configuration, routing, cancellation, and fusion tests | Human microphone accuracy is not a release gate | Hardware test required for the user's microphone, language, noise, and accent. |
| Pocket/Kokoro/OS TTS | Engine, fallback, cancellation, and response tests | A Pocket TTS developer run through real speakers is documented; not continuously reproduced in CI | Local TTS is implemented; audible quality and device output require a human check. |
| Camera gesture and cursor control | Geometry, temporal verification, calibration, workflow, and false-positive regression tests | Physical accuracy is not established across cameras, lighting, skin tones, backgrounds, or users | Experimental opt-in input; users must retain the stop controls. |
| Gaze tracking | Model loading, event validation, fusion, and settings tests | Physical gaze accuracy is not a release gate | Coarse on-device region signal, not eye-tracking-grade measurement. |
| Neural intent | Synthetic BrainFlow, recorded EEG playback, provenance, calibration, decoder, gateway, and fault tests | No live headset/human validation has established control accuracy | Research pipeline for synthetic and recorded EEG only; not proven live brain control or medical use. |
| Snapshots and rollback | Fail-closed policy and backend contract tests | Backend availability and real restoration depend on OS support and privileges | Destructive work is blocked when a required snapshot cannot be created; not every external effect is reversible. |

Neural details and the recorded EEGBCI snapshot are documented in [Neural Intent]({REPOSITORY_URL}/blob/main/docs/NEURAL_INTENT.md).

## Known limitations

1. Only {independent_total} of {action_total} actions currently have an independent post-condition verifier; inspect `verification.independent_postcondition` in the capability catalog.
2. CI validates software contracts but cannot establish camera, microphone, speaker, accessibility-permission, EEG, or human-factors accuracy.
3. Browser pages, third-party APIs, cloud models, and external applications can change independently of Heliox.
4. Local-first operation does not mean every configured path is offline. Cloud model and integration tasks send necessary context to the selected provider.
5. Snapshots cover supported local-system changes. Messages, purchases, remote hosts, pushed Git commits, browser scripts, and other external effects may be irreversible.
6. Learned risk and world-model outputs can add caution or interrupt; deterministic policy remains authoritative.
7. Public installers are not yet production-signed. The SignPath test-policy pipeline is validated, but the production certificate is still pending; operating-system reputation warnings may continue until that certificate is issued and the release workflow is migrated.

## Closed regression history

This is not a claim that no defects remain. It records representative failures that materially affected trust or evidence:

| Date | Observed failure | Resolution |
| --- | --- | --- |
| 2026-08-12 | The latency benchmark used an obsolete memory/permission harness contract and leaked worker threads after failure, appearing to hang. | [`f2df192`]({REPOSITORY_URL}/commit/f2df192) repaired teardown and reduced blocking CPU sampling latency. |
| 2026-07-30 | Face-like frames could produce false gesture events. | [`6d4025b`]({REPOSITORY_URL}/commit/6d4025b) added false-positive rejection and [`1d810b7`]({REPOSITORY_URL}/commit/1d810b7) added temporal verification. Physical validation remains required. |
| 2026-07-30 | An approval could be accepted yet denied by a later cognitive action gate. | [`3e034d4`]({REPOSITORY_URL}/commit/3e034d4) carried approval authority across the guarded flow. |
| 2026-07-26 | Marketplace package hashes differed across operating-system line endings. | [`f39648e`]({REPOSITORY_URL}/commit/f39648e) normalized verified marketplace hashing. |
| 2026-07-24 | Approval RPC handling could deadlock the active request. | [`a20297d`]({REPOSITORY_URL}/commit/a20297d) separated approval handling from the blocked request path. |

For all current failures, use the [live CI history]({REPOSITORY_URL}/actions) and [issue tracker]({REPOSITORY_URL}/issues).

## Reproduction entry points

```text
# Capability and provider coverage
python scripts/generate_capability_catalog.py --output capabilities.json
python -m pytest daemon/tests/test_capability_catalog.py daemon/tests/test_specialist_expansion.py -q

# Local non-LLM latency
cd daemon
python benchmarks/react_latency.py --iterations 25

# Neural no-hardware paths; these do not validate live brain control
pilot-neurod-benchmark brainflow-synthetic --seconds 2
pilot-neurod-benchmark eegbci --subject 1 --runs 6 10 14
```
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "proof.md",
        help="Destination for the generated Markdown evidence page.",
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_proof(), encoding="utf-8")
    print(f"Wrote public evidence page to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
