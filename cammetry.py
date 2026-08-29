#!/usr/bin/env python3
from __future__ import annotations

import os
import sys


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
    from tts_modern_ui import App
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
