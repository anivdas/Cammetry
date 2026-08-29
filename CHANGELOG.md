# Changelog

## Unreleased — 0.5.1

Windows beta polish based on testing the public v0.5.0 installer against a real TeslaCam folder.

- Changed the main action to **Browse TeslaCam…** and made the folder picker start from the current path, a detected TeslaCam drive, or the user's Videos folder.
- Automatically selects the newest visible recording after a successful scan.
- Added an always-visible dark vertical scrollbar to the Events list so long TeslaCam histories show position and remaining scroll range while preserving mouse-wheel scrolling.
- Automatically chooses Single, Four Camera, or Six Camera preview based on the cameras actually present in the selected recording.
- Removed the `Unofficial` suffix from official Cammetry window titles.
- Fixed misleading pre-selection telemetry and route states; empty values now remain neutral until a recording is loaded.
- Clears stale telemetry, route, insights, and event details immediately when switching recordings.
- Bundles the Cammetry icon as a runtime asset so packaged Windows builds can use it in the application title bar.
- Changed the Windows installer target to `Program Files\Cammetry` with a conventional per-machine UAC installation and system-wide Start Menu registration.
- Added SignPath Foundation code-signing policy and a fail-closed signed Windows release workflow for use after project enrollment is approved.

## 0.5.0

Localization and cross-platform feature release.

- Expanded and verified the desktop feature set across playback, telemetry, export, privacy, and localization.
- Completed all 13 bundled language packs across all 218 standard UI/message keys.
- Added automated localization coverage and format-placeholder tests.
- Localized layout, export-quality, dashboard, size, and map-mode choices while preserving stable internal values.
- Added Apple VideoToolbox encoder discovery/selection when the active FFmpeg build exposes it.
- Added multiple date-format choices alongside 12/24-hour time.
- Added automatic TeslaCam drive/folder discovery.
- Added human-readable event trigger labels, event jump, and active-camera snapshot export.
- Added non-blocking floating export progress.
- Added optional OpenStreetMap route backgrounds with visible attribution; fully local/offline route rendering remains the default.
- Added source-run helper for macOS/Linux and cross-platform GitHub CI.
- Documented deployment-dependent sharing/support features rather than claiming a hosted service that does not exist.
- Reaffirmed zero anonymous analytics in official Cammetry builds.
- Retested SEI parsing against the real 916-frame Tesla sample used during development.

## 0.4.0

Rebranded the project as **Cammetry** and prepared it for a public open-source GitHub release.

- Adopted the independent Cammetry name and project identity.
- Added explicit Tesla non-affiliation and trademark guidance.
- Added the official-project “free forever” commitment and clarified how that interacts with the MIT license.
- Added contributor, security, code-of-conduct, trademark, architecture, building, releasing, and GitHub setup documentation.
- Added GitHub issue forms and pull-request template.
- Added `.gitignore` protections for TeslaCam media, GPS/CSV exports, local environments, and build outputs.
- Added a minimal unit-test scaffold and documented local checks.
- Renamed Windows application and installer artifacts to Cammetry.

The application capabilities inherited from the 0.3 development build include:

Major desktop-viewer redesign.

- Replaced the original utility-style UI with a dark three-pane event viewer inspired by modern TeslaCam desktop tools.
- Added synchronized six-camera preview support including HW4 left/right pillar cameras.
- Added Six Camera, Four Camera, and Single Camera layouts.
- Added integrated transport controls, 0.5x–4x playback, seek controls, and configurable keyboard shortcuts.
- Added telemetry dashboard with live speed, gear, driver-assist state, steering, accelerator, and brake state.
- Added local GPS route canvas with driver-assist coloring, zoom, and pan.
- Added clip insights including average/max speed, distance estimate, driver-assist percentage, and telemetry count.
- Added Recent/Sentry/Saved filtering, search, event metadata parsing, and event-camera highlighting.
- Added timeline visualization for driver assist, braking, blinkers, events, playhead, and trim selection.
- Added interactive privacy blur-zone selection.
- Added generalized single/four/six-camera exporter.
- Added NVIDIA NVENC, Intel QuickSync, AMD AMF, and CPU x264 encoder selection.
- Added Mobile/Medium/High/Maximum export quality tiers.
- Added Default/Compact telemetry dashboard styles, configurable sizes, and 12/24-hour timestamp overlays.
- Added local GPS minimap rendering in exports.
- Added 13-language UI and localized export labels.
- Added configurable GitHub Release update checking and installer launch.
- Added configurable support URL, optional support/chat REST endpoint, opt-in clip sharing, and shared-clip management.
- Added an optional sample 48-hour self-hosted clip-share backend.
- Updated the Windows release builder to bundle a full FFmpeg distribution so NVENC/QSV/AMF discovery works on clean installations when supported by the GPU/driver.
- Preserved the tested Tesla SEI parser and the Tesla 10,000-fps metadata workaround from 0.2.

## 0.2.0

- Validated Tesla SEI decoding against a real 2026 Tesla clip.
- Added robust average-frame-rate selection for Tesla footage reporting a bogus `r_frame_rate` value.
- Added Windows installer and portable build targets.
- Added GitHub Actions release workflow.

## 0.1.0

- Initial SEI telemetry decoder, CSV export, HUD export, and basic four-camera mosaic support.
