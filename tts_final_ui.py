from __future__ import annotations

import os
import sys
import threading
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from tts_core import APP_NAME, APP_VERSION
from tts_release_ui import ReleaseApp, ReleaseCalendarPicker
from tts_settings import save_settings, settings_dir
from tts_ui import ACCENT, BG, BORDER, CARD2, MUTED, PANEL, TEXT
from tts_ui_polish import (
    AccessibleCheck,
    FluentButton,
    flat_button,
    install_runtime_polish,
    upgrade_native_checkbuttons,
)
from tts_updater import (
    authenticode_is_trusted,
    download_setup,
    fetch_latest_release,
    schedule_windows_install_on_exit,
)


class FinalCalendarPicker(ReleaseCalendarPicker):
    """Calendar picker compatible with the final canvas-backed Fluent buttons."""

    def _add_yesterday_button(self) -> None:
        for child in self.winfo_children():
            if not isinstance(child, tk.Frame) or child is self.grid_frame:
                continue
            found_today = False
            for widget in child.winfo_children():
                try:
                    if str(widget.cget("text")) == "Today":
                        found_today = True
                        break
                except Exception:
                    pass
            if found_today:
                flat_button(child, "Yesterday", self._yesterday).pack(side="left", padx=2)
                break


class FinalApp(ReleaseApp):
    """Final v0.5.1 beta UI and release-gate refinements."""

    def __init__(self):
        # Patch the shared flat-button factory and hardware encoder smoke test before
        # LegacyApp builds any widgets. Existing class methods resolve these module
        # globals at runtime, so the whole UI benefits without rewriting the parser/player.
        install_runtime_polish()
        self._export_apply_adjustments_var: tk.BooleanVar | None = None
        self._encoder_choices = ["CPU x264"]
        super().__init__()
        policy = str(self.settings.get("update_policy", "Notify me"))
        if policy not in {"Off", "Notify me", "Automatic"}:
            policy = "Notify me"
        self.settings["update_policy"] = policy
        self.settings["check_updates"] = policy != "Off"
        threading.Thread(target=self._prewarm_encoders, daemon=True).start()

    # ------------------------------------------------------------------
    # Main UI: fix event browser parentage and remove classic popup menus.
    # ------------------------------------------------------------------
    def _build_left(self):
        # The previous beta created the Treeview with self.left as its parent while
        # putting the scrollbar in treebox. Tk cannot re-parent widgets, which caused
        # the large empty scrolling panel seen in beta screenshots. Build both inside
        # one grid-owned container instead.
        self.left.grid_columnconfigure(0, weight=1)
        self.left.grid_rowconfigure(4, weight=1)

        top = tk.Frame(self.left, bg=PANEL)
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        tk.Label(top, text=self.t("events").upper(), bg=PANEL, fg=TEXT,
                 font=("Segoe UI Semibold", 10)).pack(side="left")
        self.count_label = tk.Label(top, text="0", bg=PANEL, fg=MUTED,
                                    font=("Segoe UI", 9))
        self.count_label.pack(side="right")

        tabs = tk.Frame(self.left, bg=PANEL)
        tabs.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 6))
        self.filter_buttons = {}
        for kind, key in (("All", "all"), ("Recent", "recent"), ("Sentry", "sentry"), ("Saved", "saved")):
            button = flat_button(tabs, self.t(key), lambda k=kind: self.set_filter(k))
            button.pack(side="left", padx=2)
            self.filter_buttons[kind] = button

        datebar = tk.Frame(self.left, bg=PANEL)
        datebar.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 6))
        self.date_filter_button = flat_button(datebar, "Calendar: All dates", self.open_calendar)
        self.date_filter_button.pack(fill="x")

        searchbox = tk.Frame(self.left, bg="#0c1218", highlightthickness=1, highlightbackground=BORDER)
        searchbox.grid(row=3, column=0, sticky="ew", padx=10, pady=(2, 8))
        tk.Label(searchbox, text="Search", bg="#0c1218", fg=MUTED,
                 font=("Segoe UI Semibold", 8)).pack(side="left", padx=(8, 5))
        entry = tk.Entry(searchbox, textvariable=self.search_var, bg="#0c1218", fg=TEXT,
                         insertbackground="white", relief="flat", bd=0, font=("Segoe UI", 9))
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=7)
        entry.bind("<KeyRelease>", lambda _e: self.refresh_event_list())

        treebox = tk.Frame(self.left, bg=PANEL)
        treebox.grid(row=4, column=0, sticky="nsew", padx=8, pady=(0, 8))
        cols = ("time", "type", "trigger", "cams")
        self.event_tree = ttk.Treeview(
            treebox,
            columns=cols,
            show="headings",
            selectmode="browse",
            style="Dark.Treeview",
        )
        for col, text in (("time", "RECORDED"), ("type", "TYPE"), ("trigger", "TRIGGER"), ("cams", "CAMS")):
            self.event_tree.heading(col, text=text)
        self.event_tree.column("time", width=132, anchor="w")
        self.event_tree.column("type", width=58, anchor="center")
        self.event_tree.column("trigger", width=105, anchor="w")
        self.event_tree.column("cams", width=42, anchor="center")
        scroll = ttk.Scrollbar(treebox, orient="vertical", command=self.event_tree.yview,
                               style="Dark.Vertical.TScrollbar")
        self.event_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.event_tree.pack(side="left", fill="both", expand=True)
        self.event_tree.bind("<<TreeviewSelect>>", self.on_event_select)

        foot = tk.Frame(self.left, bg=PANEL)
        foot.grid(row=5, column=0, sticky="ew", padx=8, pady=(0, 8))
        flat_button(foot, self.t("delete"), self.delete_selected, danger=True).pack(side="left")
        flat_button(foot, self.t("scan"), self.scan).pack(side="right")

    def _build_center(self):
        super()._build_center()
        # Replace the classic tk.Menu launcher. Settings is always visible and the
        # remaining utilities live in a normal themed popover window.
        more = None
        for widget in self._walk_widgets(self.center):
            try:
                if str(widget.cget("text")) == "More...":
                    more = widget
                    break
            except Exception:
                pass
        if more is not None:
            parent = more.master
            more.destroy()
            flat_button(parent, "Settings", self.open_settings).pack(side="right", padx=2)
            flat_button(parent, "Tools", self.show_tools_panel).pack(side="right", padx=2)

    def show_more_menu(self):
        self.show_tools_panel()

    def show_tools_panel(self):
        panel = tk.Toplevel(self)
        panel.title("Cammetry tools")
        panel.geometry("340x230")
        panel.configure(bg=BG)
        panel.transient(self)
        panel.resizable(False, False)
        tk.Label(panel, text="TOOLS", bg=BG, fg=TEXT,
                 font=("Segoe UI Semibold", 12)).pack(anchor="w", padx=16, pady=(14, 8))
        card = tk.Frame(panel, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        def action(callback):
            def run():
                panel.destroy()
                callback()
            return run

        flat_button(card, "Jump to event", action(self.jump_to_event)).pack(fill="x", padx=10, pady=(10, 4))
        flat_button(card, "Privacy blur zones", action(self.edit_blur_zones)).pack(fill="x", padx=10, pady=4)
        flat_button(card, "Export telemetry CSV", action(self.export_csv_ui)).pack(fill="x", padx=10, pady=4)
        flat_button(panel, "Close", panel.destroy).pack(side="right", padx=16, pady=(0, 14))
        panel.bind("<Escape>", lambda _e: panel.destroy())

    def open_calendar(self):
        FinalCalendarPicker(self, self.groups, self._set_date_filter)

    def _capture_clip_action_buttons(self) -> None:
        target_labels = {
            "Play", "Vehicle View", "Start", "End", "Clear", "Export", "Publish",
            str(self.t("snapshot")), "Tools",
        }
        self._clip_action_buttons = []
        for widget in self._walk_widgets(self):
            if isinstance(widget, (FluentButton, tk.Button, ttk.Button)):
                try:
                    label = str(widget.cget("text"))
                    is_seek = (label.startswith("-") or label.startswith("+")) and label.endswith("s")
                    if label in target_labels or is_seek:
                        self._clip_action_buttons.append(widget)
                    if label == "Start":
                        self._start_marker_button = widget
                    elif label == "End":
                        self._end_marker_button = widget
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Playback/render performance.
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Export dialog accessibility + robust hardware encoder detection.
    # ------------------------------------------------------------------
    def _prewarm_encoders(self):
        try:
            from tts_export_v051 import available_encoders
            self._encoder_choices = available_encoders()
        except Exception:
            self._encoder_choices = ["CPU x264"]

    def _find_dialog(self, title: str):
        for child in reversed(self.winfo_children()):
            if isinstance(child, tk.Toplevel):
                try:
                    if child.title() == title:
                        return child
                except Exception:
                    pass
        return None

    def _find_scroll_form(self, dialog):
        stack = list(dialog.winfo_children())
        while stack:
            widget = stack.pop(0)
            children = list(widget.winfo_children())
            if isinstance(widget, tk.Canvas):
                for child in children:
                    if isinstance(child, tk.Frame):
                        return child
            stack.extend(children)
        return None

    def open_export(self):
        self._export_apply_adjustments_var = tk.BooleanVar(
            value=bool(self.settings.get("apply_image_adjustments_export", True))
        )
        super().open_export()
        export_dialog = self._find_dialog("Export clip")
        if export_dialog is None:
            return
        form = self._find_scroll_form(export_dialog)
        if form is not None:
            row = tk.Frame(form, bg=PANEL)
            row.pack(fill="x", padx=12, pady=(3, 9))
            tk.Label(row, text="Apply image adjustments to exported video", bg=PANEL,
                     fg=TEXT, anchor="w").pack(side="left")
            AccessibleCheck(row, self._export_apply_adjustments_var).pack(side="right", padx=2)
        # Replace every native dark indicator from the inherited telemetry options.
        upgrade_native_checkbuttons(export_dialog)

    def start_export(self, dest, options):
        if self._export_apply_adjustments_var is not None:
            enabled = bool(self._export_apply_adjustments_var.get())
            options.apply_image_adjustments = enabled
            self.settings["apply_image_adjustments_export"] = enabled
            save_settings(self.settings)
        return super().start_export(dest, options)

    # ------------------------------------------------------------------
    # Settings / updates.
    # ------------------------------------------------------------------
    def open_settings(self):
        super().open_settings()
        dialog = self._find_dialog(self.t("settings_title"))
        if dialog is None:
            return
        # Remove the obsolete boolean "check updates" row. v0.5.1 uses the explicit
        # Off / Notify me / Automatic policy instead.
        target = self.t("check_updates")
        for widget in list(self._walk_widgets(dialog)):
            if not isinstance(widget, tk.Label):
                continue
            try:
                if str(widget.cget("text")) == target:
                    row = widget.master
                    row.destroy()
                    break
            except Exception:
                pass
        form = self._find_scroll_form(dialog)
        if form is not None:
            row = tk.Frame(form, bg=PANEL)
            row.pack(fill="x", padx=12, pady=7)
            tk.Label(row, text="Updates", bg=PANEL, fg=MUTED, width=18, anchor="w").pack(side="left")
            tk.Label(row, text=str(self.settings.get("update_policy", "Notify me")), bg=PANEL,
                     fg=TEXT).pack(side="left", padx=6)

            def prefs():
                dialog.destroy()
                self.after(50, self.open_update_preferences)

            flat_button(row, "Update preferences", prefs).pack(side="right")
        upgrade_native_checkbuttons(dialog)

    def open_update_preferences(self):
        dialog = tk.Toplevel(self)
        dialog.title("Cammetry updates")
        dialog.geometry("520x330")
        dialog.configure(bg=BG)
        dialog.transient(self)
        dialog.grab_set()
        tk.Label(dialog, text="UPDATES", bg=BG, fg=TEXT,
                 font=("Segoe UI Semibold", 14)).pack(anchor="w", padx=18, pady=(16, 3))
        tk.Label(dialog, text=f"Installed version: {APP_VERSION}", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=(0, 12))
        card = tk.Frame(dialog, bg=PANEL, highlightthickness=1, highlightbackground=CARD2)
        card.pack(fill="x", padx=18, pady=4)
        policy = tk.StringVar(value=str(self.settings.get("update_policy", "Notify me")))
        tk.Label(card, text="Update behavior", bg=PANEL, fg=TEXT,
                 width=19, anchor="w").pack(side="left", padx=12, pady=14)
        ttk.Combobox(card, textvariable=policy, values=("Off", "Notify me", "Automatic"),
                     state="readonly", width=21, style="Dark.TCombobox").pack(side="right", padx=12, pady=14)
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
        dialog = self._find_dialog("Help & About")
        if dialog is None:
            return
        bar = tk.Frame(dialog, bg=BG)
        bar.pack(fill="x", padx=18, pady=(0, 10))
        flat_button(bar, "Update preferences", self.open_update_preferences).pack(side="left")
        tk.Label(bar, text=f"Policy: {self.settings.get('update_policy', 'Notify me')}",
                 bg=BG, fg=MUTED).pack(side="left", padx=10)

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
            if messagebox.askyesno(
                APP_NAME,
                f"Cammetry {info.latest_version} is available.\n\nInstalled: {APP_VERSION}\n\nOpen the release page now?",
            ):
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
        messagebox.showinfo(
            APP_NAME,
            f"Cammetry {info.latest_version} is ready. Cammetry will close, install the trusted update, and reopen.",
        )
        self.destroy()


App = FinalApp
