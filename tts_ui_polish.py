from __future__ import annotations

import os
import subprocess
import tkinter as tk
from typing import Callable, Optional


BG = "#0b0f14"
PANEL = "#111821"
CARD2 = "#1b2632"
TEXT = "#edf3f8"
MUTED = "#8b99a8"
ACCENT = "#3b82f6"
DANGER = "#ef5b5b"
BORDER = "#334155"
GOOD = "#37c978"


def _mix(hex_color: str, amount: float) -> str:
    color = hex_color.lstrip("#")
    try:
        r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    except Exception:
        return hex_color
    if amount >= 0:
        r += int((255 - r) * amount); g += int((255 - g) * amount); b += int((255 - b) * amount)
    else:
        factor = 1.0 + amount
        r = int(r * factor); g = int(g * factor); b = int(b * factor)
    return f"#{max(0,min(255,r)):02x}{max(0,min(255,g)):02x}{max(0,min(255,b)):02x}"


def _widget_bg(widget, fallback: str) -> str:
    for key in ("bg", "background"):
        try:
            value = str(widget.cget(key))
            if value:
                return value
        except Exception:
            pass
    return fallback


class FluentButton(tk.Canvas):
    """Canvas-backed button with a modern flat/rounded appearance and keyboard focus."""

    def __init__(self, parent, text: str, command: Callable[[], None], accent: bool = False,
                 width: Optional[int] = None, danger: bool = False):
        self._text = str(text)
        self._command = command
        self._state = "normal"
        self._base_fill = ACCENT if accent else DANGER if danger else CARD2
        self._parent_bg = _widget_bg(parent, BG)
        self._height_px = 34
        self._natural_width = max(42, int(width or 0) * 10 + 18) if width else max(58, len(self._text) * 7 + 28)
        self._width_px = self._natural_width
        super().__init__(
            parent,
            width=self._width_px,
            height=self._height_px,
            bg=self._parent_bg,
            highlightthickness=0,
            bd=0,
            relief="flat",
            cursor="hand2",
            takefocus=1,
        )
        self.bind("<Button-1>", self._click)
        self.bind("<Return>", self._key_invoke)
        self.bind("<space>", self._key_invoke)
        self.bind("<Enter>", lambda _e: self._draw(hover=True))
        self.bind("<Leave>", lambda _e: self._draw())
        self.bind("<FocusIn>", lambda _e: self._draw(focused=True))
        self.bind("<FocusOut>", lambda _e: self._draw())
        self.bind("<Configure>", self._on_resize)
        self._draw()

    def _on_resize(self, event):
        width = max(2, int(event.width))
        height = max(2, int(event.height))
        if width != self._width_px or height != self._height_px:
            self._width_px = width
            self._height_px = height
            self._draw()

    def _round_rect(self, x1, y1, x2, y2, radius, *, fill, outline, width=1):
        r = max(2, min(radius, int((y2 - y1) / 2)))
        self.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline="")
        self.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline="")
        self.create_arc(x1, y1, x1 + 2*r, y1 + 2*r, start=90, extent=90, fill=fill, outline="")
        self.create_arc(x2 - 2*r, y1, x2, y1 + 2*r, start=0, extent=90, fill=fill, outline="")
        self.create_arc(x1, y2 - 2*r, x1 + 2*r, y2, start=180, extent=90, fill=fill, outline="")
        self.create_arc(x2 - 2*r, y2 - 2*r, x2, y2, start=270, extent=90, fill=fill, outline="")
        if outline:
            self.create_line(x1+r, y1, x2-r, y1, fill=outline, width=width)
            self.create_line(x1+r, y2, x2-r, y2, fill=outline, width=width)
            self.create_line(x1, y1+r, x1, y2-r, fill=outline, width=width)
            self.create_line(x2, y1+r, x2, y2-r, fill=outline, width=width)

    def _draw(self, hover: bool = False, focused: bool = False):
        self.delete("all")
        disabled = self._state == "disabled"
        fill = "#18212b" if disabled else _mix(self._base_fill, 0.10 if hover else 0.0)
        outline = ACCENT if focused and not disabled else _mix(fill, 0.18)
        fg = "#64748b" if disabled else "#ffffff"
        self._round_rect(1, 1, self._width_px - 2, self._height_px - 2, 7, fill=fill, outline=outline)
        self.create_text(self._width_px / 2, self._height_px / 2, text=self._text, fill=fg,
                         font=("Segoe UI Semibold", 9), anchor="center")
        try:
            super().configure(cursor="arrow" if disabled else "hand2")
        except Exception:
            pass

    def _click(self, _event=None):
        if self._state != "disabled" and callable(self._command):
            self.focus_set()
            self._command()

    def _key_invoke(self, _event=None):
        self._click()
        return "break"

    def invoke(self):
        self._click()

    def configure(self, cnf=None, **kwargs):
        if cnf:
            kwargs.update(cnf)
        redraw = False
        if "text" in kwargs:
            self._text = str(kwargs.pop("text"))
            self._natural_width = max(58, len(self._text) * 7 + 28)
            try:
                super().configure(width=self._natural_width)
            except Exception:
                pass
            redraw = True
        if "state" in kwargs:
            self._state = str(kwargs.pop("state")); redraw = True
        if "bg" in kwargs:
            self._base_fill = str(kwargs.pop("bg")); redraw = True
        if "command" in kwargs:
            self._command = kwargs.pop("command")
        if kwargs:
            try:
                super().configure(**kwargs)
            except tk.TclError:
                pass
        if redraw and self.winfo_exists():
            self._draw()
        return None

    config = configure

    def cget(self, key):
        if key == "text": return self._text
        if key == "state": return self._state
        if key == "bg": return self._base_fill
        return super().cget(key)


