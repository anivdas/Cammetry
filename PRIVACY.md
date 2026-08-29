# Cammetry privacy statement

Cammetry is designed around a simple default: **your TeslaCam recordings and location data stay on your computer unless you explicitly choose otherwise.**

## Local processing

Core playback, camera synchronization, SEI telemetry decoding, offline route visualization, CSV export, privacy blur processing, snapshots, and video export are performed locally.

Cammetry does not require Tesla account credentials.

## Analytics

Official Cammetry builds do **not** enable background user analytics, anonymous version statistics, advertising tracking, or sale of usage data.

## GPS

Compatible recordings may contain precise latitude/longitude data. Treat exported CSV files, route screenshots, shared clips, and overlays as location-sensitive information.

GPS text/minimap export options remain opt-in rather than silently exposing coordinates.

## Map modes

The default **Local Grid (offline)** route view makes no map-server request.

If the user explicitly switches to **OpenStreetMap (online)**, Cammetry requests only the map tiles needed to display the route area. Those requests disclose the approximate viewed map area and the app's network address to the tile service. Cammetry does not upload the TeslaCam video or SEI telemetry payload with those requests. Tiles are cached locally, and OpenStreetMap attribution is displayed in the map view.

OpenStreetMap use is subject to its own terms and tile-use policy.

## Optional network features

The application contains configurable hooks for:

- update checking through GitHub Releases;
- project support/feedback;
- temporary clip sharing;
- optional OpenStreetMap route backgrounds.

They are separate from core playback/export and should remain clearly user-initiated/configured. Temporary sharing necessarily transmits the selected exported media to the configured sharing service.

A self-hostable example sharing backend is provided under `share_backend/`. Official builds do not silently configure a third-party clip-hosting service.

## Test footage

Maintainers and contributors should not commit private vehicle recordings or GPS traces to the public repository. Common video/telemetry output formats and TeslaCam folders are ignored by Git by default.

## Non-affiliation

Cammetry is not affiliated with Tesla, Inc. See `TRADEMARKS.md`.
