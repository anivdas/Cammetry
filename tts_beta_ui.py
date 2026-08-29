from __future__ import annotations

import tkinter as tk

from tts_core import CAMERA_WALL_ORDER
from tts_locales import camera_label
from tts_next_ui import NextApp
from tts_transport_polish import TransportSeekButton, install_button_interaction_polish
from tts_ui import ACCENT, BG, BORDER, CARD, CARD2, GOOD, MUTED, PANEL, TEXT
from tts_ui_polish import FluentButton, flat_button


class BetaApp(NextApp):
    """Installed-beta UX fixes that keep transient tools inside the main window."""

    def __init__(self):
        # Install interaction polish before any shared FluentButton instances are built.
        install_button_interaction_polish()
        self._tools_overlay = None
        self._vehicle_overlay = None
        self._seek_back_button = None
        self._seek_forward_button = None
        super().__init__()

    def _close_overlay(self, attr: str) -> None:
        panel = getattr(self, attr, None)
        if panel is not None:
            try:
                panel.destroy()
            except Exception:
                pass
        setattr(self, attr, None)

    # ------------------------------------------------------------------
    # Main transport: dedicated media-style seek controls.
    # ------------------------------------------------------------------
    def _build_center(self):
        super()._build_center()
        self._upgrade_seek_controls()

    def _upgrade_seek_controls(self) -> None:
        seek_seconds = max(1, int(self.settings.get("seek_seconds", 10)))
        play = getattr(self, "play_button", None)
        if play is None:
            return
        row = play.master
        old_back = None
        old_forward = None
        for child in list(row.winfo_children()):
            if child is play:
                continue
            try:
                label = str(child.cget("text"))
            except Exception:
                continue
            if label == f"-{seek_seconds}s":
                old_back = child
            elif label == f"+{seek_seconds}s":
                old_forward = child

        if old_back is not None:
            old_back.destroy()
        if old_forward is not None:
            old_forward.destroy()

        self._seek_back_button = TransportSeekButton(
            row, seek_seconds, -1, lambda: self.skip(-seek_seconds)
        )
        self._seek_forward_button = TransportSeekButton(
            row, seek_seconds, 1, lambda: self.skip(seek_seconds)
        )
        self._seek_back_button.pack(side="left", padx=(10, 3), before=play)
        self._seek_forward_button.pack(side="left", padx=(3, 3), after=play)

        # Keep release-state logic aware of the transport buttons.
        if hasattr(self, "_clip_action_buttons"):
            self._clip_action_buttons.extend([self._seek_back_button, self._seek_forward_button])
        enabled = bool(getattr(self, "selected_group", None))
        state = "normal" if enabled else "disabled"
        self._seek_back_button.configure(state=state)
        self._seek_forward_button.configure(state=state)

    # ------------------------------------------------------------------
    # Tools: one in-app flyout, never an OS-level floating window.
    # ------------------------------------------------------------------
    def show_tools_panel(self):
        panel = getattr(self, "_tools_overlay", None)
        if panel is not None:
            try:
                if panel.winfo_exists():
                    panel.tkraise()
                    panel.focus_set()
                    return
            except Exception:
                self._tools_overlay = None

        panel = tk.Frame(
            self, bg=BG, highlightthickness=1, highlightbackground="#46627f"
        )
        self._tools_overlay = panel
        panel.place(relx=1.0, rely=1.0, x=-22, y=-72, anchor="se", width=380, height=248)
        panel.tkraise()

        head = tk.Frame(panel, bg=BG)
        head.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(head, text="TOOLS", bg=BG, fg=TEXT,
                 font=("Segoe UI Semibold", 12)).pack(side="left")
        flat_button(head, "Close", lambda: self._close_overlay("_tools_overlay")).pack(side="right")

        card = tk.Frame(panel, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        def action(callback):
            def run():
                self._close_overlay("_tools_overlay")
                self.after(20, callback)
            return run

        flat_button(card, "Jump to event", action(self.jump_to_event)).pack(fill="x", padx=12, pady=(12, 5))
        flat_button(card, "Privacy blur zones", action(self.edit_blur_zones)).pack(fill="x", padx=12, pady=5)
        flat_button(card, "Export telemetry CSV", action(self.export_csv_ui)).pack(fill="x", padx=12, pady=5)
        panel.focus_set()
        panel.bind("<Escape>", lambda _e: self._close_overlay("_tools_overlay"))

    def show_more_menu(self):
        self.show_tools_panel()

    # ------------------------------------------------------------------
    # Vehicle View: one in-app pseudo-isometric camera map.
    # ------------------------------------------------------------------
    def open_vehicle_view(self):
        if not self.selected_group:
            return
        panel = getattr(self, "_vehicle_overlay", None)
        if panel is not None:
            try:
                if panel.winfo_exists():
                    panel.tkraise()
                    panel.focus_set()
                    self._draw_vehicle_overlay()
                    return
            except Exception:
                self._vehicle_overlay = None

        panel = tk.Frame(
            self, bg=BG, highlightthickness=1, highlightbackground="#46627f"
        )
        self._vehicle_overlay = panel
        panel.place(relx=0.5, rely=0.5, anchor="center", width=650, height=560)
        panel.tkraise()

        head = tk.Frame(panel, bg=BG)
        head.pack(fill="x", padx=18, pady=(14, 4))
        tk.Label(head, text="VEHICLE VIEW", bg=BG, fg=TEXT,
                 font=("Segoe UI Semibold", 14)).pack(side="left")
        flat_button(head, "Close", lambda: self._close_overlay("_vehicle_overlay")).pack(side="right")
        self._vehicle_profile = tk.Label(
            panel, bg=BG, fg=MUTED, font=("Segoe UI", 9), anchor="w"
        )
        self._vehicle_profile.pack(fill="x", padx=18, pady=(0, 8))

        self._vehicle_canvas = tk.Canvas(
            panel, bg=PANEL, highlightthickness=1, highlightbackground=BORDER,
            width=610, height=420
        )
        self._vehicle_canvas.pack(fill="both", expand=True, padx=18, pady=(0, 10))

        foot = tk.Frame(panel, bg=BG)
        foot.pack(fill="x", padx=18, pady=(0, 14))
        tk.Label(
            foot, text="Select a camera to focus it, or return to the automatic multi-camera layout.",
            bg=BG, fg=MUTED, font=("Segoe UI", 8)
        ).pack(side="left")
        flat_button(foot, "All cameras / Auto", self._vehicle_auto, accent=True).pack(side="right")

        panel.bind("<Escape>", lambda _e: self._close_overlay("_vehicle_overlay"))
        panel.focus_set()
        self._draw_vehicle_overlay()

    def _vehicle_auto(self):
        if not self.selected_group:
            return
        label = self._auto_label(self.selected_group)
        self.layout_combo.configure(values=(label, "Single Camera", "Four Camera", "Six Camera"))
        self.preview_layout.set(label)
        self.update_camera_layout()
        self._close_overlay("_vehicle_overlay")

    def _vehicle_focus(self, camera: str):
        if not self.selected_group or camera not in self.selected_group.cameras:
            return
        self.set_active_camera(camera)
        self.preview_layout.set("Single Camera")
        self.update_camera_layout()
        self._close_overlay("_vehicle_overlay")

    def _draw_vehicle_overlay(self):
        canvas = getattr(self, "_vehicle_canvas", None)
        group = self.selected_group
        if canvas is None or group is None:
            return
        canvas.delete("all")
        self._vehicle_profile.configure(text=f"Recording profile: {len(group.cameras)} playable cameras")

        # Original Cammetry pseudo-isometric EV silhouette. It intentionally avoids
        # Tesla logos/assets while giving the camera map more depth than a top-down outline.
        body = [(300, 62), (390, 104), (432, 184), (420, 310),
                (350, 366), (244, 354), (188, 286), (184, 164), (224, 92)]
        shadow = [(x + 16, y + 14) for x, y in body]
        canvas.create_polygon(shadow, fill="#080b0f", outline="", smooth=True)
        canvas.create_polygon(body, fill="#1a2632", outline="#6f8196", width=2, smooth=True)
        # Glass roof / windshield / rear glass establish the 3/4 perspective.
        canvas.create_polygon(252, 104, 345, 119, 380, 176, 232, 162,
                              fill="#0b141d", outline="#405268", width=1)
        canvas.create_polygon(226, 180, 382, 194, 388, 244, 215, 228,
                              fill="#101a24", outline="#36485b", width=1)
        canvas.create_polygon(220, 252, 384, 267, 350, 330, 238, 318,
                              fill="#0b141d", outline="#405268", width=1)
        # Wheel hints and center ridge make the silhouette read as a vehicle, not a capsule.
        for x, y in ((196, 178), (405, 194), (202, 286), (394, 303)):
            canvas.create_oval(x - 12, y - 23, x + 12, y + 23, fill="#090d12", outline="#2e3b49")
        canvas.create_line(300, 64, 288, 352, fill="#314153", width=1)

        positions = {
            "front": (304, 62, 304, 24),
            "left_pillar": (226, 132, 130, 102),
            "right_pillar": (380, 151, 486, 120),
            "left_repeater": (188, 220, 92, 220),
            "right_repeater": (425, 236, 522, 236),
            "back": (292, 356, 292, 397),
        }
        for camera in CAMERA_WALL_ORDER:
            if camera not in positions or camera not in group.cameras:
                continue
            x, y, lx, ly = positions[camera]
            active = camera == self.active_camera
            node = ACCENT if active else GOOD
            fov = "#16395f" if active else "#15352d"
            tag = f"vehicle-camera:{camera}"

            if camera == "front":
                canvas.create_polygon(x, y, x - 58, 20, x + 58, 20, fill=fov, outline="", tags=(tag,))
            elif camera == "back":
                canvas.create_polygon(x, y, x - 56, 410, x + 56, 410, fill=fov, outline="", tags=(tag,))
            elif "left" in camera:
                canvas.create_polygon(x, y, 58, y - 44, 58, y + 44, fill=fov, outline="", tags=(tag,))
            else:
                canvas.create_polygon(x, y, 552, y - 44, 552, y + 44, fill=fov, outline="", tags=(tag,))

            r = 10 if active else 8
            canvas.create_oval(x-r, y-r, x+r, y+r, fill=node,
                               outline="white" if active else node, width=2, tags=(tag,))
            canvas.create_line(x, y, lx, ly, fill="#53677c", width=1, tags=(tag,))
            label = camera_label(self.language, camera)
            canvas.create_text(lx, ly, text=label, fill=TEXT, font=("Segoe UI Semibold", 9),
                               anchor="center", tags=(tag,))
            canvas.tag_bind(tag, "<Button-1>", lambda _e, cam=camera: self._vehicle_focus(cam))
            canvas.tag_bind(tag, "<Enter>", lambda _e: canvas.configure(cursor="hand2"))
            canvas.tag_bind(tag, "<Leave>", lambda _e: canvas.configure(cursor=""))

        canvas.create_text(18, 18, text="Playable camera", fill=MUTED,
                           font=("Segoe UI", 8), anchor="nw")
        canvas.create_oval(112, 16, 124, 28, fill=GOOD, outline=GOOD)


App = BetaApp
