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

    def _refresh_frames(self, pos=None):
        """Render only mapped camera tiles and decode only those camera streams.

        ReleaseApp already suppresses duplicate refreshes. This final layer keeps that
        protection while avoiding decode work for hidden cameras, which is especially
        useful in Single Camera mode and while switching layouts.
        """
        if not self.selected_group or not hasattr(self, "tiles"):
            return
        if self.state() == "iconic" or not self.winfo_viewable():
            return

        signature = self._render_signature(pos)
        if signature == self._last_render_signature:
            self._preview_duplicate_skips += 1
            return
        self._last_render_signature = signature

        visible_cameras = [
            camera
            for camera, tile in self.tiles.items()
            if tile.winfo_ismapped() and camera in self.selected_group.cameras
        ]
        frames = self.player.get_frames(
            self.player.position if pos is None else pos,
            cameras=visible_cameras,
        )
        self.last_frames = frames

        for camera, tile in self.tiles.items():
            if not tile.winfo_ismapped():
                continue
            if camera not in self.selected_group.cameras:
                tile.set_placeholder()
                continue
            frame = frames.get(camera)
            if frame is None:
                continue
            tile.set_render_options(
                self.viewport_mode.get(),
                self.zoom_var.get(),
                self.exposure_var.get(),
                self.contrast_var.get(),
                self.saturation_var.get(),
                self.gamma_var.get(),
            )
            tile.set_frame(
                frame,
                (
                    max(120, tile.image.winfo_width()),
                    max(90, tile.image.winfo_height()),
                ),
            )

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
