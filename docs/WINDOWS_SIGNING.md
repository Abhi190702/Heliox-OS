# Windows code signing

Heliox OS uses the SignPath Foundation program for Windows Authenticode
signing. The integration deliberately separates test signing from production
release signing so a self-signed test certificate can never be presented to
users as a trusted release certificate.

## SignPath project

- Organization: `HelioxOS [OSS]`
- Project: `Heliox-OS`
- Artifact configuration: `windows-installers`
- Test policy: `test-signing`
- Production policy: `release-signing`

The `windows-installers` artifact configuration accepts the ZIP produced by
GitHub Actions and signs all three relevant layers:

1. the NSIS setup executable;
2. the MSI package; and
3. the Heliox executable embedded in the MSI.

## Test-signing workflow

Run **SignPath Windows test signing** manually from GitHub Actions. It:

1. builds one Windows EXE and one MSI on a GitHub-hosted runner;
2. uploads the unsigned pair as a short-lived GitHub Actions artifact;
3. submits that exact artifact to SignPath using the `test-signing` policy;
4. downloads the signed result;
5. fails unless both installers contain Authenticode signatures; and
6. uploads the signed test pair for inspection for seven days.

The workflow has read-only repository permissions and contains no release or
publication step. The API token is stored only as the repository secret
`SIGNPATH_API_TOKEN`.

The test certificate is self-signed. Windows may therefore report it as
untrusted even when the Authenticode signature is structurally present. Test
artifacts are for SignPath setup validation only and must not be distributed as
a Heliox release.

## Production cutover

Do not enable production publication until all of the following are true:

- the SignPath GitHub App is installed with access limited to `Heliox-OS`;
- the test-signing workflow completes successfully;
- SignPath has reviewed the setup;
- the Foundation production certificate is issued and the
  `release-signing` policy is valid; and
- the release workflow verifies a trusted Authenticode signature before
  attaching Windows installers to a public release.

The production certificate and private key remain in SignPath. They must not
be exported into GitHub secrets or committed to this repository.
