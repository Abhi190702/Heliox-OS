# Heliox OS release runbook

Heliox releases are deliberately two-phase. A version tag builds signed
installers into a draft prerelease, while PyPI publication and the final GitHub
promotion remain explicit maintainer actions.

## One-time repository setup

Configure these GitHub Actions secrets:

| Platform | Required secrets |
| --- | --- |
| PyPI | `PYPI_API_TOKEN` |
| Windows | `WINDOWS_CERTIFICATE` (raw Base64 `.pfx`), `WINDOWS_CERTIFICATE_PASSWORD` |
| macOS | `APPLE_CERTIFICATE` (raw Base64 `.p12`), `APPLE_CERTIFICATE_PASSWORD`, `APPLE_ID`, `APPLE_PASSWORD` (app-specific), `APPLE_TEAM_ID`, `KEYCHAIN_PASSWORD` |

Create a GitHub environment named `pypi` and require a maintainer approval for
deployments to it. Never store certificate files or passwords in the
repository.

Windows builds import the certificate into the runner and configure Tauri with
its thumbprint. macOS builds import a `Developer ID Application` certificate,
sign the app, notarize it, and require a stapled notarization ticket. The
workflow fails closed when credentials are absent or any signature check fails.

## 1. Prepare the release commit

All release metadata must contain the same semantic version:

```powershell
python scripts/check_release.py
```

Run the complete local validation suite, commit, push `main`, and wait until all
11 required CI jobs pass for that exact commit. The release workflow checks
those job results again and refuses a different or unverified commit.

## 2. Create the draft prerelease

After CI is green:

```powershell
git tag -s v0.10.0 -m "Heliox OS v0.10.0"
git push origin v0.10.0
```

The tag workflow:

1. verifies the tag against every Python, npm, Cargo, Tauri, and changelog
   version source;
2. builds the daemon wheel and source distribution and runs `twine check`;
3. confirms the exact commit passed the complete main CI matrix;
4. reproducibly installs frontend dependencies with `npm ci`;
5. signs Windows installers and signs/notarizes macOS installers;
6. validates Windows signatures, macOS signatures/tickets, and Linux package
   structures; and
7. creates a **draft prerelease** with generated release notes.

It does **not** publish to PyPI on a tag push.

## 3. Validate the daemon distribution

Download the `pilot-daemon-<version>` workflow artifact and test it in a new
Python 3.11 and Python 3.12 virtual environment:

```powershell
python -m venv release-smoke
release-smoke\Scripts\python -m pip install "pilot_daemon-0.10.0-py3-none-any.whl[all]"
release-smoke\Scripts\python -c "import pilot; print(pilot.__version__)"
```

Confirm the printed version matches the desktop version and that the wheel
contains `pilot/security/risk_gate_weights.npz`, the marketplace implementation,
and bundled skills.

## 4. Publish the matching daemon

Only after the distribution smoke test passes, run the release workflow
manually against the existing tag:

```powershell
gh workflow run release.yml --ref v0.10.0 `
  -f release_tag=v0.10.0 `
  -f publish_pypi=true `
  -f build_installers=false
```

The `pypi` environment approval is the final publication gate. The workflow
refuses an existing PyPI version. The desktop bootstrap pins
`pilot-daemon[all]` to its own package version, so it cannot silently install an
incompatible future daemon.

## 5. Clean-machine acceptance

Use fresh Windows, macOS Intel, macOS Apple Silicon, and Linux machines or VMs.
For each platform:

1. download the installer from the draft release;
2. verify the publisher/signature before opening it;
3. install Python 3.11 or 3.12, then install and launch Heliox;
4. wait for first-run setup, restart once, and confirm the daemon becomes
   online;
5. save and use a cloud API key through the OS credential store;
6. test a non-destructive command, an approved command, a denied command, and a
   failed command;
7. test microphone input, camera gaze plus gesture coexistence, cursor mode,
   Pocket TTS, and the learned risk interruption path on real hardware; and
8. uninstall the application and confirm no running daemon remains.

Record the OS version and result for every row. CI cannot substitute for this
hardware and first-run validation.

## 6. Promote

When every acceptance row passes, edit the GitHub draft:

1. review the generated notes;
2. remove the prerelease flag;
3. publish the release; and
4. verify all download links and the PyPI project page from a signed-out browser.

If acceptance fails after PyPI publication, leave the GitHub release as a draft,
fix forward with a new patch version, and never overwrite the published PyPI
artifact.
