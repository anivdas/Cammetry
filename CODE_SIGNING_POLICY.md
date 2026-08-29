# Code signing policy

Cammetry is an open-source desktop application. Official Windows releases are intended to be Authenticode-signed after the project is approved for the SignPath Foundation open-source code-signing program.

**Free code signing provided by SignPath.io, certificate by SignPath Foundation.**

## Project and source

- Project: Cammetry
- Source repository: https://github.com/anivdas/Cammetry
- License: MIT
- Official downloads: https://github.com/anivdas/Cammetry/releases

Only artifacts built from the official Cammetry repository and official release workflow are eligible for Cammetry release signing.

## Team roles

Cammetry is currently maintained by a single project owner.

- **Author / committer:** [Aniv Das (@anivdas)](https://github.com/anivdas)
- **Reviewer:** [Aniv Das (@anivdas)](https://github.com/anivdas). Contributions from people without direct commit access must be reviewed before they are merged.
- **Signing approver:** [Aniv Das (@anivdas)](https://github.com/anivdas)

All maintainers participating in source control or SignPath administration must use multi-factor authentication.

## Release-signing rules

1. Release artifacts must be produced by GitHub Actions on GitHub-hosted runners from this repository.
2. Release signing must use SignPath origin verification and the Cammetry release-signing policy.
3. Every release-signing request requires explicit approval by an authorized Cammetry signing approver.
4. Cammetry signs only project-owned executable files. Third-party open-source binaries bundled with Cammetry, including FFmpeg, retain their upstream identity and license and are not re-signed as Cammetry.
5. Product metadata for signed Cammetry executables must identify the product as `Cammetry` and must match the release version.
6. Release artifacts are published only after successful signing and signature verification.
7. The official GitHub Release page is the authoritative download location for Cammetry binaries.

## Privacy

Cammetry is local-first. It does not send video, GPS, telemetry, analytics, or other user data to networked systems unless the user explicitly requests a network-dependent feature. See [PRIVACY.md](PRIVACY.md) for details, including update checks, optional map tiles, support hooks, and optional temporary sharing.

## Installation and system changes

Cammetry's Windows installer clearly identifies the installation location, installs per-user by default, and includes an uninstaller. The application does not silently change unrelated system settings.

## Current release status

Cammetry v0.5.0 was published before SignPath enrollment and is therefore unsigned. Once SignPath Foundation approves the project and the signing integration is activated, future official Windows releases will be signed through the documented release workflow.
