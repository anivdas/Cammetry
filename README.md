# Cammetry

> Free, open-source TeslaCam viewing, telemetry exploration, and video export — processed locally by default.

Cammetry is a community-built desktop application for browsing TeslaCam recordings, synchronizing multiple camera angles, decoding supported embedded driving telemetry, exploring routes and events, and exporting polished clips with telemetry overlays.

**Cammetry is independent software. It is not affiliated with, endorsed by, sponsored by, or produced by Tesla, Inc.** References to Tesla, TeslaCam, Autopilot, Full Self-Driving/FSD, Sentry Mode, and other Tesla product names are descriptive only. See [TRADEMARKS.md](TRADEMARKS.md).

## Free forever

The official Cammetry application and official Cammetry releases are intended to remain **free of charge forever**, with no paid edition, subscription, feature paywall, advertising requirement, or telemetry-selling business model.

The source code is published under the [MIT License](LICENSE). The MIT license allows broad reuse, including third-party forks and redistribution, so this promise applies to the **official Cammetry project and official Cammetry releases** rather than every possible fork made by someone else.

## Highlights

- Browse `RecentClips`, `SavedClips`, and `SentryClips`.
- Synchronized playback for up to six TeslaCam camera files when available.
- Decode compatible embedded MP4 SEI telemetry.
- Speed, gear, steering, accelerator, brake, turn signals, heading, acceleration, GPS, and driver-assistance state where present.
- Interactive route and timeline views, with an offline route by default and optional OpenStreetMap background.
- Automatic mounted TeslaCam drive detection, event jump, and active-camera snapshots.
- Trim clips and export single-, four-, or six-camera layouts.
- Telemetry dashboards, timestamps, GPS minimaps, and privacy blur zones.
- CSV telemetry export.
- NVIDIA NVENC, Intel Quick Sync, AMD AMF, Apple VideoToolbox, and CPU x264 export when supported.
- Full 13-language UI/message packs with localized export dashboard labels.
- Local-first operation. No Tesla account or credentials are required.
- Optional update, support, and sharing integrations are explicit and configurable.
- Windows installer and portable builds.

The `feature/v0.6-enhancements` development line adds a Local Library, continuous
event playback, local review markers, an Incident Workspace, Privacy Export,
compatibility preflight, and the first real WinUI 3 migration shell. Released
v0.5.x builds continue to use the proven Tkinter interface while the native
Windows shell progresses through its documented migration gates.

See [docs/FEATURES.md](docs/FEATURES.md) for the detailed feature list.

## Privacy first

Cammetry reads video and telemetry from files you choose. Video and GPS processing are local by default. The application does not require a Tesla login and does not enable background analytics or user tracking.

Nothing is uploaded unless the user deliberately invokes and configures a network feature such as temporary sharing. See [PRIVACY.md](PRIVACY.md).

## Downloading Cammetry

For normal users, download the latest installer from the [Cammetry Releases](https://github.com/anivdas/Cammetry/releases) page:

`Cammetry-Setup-vX.Y.Z.exe`

A portable executable/ZIP is also produced for users who prefer not to install the application.

Cammetry v0.5.0, v0.5.1 Beta, and v0.6.0 Beta are unsigned Windows pre-releases. Windows may display an unknown-publisher or SmartScreen warning; verify that downloads came from the official Cammetry Releases page before running them.

## Code signing policy

Cammetry's current Windows pre-releases are unsigned. A future signing provider may be added after its identity-validation and technical requirements are met. Any signing workflow must use controlled builds and verify Authenticode signatures before signed binaries are published. Cammetry-owned executables may be signed; bundled third-party open-source programs keep their own upstream identity and licenses.

The project roles, release rules, privacy commitments, and current signing status are documented in [CODE_SIGNING_POLICY.md](CODE_SIGNING_POLICY.md). Maintainer implementation details are in [docs/SIGNING.md](docs/SIGNING.md).

## Run from source — Windows

The easiest source workflow is:

1. Install **Python 3.12+** from python.org and enable the option to add Python to PATH.
2. Download or clone this repository.
3. Double-click `Run-From-Source.cmd`.

The script creates an isolated `.venv`, installs the runtime Python dependencies, and launches Cammetry.

Manual equivalent:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python cammetry.py
```

More detail, Linux/macOS source instructions, troubleshooting, and FFmpeg behavior are in [docs/BUILDING.md](docs/BUILDING.md).

## Build the Windows installer yourself

On Windows:

```powershell
.\Build-Release.ps1
```

or double-click `Build-Release.cmd`.

The build process creates normal Windows application files, a portable executable/ZIP, and an NSIS installer. Local builds are not automatically trusted merely because they were built from this source; official signed releases go through the controlled signing workflow described above.

macOS is also an automated release target. GitHub Actions builds native Apple Silicon (`arm64`) and Intel (`x86_64`) packages from the same source. Public macOS builds can be Developer ID signed/notarized once project signing credentials are configured.

## Supported footage and telemetry

Cammetry can display ordinary TeslaCam video even when embedded telemetry is absent. Rich telemetry depends on the vehicle, firmware, recording state, and file contents.

Tesla has publicly documented a Dashcam SEI telemetry schema and sample tooling. Cammetry's implementation is independent and uses documented/observed file structures rather than Tesla credentials or private APIs.

Useful upstream reference:

- Tesla Dashcam repository: https://github.com/teslamotors/dashcam

## Project structure

```text
Cammetry/
├─ cammetry.py
├─ tts_core.py
├─ tts_player.py
├─ tts_ui.py
├─ tts_export.py
├─ tts_settings.py
├─ tts_locales.py
├─ tts_map.py
├─ tts_sequence.py
├─ tts_event_detection.py
├─ tts_compatibility.py
├─ tts_library.py
├─ tts_incident.py
├─ tts_privacy.py
├─ cammetry_bridge.py
├─ windows/Cammetry.WinUI/
├─ assets/
├─ installer/
├─ share_backend/
├─ docs/
├─ tests/
└─ .github/
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for component boundaries and
[docs/WINUI3.md](docs/WINUI3.md) for the native Windows migration status.

## Contributing

Bug reports, documentation fixes, translations, compatibility reports, and pull requests are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md) or open an [Issue](https://github.com/anivdas/Cammetry/issues).

Please do not submit proprietary Tesla software, private API credentials, copyrighted assets copied from another application, or user recordings that you do not have permission to share.

## Security

For vulnerabilities or reports involving potentially sensitive GPS/video handling, follow [SECURITY.md](SECURITY.md) rather than posting private footage in a public issue.

## License

Cammetry source code is released under the [MIT License](LICENSE). Bundled or downloaded third-party components retain their respective licenses. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Status

Cammetry is community software and may contain bugs. Always preserve your original TeslaCam files before deleting, editing, or exporting anything.
