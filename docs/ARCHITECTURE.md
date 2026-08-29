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

## `tts_locales.py`

UI translation dictionaries.

## `share_backend/`

Optional, separate self-hosted service for temporary sharing. Cammetry itself remains useful without this component.
