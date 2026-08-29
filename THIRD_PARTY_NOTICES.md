# Third-party notices

Cammetry source code is distributed under the MIT License. The release builder also packages independent third-party components under their own licenses.

## FFmpeg

Windows release builds download FFmpeg binaries from the BtbN FFmpeg-Builds project:

- Project: https://github.com/BtbN/FFmpeg-Builds
- Upstream FFmpeg: https://ffmpeg.org/
- Build used by `Build-Release.ps1`: `ffmpeg-master-latest-win64-gpl.zip`

The bundled FFmpeg executable is a separate third-party program and is distributed under the license applicable to that build. FFmpeg licensing information and source-code links are available from the upstream projects above. Cammetry invokes FFmpeg as an external executable for probing, compositing, privacy blur, telemetry overlays, and video encoding.

## Other Python packages

Release builds may bundle the Python runtime and packages listed in `requirements.txt` / `requirements-build.txt`, including OpenCV, Pillow, ImageIO-FFmpeg, Send2Trash, and PyInstaller. Each remains subject to its own license.

No Tesla source code, logos, icons, or proprietary assets are included in Cammetry.

## OpenStreetMap

Cammetry can optionally display an online OpenStreetMap tile background for GPS routes. The offline local route view remains the default.

- OpenStreetMap: https://www.openstreetmap.org/
- Copyright/licensing: https://www.openstreetmap.org/copyright
- Standard tile policy: https://operations.osmfoundation.org/policies/tiles/

OpenStreetMap data is made available under the Open Data Commons Open Database License (ODbL). The UI displays `© OpenStreetMap contributors` when the online map is in use. The standard tile service is a separate community-funded service and is not bundled with Cammetry.
