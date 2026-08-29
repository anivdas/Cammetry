from __future__ import annotations

import tkinter as tk

from tts_release_ui import ReleaseApp
from tts_settings import save_settings
from tts_ui import CARD2, PANEL, TEXT


class FinalApp(ReleaseApp):
    """Final v0.5.1 UI gate additions kept isolated from the larger modern UI layer."""

    def __init__(self):
        self._export_apply_adjustments_var: tk.BooleanVar | None = None
        super().__init__()

    def open_export(self):
        self._export_apply_adjustments_var = tk.BooleanVar(
            value=bool(self.settings.get("apply_image_adjustments_export", True))
        )
        super().open_export()

        # The modern export dialog is created synchronously. Append the missing
        # explicit export toggle to its scrollable form without duplicating the
        # large dialog implementation.
        export_dialog = None
        for child in reversed(self.winfo_children()):
            if isinstance(child, tk.Toplevel):
                try:
                    if child.title() == "Export clip":
                        export_dialog = child
                        break
                except Exception:
                    pass
        if export_dialog is None:
            return

        form = None
        stack = list(export_dialog.winfo_children())
        while stack:
            widget = stack.pop(0)
            children = list(widget.winfo_children())
            if isinstance(widget, tk.Canvas):
                for child in children:
                    if isinstance(child, tk.Frame):
                        form = child
                        break
            if form is not None:
                break
            stack.extend(children)
        if form is None:
            return

        row = tk.Frame(form, bg=PANEL)
        row.pack(fill="x", padx=12, pady=(2, 8))
        tk.Label(
            row,
            text="Apply image adjustments to exported video",
            bg=PANEL,
            fg=TEXT,
            anchor="w",
        ).pack(side="left")
        tk.Checkbutton(
            row,
            variable=self._export_apply_adjustments_var,
            bg=PANEL,
            activebackground=PANEL,
            selectcolor=CARD2,
        ).pack(side="right")

    def start_export(self, dest, options):
        if self._export_apply_adjustments_var is not None:
            enabled = bool(self._export_apply_adjustments_var.get())
            options.apply_image_adjustments = enabled
            self.settings["apply_image_adjustments_export"] = enabled
            save_settings(self.settings)
        return super().start_export(dest, options)


App = FinalApp
