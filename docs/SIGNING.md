# Windows code signing

Cammetry's current Windows pre-releases are unsigned. Windows may display an unknown-publisher or SmartScreen warning when they are launched.

## Current release flow

1. GitHub Actions checks out the source on a GitHub-hosted Windows runner.
2. PyInstaller builds the installed application and portable executable.
3. NSIS builds the Windows Setup executable.
4. Automated checks install, launch, and uninstall the packaged application.
5. Release notes must clearly identify unsigned Windows artifacts before publication.

Users should download binaries only from the official [Cammetry Releases](https://github.com/anivdas/Cammetry/releases) page and preserve the original TeslaCam files used for testing.

## Future signed releases

A future signing integration must follow these requirements:

- Build release artifacts from this repository on controlled runners.
- Sign Cammetry-owned executables only. Bundled third-party components such as FFmpeg retain their upstream identity and licenses.
- Sign the installed `Cammetry.exe`, the portable executable, and the finished Setup executable where supported.
- Verify every returned Authenticode signature before publication.
- Keep credentials outside source control and require multi-factor authentication for maintainers with release or signing access.
- Label every GitHub Release accurately as signed or unsigned.

The specific provider and workflow will be documented only after it is selected and configured.

## Verifying a signed build

When signed builds become available, verify them in PowerShell:

```powershell
Get-AuthenticodeSignature .\Cammetry.exe
Get-AuthenticodeSignature .\Cammetry-Portable-vX.Y.Z.exe
Get-AuthenticodeSignature .\Cammetry-Setup-vX.Y.Z.exe
```

Each official signed executable must report a valid signature and the expected publisher. An unsigned build must never be represented as signed.