class AccessibleCheck(tk.Canvas):
    """High-contrast checkbox indicator bound to an existing BooleanVar."""

    def __init__(self, parent, variable: tk.Variable, size: int = 20):
        self.variable = variable
        self.size = max(18, int(size))
        super().__init__(parent, width=self.size, height=self.size, bg=_widget_bg(parent, PANEL),
                         highlightthickness=0, bd=0, cursor="hand2", takefocus=1)
        self.bind("<Button-1>", self._toggle)
        self.bind("<Return>", self._toggle)
        self.bind("<space>", self._toggle)
        self.bind("<FocusIn>", lambda _e: self._draw(True))
        self.bind("<FocusOut>", lambda _e: self._draw(False))
        try:
            self.variable.trace_add("write", lambda *_: self._draw(False))
        except Exception:
            pass
        self._draw(False)

    def _toggle(self, _event=None):
        try:
            self.variable.set(not bool(self.variable.get()))
        except Exception:
            pass
        self.focus_set()
        return "break"

    def _draw(self, focused: bool):
        self.delete("all")
        checked = bool(self.variable.get())
        pad = 2
        outline = "#93c5fd" if focused else (ACCENT if checked else "#718096")
        fill = ACCENT if checked else "#0b1118"
        self.create_rectangle(pad, pad, self.size-pad, self.size-pad, fill=fill, outline=outline, width=2)
        if checked:
            self.create_line(self.size*0.25, self.size*0.52, self.size*0.43, self.size*0.70,
                             self.size*0.76, self.size*0.31, fill="white", width=2,
                             capstyle="round", joinstyle="round")


def flat_button(parent, text, command, accent=False, width=None, danger=False):
    return FluentButton(parent, text, command, accent=accent, width=width, danger=danger)


def upgrade_native_checkbuttons(root: tk.Misc) -> None:
    """Replace dark native Tk indicators with high-contrast custom indicators.

    The original BooleanVar is reused, so existing dialog save/export closures keep
    working unchanged.
    """
    stack = list(root.winfo_children())
    while stack:
        widget = stack.pop(0)
        children = list(widget.winfo_children())
        stack.extend(children)
        if not isinstance(widget, tk.Checkbutton):
            continue
        try:
            variable_name = str(widget.cget("variable"))
            variable = tk.BooleanVar(master=root, name=variable_name)
            parent = widget.master
            manager = widget.winfo_manager()
            pack_info = widget.pack_info() if manager == "pack" else None
            grid_info = widget.grid_info() if manager == "grid" else None
            widget.destroy()
            replacement = AccessibleCheck(parent, variable)
            if manager == "pack" and pack_info:
                opts = {k: v for k, v in pack_info.items() if k not in {"in"}}
                replacement.pack(**opts)
            elif manager == "grid" and grid_info:
                opts = {k: v for k, v in grid_info.items() if k not in {"in"}}
                replacement.grid(**opts)
        except Exception:
            continue


def install_runtime_polish() -> None:
    """Install UI factory and hardware-encoder probe refinements before App builds."""
    import tts_ui
    import tts_modern_ui
    import tts_release_ui
    import tts_export_v051

    tts_ui.flat_button = flat_button
    tts_modern_ui.flat_button = flat_button
    tts_release_ui.flat_button = flat_button

    def robust_encoder_smoke_test(codec: str) -> bool:
        if codec == "libx264":
            return True
        ffmpeg = tts_export_v051.get_ffmpeg_exe()
        key = (ffmpeg, codec, "640x360-v2")
        cache = tts_export_v051._ENCODER_SMOKE_CACHE
        cached = cache.get(key)
        if cached is not None:
            return bool(cached)
        cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=black:s=640x360:r=30:d=0.15",
            "-frames:v", "3", "-an", "-pix_fmt", "yuv420p",
            "-c:v", codec, "-f", "null", "-",
        ]
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
            )
            ok = result.returncode == 0
        except Exception:
            ok = False
        cache[key] = ok
        return ok

    tts_export_v051._encoder_smoke_test = robust_encoder_smoke_test
