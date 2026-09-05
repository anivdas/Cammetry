# Architecture

Cammetry intentionally keeps the desktop code straightforward so hobbyists can understand and compile it.

## `cammetry.py`

Small entry point. Enables Windows DPI awareness and starts the desktop UI.

## `tts_core.py`

Core domain layer:

- TeslaCam filename recognition and clip grouping
- MP4/SEI telemetry parsing
- telemetry dataclasses and unit helpers
- video probing
- CSV export
- FFmpeg runtime discovery

Despite the historical `tts_` module prefix, these modules are part of Cammetry. Renaming internal modules can be done later as a compatibility-neutral refactor.

## `tts_player.py`

Synchronized local preview engine backed by OpenCV. Maintains one shared playback clock across available camera files.

## `tts_ui.py`

Tkinter/Pillow/OpenCV desktop interface, event browser, camera wall, telemetry panels, settings, update hooks, sharing hooks, and export orchestration.

## `tts_export.py`

FFmpeg command construction for layouts, overlays, privacy blur zones, minimaps, trimming, and encoder selection.

## `tts_settings.py`

Local JSON settings. On Windows, preferences live under the user's application-data directory.

## Cammetry 0.6 workflow services

- `tts_sequence.py` models adjacent one-minute source groups as one continuous event timeline.
- `tts_event_detection.py` creates deterministic, local telemetry review markers.
- `tts_compatibility.py` performs export and playback preflight checks and produces privacy-safe reports.
- `tts_library.py` owns the local SQLite catalog, user notes/tags/bookmarks, and verified imports.
- `tts_incident.py` creates portable incident manifests, reports, hashes, and optional evidence copies.
- `tts_privacy.py` owns privacy presets and optional local first-pass face/plate region detection.

These modules deliberately contain no user-interface dependency.

## `tts_v060_ui.py`

The integrated Python 0.6 workflow layer. It exposes the new services while
preserving the tested v0.5 playback and export implementation.

## `cammetry_bridge.py`

A local line-delimited JSON protocol over stdin/stdout. It opens no listening
port and allows native presentation shells to call the Python domain services.

## `windows/Cammetry.WinUI/`

The native C#/XAML Windows shell. This is an actual WinUI 3 Windows App SDK
project rather than a styled Tkinter window. The existing Python UI remains the
production fallback until the native viewer/export migration gates pass. See
`docs/WINUI3.md`.

## `tts_locales.py`

UI translation dictionaries.

## `share_backend/`

Optional, separate self-hosted service for temporary sharing. Cammetry itself remains useful without this component.
