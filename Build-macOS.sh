#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

VERSION="$(python3 -c 'from tts_core import APP_VERSION; print(APP_VERSION)')"
ARCH="$(uname -m)"
case "$ARCH" in
  arm64|aarch64) RELEASE_ARCH="arm64" ;;
  x86_64) RELEASE_ARCH="x86_64" ;;
  *) echo "Unsupported macOS architecture: $ARCH" >&2; exit 2 ;;
esac

rm -rf build dist release/macos-temp
mkdir -p build release

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements-build.txt

FFMPEG_SRC="$(python3 -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')"
mkdir -p build/ffmpeg_bin
cp "$FFMPEG_SRC" build/ffmpeg_bin/ffmpeg
chmod +x build/ffmpeg_bin/ffmpeg

echo "Bundled FFmpeg: $(build/ffmpeg_bin/ffmpeg -version | head -1)"
if build/ffmpeg_bin/ffmpeg -hide_banner -encoders 2>/dev/null | grep -q h264_videotoolbox; then
  echo "Apple VideoToolbox encoder detected."
else
  echo "WARNING: bundled FFmpeg does not expose h264_videotoolbox; Cammetry will use CPU H.264 unless another compatible FFmpeg is available." >&2
fi

ICONSET="build/Cammetry.iconset"
mkdir -p "$ICONSET"
for spec in "16 icon_16x16.png" "32 icon_16x16@2x.png" "32 icon_32x32.png" "64 icon_32x32@2x.png" "128 icon_128x128.png" "256 icon_128x128@2x.png" "256 icon_256x256.png" "512 icon_256x256@2x.png" "512 icon_512x512.png" "1024 icon_512x512@2x.png"; do
  set -- $spec
  sips -z "$1" "$1" assets/app.png --out "$ICONSET/$2" >/dev/null
done
iconutil -c icns "$ICONSET" -o build/Cammetry.icns

python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name Cammetry \
  --icon build/Cammetry.icns \
  --osx-bundle-identifier us.aniv.cammetry \
  --add-binary "build/ffmpeg_bin/ffmpeg:ffmpeg_bin" \
  --add-data "LICENSE:." \
  --add-data "PRIVACY.md:." \
  --add-data "TRADEMARKS.md:." \
  cammetry.py

APP="dist/Cammetry.app"
if [[ ! -d "$APP" ]]; then
  echo "PyInstaller did not create $APP" >&2
  exit 3
fi

codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"

# Remove PyInstaller intermediates before packaging to preserve runner disk space.
rm -rf build

ZIP="release/Cammetry-macOS-${RELEASE_ARCH}-v${VERSION}.zip"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ZIP"

SHA_FILE="release/Cammetry-macOS-${RELEASE_ARCH}-v${VERSION}.sha256.txt"
if [[ "$RELEASE_ARCH" == "arm64" ]]; then
  # Apple Silicon hosted runners have enough headroom for the user-friendly DMG.
  ln -s /Applications "dist/Applications"
  DMG="release/Cammetry-macOS-${RELEASE_ARCH}-v${VERSION}.dmg"
  hdiutil create -volname "Cammetry" -srcfolder "dist" -ov -format UDZO "$DMG" >/dev/null
  rm -f "dist/Applications"
  shasum -a 256 "$DMG" "$ZIP" | tee "$SHA_FILE"
  echo "macOS release created:"
  echo "  $DMG"
  echo "  $ZIP"
else
  # GitHub's hosted Intel image has very limited free disk after the native app
  # is frozen. Publish the signed app bundle as a ZIP rather than risking a
  # failing DMG build. Users can unzip and drag Cammetry.app to Applications.
  shasum -a 256 "$ZIP" | tee "$SHA_FILE"
  echo "macOS Intel release created:"
  echo "  $ZIP"
fi
