# Changelog

## 0.5.1 Beta

Consolidated Windows beta based on hands-on testing of v0.5.0 against a real TeslaCam library.

### Viewer and navigation
- Changed the main action to **Browse TeslaCam…** and made the folder picker start from the current path, a detected TeslaCam drive, or the user's Videos folder.
- Automatically selects the newest visible recording after a successful scan.
- Added an always-visible dark vertical scrollbar to the Events list while preserving mouse-wheel scrolling.
- Added independent calendar/date filtering with per-day clip counts, Today, Last 7 Days, Last 30 Days, All Dates, single-day selection, and custom date ranges.
- Added an adaptive **Auto (N cameras)** layout driven by the streams actually present in each recording rather than assuming a vehicle hardware generation.
- Added an original **Vehicle View / Camera Map** with clickable recorded camera positions and a return-to-Auto action.
- Added Fit/Fill viewport modes and zoom controls.
- Added live non-destructive exposure, contrast, saturation, and gamma adjustments.

### Playback and trim UX
- Reworked the center-bottom controls into a cohesive media transport/trim surface with timecode, playback speed, skip, Play/Pause, a wide telemetry timeline, Start/End trim markers, Export, Publish, Snapshot, and an overflow menu.
- Timeline playback now moves only the playhead instead of rebuilding the entire telemetry visualization every frame.
- Video rendering is suspended while minimized and throttled/debounced while resizing to improve minimize/maximize and window-resize responsiveness.
- Route and telemetry redraw rates are reduced independently from video refresh.
- Only camera tiles visible in the active layout are rendered.

### Export and telemetry HUD
- Fixed malformed ASS subtitle rows that caused the telemetry HUD text to disappear while the minimap still rendered.
- Added an original Cammetry telemetry HUD with Full, Compact, and Minimal styles plus size, opacity, and top/bottom placement controls.
- Added independent export toggles for speed, driver-assist state, gear, steering, accelerator, brake, blinkers, G-force, timestamp, GPS coordinates, and GPS minimap.
- Single-camera exports now support **Preserve Source**, **Fit 16:9**, and **Fill 16:9** framing; Preserve Source avoids unnecessary black side bars.
- Current exposure/contrast/saturation/gamma adjustments can be applied to exports.
- Hardware encoders are now validated with a tiny real encode before they are offered.
- **Auto** selects a working encoder; hardware failures automatically retry using CPU x264 instead of forcing users onto one specific GPU-driver version.
- Export errors are shorter and more actionable while Diagnostics retains the useful environment/encoder information.

### Help, publishing, and privacy
- Replaced the meaningless empty support-chat experience with **Help & About**, quick-start instructions, shortcuts, documentation/issues links, update checking, and privacy-safe diagnostics.
- Reworked Share into **Publish / Share**. The initial beta provides YouTube/Vimeo/TikTok upload-page handoff, Reveal File, Copy Path, and the optional existing temporary-link backend when configured. Direct OAuth publishing can be layered in later without blocking the local workflow.
- Publish shows a privacy reminder for GPS/minimap, timestamps, faces, and license plates.
- Diagnostics intentionally avoids exposing GPS coordinates.

### Windows installation and polish
- Removed the `Unofficial` suffix from official Cammetry window titles.
- Fixed misleading pre-selection telemetry and route states and clears stale state when switching recordings.
- Bundles the Cammetry icon as a runtime asset for the Windows title bar.
- Windows Setup defaults to `Program Files\Cammetry` with conventional per-machine UAC installation and system-wide Start Menu registration.
- Setup and Uninstall now detect a running Cammetry instance, ask to close it, close/terminate any remaining process if necessary, and only then replace/remove the install tree. This prevents partial uninstalls caused by locked application files.
- Documented the Windows code-signing policy and release verification requirements.

### Notes
- Cammetry remains free and open source, local-first by default, and unaffiliated with or endorsed by Tesla, Inc.
- The existing 13-language translation system remains intact. Newly introduced beta-only advanced controls may receive additional translation polish before a later stable release.

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
- Added synchronized six-camera preview support including left/right pillar camera streams when present.
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
