# SignPath Foundation application notes

This file keeps the information needed to apply for the SignPath Foundation open-source code-signing program consistent with the public Cammetry repository.

## Project

- **Project name / handle:** Cammetry
- **Repository:** https://github.com/anivdas/Cammetry
- **Download / release page:** https://github.com/anivdas/Cammetry/releases
- **License:** MIT
- **Maintainer:** Aniv Das (`@anivdas`)
- **Platforms:** Windows and macOS; source operation also supported on Linux

## Short description

Cammetry is a free, open-source, local-first desktop application for browsing TeslaCam recordings, synchronizing multiple camera angles, decoding supported embedded SEI driving telemetry, exploring routes/events, and exporting video clips with optional telemetry dashboards and privacy blur.

## Why code signing is requested

Official Windows binaries are distributed directly from GitHub Releases. Unsigned test builds trigger Microsoft Defender SmartScreen's unknown-publisher warning. Code signing is requested so users can verify that official Cammetry Windows binaries were produced from the public repository through the controlled GitHub Actions build and release process.

## Privacy summary

Cammetry processes video, GPS, and telemetry locally by default. It has no background analytics and requires no Tesla account. Network-dependent features are explicit: GitHub update checks, optional OpenStreetMap tiles, optional support endpoints, and optional user-initiated temporary clip sharing. Full policy: https://github.com/anivdas/Cammetry/blob/main/PRIVACY.md

## Code signing policy

https://github.com/anivdas/Cammetry/blob/main/CODE_SIGNING_POLICY.md

The required policy statement is published there and in the main README. Current roles are:

- Author / committer: Aniv Das (`@anivdas`)
- Reviewer: Aniv Das (`@anivdas`)
- Signing approver: Aniv Das (`@anivdas`)

## Build system

Official Windows builds use GitHub Actions on GitHub-hosted Windows runners. The SignPath integration is fail-closed: the ordinary Windows workflow produces test artifacts only, while the signed release workflow requires SignPath credentials and validates returned Authenticode signatures before publishing.

The repository contains canonical SignPath artifact-configuration XML under `.signpath/artifact-configurations/`.

## Requested SignPath identifiers

When SignPath provisions/configures the project, use these slugs if available so the committed workflow works without further edits:

- Project slug: `cammetry`
- Release signing policy: `release-signing`
- Inner executable artifact configuration: `windows-inner`
- Setup executable artifact configuration: `windows-setup`

## Secrets needed after approval

The GitHub repository will need these Actions secrets:

- `SIGNPATH_API_TOKEN`
- `SIGNPATH_ORGANIZATION_ID`

They must never be committed to the repository.

## Third-party binaries

Cammetry bundles/distributes open-source FFmpeg binaries for video processing. These third-party binaries retain their upstream identity and license and are not intended to be signed with the Cammetry/SignPath Foundation identity. See `THIRD_PARTY_NOTICES.md`.

## Current release

v0.5.0 is an unsigned pre-release published before SignPath enrollment. It demonstrates the exact Windows application/installer format intended for signing and provides an existing release for eligibility review.
