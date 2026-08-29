# Contributing to Cammetry

Thank you for helping improve Cammetry.

## Good first contributions

- Reproduce and document compatibility issues with TeslaCam files.
- Improve documentation or translations.
- Add tests for clip naming, event parsing, SEI telemetry decoding, and export logic.
- Improve accessibility and keyboard navigation.
- Optimize playback or export without weakening privacy defaults.

## Before opening a pull request

1. Search existing issues and pull requests.
2. For major UI or architecture changes, open a discussion/issue first.
3. Keep changes focused.
4. Do not commit personal TeslaCam footage, GPS tracks, access tokens, API keys, passwords, or private URLs.
5. Do not copy code, icons, screenshots, or proprietary assets from Tesla or another application unless the license explicitly permits it and attribution requirements are satisfied.
6. Run the smoke checks described below.

## Development setup

Windows quick start:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python cammetry.py
```

## Checks

```powershell
python -m compileall cammetry.py tts_core.py tts_ui.py tts_player.py tts_export.py tts_settings.py tts_locales.py
python -m unittest discover -s tests -v
```

When changing video export logic, also test at least one real clip locally. Never upload somebody else's recording to a public issue without permission.

## Pull requests

A strong pull request includes:

- what changed and why;
- screenshots for visible UI changes;
- testing performed;
- privacy/security impact if relevant;
- operating system and Python version for environment-sensitive changes.

By contributing, you agree that your contribution is licensed under the project's MIT License.
