from __future__ import annotations

import tkinter as tk
from typing import Callable

from tts_ui_polish import ACCENT, BG, BORDER, CARD2, FluentButton, MUTED, TEXT, _mix, _widget_bg


_POLISH_INSTALLED = False


def install_button_interaction_polish() -> None:
    """Give Cammetry buttons subtle Fluent-like hover/press feedback.

    The previous beta brightened the entire surface on hover and invoked immediately
    on mouse-down, which made controls look as though they changed theme. This patch
    keeps the surface stable, adds a quiet border/elevation cue, and invokes on release.
    """
    global _POLISH_INSTALLED
    if _POLISH_INSTALLED:
        return
    _POLISH_INSTALLED = True

    original_init = FluentButton.__init__

    def polished_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._hovered = False
        self._pressed = False
        # Replace inherited pointer bindings with explicit state transitions.
        self.bind("<Enter>", self._cammetry_enter)
        self.bind("<Leave>", self._cammetry_leave)
        self.bind("<ButtonPress-1>", self._cammetry_press)
        self.bind("<ButtonRelease-1>", self._cammetry_release)
        self.bind("<FocusIn>", lambda _e: self._draw(focused=True))
        self.bind("<FocusOut>", lambda _e: self._draw())
        self._draw()

    def enter(self, _event=None):
        self._hovered = True
        if self._state != "disabled":
            self._draw(hover=True)

    def leave(self, _event=None):
        self._hovered = False
        self._pressed = False
        self._draw()

    def press(self, _event=None):
        if self._state == "disabled":
            return "break"
        self._pressed = True
        self.focus_set()
        self._draw(hover=True)
        return "break"

    def release(self, event=None):
        if self._state == "disabled":
            return "break"
        was_pressed = bool(getattr(self, "_pressed", False))
        self._pressed = False
        inside = True
        if event is not None:
            inside = 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height()
        self._hovered = inside
        self._draw(hover=inside)
        if was_pressed and inside and callable(self._command):
            self._command()
        return "break"

    def draw(self, hover: bool = False, focused: bool = False):
        self.delete("all")
        disabled = self._state == "disabled"
        hovered = bool(hover or getattr(self, "_hovered", False)) and not disabled
        pressed = bool(getattr(self, "_pressed", False)) and not disabled

        if disabled:
            fill = "#151c24"
            outline = "#26313e"
            fg = "#657486"
        else:
            # Keep hover deliberately subtle. Accent buttons remain accent instead
            # of flashing to a pale blue; neutral buttons gain only a small lift.
            fill = self._base_fill
            if pressed:
                fill = _mix(fill, -0.09)
            elif hovered:
                fill = _mix(fill, 0.025)
            if focused:
                outline = "#8bb9ff"
            elif hovered:
                outline = _mix(BORDER, 0.22)
            else:
                outline = BORDER if self._base_fill == CARD2 else _mix(self._base_fill, 0.12)
            fg = "#ffffff"

        # A one-pixel top highlight gives the control depth without a Windows-95 bevel.
        self._round_rect(1, 1, self._width_px - 2, self._height_px - 2, 8,
                         fill=fill, outline=outline, width=1)
        if not disabled and not pressed:
            self.create_line(9, 2, max(9, self._width_px - 10), 2,
                             fill=_mix(fill, 0.13 if hovered else 0.07), width=1)
        y = self._height_px / 2 + (1 if pressed else 0)
        self.create_text(self._width_px / 2, y, text=self._text, fill=fg,
                         font=("Segoe UI Semibold", 9), anchor="center")
        try:
            tk.Canvas.configure(self, cursor="arrow" if disabled else "hand2")
        except Exception:
            pass

    FluentButton.__init__ = polished_init
    FluentButton._cammetry_enter = enter
    FluentButton._cammetry_leave = leave
    FluentButton._cammetry_press = press
    FluentButton._cammetry_release = release
    FluentButton._draw = draw


