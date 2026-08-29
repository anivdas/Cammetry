# Windows code signing with SignPath

Cammetry uses a two-stage Windows signing design because the NSIS Setup executable contains the application executable.

## Why two signing requests?

The installed `Cammetry.exe` should itself carry a valid Authenticode signature, and the finished `Cammetry-Setup-vX.Y.Z.exe` should also be signed. NSIS is not treated as a deep-signable package format in Cammetry's SignPath design, so the inner application is signed before the installer is created, then the completed installer is signed in a second request.

The portable executable is signed in the first request.

## Planned release flow

1. GitHub Actions checks out an immutable release tag on a GitHub-hosted Windows runner.
2. PyInstaller builds:
   - `dist-installer/Cammetry/Cammetry.exe` and its runtime directory;
   - `Cammetry-Portable-vX.Y.Z.exe`.
3. The Cammetry-owned PE files are packed into the first SignPath signing artifact.
4. SignPath verifies GitHub build origin and an authorized maintainer manually approves the request.
5. The signed `Cammetry.exe` is placed back into the installer application directory and the signed portable EXE is staged for release.
6. NSIS builds `Cammetry-Setup-vX.Y.Z.exe` from the already-signed application directory.
7. The Setup EXE is submitted to SignPath as the second signing request and manually approved.
8. GitHub verifies the returned signatures before publishing the Windows release assets.

This intentionally does **not** sign third-party FFmpeg binaries with the Cammetry identity.

## SignPath project values

The GitHub workflow is designed to use these repository secrets after SignPath approval:

- `SIGNPATH_API_TOKEN`
- `SIGNPATH_ORGANIZATION_ID`

The non-secret identifiers are kept in the workflow once SignPath assigns them:

- project slug, expected: `cammetry`
- signing policy slug, expected: `release-signing`
- inner artifact configuration slug
- setup artifact configuration slug

Do not commit the API token to source control.

## Canonical artifact configurations

Reference XML files are stored in `.signpath/artifact-configurations/`. They are intended to be copied/reviewed in SignPath when the project is provisioned. SignPath remains the authoritative configuration store for actual signing.

## Release requirements

- Release signing must run only from GitHub-hosted runners.
- The repository URL in SignPath must be `https://github.com/anivdas/Cammetry`.
- Origin verification must be enabled.
- The release policy should be restricted to official release tags / the repository's controlled release path as supported by the provisioned SignPath policy.
- Every release request must receive manual approval as required by SignPath Foundation.
- All maintainers must use MFA for GitHub and SignPath.
- Product name and product version metadata must match the Cammetry release.

## Signature verification

Before publishing, the Windows workflow should verify each signed PE using Windows signature inspection, and fail closed if a valid signature is absent.

Expected signed Cammetry-owned files are:

- installed `Cammetry.exe`;
- `Cammetry-Portable-vX.Y.Z.exe`;
- `Cammetry-Setup-vX.Y.Z.exe`.

Unsigned upstream/open-source components may still be contained in the installer under their own licenses, consistent with the project's third-party notices and SignPath Foundation rules.

## v0.5.0

The first public v0.5.0 release predates SignPath enrollment and is unsigned. It should remain labeled as a pre-release/test build rather than being represented as code-signed.
