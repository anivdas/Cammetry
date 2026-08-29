from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from tts_beta_ui import BetaApp
from tts_export_guard import cancel_active_export, install_export_guards
from tts_export_layout_polish import (
    MAP_POSITIONS,
    MAP_SIZES,
    configure_map_layout,
    install_export_layout_polish,
)
from tts_settings import save_settings
from tts_transport_live import modernize_transport_row
from tts_transport_polish import install_button_interaction_polish
from tts_ui import DANGER, MUTED, PANEL
from tts_ui_polish import flat_button


class HotfixApp(BetaApp):
    """Runtime hotfix layer for beta export reliability and installed-beta polish."""

    def __init__(self):
        # Install presentation/export hooks before inherited widgets are constructed.
        install_button_interaction_polish()
        install_export_guards()
        install_export_layout_polish()
        self._export_cancel_button = None
        self._map_size_var = None
        self._map_position_var = None
        super().__init__()

    def _build_center(self):
        super()._build_center()
        modernize_transport_row(self)

    def _build_bottom(self):
        super()._build_bottom()
        self._export_cancel_button = flat_button(
            self.export_action_frame,
            "Cancel export",
            self._cancel_export,
            danger=True,
        )
        self._set_export_action_mode("running")

    def _set_export_action_mode(self, mode: str) -> None:
        super()._set_export_action_mode(mode)
        button = getattr(self, "_export_cancel_button", None)
        if button is not None:
            try:
                button.pack_forget()
            except Exception:
                pass
            if mode == "running":
                button.pack(side="left", padx=2)

    def _cancel_export(self):
        cancel_active_export()
        self.status_var.set("Cancelling export...")
        self.export_inline_label.configure(text="Cancelling export...", fg=DANGER)

    def open_export(self):
        self._map_size_var = tk.StringVar(value=str(self.settings.get("export_map_size", "Medium")))
        self._map_position_var = tk.StringVar(value=str(self.settings.get("export_map_position", "Top right")))
        super().open_export()
        dialog = self._find_dialog("Export clip")
        if dialog is None:
            return
        form = self._find_scroll_form(dialog)
        if form is None:
            return

        row = tk.Frame(form, bg=PANEL)
        row.pack(fill="x", padx=12, pady=(5, 2))
        tk.Label(row, text="Map size", bg=PANEL, fg=MUTED, width=20, anchor="w").pack(side="left")
        ttk.Combobox(
            row,
            textvariable=self._map_size_var,
            values=MAP_SIZES,
            state="readonly",
            style="Dark.TCombobox",
        ).pack(side="right", fill="x", expand=True)

        row = tk.Frame(form, bg=PANEL)
        row.pack(fill="x", padx=12, pady=(2, 9))
        tk.Label(row, text="Map position", bg=PANEL, fg=MUTED, width=20, anchor="w").pack(side="left")
        ttk.Combobox(
            row,
            textvariable=self._map_position_var,
            values=MAP_POSITIONS,
            state="readonly",
            style="Dark.TCombobox",
        ).pack(side="right", fill="x", expand=True)

    def start_export(self, dest, options):
        size = self._map_size_var.get() if self._map_size_var is not None else str(self.settings.get("export_map_size", "Medium"))
        position = self._map_position_var.get() if self._map_position_var is not None else str(self.settings.get("export_map_position", "Top right"))
        configure_map_layout(size, position)
        self.settings["export_map_size"] = size
        self.settings["export_map_position"] = position
        save_settings(self.settings)
        return super().start_export(dest, options)


App = HotfixApp