class TransportSeekButton(tk.Canvas):
    """Compact rewind/forward control with the seek interval integrated into the icon."""

    def __init__(self, parent, seconds: int, direction: int, command: Callable[[], None]):
        self.seconds = max(1, int(abs(seconds)))
        self.direction = -1 if direction < 0 else 1
        self.command = command
        self._hovered = False
        self._pressed = False
        self._enabled = True
        self._parent_bg = _widget_bg(parent, BG)
        super().__init__(parent, width=48, height=38, bg=self._parent_bg,
                         highlightthickness=0, bd=0, takefocus=1, cursor="hand2")
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Return>", self._key)
        self.bind("<space>", self._key)
        self.bind("<FocusIn>", lambda _e: self._draw(True))
        self.bind("<FocusOut>", lambda _e: self._draw(False))
        self._draw(False)

    def _enter(self, _event=None):
        self._hovered = True
        self._draw(False)

    def _leave(self, _event=None):
        self._hovered = False
        self._pressed = False
        self._draw(False)

    def _press(self, _event=None):
        if not self._enabled:
            return "break"
        self._pressed = True
        self.focus_set()
        self._draw(True)
        return "break"

    def _release(self, event=None):
        if not self._enabled:
            return "break"
        was_pressed = self._pressed
        self._pressed = False
        inside = True if event is None else (0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height())
        self._hovered = inside
        self._draw(False)
        if was_pressed and inside:
            self.command()
        return "break"

    def _key(self, _event=None):
        if self._enabled:
            self.command()
        return "break"

    def configure(self, cnf=None, **kwargs):
        if cnf:
            kwargs.update(cnf)
        if "state" in kwargs:
            self._enabled = str(kwargs.pop("state")) != "disabled"
            self._draw(False)
        if "command" in kwargs:
            self.command = kwargs.pop("command")
        if kwargs:
            try:
                tk.Canvas.configure(self, **kwargs)
            except tk.TclError:
                pass

    config = configure

    def cget(self, key):
        if key == "state":
            return "normal" if self._enabled else "disabled"
        if key == "text":
            sign = "-" if self.direction < 0 else "+"
            return f"{sign}{self.seconds}s"
        return tk.Canvas.cget(self, key)

    def _draw(self, focused: bool):
        self.delete("all")
        disabled = not self._enabled
        fill = "#151c24" if disabled else ("#17202a" if not self._pressed else "#121920")
        if self._hovered and not disabled and not self._pressed:
            fill = "#1a2530"
        outline = "#8bb9ff" if focused and not disabled else ("#445568" if self._hovered else BORDER)
        fg = "#657486" if disabled else TEXT
        muted = "#566474" if disabled else MUTED

        # Soft capsule surface.
        self.create_rectangle(8, 4, 40, 34, fill=fill, outline=outline, width=1)
        self.create_arc(2, 4, 22, 34, start=90, extent=180, fill=fill, outline=outline, width=1)
        self.create_arc(26, 4, 46, 34, start=270, extent=180, fill=fill, outline=outline, width=1)

        # Curved seek glyph and arrow head, drawn directly so no platform font icon is required.
        if self.direction < 0:
            self.create_arc(12, 9, 36, 31, start=35, extent=265, style="arc", outline=fg, width=2)
            self.create_polygon(11, 11, 19, 10, 15, 17, fill=fg, outline="")
        else:
            self.create_arc(12, 9, 36, 31, start=-120, extent=265, style="arc", outline=fg, width=2)
            self.create_polygon(37, 11, 29, 10, 33, 17, fill=fg, outline="")

        # Interval is part of the icon rather than a separate +/- text label.
        self.create_text(24, 20 + (1 if self._pressed else 0), text=str(self.seconds),
                         fill=fg, font=("Segoe UI Semibold", 8), anchor="center")
        self.create_text(24, 30, text="s", fill=muted, font=("Segoe UI", 6), anchor="center")
