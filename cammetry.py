#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

APP_VERSION = "0.6.0-beta"


def enable_windows_dpi_awareness() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def main() -> int:
    enable_windows_dpi_awareness()
    import tts_core
    tts_core.APP_VERSION = APP_VERSION
    from tts_v060_ui import App
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
