# Cammetry feature overview

Cammetry is a local-first desktop TeslaCam viewer, telemetry explorer, and exporter. The application is independently developed and is not affiliated with Tesla, Inc.

## Clip browsing and events

- Open a normal TeslaCam root or an arbitrary folder containing compatible camera files.
- Automatically detect mounted TeslaCam USB drives/folders when possible.
- Browse Recent, Saved, and Sentry clips.
- Search/filter events and browse by recorded time.
- Group synchronized camera files by Tesla timestamp.
- Read `event.json` metadata when present.
- Human-readable trigger labels including Manual Save, Sentry, Honk, Object Detected, Alarm, and safety/impact events when metadata provides them.
- Highlight the triggering camera when the metadata identifies it unambiguously.
- Jump directly to an event marker.
- Delete a selected event/camera set using Recycle Bin/Trash when the platform supports it.
- Save a still image from the active camera.

## Multi-camera playback

- Up to six synchronized exterior camera views.
- Front, rear, left/right repeaters, and supported HW4/AI4 left/right pillar camera files.
- Six-camera, four-camera, and single-camera layouts.
- Shared playhead and seeking across cameras.
- Playback at 0.5x, 1x, 2x, and 4x.
- Click a camera to make it the active/focus camera.

## Embedded SEI telemetry

For compatible driving clips containing Tesla's embedded metadata, Cammetry can visualize/export:

- vehicle speed
- gear
- steering wheel angle
- accelerator position
- brake state
- left/right turn indicators
- driver-assistance state (including Self-Driving/FSD, Autosteer, and TACC values when present)
- GPS latitude/longitude
- heading
- X/Y/Z linear acceleration
- telemetry sample/frame matching
- CSV telemetry export

Telemetry availability depends on the vehicle, firmware, recording state, and the contents of each MP4.

## Maps and timeline

- Fully local/offline GPS route view by default.
- Optional OpenStreetMap background, enabled explicitly by the user.
- Driver-assist route coloring (Self-Driving vs. manual segments).
- Current-position marker synchronized with playback.
- Route zoom and pan.
- Event/telemetry timeline with playhead, trim points, driver-assist, brake, and turn-indicator activity.

## Clip insights

- average speed
- maximum speed
- approximate distance covered
- percentage of telemetry samples using driver assistance
- brake-frame/sample count
- telemetry/video sample match

## Export

- In/Out trim points.
- Single-, four-, and six-camera exports.
- Four quality presets: Mobile, Medium, High, Maximum.
- Hardware encoder discovery and CPU fallback:
  - NVIDIA NVENC
  - AMD AMF
  - Intel Quick Sync
  - Apple VideoToolbox
  - CPU x264
- Default and Compact telemetry dashboard styles.
- Dashboard size: Small, Medium, Large, X-Large.
- Localized dashboard/telemetry labels.
- Optional timestamp overlay.
- 12-hour or 24-hour time.
- Multiple date formats.
- Optional GPS text.
- Optional locally-rendered GPS minimap.
- User-drawn persistent privacy blur zones with adjustable blur strength.
- Non-blocking export with floating progress notification.

## 13-language localization

Cammetry ships language packs for:

1. English
2. Spanish
3. French
4. German
5. Chinese (Simplified)
6. Japanese
7. Korean
8. Portuguese
9. Russian
10. Italian
11. Dutch
12. Polish
13. Turkish

In v0.5, all 218 standard UI/message keys are present in every language pack. Automated tests also verify that translated format strings preserve the required placeholders. Export dashboard labels follow the selected language. Technical names such as GPS, CSV, FFmpeg, encoder names, file extensions, and date-format tokens intentionally remain canonical where appropriate.

## Settings and quality of life

- Imperial/metric units.
- 12/24-hour time.
- Four date formats.
- Offline or optional online route-map mode.
- Adjustable seek interval.
- Custom keyboard bindings for primary transport/trim actions.
- Default TeslaCam folder.
- Automatic mounted-drive detection.
- Configurable privacy blur strength.
- Configurable GitHub Releases update source.
- First-run privacy notice.
- No anonymous usage/version analytics in official Cammetry builds.

## Optional network features

Cammetry's core viewer/exporter works locally and without an account.

- **Updates:** optional GitHub Releases checks when a repository is configured.
- **Temporary sharing:** the client, 48-hour expiry metadata, share history, preview/open/copy/delete management, and a self-hostable reference backend are included. A public Cammetry sharing service is not bundled or silently configured.
- **Support:** built-in support/feedback UI can open a project support page or use a maintainer-configured REST endpoint.
- **OpenStreetMap:** optional map tiles are requested only when the user selects the online map mode; the offline local route remains the default.

See `PRIVACY.md` before enabling network features.

## Platform status

- Windows 10/11: primary tested platform; installer and portable release targets are included.
- macOS: native Apple Silicon and Intel `.app`/`.dmg` release targets are automated with GitHub Actions. Test builds are ad-hoc signed; Apple Developer ID signing/notarization remains the production-distribution step.
- Linux: source workflow supported; native package formats are not yet an official release target.

See `docs/BUILDING.md`.
