# Heliox Plugin Marketplace

Heliox publishes plugins through reviewed pull requests to the public
[`VyomKulshrestha/Heliox-OS`](https://github.com/VyomKulshrestha/Heliox-OS)
repository. The app reads the approved catalog from `main`, so merging a plugin
pull request publishes it to the marketplace. A new desktop release is not
required.

## Publishing flow

1. In Heliox, open **Plugin Marketplace** and select **Create Local Plugin**.
2. Test every exposed tool on your device.
3. Fork the Heliox repository and create a branch.
4. Add these files:

   ```text
   plugins/<plugin-name>/
   ├── manifest.json
   └── plugin.py
   ```

5. Add the plugin metadata and package files to `plugins/registry.json`.
6. From the repository root, update the package hashes:

   ```powershell
   python scripts/validate_marketplace.py --write
   ```

7. Verify the finished catalog:

   ```powershell
   python scripts/validate_marketplace.py
   ```

8. Open a pull request explaining the plugin's purpose, external services,
   credentials, side effects, and how reviewers can test each tool.

After CI passes and a maintainer approves and merges the pull request, the
plugin appears when users press **Refresh** in the marketplace. Until then, a
plugin created in the app is local to its creator's device.

## Package contract

- Plugin names use lowercase letters, numbers, and single hyphens, are at most
  64 characters, and cannot begin or end with a hyphen.
- The package path is exactly `plugins/<plugin-name>`.
- Python marketplace plugins use `plugin.py` as the entry point and export:

  ```python
  def handle_tool(tool_name, params):
      return {"status": "success"}
  ```

- `manifest.json` and `plugin.py` are required. A package may contain at most
  64 files and each file may be at most 5 MB.
- Every package file has a SHA-256 digest in `plugins/registry.json`.
- Tool names are globally unique and use lowercase `snake_case`.
- Dependencies must be declared truthfully. Credentials must come from the
  environment or an authenticated service and must never be committed.
- Fake success responses, fabricated live data, embedded secrets, silent
  telemetry, and undeclared side effects are grounds for rejection.

The first marketplace version intentionally permits only Python standard-library
imports from `__future__`, `json`, `os`, `typing`, and `urllib`. The validator
also rejects `compile`, `eval`, `exec`, and `__import__`. Expand this policy only
through a reviewed platform change, not inside an individual plugin pull
request.

## Review and trust model

The public GitHub repository and its reviewed `main` branch are the publication
authority. Marketplace CI validates the catalog, package paths, manifests,
allowed imports, and hashes. Maintainers must still review behavior and run the
plugin because static checks cannot prove that network calls or device actions
are harmless.

Repository administrators should configure the `main` branch ruleset to require:

- the **Validate catalog and packages** status check;
- at least one approving review;
- review from the marketplace `CODEOWNERS`; and
- dismissal of approvals when new commits are pushed.

During installation, Heliox:

1. downloads the catalog over HTTPS from the approved GitHub repository;
2. accepts only a plugin listed in that catalog;
3. downloads only the catalog-declared files;
4. blocks path traversal and oversized files;
5. verifies every SHA-256 digest before installation; and
6. signs the verified local installation for later tamper detection.

If GitHub is unavailable, the app clearly shows a bundled offline catalog.
Bundled entries remain installable, but newly merged plugins appear only after
the GitHub catalog is reachable.

Installed plugin actions are exposed to the planner and require user
confirmation before execution. Clicking **Execute** in the marketplace is an
explicit manual action by the user.

## Updating a plugin

Submit another pull request that changes the package version and files, then run
the validator with `--write` to refresh hashes. The current MVP requires users
to uninstall the older version and install the updated version after the pull
request is merged.
