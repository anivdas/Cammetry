from __future__ import annotations

import os
import sys
import threading
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from tts_core import APP_NAME, APP_VERSION
from tts_release_ui import ReleaseApp
from tts_settings import save_settings, settings_dir
from tts_ui import BG, CARD2, MUTED, PANEL, TEXT, flat_button
from tts_updater import (
    authenticode_is_trusted,
    download_setup,
    fetch_latest_release,
    schedule_windows_install_on_exit,
)


class FinalApp(ReleaseApp):
    """Final v0.5.1 UI gate additions kept isolated from the larger modern UI layer."""

    def __init__(self):
        self._export_apply_adjustments_var: tk.BooleanVar | None = None
        super().__init__()
        policy = str(self.settings.get("update_policy", "Notify me"))
        if policy not in {"Off", "Notify me", "Automatic"}:
            policy = "Notify me"
        self.settings["update_policy"] = policy
        self.settings["check_updates"] = policy != "Off"

    def _refresh_frames(self, pos=None):
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
            camera for camera, tile in self.tiles.items()
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
                self.viewport_mode.get(), self.zoom_var.get(), self.exposure_var.get(),
                self.contrast_var.get(), self.saturation_var.get(), self.gamma_var.get(),
            )
            tile.set_frame(frame, (max(120, tile.image.winfo_width()), max(90, tile.image.winfo_height())))

    def open_export(self):
        self._export_apply_adjustments_var = tk.BooleanVar(
            value=bool(self.settings.get("apply_image_adjustments_export", True))
        )
        super().open_export()
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
        tk.Label(row, text="Apply image adjustments to exported video", bg=PANEL, fg=TEXT, anchor="w").pack(side="left")
        tk.Checkbutton(row, variable=self._export_apply_adjustments_var, bg=PANEL, activebackground=PANEL, selectcolor=CARD2).pack(side="right")

    def start_export(self, dest, options):
        if self._export_apply_adjustments_var is not None:
            enabled = bool(self._export_apply_adjustments_var.get())
            options.apply_image_adjustments = enabled
            self.settings["apply_image_adjustments_export"] = enabled
            save_settings(self.settings)
        return super().start_export(dest, options)

    def open_update_preferences(self):
        dialog = tk.Toplevel(self)
        dialog.title("Cammetry updates")
        dialog.geometry("520x330")
        dialog.configure(bg=BG)
        dialog.transient(self)
        dialog.grab_set()
        tk.Label(dialog, text="UPDATES", bg=BG, fg=TEXT, font=("Segoe UI Semibold", 14)).pack(anchor="w", padx=18, pady=(16, 3))
        tk.Label(dialog, text=f"Installed version: {APP_VERSION}", bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=(0, 12))
        card = tk.Frame(dialog, bg=PANEL, highlightthickness=1, highlightbackground=CARD2)
        card.pack(fill="x", padx=18, pady=4)
        policy = tk.StringVar(value=str(self.settings.get("update_policy", "Notify me")))
        tk.Label(card, text="Update behavior", bg=PANEL, fg=TEXT, width=19, anchor="w").pack(side="left", padx=12, pady=14)
        ttk.Combobox(card, textvariable=policy, values=("Off", "Notify me", "Automatic"), state="readonly", width=21).pack(side="right", padx=12, pady=14)
        tk.Label(
            dialog,
            text=(
                "Off: Cammetry only checks when you ask.\n"
                "Notify me: checks on launch and tells you when an official release is newer.\n"
                "Automatic: on Windows, a trusted-signed official Setup can be downloaded and installed automatically. "
                "Unsigned/beta or unsupported-platform updates fall back to notification."
            ),
            bg=BG, fg=MUTED, justify="left", wraplength=475, font=("Segoe UI", 8),
        ).pack(anchor="w", padx=18, pady=12)
        bar = tk.Frame(dialog, bg=BG)
        bar.pack(fill="x", padx=18, pady=(6, 14))
        flat_button(bar, "Check now", lambda: self.check_updates(True)).pack(side="left")
        def save():
            value = policy.get()
            self.settings["update_policy"] = value
            self.settings["check_updates"] = value != "Off"
            save_settings(self.settings)
            dialog.destroy()
        flat_button(bar, "Cancel", dialog.destroy).pack(side="right", padx=4)
        flat_button(bar, "Save", save, accent=True).pack(side="right", padx=4)

    def open_support(self):
        super().open_support()
        dialog = None
        for child in reversed(self.winfo_children()):
            if isinstance(child, tk.Toplevel):
                try:
                    if child.title() == "Help & About":
                        dialog = child
                        break
                except Exception:
                    pass
        if dialog is None:
            return
        bar = tk.Frame(dialog, bg=BG)
        bar.pack(fill="x", padx=18, pady=(0, 10))
        flat_button(bar, "Update preferences", self.open_update_preferences).pack(side="left")
        tk.Label(bar, text=f"Policy: {self.settings.get('update_policy', 'Notify me')}", bg=BG, fg=MUTED).pack(side="left", padx=10)

    def check_updates(self, manual=True):
        policy = str(self.settings.get("update_policy", "Notify me"))
        if not manual and policy == "Off":
            return
        repo = str(self.settings.get("update_repo", "anivdas/Cammetry")).strip() or "anivdas/Cammetry"
        if manual:
            self.status_var.set("Checking for updates...")
        def work():
            try:
                info = fetch_latest_release(repo, APP_VERSION)
                self.after(0, lambda: self._handle_update_result(info, manual, policy))
            except Exception as exc:
                error = str(exc)
                self.after(0, lambda: self._handle_update_error(error, manual))
        threading.Thread(target=work, daemon=True).start()

    def _handle_update_error(self, error: str, manual: bool):
        self.status_var.set("Update check unavailable")
        if manual:
            messagebox.showerror(APP_NAME, f"Cammetry could not check for updates.\n\n{error}")

    def _handle_update_result(self, info, manual: bool, policy: str):
        if info is None:
            self.status_var.set(f"Cammetry {APP_VERSION} is up to date")
            if manual:
                messagebox.showinfo(APP_NAME, f"Cammetry {APP_VERSION} is up to date.")
            return
        self.status_var.set(f"Cammetry {info.latest_version} is available")
        if policy == "Automatic" and os.name == "nt" and info.setup_url:
            self._begin_automatic_update(info)
            return
        if manual or policy != "Off":
            if messagebox.askyesno(APP_NAME, f"Cammetry {info.latest_version} is available.\n\nInstalled: {APP_VERSION}\n\nOpen the release page now?"):
                webbrowser.open(info.html_url)

    def _begin_automatic_update(self, info):
        self.status_var.set(f"Downloading Cammetry {info.latest_version}...")
        def work():
            try:
                installer = download_setup(info, settings_dir() / "updates")
                trusted = authenticode_is_trusted(installer)
                self.after(0, lambda: self._automatic_update_downloaded(info, installer, trusted))
            except Exception as exc:
                error = str(exc)
                self.after(0, lambda: self._handle_update_error(error, True))
        threading.Thread(target=work, daemon=True).start()

    def _automatic_update_downloaded(self, info, installer: Path, trusted: bool):
        if not trusted:
            self.status_var.set(f"Cammetry {info.latest_version} available — manual install required")
            messagebox.showinfo(
                APP_NAME,
                f"Cammetry {info.latest_version} was found, but its installer is not trusted-signed. "
                "For safety Cammetry will not run it automatically. The release page will open instead.",
            )
            webbrowser.open(info.html_url)
            return
        if not getattr(sys, "frozen", False):
            self.status_var.set(f"Cammetry {info.latest_version} available — packaged install required")
            messagebox.showinfo(APP_NAME, "Automatic installation is only enabled from an installed Cammetry build.")
            return
        schedule_windows_install_on_exit(installer, os.getpid(), Path(sys.executable))
        messagebox.showinfo(APP_NAME, f"Cammetry {info.latest_version} is ready. Cammetry will close, install the trusted update, and reopen.")
        self.destroy()


App = FinalApp
