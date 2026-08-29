from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

DEFAULT_SETTINGS: Dict[str, Any] = {
    "default_folder": "",
    "units": "mph",
    "time_format": "12h",
    "date_format": "YYYY-MM-DD",
    "map_mode": "Local Grid (offline)",
    "language": "English",
    "seek_seconds": 10,
    "shortcut_play": "Space",
    "shortcut_back": "Left Arrow",
    "shortcut_forward": "Right Arrow",
    "shortcut_in": "I",
    "shortcut_out": "O",
    "glass_blur": 12,
    "export_quality": "High",
    "export_layout": "Six Camera",
    "dashboard_size": "Medium",
    "dashboard_style": "Default",
    "show_timestamp": True,
    "show_minimap": False,
    "show_gps_text": False,
    "encoder": "Auto",
    "check_updates": True,
    "update_repo": "anivdas/Cammetry",
    "support_url": "https://github.com/anivdas/Cammetry/issues",
    "support_endpoint": "",
    "share_endpoint": "",
    "privacy_notice_seen": False,
}


def settings_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
        return base / "Cammetry"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Cammetry"
    return Path.home() / ".config" / "Cammetry"


def settings_path() -> Path:
    return settings_dir() / "settings.json"


def load_settings() -> Dict[str, Any]:
    settings = dict(DEFAULT_SETTINGS)
    p = settings_path()
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            settings.update(payload)
    except Exception:
        pass
    return settings


def save_settings(settings: Dict[str, Any]) -> None:
    p = settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
