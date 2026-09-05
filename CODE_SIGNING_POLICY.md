# Code signing policy

Cammetry is an open-source desktop application. Current Windows pre-releases are unsigned. Official Windows releases may be Authenticode-signed after a suitable signing provider and identity-validation process are configured.

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

All maintainers participating in source control or signing administration must use multi-factor authentication.

## Release-signing rules

1. Release artifacts must be produced by GitHub Actions on GitHub-hosted runners from this repository.
2. Release signing must use a controlled signing service and the Cammetry release-signing policy.
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

Cammetry v0.5.0 and v0.5.1 Beta are unsigned. Future releases will be labeled accurately as signed or unsigned, and signed releases will be published only after their Authenticode signatures validate successfully.
