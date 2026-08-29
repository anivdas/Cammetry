from __future__ import annotations

from tts_beta_ui import BetaApp
from tts_export_guard import cancel_active_export, install_export_guards
from tts_ui import DANGER
from tts_ui_polish import flat_button


class HotfixApp(BetaApp):
    """Runtime hotfix layer for beta export reliability."""

    def __init__(self):
        install_export_guards()
        self._export_cancel_button = None
        super().__init__()

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


App = HotfixApp
