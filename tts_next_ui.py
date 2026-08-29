from __future__ import annotations

import os
import queue
import subprocess
import sys
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import ttk

import tts_export_v051
import tts_ui
from tts_final_ui import FinalApp
from tts_hud import write_dashboard_ass as write_cluster_hud
from tts_map_export import MAP_STYLES, configure_export_map, render_route_video as render_rich_route_video
from tts_settings import save_settings, settings_dir
from tts_ui import ACCENT, BG, BORDER, CARD2, DANGER, GOOD, MUTED, PANEL, TEXT, WARN
from tts_ui_polish import flat_button


TESLA_DASHCAM_WEB = "https://dashcam.tesla.com"


class NextApp(FinalApp):
    """Installed-beta refinements discovered during real Windows testing."""

    def __init__(self):
        # Replace only presentation/export hooks; parser/player/telemetry core remains unchanged.
        tts_export_v051.write_dashboard_ass = write_cluster_hud
        tts_export_v051.render_route_video = render_rich_route_video
        self._install_encrypted_clip_filter()
        self._export_map_style_var: tk.StringVar | None = None
        super().__init__()

    @staticmethod
    def _install_encrypted_clip_filter() -> None:
        # EncryptedClips may contain files whose names resemble normal TeslaCam MP4s,
        # but they are not playable until decrypted with the vehicle/account key.
        if getattr(tts_ui, "_cammetry_encrypted_filter_installed", False):
            return
        original = tts_ui.discover_clips

        def discover_playable(root: Path):
            groups = original(root)
            return [
                group for group in groups
                if "encryptedclips" not in {part.lower() for part in group.folder.parts}
            ]

        tts_ui.discover_clips = discover_playable
        tts_ui._cammetry_encrypted_filter_installed = True

    # ------------------------------------------------------------------
    # Left browser: inline encrypted-clips notice instead of playback errors.
    # ------------------------------------------------------------------
    def _build_left(self):
        super()._build_left()
        # Move the Delete/Scan footer down one row and reserve a compact notice row.
        for child in self.left.grid_slaves(row=5):
            child.grid_configure(row=6)
        self.encrypted_banner = tk.Frame(
            self.left, bg="#121a24", highlightthickness=1, highlightbackground="#31527a"
        )
        self.encrypted_banner.grid(row=5, column=0, sticky="ew", padx=8, pady=(0, 8))
        self.encrypted_banner.grid_remove()
        self.encrypted_label = tk.Label(
            self.encrypted_banner, text="", bg="#121a24", fg=TEXT,
            justify="left", anchor="w", wraplength=270, font=("Segoe UI", 8),
        )
        self.encrypted_label.pack(fill="x", padx=9, pady=(8, 5))
        flat_button(
            self.encrypted_banner, "Decrypt with Tesla", self.open_tesla_dashcam_web
        ).pack(anchor="w", padx=8, pady=(0, 8))

    def scan(self):
        result = super().scan()
        self._refresh_encrypted_notice()
        return result

    def _encrypted_directories(self) -> list[Path]:
        raw = self.root_path.get().strip() if hasattr(self, "root_path") else ""
        if not raw:
            return []
        root = Path(raw)
        if not root.exists():
            return []
        matches = []
        if root.name.lower() == "encryptedclips" and root.is_dir():
            matches.append(root)
        try:
            for candidate in root.rglob("EncryptedClips"):
                if candidate.is_dir():
                    matches.append(candidate)
        except Exception:
            pass
        unique = []
        seen = set()
        for candidate in matches:
            key = str(candidate.resolve()).lower() if os.name == "nt" else str(candidate.resolve())
            if key not in seen:
                seen.add(key)
                unique.append(candidate)
        return unique

    def _refresh_encrypted_notice(self) -> None:
        directories = self._encrypted_directories()
        count = 0
        for directory in directories:
            try:
                count += sum(1 for item in directory.rglob("*") if item.is_file())
            except Exception:
                count += 1
        if count:
            noun = "file" if count == 1 else "files"
            self.encrypted_label.configure(
                text=(
                    f"🔒 {count} encrypted recording {noun} detected. Cammetry leaves encrypted files untouched. "
                    "Use Tesla's official browser decryptor, then scan the decrypted recordings."
                )
            )
            self.encrypted_banner.grid()
        else:
            self.encrypted_banner.grid_remove()

    def open_tesla_dashcam_web(self):
        self.status_var.set("Opening Tesla's official encrypted-clip viewer in your browser...")
        webbrowser.open(TESLA_DASHCAM_WEB)

    # ------------------------------------------------------------------
    # Bottom status surface: export progress/completion stays in the main UI.
    # ------------------------------------------------------------------
    def _build_bottom(self):
        self.export_inline = tk.Frame(
            self, bg=PANEL, highlightthickness=1, highlightbackground=BORDER, height=48
        )
        self.export_inline.pack(fill="x", padx=12, pady=(0, 6))
        self.export_inline.pack_propagate(False)
        self.export_inline.pack_forget()

        self.export_inline_label = tk.Label(
            self.export_inline, text="", bg=PANEL, fg=TEXT,
            font=("Segoe UI Semibold", 9), anchor="w",
        )
        self.export_inline_label.pack(side="left", padx=(12, 8), fill="x", expand=True)
        self.export_inline_progress = ttk.Progressbar(
            self.export_inline, style="Dark.Horizontal.TProgressbar",
            mode="determinate", maximum=100, length=210,
        )
        self.export_inline_progress.pack(side="left", padx=8)
        self.export_action_frame = tk.Frame(self.export_inline, bg=PANEL)
        self.export_action_frame.pack(side="right", padx=(4, 8), pady=6)
        self.export_open_button = flat_button(self.export_action_frame, "Open file", self._open_export_file)
        self.export_folder_button = flat_button(self.export_action_frame, "Show in folder", self._show_export_folder)
        self.export_diag_button = flat_button(self.export_action_frame, "Diagnostics", self.open_diagnostics)
        self.export_dismiss_button = flat_button(self.export_action_frame, "Dismiss", self._dismiss_export_status)
        for button in (self.export_open_button, self.export_folder_button, self.export_diag_button, self.export_dismiss_button):
            button.pack(side="left", padx=2)
        self._set_export_action_mode("running")

        foot = tk.Frame(self, bg=BG, height=30)
        foot.pack(fill="x", padx=12, pady=(0, 8))
        foot.pack_propagate(False)
        self.progress = ttk.Progressbar(
            foot, style="Dark.Horizontal.TProgressbar", mode="determinate", maximum=100, length=160
        )
        self.progress.pack(side="right", padx=(8, 0), pady=8)
        tk.Label(
            foot, textvariable=self.status_var, bg=BG, fg=MUTED,
            font=("Segoe UI", 8), anchor="w",
        ).pack(side="left", fill="x", expand=True)

    def _set_export_action_mode(self, mode: str) -> None:
        for button in (self.export_open_button, self.export_folder_button, self.export_diag_button, self.export_dismiss_button):
            button.pack_forget()
        if mode == "done":
            self.export_open_button.pack(side="left", padx=2)
            self.export_folder_button.pack(side="left", padx=2)
            self.export_dismiss_button.pack(side="left", padx=2)
        elif mode == "error":
            self.export_diag_button.pack(side="left", padx=2)
            self.export_dismiss_button.pack(side="left", padx=2)

    def _show_export_toast(self):
        # Kept under the inherited method name so existing exporter calls require no rewrite.
        self.export_inline_label.configure(text="Preparing export...", fg=TEXT)
        self.export_inline_progress["value"] = 1
        self._set_export_action_mode("running")
        self.export_inline.pack(fill="x", padx=12, pady=(0, 6), before=self.winfo_children()[-1])

    def _update_export_toast(self, frac, text):
        self.export_inline_label.configure(text=text, fg=TEXT)
        self.export_inline_progress["value"] = max(0, min(100, float(frac) * 100))
        if not self.export_inline.winfo_ismapped():
            self.export_inline.pack(fill="x", padx=12, pady=(0, 6))

    def _finish_export_toast(self, success, text):
        self.export_inline_label.configure(text=text, fg=GOOD if success else DANGER)
        self.export_inline_progress["value"] = 100 if success else 0
        self._set_export_action_mode("done" if success else "error")
        if not self.export_inline.winfo_ismapped():
            self.export_inline.pack(fill="x", padx=12, pady=(0, 6))

    def _dismiss_export_status(self):
        self.export_inline.pack_forget()

    def _open_export_file(self):
        output = getattr(self, "last_output", None)
        if not output or not Path(output).exists():
            return
        path = Path(output)
        try:
            if os.name == "nt":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            self.status_var.set(f"Could not open export: {exc}")

    def _show_export_folder(self):
        output = getattr(self, "last_output", None)
        if not output or not Path(output).exists():
            return
        path = Path(output)
        try:
            if os.name == "nt":
                subprocess.Popen(["explorer", "/select,", str(path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path.parent)])
        except Exception as exc:
            self.status_var.set(f"Could not reveal export: {exc}")

    def _poll_worker(self):
        try:
            while True:
                kind, payload = self._worker_q.get_nowait()
                if kind == "loaded":
                    token, group, samples, info = payload
                    if token != self._load_token:
                        continue
                    self.samples = samples
                    self.telemetry_fps = info.fps if info else 36.0
                    if info and info.duration > 0:
                        self.video_duration = info.duration
                        self.player.duration = info.duration
                    self.timeline.set_data(
                        self.samples, self.telemetry_fps, self.video_duration,
                        self._event_relative_time(group),
                    )
                    self.timeline.set_trim(self.in_point, self.out_point)
                    self.route.set_empty_text(self.t("no_gps_route"))
                    self.route.set_data(self.samples, self.telemetry_fps)
                    if samples:
                        self.telemetry_badge.configure(
                            text=f"{len(samples)} {self.t('samples').upper()}", fg=GOOD
                        )
                        self.status_var.set(
                            self.tf("telemetry_synced", count=len(samples), fps=self.telemetry_fps)
                        )
                    else:
                        self.telemetry_badge.configure(text=self.t("no_sei").upper(), fg=WARN)
                        self.status_var.set(self.t("no_telemetry"))
                    self._update_insights()
                    self._update_event_info()
                    self.seek(self.player.position)
                elif kind == "error":
                    token, msg = payload
                    if token == self._load_token:
                        self.telemetry_badge.configure(text=self.t("error").upper(), fg=DANGER)
                        self.status_var.set(msg)
                elif kind == "export_progress":
                    frac, _msg = payload
                    self.progress["value"] = frac * 100
                    text = self.tf("exporting", percent=frac * 100)
                    self.status_var.set(text)
                    self._update_export_toast(frac, text)
                elif kind == "export_done":
                    output, encoder = payload
                    self.progress["value"] = 0
                    self.last_output = Path(output)
                    text = f"✓ Export complete • {encoder}"
                    self.status_var.set(self.tf("export_complete", encoder=encoder, path=output))
                    self._finish_export_toast(True, text)
                elif kind == "export_error":
                    self.progress["value"] = 0
                    self.status_var.set(self.t("export_failed"))
                    self._finish_export_toast(False, f"Export failed • {payload}")
        except queue.Empty:
            pass
        self.after(100, self._poll_worker)

    # ------------------------------------------------------------------
    # Export map layer: explicit Off / route / streets / satellite selection.
    # ------------------------------------------------------------------
    def open_export(self):
        previous = self.settings.get("export_map_style")
        if previous not in MAP_STYLES:
            previous = "Route only" if self.settings.get("show_minimap", False) else "Off"
        self._export_map_style_var = tk.StringVar(value=previous)
        super().open_export()
        dialog = self._find_dialog("Export clip")
        if dialog is None:
            return
        form = self._find_scroll_form(dialog)
        if form is None:
            return

        # Remove the inherited boolean minimap row; the richer selector below owns it.
        for widget in list(self._walk_widgets(form)):
            if not isinstance(widget, tk.Label):
                continue
            try:
                if str(widget.cget("text")) == "GPS minimap":
                    widget.master.destroy()
                    break
            except Exception:
                pass

        row = tk.Frame(form, bg=PANEL)
        row.pack(fill="x", padx=12, pady=(5, 2))
        tk.Label(row, text="Map overlay", bg=PANEL, fg=MUTED, width=20, anchor="w").pack(side="left")
        ttk.Combobox(
            row, textvariable=self._export_map_style_var, values=MAP_STYLES,
            state="readonly", style="Dark.TCombobox",
        ).pack(side="right", fill="x", expand=True)
        tk.Label(
            form,
            text=(
                "Route only stays offline. Street map uses OpenStreetMap tiles. Satellite uses your own MapTiler key. "
                "Online map modes send only the approximate tile area to the map provider — never video or SEI data."
            ),
            bg=PANEL, fg=MUTED, justify="left", wraplength=520, font=("Segoe UI", 8),
        ).pack(anchor="w", padx=12, pady=(2, 9))

    def start_export(self, dest, options):
        style = self._export_map_style_var.get() if self._export_map_style_var is not None else "Off"
        key = str(self.settings.get("maptiler_key", "")).strip()
        effective = style
        if style == "Satellite" and not key:
            effective = "Street map"
            self.status_var.set("Satellite map key is not configured; this export will use Street map instead.")
        options.show_minimap = effective != "Off"
        self.settings["export_map_style"] = style
        self.settings["show_minimap"] = options.show_minimap
        save_settings(self.settings)
        configure_export_map(effective, key, settings_dir() / "map_tiles")
        return super().start_export(dest, options)

    # ------------------------------------------------------------------
    # Settings/help additions for maps and encrypted recordings.
    # ------------------------------------------------------------------
    def open_settings(self):
        super().open_settings()
        dialog = self._find_dialog(self.t("settings_title"))
        if dialog is None:
            return
        form = self._find_scroll_form(dialog)
        if form is None:
            return
        row = tk.Frame(form, bg=PANEL)
        row.pack(fill="x", padx=12, pady=7)
        tk.Label(row, text="Maps", bg=PANEL, fg=MUTED, width=18, anchor="w").pack(side="left")
        configured = bool(str(self.settings.get("maptiler_key", "")).strip())
        tk.Label(row, text="Satellite configured" if configured else "Street maps available",
                 bg=PANEL, fg=TEXT).pack(side="left", padx=6)
        flat_button(row, "Map preferences", lambda: self._open_map_preferences_from(dialog)).pack(side="right")

    def _open_map_preferences_from(self, parent_dialog):
        try:
            parent_dialog.destroy()
        except Exception:
            pass
        self.after(50, self.open_map_preferences)

    def open_map_preferences(self):
        dialog = tk.Toplevel(self)
        dialog.title("Cammetry maps")
        dialog.geometry("560x400")
        dialog.configure(bg=BG)
        dialog.transient(self)
        dialog.grab_set()
        tk.Label(dialog, text="MAPS", bg=BG, fg=TEXT,
                 font=("Segoe UI Semibold", 14)).pack(anchor="w", padx=18, pady=(16, 3))
        tk.Label(
            dialog,
            text="Map backgrounds are optional. Route-only mode never sends your GPS area to a map service.",
            bg=BG, fg=MUTED, wraplength=510, justify="left", font=("Segoe UI", 8),
        ).pack(anchor="w", padx=18, pady=(0, 12))

        card = tk.Frame(dialog, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", padx=18, pady=4)
        viewer = tk.StringVar(
            value="Street map (online)" if str(self.settings.get("map_mode", "")).startswith("OpenStreetMap")
            else "Route only (offline)"
        )
        tk.Label(card, text="Viewer route map", bg=PANEL, fg=TEXT, width=20, anchor="w").pack(side="left", padx=12, pady=12)
        ttk.Combobox(
            card, textvariable=viewer,
            values=("Route only (offline)", "Street map (online)"),
            state="readonly", style="Dark.TCombobox", width=24,
        ).pack(side="right", padx=12, pady=12)

        key_card = tk.Frame(dialog, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        key_card.pack(fill="x", padx=18, pady=8)
        tk.Label(key_card, text="MapTiler satellite key", bg=PANEL, fg=TEXT,
                 width=20, anchor="w").pack(side="left", padx=12, pady=12)
        key_var = tk.StringVar(value=str(self.settings.get("maptiler_key", "")))
        entry = tk.Entry(
            key_card, textvariable=key_var, bg="#0c1218", fg=TEXT, insertbackground="white",
            relief="flat", show="•", font=("Segoe UI", 9),
        )
        entry.pack(side="right", fill="x", expand=True, padx=12, pady=12)
        tk.Label(
            dialog,
            text=(
                "Satellite is optional and uses MapTiler's satellite-v4 tiles with your own API key. "
                "Cammetry stores the key only in its local settings. Map attribution remains visible in exported video."
            ),
            bg=BG, fg=MUTED, wraplength=510, justify="left", font=("Segoe UI", 8),
        ).pack(anchor="w", padx=18, pady=8)

        bar = tk.Frame(dialog, bg=BG)
        bar.pack(fill="x", padx=18, pady=(8, 14))

        def save():
            self.settings["map_mode"] = (
                "OpenStreetMap (online)" if viewer.get().startswith("Street") else "Local Grid (offline)"
            )
            self.settings["maptiler_key"] = key_var.get().strip()
            save_settings(self.settings)
            try:
                self.route.map_mode = self.settings["map_mode"]
                self.route.set_data(self.samples, self.telemetry_fps)
            except Exception:
                pass
            dialog.destroy()

        flat_button(bar, "Cancel", dialog.destroy).pack(side="right", padx=4)
        flat_button(bar, "Save", save, accent=True).pack(side="right", padx=4)

    def open_support(self):
        super().open_support()
        dialog = self._find_dialog("Help & About")
        if dialog is None:
            return
        card = tk.Frame(dialog, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", padx=18, pady=(0, 10))
        tk.Label(card, text="ENCRYPTED RECORDINGS", bg=PANEL, fg=TEXT,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=12, pady=(10, 3))
        tk.Label(
            card,
            text=(
                "Newer Tesla software can save recordings in EncryptedClips. Cammetry does not request or store "
                "Tesla account credentials or decryption keys. Use Tesla's official browser viewer to decrypt locally, "
                "then open the decrypted files in Cammetry."
            ),
            bg=PANEL, fg=MUTED, wraplength=610, justify="left", font=("Segoe UI", 8),
        ).pack(anchor="w", padx=12, pady=(0, 7))
        flat_button(card, "Open Tesla dashcam decryptor", self.open_tesla_dashcam_web).pack(anchor="w", padx=10, pady=(0, 10))


App = NextApp
