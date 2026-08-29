# Building and running Cammetry from source

## Runtime requirements

- Python 3.12 or newer compatible release
- Internet access for the first dependency installation
- Tk support for your Python installation
- FFmpeg: Cammetry first uses a packaged/system FFmpeg, then falls back to ImageIO-FFmpeg for basic source operation

## Windows — easiest source workflow

1. Install Python 3.12+ from python.org and enable the PATH option.
2. Download/clone the repository.
3. Double-click `Run-From-Source.cmd`.

Manual equivalent:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python cammetry.py
```

## macOS — run from source

Python from python.org is recommended because it includes a suitable Tk build. Cammetry can use its Python-bundled FFmpeg automatically; a recent Homebrew FFmpeg can also be used during source development and may expose additional codecs.

```bash
./Run-From-Source.sh
```

or manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python cammetry.py
```

If your FFmpeg exposes `h264_videotoolbox`, Cammetry offers **Apple VideoToolbox** in the encoder list.

## Linux

Install Python, Tk, and FFmpeg using your distribution's package manager. For Debian/Ubuntu-family systems, typical prerequisites are:

```bash
sudo apt install python3 python3-venv python3-tk ffmpeg
```

Then:

```bash
./Run-From-Source.sh
```

## Build distributable macOS packages

On a Mac, run:

```bash
./Build-macOS.sh
```

This creates a native `.app`, a drag-to-Applications `.dmg`, a zipped `.app`, and SHA-256 checksums. The build bundles FFmpeg so end users do not need Homebrew or a separate FFmpeg install.

Expected outputs on Apple Silicon:

```text
release/
  Cammetry-macOS-arm64-vX.Y.Z.dmg
  Cammetry-macOS-arm64-vX.Y.Z.zip
  Cammetry-macOS-arm64-vX.Y.Z.sha256.txt
```

Intel builds use `x86_64` in the filenames. GitHub Actions builds both architectures on native hosted macOS runners.

### macOS signing and Gatekeeper

Local/test builds are ad-hoc signed. That verifies bundle integrity but does **not** make them Apple-notarized. Public releases should eventually be signed with an Apple Developer ID certificate and notarized with Apple so users do not receive an unidentified-developer warning. The project intentionally does not require a paid Apple Developer account merely to compile from source.

## Build distributable Windows packages

```powershell
.\Build-Release.ps1
```

The script uses PyInstaller and NSIS and outputs files to `release/`.

The Windows builder stages a full FFmpeg distribution so clean installations can discover supported GPU encoders without requiring users to install FFmpeg separately. If NSIS is missing and `winget` is available, the script attempts to install it automatically.

Expected outputs:

```text
release/
  Cammetry-Setup-vX.Y.Z.exe
  Cammetry-Portable-vX.Y.Z.exe
  Cammetry-Portable-vX.Y.Z.zip
```

## Hardware encoding

Actual hardware acceleration depends on OS, GPU, driver, and the available FFmpeg build. Cammetry detects:

- NVIDIA: `h264_nvenc`
- Intel: `h264_qsv`
- AMD: `h264_amf`
- Apple: `h264_videotoolbox`
- fallback: `libx264`

## Tests

```bash
python -m py_compile cammetry.py tts_core.py tts_export.py tts_locales.py tts_map.py tts_player.py tts_settings.py tts_ui.py
python -m unittest discover -s tests -p "test_*.py" -v
```

The GitHub CI workflow runs the unit tests on Windows, macOS, and Linux. It includes checks that all 13 language packs contain every standard localization key and preserve format placeholders.

## Packaging status

- Windows Setup.exe + portable builds: supported build target.
- macOS `.app` + `.dmg`: supported automated build target for Apple Silicon and Intel. Test builds are ad-hoc signed; Developer ID signing/notarization is the remaining public-distribution step.
- Linux: source workflow supported; AppImage/deb/rpm packaging is not yet an official target.

## Troubleshooting

### Python is not found

Install Python 3.12+ and retry. On Windows, the `py` launcher is preferred when available.

### Tkinter is missing

Linux distributions often package Tk separately (`python3-tk`). Python.org's Windows/macOS distributions normally include Tk.

### Video opens but telemetry is empty

Not every TeslaCam file contains embedded SEI telemetry. Parked/Sentry footage may contain video without driving telemetry. Compatibility also depends on vehicle, firmware, and file format.

### Hardware encoder is unavailable

Update the GPU driver and verify that your FFmpeg build reports the desired encoder. Cammetry falls back to CPU x264 when hardware encoding is unavailable.
