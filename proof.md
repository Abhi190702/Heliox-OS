# Heliox OS Evidence and Limitations

> This page separates reproducible software evidence, live CI status, developer-run hardware observations, and claims that have not yet been established. It is an evidence index, not a promise that every feature works on every computer.

Evidence snapshot date: **2026-08-12**  
Product version: **0.11.0**

## Capability and routing evidence

- **156** declared action types are generated from `daemon/pilot/actions.py`.
- **21** executable specialists register providers for all **156** action types.
- Mesh coverage is **complete**; uncovered action types: **0**.
- **11** action types have a separate observed post-condition verifier.
- **145** action types currently rely on the executor result without an independent post-condition check.
- **6** plugin manifests are represented in the generated catalog.

Source: [machine-readable capability catalog](https://github.com/VyomKulshrestha/Heliox-OS/blob/main/capabilities.json). Platform declarations describe product targets; host tools, credentials, permissions, hardware, and integrations still determine runtime availability.

## Continuous-integration coverage

The committed CI workflow currently defines:

| Gate | Coverage | Live result |
| --- | --- | --- |
| Python | Ruff and Pytest on ubuntu-latest, windows-latest, macos-latest with Python 3.11, 3.12 | [CI workflow](https://github.com/VyomKulshrestha/Heliox-OS/actions/workflows/ci.yml) |
| Frontend | Prettier, Svelte type checking, dependency audit, static/unit tests, and Vite build | [CI workflow](https://github.com/VyomKulshrestha/Heliox-OS/actions/workflows/ci.yml) |
| Visual regression | Chromium snapshots on ubuntu-latest, windows-latest, macos-latest | [CI workflow](https://github.com/VyomKulshrestha/Heliox-OS/actions/workflows/ci.yml) |
| Rust desktop shell | Formatting, Clippy with warnings denied, and tests | [CI workflow](https://github.com/VyomKulshrestha/Heliox-OS/actions/workflows/ci.yml) |
| Marketplace | Manifest, hash, and moderation validation | [Marketplace workflow](https://github.com/VyomKulshrestha/Heliox-OS/actions/workflows/marketplace.yml) |
| Installers | Separate gated Windows, macOS, and Linux release jobs | [Release workflow](https://github.com/VyomKulshrestha/Heliox-OS/actions/workflows/release.yml) |

The result is intentionally linked rather than copied as “green”: CI status can change after this file is generated.

## Measured local request latency

Command:

```text
cd daemon
python benchmarks/react_latency.py --iterations 25
```

Scope: Full guarded non-LLM CPU usage request path with a local planner fast path and zero model calls. Environment: Windows, Python 3.12.

| Metric | Before | After `f2df192` | Change |
| --- | ---: | ---: | ---: |
| Mean | 117.68 ms | 37.08 ms | 68.5% lower |
| Median | 110.71 ms | 30.59 ms | 72.4% lower |
| Minimum | 108.97 ms | 29.24 ms | — |
| Maximum | 285.49 ms | 194.21 ms | — |

- The maximum retains the real first-use thread-pool cold start.
- The benchmark makes zero model calls and therefore does not measure provider or network latency.
- It does not measure VLM analysis, browser page loading, microphone capture, TTS playback, camera inference, or neural hardware.
- This is a local reproducibility snapshot, not a universal performance guarantee.

Raw evidence: [`react-latency-2026-08-12.json`](https://github.com/VyomKulshrestha/Heliox-OS/blob/main/docs/evidence/react-latency-2026-08-12.json).

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

Neural details and the recorded EEGBCI snapshot are documented in [Neural Intent](https://github.com/VyomKulshrestha/Heliox-OS/blob/main/docs/NEURAL_INTENT.md).

## Known limitations

1. Only 11 of 156 actions currently have an independent post-condition verifier; inspect `verification.independent_postcondition` in the capability catalog.
2. CI validates software contracts but cannot establish camera, microphone, speaker, accessibility-permission, EEG, or human-factors accuracy.
3. Browser pages, third-party APIs, cloud models, and external applications can change independently of Heliox.
4. Local-first operation does not mean every configured path is offline. Cloud model and integration tasks send necessary context to the selected provider.
5. Snapshots cover supported local-system changes. Messages, purchases, remote hosts, pushed Git commits, browser scripts, and other external effects may be irreversible.
6. Learned risk and world-model outputs can add caution or interrupt; deterministic policy remains authoritative.
7. Installers are currently distributed without a paid commercial code-signing certificate and may trigger operating-system reputation warnings.

## Closed regression history

This is not a claim that no defects remain. It records representative failures that materially affected trust or evidence:

| Date | Observed failure | Resolution |
| --- | --- | --- |
| 2026-08-12 | The latency benchmark used an obsolete memory/permission harness contract and leaked worker threads after failure, appearing to hang. | [`f2df192`](https://github.com/VyomKulshrestha/Heliox-OS/commit/f2df192) repaired teardown and reduced blocking CPU sampling latency. |
| 2026-07-30 | Face-like frames could produce false gesture events. | [`6d4025b`](https://github.com/VyomKulshrestha/Heliox-OS/commit/6d4025b) added false-positive rejection and [`1d810b7`](https://github.com/VyomKulshrestha/Heliox-OS/commit/1d810b7) added temporal verification. Physical validation remains required. |
| 2026-07-30 | An approval could be accepted yet denied by a later cognitive action gate. | [`3e034d4`](https://github.com/VyomKulshrestha/Heliox-OS/commit/3e034d4) carried approval authority across the guarded flow. |
| 2026-07-26 | Marketplace package hashes differed across operating-system line endings. | [`f39648e`](https://github.com/VyomKulshrestha/Heliox-OS/commit/f39648e) normalized verified marketplace hashing. |
| 2026-07-24 | Approval RPC handling could deadlock the active request. | [`a20297d`](https://github.com/VyomKulshrestha/Heliox-OS/commit/a20297d) separated approval handling from the blocked request path. |

For all current failures, use the [live CI history](https://github.com/VyomKulshrestha/Heliox-OS/actions) and [issue tracker](https://github.com/VyomKulshrestha/Heliox-OS/issues).

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
