# Release process

## Versioning

Cammetry uses semantic-style versions: `MAJOR.MINOR.PATCH`.

Update the version consistently in application metadata, installer metadata, and build scripts before tagging a release.

## Local release build

```powershell
.\Build-Release.ps1
```

Verify the installer, portable executable, and portable ZIP in `release/`.

## GitHub release

The repository includes `.github/workflows/windows-release.yml`.

Typical flow:

```powershell
git checkout main
git pull
git tag v0.5.0
git push origin v0.5.0
```

A tag matching `v*` triggers the Windows build and attaches the generated artifacts to a GitHub Release.

## Before publishing

- Launch a clean installer build on a Windows test machine/VM.
- Open representative Recent/Saved/Sentry footage.
- Verify clips without telemetry still fail gracefully.
- Test CPU export and at least one available hardware encoder.
- Confirm GPS is not exposed unexpectedly.
- Confirm the installer/uninstaller and shortcuts work.
- Review third-party notices.
- Do not include private test footage in release artifacts.


## macOS release assets

The `Build macOS Release` GitHub Actions workflow runs on native Apple Silicon and Intel hosted runners. A version tag builds and attaches architecture-specific `.dmg`, `.zip`, and checksum files to the GitHub Release.

Before calling macOS builds fully production-trusted, configure Apple Developer ID signing and notarization. Until then, the generated application is ad-hoc signed and suitable for testing/source users, but Gatekeeper may show an unidentified-developer warning.
