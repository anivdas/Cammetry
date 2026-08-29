from __future__ import annotations

import tkinter as tk
from typing import Callable

from tts_transport_polish import TransportSeekButton
from tts_ui import BG, MUTED, PANEL, TEXT
from tts_ui_polish import flat_button


SPEEDS = (0.5, 1.0, 2.0, 4.0)


def _format_speed(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value))}\u00d7"
    return f"{value:g}\u00d7"


class PlaybackSpeedButton:
    """Explicit media-player speed selector with an in-app option flyout."""

    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        self._overlay = None
        self.button = flat_button(parent, self._label(), self.toggle)

    def _value(self) -> float:
        try:
            return float(self.app.play_speed.get())
        except Exception:
            return 1.0

    def _label(self) -> str:
        return f"Speed  {_format_speed(self._value())}"

    def pack(self, **kwargs):
        return self.button.pack(**kwargs)

    def configure(self, **kwargs):
        return self.button.configure(**kwargs)

    config = configure

    def destroy(self):
        self.close()
        self.button.destroy()

    def close(self):
        panel = self._overlay
        self._overlay = None
        if panel is not None:
            try:
                panel.destroy()
            except Exception:
                pass

    def toggle(self):
        if self._overlay is not None:
            try:
                if self._overlay.winfo_exists():
                    self.close()
                    return
            except Exception:
                self._overlay = None

        self.app.update_idletasks()
        panel = tk.Frame(
            self.app,
            bg=PANEL,
            highlightthickness=1,
            highlightbackground="#46627f",
        )
        self._overlay = panel

        x = self.button.winfo_rootx() - self.app.winfo_rootx()
        y = self.button.winfo_rooty() - self.app.winfo_rooty() + self.button.winfo_height() + 5
        panel.place(x=x, y=y, width=128, height=184)
        panel.tkraise()

        tk.Label(
            panel,
            text="PLAYBACK SPEED",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI Semibold", 8),
            anchor="w",
        ).pack(fill="x", padx=10, pady=(9, 5))

        current = self._value()
        for speed in SPEEDS:
            text = f"\u2713  {_format_speed(speed)}" if abs(speed - current) < 1e-9 else f"    {_format_speed(speed)}"
            flat_button(panel, text, lambda value=speed: self.select(value)).pack(fill="x", padx=8, pady=2)

        panel.bind("<Escape>", lambda _e: self.close())
        panel.focus_set()

    def select(self, value: float):
        self.app.play_speed.set(float(value))
        try:
            self.app.player.set_speed(float(value))
        except Exception:
            pass
        self.button.configure(text=f"Speed  {_format_speed(float(value))}")
        self.close()


def modernize_transport_row(app) -> None:
    """Replace ambiguous combo/text seek controls after the inherited center UI builds."""
    combo = getattr(app, "speed_combo", None)
    if combo is None:
        return
    controls = combo.master

    # Remove inherited speed label/combo and old +/- seek text buttons.
    for child in list(controls.winfo_children()):
        if child is getattr(app, "play_button", None) or child is getattr(app, "time_label", None):
            continue
        text = ""
        try:
            text = str(child.cget("text"))
        except Exception:
            pass
        if child is combo or "playback" in text.lower() or "speed" in text.lower() or ("s" in text and ("\u25c0" in text or "\u25b6" in text)):
            try:
                child.destroy()
            except Exception:
                pass

    try:
        combo.destroy()
    except Exception:
        pass

    # Repack the transport as one coherent media-player cluster.
    for widget in (getattr(app, "play_button", None), getattr(app, "time_label", None)):
        try:
            widget.pack_forget()
        except Exception:
            pass

    app.time_label.pack(side="left", padx=(0, 12))
    app.speed_control = PlaybackSpeedButton(app, controls)
    app.speed_control.pack(side="left", padx=(0, 8))

    seek = max(1, int(app.settings.get("seek_seconds", 10)))
    app.seek_back_button = TransportSeekButton(controls, seek, -1, lambda: app.skip(-seek))
    app.seek_back_button.pack(side="left", padx=(0, 5))

    app.play_button.pack(side="left", padx=4)

    app.seek_forward_button = TransportSeekButton(controls, seek, 1, lambda: app.skip(seek))
    app.seek_forward_button.pack(side="left", padx=(5, 0))

    # Keep a small spacer between transport and the rest of the viewer surface.
    tk.Label(controls, text="", bg=BG, fg=TEXT, width=1).pack(side="left")

    # The old combobox reference is kept as None so later code cannot accidentally
    # treat it as a live native widget.
    app.speed_combo = None
