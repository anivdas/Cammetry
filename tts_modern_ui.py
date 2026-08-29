from __future__ import annotations

import calendar
import ctypes
import os
import platform
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import cv2  # type: ignore
import numpy as np  # type: ignore
import tkinter as tk
from PIL import Image, ImageTk
from tkinter import filedialog, messagebox, ttk

from tts_core import APP_NAME, APP_VERSION, CAMERA_WALL_ORDER, ClipGroup, get_ffmpeg_exe
from tts_export import BlurZone
from tts_export_v051 import ExportOptions, available_encoders, encoder_status, export_video
from tts_locales import camera_label, event_reason_label
from tts_settings import save_settings
from tts_ui import (
    ACCENT, BG, BORDER, CARD, CARD2, DANGER, FSD, GOOD, MANUAL, MUTED, PANEL, TEXT, WARN,
    App as LegacyApp, CameraTile, TimelineCanvas, flat_button, fmt_time,
)


class EfficientTimeline(TimelineCanvas):
    def set_position(self, pos):
        self.position = pos
        self._move_playhead()

    def _move_playhead(self):
        if self.duration <= 0:
            return
        w, h = max(1, self.winfo_width()), max(1, self.winfo_height())
        px = max(0, min(w, self.position / self.duration * w))
        items = self.find_withtag("playhead")
        if items:
            self.coords(items[0], px, 0, px, h)
        else:
            self.create_line(px, 0, px, h, fill="#ffffff", width=2, tags=("playhead",))

    def redraw(self, position_only=False):
        if position_only:
            self._move_playhead(); return
        self.delete("all")
        w, h = max(1, self.winfo_width()), max(1, self.winfo_height())
        self.create_rectangle(0, 0, w, h, fill="#0b1118", outline="")
        if self.duration <= 0:
            self.create_text(12, h // 2, text="Timeline", fill=MUTED, anchor="w", font=("Segoe UI", 9)); return
        y0, y1 = 18, h - 18
        self.create_line(0, (y0 + y1) // 2, w, (y0 + y1) // 2, fill="#293746", width=2)
        if self.samples:
            total = len(self.samples)
            for x in range(w):
                idx = min(total - 1, int(x / max(1, w - 1) * (total - 1)))
                sample = self.samples[idx]
                if sample.autopilot_state: self.create_line(x, y1 - 7, x, y1, fill=FSD)
                if sample.brake_applied: self.create_line(x, y0, x, y0 + 8, fill=DANGER)
                elif sample.blinker_on_left or sample.blinker_on_right: self.create_line(x, y0, x, y0 + 6, fill=WARN)
        if self.event_time is not None and 0 <= self.event_time <= self.duration:
            ex = self.event_time / self.duration * w; self.create_line(ex, 0, ex, h, fill=WARN, width=2)
        if self.out_point > self.in_point:
            x0, x1 = self.in_point / self.duration * w, self.out_point / self.duration * w
            self.create_rectangle(x0, 8, x1, h - 8, fill="#10291f", outline=GOOD, stipple="gray50")
            self.create_line(x0, 0, x0, h, fill=GOOD, width=3); self.create_line(x1, 0, x1, h, fill=DANGER, width=3)
            self.create_text(x0 + 4, 5, text="START", fill=GOOD, anchor="nw", font=("Segoe UI Semibold", 7)); self.create_text(x1 - 4, 5, text="END", fill=DANGER, anchor="ne", font=("Segoe UI Semibold", 7))
        self._move_playhead()


class ModernCameraTile(CameraTile):
    def __init__(self, parent, camera: str, click_cb, language: str = "English"):
        super().__init__(parent, camera, click_cb, language)
        self.display_mode, self.zoom = "Fit", 1.0
        self.exposure, self.contrast, self.saturation, self.gamma = 0.0, 1.0, 1.0, 1.0

    def set_render_options(self, display_mode: str, zoom: float, exposure: float, contrast: float, saturation: float, gamma: float):
        self.display_mode = display_mode; self.zoom = max(0.5, min(3.0, float(zoom))); self.exposure = max(-3.0, min(3.0, float(exposure))); self.contrast = max(0.25, min(2.5, float(contrast))); self.saturation = max(0.0, min(2.5, float(saturation))); self.gamma = max(0.25, min(3.0, float(gamma)))

    def _adjust(self, frame):
        img = frame.astype(np.float32); img *= 2.0 ** self.exposure; img = (img - 127.5) * self.contrast + 127.5; img = np.clip(img, 0, 255).astype(np.uint8)
        if abs(self.saturation - 1.0) > 0.001:
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32); hsv[:, :, 1] = np.clip(hsv[:, :, 1] * self.saturation, 0, 255); img = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        if abs(self.gamma - 1.0) > 0.001:
            inv = 1.0 / self.gamma; lut = np.array([((i / 255.0) ** inv) * 255 for i in range(256)], dtype=np.uint8); img = cv2.LUT(img, lut)
        return img

    def set_frame(self, frame, max_size: Tuple[int, int]):
        if frame is None: self.set_placeholder(); return
        w, h = max_size
        if w <= 10 or h <= 10: return
        rgb = cv2.cvtColor(self._adjust(frame), cv2.COLOR_BGR2RGB); ih, iw = rgb.shape[:2]
        base = max(w / iw, h / ih) if self.display_mode == "Fill" else min(w / iw, h / ih); scale = max(0.01, base * self.zoom); nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        resized = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR); canvas = Image.new("RGB", (w, h), (3, 5, 6))
        if nw > w or nh > h:
            x0, y0 = max(0, (nw - w) // 2), max(0, (nh - h) // 2); crop = resized[y0:y0 + min(h, nh), x0:x0 + min(w, nw)]; pil = Image.fromarray(crop); canvas.paste(pil, ((w - pil.width) // 2, (h - pil.height) // 2))
        else:
            pil = Image.fromarray(resized); canvas.paste(pil, ((w - nw) // 2, (h - nh) // 2))
        self.photo = ImageTk.PhotoImage(canvas); self.image.configure(image=self.photo, text="")


class CalendarPicker(tk.Toplevel):
    def __init__(self, parent, groups: Sequence[ClipGroup], callback):
        super().__init__(parent); self.title("Filter clips by date"); self.configure(bg=BG); self.resizable(False, False); self.transient(parent); self.callback = callback; self.counts: Dict[date, int] = {}
        for group in groups:
            try:
                d = datetime.strptime(group.timestamp[:10], "%Y-%m-%d").date(); self.counts[d] = self.counts.get(d, 0) + 1
            except Exception: pass
        newest = max(self.counts) if self.counts else date.today(); self.year, self.month = newest.year, newest.month
        self.grid_frame = tk.Frame(self, bg=PANEL); self.grid_frame.pack(fill="both", expand=True, padx=12, pady=(10, 8)); self._draw()
        quick = tk.Frame(self, bg=BG); quick.pack(fill="x", padx=12, pady=(0, 8)); flat_button(quick, "Today", lambda: self._quick(0)).pack(side="left", padx=2); flat_button(quick, "Last 7 days", lambda: self._quick(6)).pack(side="left", padx=2); flat_button(quick, "Last 30 days", lambda: self._quick(29)).pack(side="left", padx=2); flat_button(quick, "All dates", lambda: self._apply(None, None, "All dates")).pack(side="right", padx=2)
        custom = tk.Frame(self, bg=BG); custom.pack(fill="x", padx=12, pady=(0, 12)); self.from_var, self.to_var = tk.StringVar(), tk.StringVar(); tk.Label(custom, text="From", bg=BG, fg=MUTED).pack(side="left"); tk.Entry(custom, textvariable=self.from_var, width=11, bg=CARD2, fg=TEXT, insertbackground="white", relief="flat").pack(side="left", padx=(5, 9), ipady=4); tk.Label(custom, text="To", bg=BG, fg=MUTED).pack(side="left"); tk.Entry(custom, textvariable=self.to_var, width=11, bg=CARD2, fg=TEXT, insertbackground="white", relief="flat").pack(side="left", padx=5, ipady=4); flat_button(custom, "Apply range", self._custom, accent=True).pack(side="right")

    def _draw(self):
        for child in self.grid_frame.winfo_children(): child.destroy()
        head = tk.Frame(self.grid_frame, bg=PANEL); head.grid(row=0, column=0, columnspan=7, sticky="ew", pady=(0, 7)); flat_button(head, "<", self._prev, width=2).pack(side="left"); tk.Label(head, text=f"{calendar.month_name[self.month]} {self.year}", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 11)).pack(side="left", expand=True); flat_button(head, ">", self._next, width=2).pack(side="right")
        for col, name in enumerate(("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")): tk.Label(self.grid_frame, text=name, bg=PANEL, fg=MUTED, width=5).grid(row=1, column=col, pady=2)
        for row, week in enumerate(calendar.Calendar(firstweekday=0).monthdatescalendar(self.year, self.month), start=2):
            for col, day in enumerate(week):
                count = self.counts.get(day, 0); text = f"{day.day}\n{count}" if count else str(day.day); fg = TEXT if day.month == self.month else "#596675"; bg = CARD2 if count else PANEL
                button = tk.Button(self.grid_frame, text=text, width=5, height=2, bg=bg, fg=fg, activebackground=ACCENT, activeforeground="white", relief="flat", bd=0, cursor="hand2", command=lambda d=day: self._apply(d, d, d.isoformat())); button.grid(row=row, column=col, padx=2, pady=2)

    def _prev(self):
        self.month -= 1
        if self.month < 1: self.month, self.year = 12, self.year - 1
        self._draw()
    def _next(self):
        self.month += 1
        if self.month > 12: self.month, self.year = 1, self.year + 1
        self._draw()
    def _quick(self, days_back: int):
        end = date.today(); start = end - timedelta(days=days_back); self._apply(start, end, "Today" if days_back == 0 else f"Last {days_back + 1} days")
    def _custom(self):
        try:
            start = datetime.strptime(self.from_var.get().strip(), "%Y-%m-%d").date(); end = datetime.strptime(self.to_var.get().strip(), "%Y-%m-%d").date()
            if end < start: start, end = end, start
            self._apply(start, end, f"{start.isoformat()} to {end.isoformat()}")
        except Exception: messagebox.showerror(APP_NAME, "Use YYYY-MM-DD for From and To.", parent=self)
    def _apply(self, start: Optional[date], end: Optional[date], label: str): self.callback(start, end, label); self.destroy()


class VehicleView(tk.Toplevel):
    POSITIONS = {"front": (160, 34), "left_pillar": (102, 92), "right_pillar": (218, 92), "left_repeater": (58, 158), "right_repeater": (262, 158), "back": (160, 286)}
    def __init__(self, parent, group: ClipGroup, active_camera: str, focus_cb, auto_cb, language: str):
        super().__init__(parent); self.title("Vehicle View"); self.geometry("360x390"); self.resizable(False, False); self.configure(bg=BG); self.transient(parent); self.group, self.active_camera, self.focus_cb, self.auto_cb, self.language = group, active_camera, focus_cb, auto_cb, language
        tk.Label(self, text="VEHICLE VIEW", bg=BG, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(anchor="w", padx=14, pady=(12, 2)); tk.Label(self, text=f"Recording profile: {len(group.cameras)} cameras", bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", padx=14)
        self.canvas = tk.Canvas(self, width=320, height=305, bg=PANEL, highlightthickness=1, highlightbackground=BORDER); self.canvas.pack(padx=14, pady=10); self._draw(); flat_button(self, "All cameras / Auto", self._auto, accent=True).pack(pady=(0, 12))
    def _draw(self):
        c = self.canvas; c.delete("all"); c.create_polygon(135, 52, 185, 52, 211, 104, 216, 228, 193, 272, 127, 272, 104, 228, 109, 104, fill="#1b2632", outline="#657487", width=2, smooth=True); c.create_polygon(125, 91, 195, 91, 202, 137, 118, 137, fill="#101820", outline="#3c4b5b"); c.create_polygon(119, 211, 201, 211, 194, 252, 126, 252, fill="#101820", outline="#3c4b5b")
        if self.active_camera in self.POSITIONS:
            x, y = self.POSITIONS[self.active_camera]
            if self.active_camera == "front": c.create_polygon(x, y, x - 70, y - 22, x + 70, y - 22, fill="#13263e", outline="")
            elif self.active_camera == "back": c.create_polygon(x, y, x - 60, y + 18, x + 60, y + 18, fill="#13263e", outline="")
            elif "left" in self.active_camera: c.create_polygon(x, y, x - 70, y - 28, x - 70, y + 28, fill="#13263e", outline="")
            else: c.create_polygon(x, y, x + 70, y - 28, x + 70, y + 28, fill="#13263e", outline="")
        for camera, (x, y) in self.POSITIONS.items():
            if camera not in self.group.cameras: continue
            active = camera == self.active_camera; radius = 9 if active else 7; fill = ACCENT if active else GOOD; tag = f"cam:{camera}"; c.create_oval(x - radius, y - radius, x + radius, y + radius, fill=fill, outline="white" if active else fill, width=2, tags=(tag,)); label = camera_label(self.language, camera); anchor = "e" if "left" in camera else "w" if "right" in camera else "s" if camera == "front" else "n"; dx = -13 if "left" in camera else 13 if "right" in camera else 0; dy = -13 if camera == "front" else 13 if camera == "back" else 0; c.create_text(x + dx, y + dy, text=label, fill=TEXT, anchor=anchor, font=("Segoe UI", 8), tags=(tag,)); c.tag_bind(tag, "<Button-1>", lambda _e, cam=camera: self._focus(cam)); c.tag_bind(tag, "<Enter>", lambda _e: c.configure(cursor="hand2")); c.tag_bind(tag, "<Leave>", lambda _e: c.configure(cursor=""))
    def _focus(self, camera: str): self.focus_cb(camera); self.destroy()
    def _auto(self): self.auto_cb(); self.destroy()


class ModernApp(LegacyApp):
    def __init__(self):
        self._resize_until = self._last_route_update = self._last_telemetry_update = 0.0; self.date_start: Optional[date] = None; self.date_end: Optional[date] = None; self.date_filter_label = "All dates"; super().__init__(); self.title(f"{APP_NAME} {APP_VERSION}"); self.bind("<Configure>", self._root_configure, add="+"); self.after(200, self._enable_windows_backdrop)
    def _enable_windows_backdrop(self):
        if os.name != "nt": return
        try:
            hwnd = self.winfo_id(); value = ctypes.c_int(1); ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value)); backdrop = ctypes.c_int(2); ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 38, ctypes.byref(backdrop), ctypes.sizeof(backdrop))
        except Exception: pass
    def _root_configure(self, event):
        if event.widget is self: self._resize_until = time.perf_counter() + 0.16

    def _build_left(self):
        top = tk.Frame(self.left, bg=PANEL); top.pack(fill="x", padx=10, pady=(10, 6)); tk.Label(top, text=self.t("events").upper(), bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 10)).pack(side="left"); self.count_label = tk.Label(top, text="0", bg=PANEL, fg=MUTED, font=("Segoe UI", 9)); self.count_label.pack(side="right")
        tabs = tk.Frame(self.left, bg=PANEL); tabs.pack(fill="x", padx=8, pady=(0, 6)); self.filter_buttons = {}
        for kind, key in (("All", "all"), ("Recent", "recent"), ("Sentry", "sentry"), ("Saved", "saved")):
            button = flat_button(tabs, self.t(key), lambda k=kind: self.set_filter(k)); button.pack(side="left", padx=2); self.filter_buttons[kind] = button
        datebar = tk.Frame(self.left, bg=PANEL); datebar.pack(fill="x", padx=10, pady=(0, 6)); self.date_filter_button = flat_button(datebar, "Calendar: All dates", self.open_calendar); self.date_filter_button.pack(fill="x")
        searchbox = tk.Frame(self.left, bg="#0c1218", highlightthickness=1, highlightbackground=BORDER); searchbox.pack(fill="x", padx=10, pady=(2, 8)); entry = tk.Entry(searchbox, textvariable=self.search_var, bg="#0c1218", fg=TEXT, insertbackground="white", relief="flat", bd=0, font=("Segoe UI", 9)); entry.pack(fill="x", padx=8, pady=7); entry.bind("<KeyRelease>", lambda _e: self.refresh_event_list())
        cols = ("time", "type", "trigger", "cams"); self.event_tree = ttk.Treeview(self.left, columns=cols, show="headings", selectmode="browse", style="Dark.Treeview")
        for col, text in (("time", "RECORDED"), ("type", "TYPE"), ("trigger", "TRIGGER"), ("cams", "CAMS")): self.event_tree.heading(col, text=text)
        self.event_tree.column("time", width=132, anchor="w"); self.event_tree.column("type", width=58, anchor="center"); self.event_tree.column("trigger", width=105, anchor="w"); self.event_tree.column("cams", width=42, anchor="center"); treebox = tk.Frame(self.left, bg=PANEL); treebox.pack(fill="both", expand=True, padx=8, pady=(0, 8)); scroll = ttk.Scrollbar(treebox, orient="vertical", command=self.event_tree.yview, style="Dark.Vertical.TScrollbar"); self.event_tree.configure(yscrollcommand=scroll.set); scroll.pack(side="right", fill="y"); self.event_tree.pack(side="left", fill="both", expand=True); self.event_tree.bind("<<TreeviewSelect>>", self.on_event_select)
        foot = tk.Frame(self.left, bg=PANEL); foot.pack(fill="x", padx=8, pady=(0, 8)); flat_button(foot, self.t("delete"), self.delete_selected, danger=True).pack(side="left"); flat_button(foot, self.t("scan"), self.scan).pack(side="right")
    def open_calendar(self): CalendarPicker(self, self.groups, self._set_date_filter)
    def _set_date_filter(self, start: Optional[date], end: Optional[date], label: str): self.date_start, self.date_end, self.date_filter_label = start, end, label; self.date_filter_button.configure(text=f"Calendar: {label}"); self.refresh_event_list()
    def refresh_event_list(self):
        q = self.search_var.get().strip().lower(); self.filtered_groups = []
        if not hasattr(self, "event_tree"): return
        self.event_tree.delete(*self.event_tree.get_children())
        for group in self.groups:
            if self.filter_kind != "All" and group.source_kind != self.filter_kind: continue
            try: group_date = datetime.strptime(group.timestamp[:10], "%Y-%m-%d").date()
            except Exception: group_date = None
            if self.date_start and (group_date is None or group_date < self.date_start): continue
            if self.date_end and (group_date is None or group_date > self.date_end): continue
            reason = (group.event_info or {}).get("reason") or (group.event_info or {}).get("event") or (group.event_info or {}).get("trigger") or ""; trigger = event_reason_label(self.language, reason) if reason else "-"; hay = f"{group.timestamp} {group.source_kind} {group.folder} {reason} {trigger}".lower()
            if q and q not in hay: continue
            self.filtered_groups.append(group); self.event_tree.insert("", "end", iid=str(len(self.filtered_groups) - 1), values=(group.display_time(), group.source_kind, trigger, len(group.cameras)))
        self.count_label.configure(text=str(len(self.filtered_groups)))
        for kind, button in self.filter_buttons.items(): button.configure(bg=ACCENT if kind == self.filter_kind else CARD2)

    def _build_center(self):
        toolbar = tk.Frame(self.center, bg=BG); toolbar.pack(fill="x", pady=(0, 7)); self.clip_title = tk.Label(toolbar, text=self.t("no_clip"), bg=BG, fg=TEXT, font=("Segoe UI Semibold", 11), anchor="w"); self.clip_title.pack(side="left", fill="x", expand=True); self.preview_layout.set("Auto"); self.layout_combo = ttk.Combobox(toolbar, textvariable=self.preview_layout, values=("Auto", "Single Camera", "Four Camera", "Six Camera"), state="readonly", width=18, style="Dark.TCombobox"); self.layout_combo.pack(side="right", padx=(6, 0)); self.layout_combo.bind("<<ComboboxSelected>>", lambda _e: self.update_camera_layout()); flat_button(toolbar, "Vehicle View", self.open_vehicle_view).pack(side="right", padx=4)
        self.viewport_mode = tk.StringVar(value="Fit"); mode = ttk.Combobox(toolbar, textvariable=self.viewport_mode, values=("Fit", "Fill"), state="readonly", width=6, style="Dark.TCombobox"); mode.pack(side="right", padx=4); mode.bind("<<ComboboxSelected>>", lambda _e: self._refresh_frames()); self.zoom_var = tk.DoubleVar(value=1.0); flat_button(toolbar, "+", lambda: self._change_zoom(0.1), width=2).pack(side="right", padx=2); flat_button(toolbar, "-", lambda: self._change_zoom(-0.1), width=2).pack(side="right", padx=2); flat_button(toolbar, "Image", self.open_image_controls).pack(side="right", padx=4)
        self.exposure_var = tk.DoubleVar(value=0.0); self.contrast_var = tk.DoubleVar(value=1.0); self.saturation_var = tk.DoubleVar(value=1.0); self.gamma_var = tk.DoubleVar(value=1.0); self.wall = tk.Frame(self.center, bg="#030506"); self.wall.pack(fill="both", expand=True); self.tiles = {camera: ModernCameraTile(self.wall, camera, self.set_active_camera, self.language) for camera in CAMERA_WALL_ORDER}; self.update_camera_layout()
        transport = tk.Frame(self.center, bg=CARD, highlightthickness=1, highlightbackground=BORDER); transport.pack(fill="x", pady=(8, 2)); row = tk.Frame(transport, bg=CARD); row.pack(fill="x", padx=8, pady=(7, 4)); self.time_label = tk.Label(row, text="00:00.00 / 00:00.00", bg=CARD, fg=TEXT, font=("Consolas", 9)); self.time_label.pack(side="left", padx=(4, 10)); self.speed_combo = ttk.Combobox(row, textvariable=self.play_speed, values=(0.5, 1.0, 2.0, 4.0), state="readonly", width=5, style="Dark.TCombobox"); self.speed_combo.pack(side="left"); self.speed_combo.bind("<<ComboboxSelected>>", lambda _e: self.player.set_speed(self.play_speed.get())); seek = int(self.settings.get("seek_seconds", 10)); flat_button(row, f"-{seek}s", lambda: self.skip(-seek)).pack(side="left", padx=(10, 3)); self.play_button = flat_button(row, "Play", self.toggle_play, accent=True, width=8); self.play_button.pack(side="left", padx=3); flat_button(row, f"+{seek}s", lambda: self.skip(seek)).pack(side="left", padx=3); self.trim_label = tk.Label(row, text=self.t("trim_full"), bg=CARD, fg=MUTED, font=("Segoe UI", 8)); self.trim_label.pack(side="right", padx=6)
        self.timeline = EfficientTimeline(transport, self.seek, self.language); self.timeline.pack(fill="x", padx=8, pady=4); actions = tk.Frame(transport, bg=CARD); actions.pack(fill="x", padx=8, pady=(3, 8)); flat_button(actions, "Start", self.set_in).pack(side="left", padx=2); flat_button(actions, "End", self.set_out).pack(side="left", padx=2); flat_button(actions, "Clear", self.clear_trim).pack(side="left", padx=2); flat_button(actions, "Export", self.open_export, accent=True).pack(side="right", padx=2); flat_button(actions, "Publish", self.share_last).pack(side="right", padx=2); flat_button(actions, self.t("snapshot"), self.save_snapshot).pack(side="right", padx=2); flat_button(actions, "More...", self.show_more_menu).pack(side="right", padx=2)
    def show_more_menu(self):
        menu = tk.Menu(self, tearoff=False, bg=CARD2, fg=TEXT, activebackground=ACCENT, activeforeground="white"); menu.add_command(label="Jump to event", command=self.jump_to_event); menu.add_command(label="Privacy blur zones", command=self.edit_blur_zones); menu.add_command(label="Export telemetry CSV", command=self.export_csv_ui); menu.add_separator(); menu.add_command(label="Settings", command=self.open_settings)
        try: menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally: menu.grab_release()
    def _change_zoom(self, delta: float): self.zoom_var.set(max(0.5, min(3.0, round(self.zoom_var.get() + delta, 1)))); self._refresh_frames()
    def open_image_controls(self):
        dialog = tk.Toplevel(self); dialog.title("Image adjustments"); dialog.geometry("430x390"); dialog.configure(bg=BG); dialog.transient(self); tk.Label(dialog, text="IMAGE ADJUSTMENTS", bg=BG, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(anchor="w", padx=16, pady=(14, 4)); tk.Label(dialog, text="Non-destructive preview. These values can also be applied during export.", bg=BG, fg=MUTED, wraplength=390, justify="left", font=("Segoe UI", 8)).pack(anchor="w", padx=16, pady=(0, 8))
        def slider(label, var, lo, hi, res):
            box = tk.Frame(dialog, bg=PANEL); box.pack(fill="x", padx=16, pady=4); tk.Label(box, text=label, bg=PANEL, fg=TEXT, width=12, anchor="w").pack(side="left", padx=8); tk.Scale(box, variable=var, from_=lo, to=hi, resolution=res, orient="horizontal", bg=PANEL, fg=TEXT, troughcolor=CARD2, highlightthickness=0, length=250, command=lambda _v: self._refresh_frames()).pack(side="right", padx=8)
        slider("Exposure", self.exposure_var, -3.0, 3.0, 0.1); slider("Contrast", self.contrast_var, 0.5, 2.0, 0.05); slider("Saturation", self.saturation_var, 0.0, 2.0, 0.05); slider("Gamma", self.gamma_var, 0.5, 2.0, 0.05)
        def reset(): self.exposure_var.set(0.0); self.contrast_var.set(1.0); self.saturation_var.set(1.0); self.gamma_var.set(1.0); self._refresh_frames()
        bar = tk.Frame(dialog, bg=BG); bar.pack(fill="x", padx=16, pady=12); flat_button(bar, "Reset", reset).pack(side="left"); flat_button(bar, "Done", dialog.destroy, accent=True).pack(side="right")
    def _auto_label(self, group: Optional[ClipGroup] = None) -> str:
        group = group or self.selected_group; return f"Auto ({len(group.cameras)} cameras)" if group else "Auto"
    def _effective_layout(self) -> str:
        value = self.preview_layout.get(); return self._best_layout_for_group(self.selected_group) if value.startswith("Auto") and self.selected_group else ("Six Camera" if value.startswith("Auto") else value)
    def load_group(self, group: ClipGroup):
        super().load_group(group); label = self._auto_label(group); self.layout_combo.configure(values=(label, "Single Camera", "Four Camera", "Six Camera")); self.preview_layout.set(label); self.update_camera_layout()
    def update_camera_layout(self):
        if not hasattr(self, "tiles"): return
        for tile in self.tiles.values(): tile.grid_forget()
        layout = self._effective_layout()
        if layout == "Single Camera":
            tile = self.tiles.get(self.active_camera, self.tiles["front"]); tile.grid(row=0, column=0, rowspan=2, columnspan=3, sticky="nsew", padx=1, pady=1)
            for i in range(3): self.wall.grid_columnconfigure(i, weight=1)
            for i in range(2): self.wall.grid_rowconfigure(i, weight=1)
        elif layout == "Four Camera":
            cams = [c for c in ("front", "back", "left_repeater", "right_repeater") if c in self.tiles]
            for i, camera in enumerate(cams): self.tiles[camera].grid(row=i // 2, column=i % 2, sticky="nsew", padx=1, pady=1)
            for i in range(2): self.wall.grid_columnconfigure(i, weight=1); self.wall.grid_rowconfigure(i, weight=1)
            self.wall.grid_columnconfigure(2, weight=0)
        else:
            for i, camera in enumerate(CAMERA_WALL_ORDER): self.tiles[camera].grid(row=i // 3, column=i % 3, sticky="nsew", padx=1, pady=1)
            for i in range(3): self.wall.grid_columnconfigure(i, weight=1)
            for i in range(2): self.wall.grid_rowconfigure(i, weight=1)
        self.after(60, self._refresh_frames)
    def open_vehicle_view(self):
        if not self.selected_group: messagebox.showinfo(APP_NAME, "Select a recording first."); return
        VehicleView(self, self.selected_group, self.active_camera, self.focus_camera, self.return_to_auto, self.language)
    def focus_camera(self, camera: str):
        if not self.selected_group or camera not in self.selected_group.cameras: return
        self.active_camera = camera; self.preview_layout.set("Single Camera"); self.update_camera_layout(); self._update_tile_borders(); self._refresh_frames()
    def return_to_auto(self):
        if self.selected_group: self.preview_layout.set(self._auto_label()); self.update_camera_layout(); self._refresh_frames()
    def _refresh_frames(self, pos=None):
        if not self.selected_group or not hasattr(self, "tiles") or self.state() == "iconic" or not self.winfo_viewable(): return
        frames = self.player.get_frames(self.player.position if pos is None else pos); self.last_frames = frames
        for camera, tile in self.tiles.items():
            if not tile.winfo_ismapped(): continue
            if camera not in self.selected_group.cameras: tile.set_placeholder(); continue
            frame = frames.get(camera)
            if frame is None: continue
            tile.set_render_options(self.viewport_mode.get(), self.zoom_var.get(), self.exposure_var.get(), self.contrast_var.get(), self.saturation_var.get(), self.gamma_var.get()); tile.set_frame(frame, (max(120, tile.image.winfo_width()), max(90, tile.image.winfo_height())))
    def _update_position_ui(self, pos):
        self.time_label.configure(text=f"{fmt_time(pos)} / {fmt_time(self.video_duration)}"); self.timeline.set_position(pos); now = time.perf_counter()
        if now - self._last_telemetry_update >= 0.08: self._last_telemetry_update = now; self._update_telemetry_panel(pos)
        if now - self._last_route_update >= 0.16: self._last_route_update = now; self.route.set_position(pos)
    def _tick(self):
        if self.selected_group:
            pos = self.player.tick(); now = time.perf_counter(); visible = self.state() != "iconic" and self.winfo_viewable()
            if visible:
                self._update_position_ui(pos)
                if self.player.playing and now >= self._resize_until and now - self._last_preview_update >= 1 / 15: self._last_preview_update = now; self._refresh_frames(pos)
            if not self.player.playing and self.play_button.cget("text").startswith("Pause"): self.play_button.configure(text="Play")
        self.after(35, self._tick)
    def toggle_play(self):
        if not self.selected_group: return
        self.play_button.configure(text="Pause" if self.player.toggle() else "Play")

    def open_export(self):
        if not self.selected_group: return
        dialog = tk.Toplevel(self); dialog.title("Export clip"); dialog.geometry("650x790"); dialog.configure(bg=BG); dialog.transient(self); dialog.grab_set(); tk.Label(dialog, text="EXPORT CLIP", bg=BG, fg=TEXT, font=("Segoe UI Semibold", 14)).pack(anchor="w", padx=18, pady=(16, 2)); tk.Label(dialog, text=f"{fmt_time(self.in_point)} to {fmt_time(self.out_point)}  |  {self.out_point - self.in_point:.1f}s", bg=BG, fg=MUTED).pack(anchor="w", padx=18, pady=(0, 10))
        outer = tk.Frame(dialog, bg=BG); outer.pack(fill="both", expand=True, padx=18); canvas = tk.Canvas(outer, bg=PANEL, highlightthickness=1, highlightbackground=BORDER); scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview, style="Dark.Vertical.TScrollbar"); canvas.configure(yscrollcommand=scroll.set); scroll.pack(side="right", fill="y"); canvas.pack(side="left", fill="both", expand=True); form = tk.Frame(canvas, bg=PANEL); win = canvas.create_window((0, 0), window=form, anchor="nw"); form.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        layout = tk.StringVar(value=self._effective_layout()); frame_mode = tk.StringVar(value="Preserve Source" if self._effective_layout() == "Single Camera" else "Fit 16:9"); quality = tk.StringVar(value=self.settings.get("export_quality", "High")); encoder = tk.StringVar(value="Auto (recommended)"); dashstyle = tk.StringVar(value="Full"); dashsize = tk.StringVar(value=self.settings.get("dashboard_size", "Medium")); dashopacity = tk.IntVar(value=78); dashposition = tk.StringVar(value="Bottom"); show_dashboard = tk.BooleanVar(value=True); show_speed = tk.BooleanVar(value=True); show_state = tk.BooleanVar(value=True); show_gear = tk.BooleanVar(value=True); show_steering = tk.BooleanVar(value=True); show_accel = tk.BooleanVar(value=True); show_brake = tk.BooleanVar(value=True); show_blinkers = tk.BooleanVar(value=True); show_gforce = tk.BooleanVar(value=False); stamp = tk.BooleanVar(value=self.settings.get("show_timestamp", True)); minimap = tk.BooleanVar(value=self.settings.get("show_minimap", False)); gps = tk.BooleanVar(value=False)
        def combo(label, var, values):
            row = tk.Frame(form, bg=PANEL); row.pack(fill="x", padx=12, pady=5); tk.Label(row, text=label, bg=PANEL, fg=MUTED, width=20, anchor="w").pack(side="left"); cb = ttk.Combobox(row, textvariable=var, values=values, state="readonly", style="Dark.TCombobox"); cb.pack(side="right", fill="x", expand=True); return cb
        def check(label, var):
            row = tk.Frame(form, bg=PANEL); row.pack(fill="x", padx=12, pady=3); tk.Label(row, text=label, bg=PANEL, fg=TEXT).pack(side="left"); tk.Checkbutton(row, variable=var, bg=PANEL, activebackground=PANEL, selectcolor=CARD2).pack(side="right")
        combo("Layout", layout, ("Single Camera", "Four Camera", "Six Camera")); combo("Frame mode", frame_mode, ("Preserve Source", "Fit 16:9", "Fill 16:9")); combo("Quality", quality, ("Mobile", "Medium", "High", "Maximum")); encoder_combo = combo("Encoder", encoder, ("Auto (recommended)", "CPU x264")); combo("HUD style", dashstyle, ("Full", "Compact", "Minimal")); combo("HUD size", dashsize, ("Small", "Medium", "Large", "X-Large")); combo("HUD position", dashposition, ("Bottom", "Top")); row = tk.Frame(form, bg=PANEL); row.pack(fill="x", padx=12, pady=5); tk.Label(row, text="HUD opacity", bg=PANEL, fg=MUTED, width=20, anchor="w").pack(side="left"); tk.Scale(row, variable=dashopacity, from_=25, to=100, orient="horizontal", bg=PANEL, fg=TEXT, troughcolor=CARD2, highlightthickness=0).pack(side="right", fill="x", expand=True)
        tk.Label(form, text="TELEMETRY OVERLAY", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=12, pady=(10, 3))
        for label, var in (("Telemetry overlay", show_dashboard), ("Speed", show_speed), ("Driver assist state", show_state), ("Gear", show_gear), ("Steering", show_steering), ("Accelerator", show_accel), ("Brake", show_brake), ("Blinkers", show_blinkers), ("G-force", show_gforce), ("Timestamp", stamp), ("GPS minimap", minimap), ("GPS coordinates", gps)): check(label, var)
        tk.Label(form, text="IMAGE ADJUSTMENTS", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=12, pady=(10, 3)); tk.Label(form, text=f"Exposure {self.exposure_var.get():+.1f}  |  Contrast {self.contrast_var.get():.2f}  |  Saturation {self.saturation_var.get():.2f}  |  Gamma {self.gamma_var.get():.2f}", bg=PANEL, fg=MUTED).pack(anchor="w", padx=12, pady=(0, 10))
        def detect():
            try: values = ["Auto (recommended)"] + available_encoders()
            except Exception: values = ["Auto (recommended)", "CPU x264"]
            self.after(0, lambda: encoder_combo.configure(values=values))
        threading.Thread(target=detect, daemon=True).start(); buttons = tk.Frame(dialog, bg=BG); buttons.pack(fill="x", padx=18, pady=14); flat_button(buttons, "Cancel", dialog.destroy).pack(side="right", padx=4)
        def go():
            dest = filedialog.asksaveasfilename(parent=dialog, defaultextension=".mp4", filetypes=[("MP4 video", "*.mp4")], initialfile=f"{self.selected_group.timestamp}-export.mp4")
            if not dest: return
            enc = "Auto" if encoder.get().startswith("Auto") else encoder.get(); date_fmt = {"YYYY-MM-DD": "%Y-%m-%d", "MM/DD/YYYY": "%m/%d/%Y", "DD/MM/YYYY": "%d/%m/%Y", "DD Mon YYYY": "%d %b %Y"}.get(self.settings.get("date_format", "YYYY-MM-DD"), "%Y-%m-%d"); timestamp_fmt = date_fmt + (" %H:%M:%S" if self.settings.get("time_format") == "24h" else " %I:%M:%S %p")
            options = ExportOptions(layout=layout.get(), active_camera=self.active_camera, start=self.in_point, end=self.out_point, units=self.settings.get("units", "mph"), language=self.language, encoder=enc, quality=quality.get(), frame_mode=frame_mode.get(), dashboard_size=dashsize.get(), dashboard_style=dashstyle.get(), dashboard_opacity=dashopacity.get(), dashboard_position=dashposition.get(), show_dashboard=show_dashboard.get(), show_speed=show_speed.get(), show_state=show_state.get(), show_gear=show_gear.get(), show_steering=show_steering.get(), show_accelerator=show_accel.get(), show_brake=show_brake.get(), show_blinkers=show_blinkers.get(), show_gforce=show_gforce.get(), show_timestamp=stamp.get(), timestamp_format=timestamp_fmt, show_minimap=minimap.get(), show_gps_text=gps.get(), exposure=self.exposure_var.get(), contrast=self.contrast_var.get(), saturation=self.saturation_var.get(), gamma=self.gamma_var.get(), blur_zones=list(self.blur_zones)); self.settings.update({"export_quality": quality.get(), "encoder": enc, "dashboard_size": dashsize.get(), "show_timestamp": stamp.get(), "show_minimap": minimap.get()}); save_settings(self.settings); dialog.destroy(); self.start_export(Path(dest), options)
        flat_button(buttons, "Export MP4", go, accent=True).pack(side="right", padx=4)
    def start_export(self, dest, options):
        group = self.selected_group; samples = list(self.samples); fps = self.telemetry_fps
        if not group: return
        self.progress["value"] = 1; self.status_var.set("Preparing export..."); self._show_export_toast()
        def work():
            try: self._worker_q.put(("export_done", (dest, export_video(group, samples, fps, dest, options, lambda p, m: self._worker_q.put(("export_progress", (p, m)))))))
            except Exception as exc: self._worker_q.put(("export_error", str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def open_support(self):
        dialog = tk.Toplevel(self); dialog.title("Help & About"); dialog.geometry("620x560"); dialog.configure(bg=BG); dialog.transient(self); tk.Label(dialog, text=f"Cammetry {APP_VERSION}", bg=BG, fg=TEXT, font=("Segoe UI Semibold", 18)).pack(anchor="w", padx=18, pady=(18, 2)); tk.Label(dialog, text="Free, open-source and privacy-first. Not affiliated with or endorsed by Tesla, Inc.", bg=BG, fg=MUTED, wraplength=570, justify="left").pack(anchor="w", padx=18, pady=(0, 14)); card = tk.Frame(dialog, bg=PANEL, highlightthickness=1, highlightbackground=BORDER); card.pack(fill="x", padx=18, pady=4); help_text = "Quick start\n1. Browse to a TeslaCam folder or drive.\n2. Pick a recording from Events.\n3. Use Auto layout or Vehicle View to choose cameras.\n4. Set Start/End if you want to trim.\n5. Export, then use Publish to hand the file to a platform.\n\nShortcuts: Space play/pause, arrows seek, I/O set trim, Ctrl+O browse, Ctrl+E export."; tk.Label(card, text=help_text, bg=PANEL, fg=TEXT, justify="left", anchor="nw", wraplength=540, padx=12, pady=12).pack(fill="x"); bar = tk.Frame(dialog, bg=BG); bar.pack(fill="x", padx=18, pady=12); flat_button(bar, "Documentation", lambda: webbrowser.open("https://github.com/anivdas/Cammetry#readme")).pack(side="left", padx=3); flat_button(bar, "Report issue", lambda: webbrowser.open("https://github.com/anivdas/Cammetry/issues")).pack(side="left", padx=3); flat_button(bar, "Check updates", lambda: self.check_updates(True)).pack(side="left", padx=3); flat_button(bar, "Diagnostics", self.open_diagnostics).pack(side="left", padx=3); flat_button(bar, "Close", dialog.destroy, accent=True).pack(side="right")
    def open_diagnostics(self):
        dialog = tk.Toplevel(self); dialog.title("Cammetry diagnostics"); dialog.geometry("700x500"); dialog.configure(bg=BG); dialog.transient(self)
        try: ffmpeg = get_ffmpeg_exe()
        except Exception as exc: ffmpeg = f"Unavailable: {exc}"
        try: status = encoder_status()
        except Exception: status = {"CPU x264": True}
        lines = [f"Cammetry: {APP_VERSION}", f"OS: {platform.platform()}", f"Python: {platform.python_version()}", f"FFmpeg: {ffmpeg}", "", "Encoder readiness:"]; lines.extend(f"  {name}: {'available' if ok else 'unavailable'}" for name, ok in status.items()); lines.extend(["", f"Selected recording: {self.selected_group.timestamp if self.selected_group else 'none'}", f"Camera streams: {len(self.selected_group.cameras) if self.selected_group else 0}", f"Telemetry samples: {len(self.samples)}"]); text = "\n".join(lines); box = tk.Text(dialog, bg=PANEL, fg=TEXT, insertbackground="white", relief="flat", wrap="word"); box.pack(fill="both", expand=True, padx=14, pady=14); box.insert("1.0", text); box.configure(state="disabled"); bar = tk.Frame(dialog, bg=BG); bar.pack(fill="x", padx=14, pady=(0, 14))
        def copy(): self.clipboard_clear(); self.clipboard_append(text)
        flat_button(bar, "Copy diagnostics", copy).pack(side="left"); flat_button(bar, "Close", dialog.destroy, accent=True).pack(side="right")
    def share_last(self):
        if not self.last_output or not self.last_output.exists(): messagebox.showinfo(APP_NAME, "Export a clip first, then choose Publish."); return
        path = self.last_output; dialog = tk.Toplevel(self); dialog.title("Publish / Share"); dialog.geometry("560x500"); dialog.configure(bg=BG); dialog.transient(self); tk.Label(dialog, text="PUBLISH / SHARE", bg=BG, fg=TEXT, font=("Segoe UI Semibold", 14)).pack(anchor="w", padx=18, pady=(16, 2)); tk.Label(dialog, text=path.name, bg=BG, fg=MUTED, wraplength=510, justify="left").pack(anchor="w", padx=18, pady=(0, 10)); privacy = tk.Frame(dialog, bg="#211b12", highlightthickness=1, highlightbackground=WARN); privacy.pack(fill="x", padx=18, pady=6); tk.Label(privacy, text="Privacy check: review GPS/minimap, timestamps, faces and license plates before publishing.", bg="#211b12", fg="#f7d58a", wraplength=500, justify="left", padx=10, pady=9).pack(fill="x"); body = tk.Frame(dialog, bg=PANEL, highlightthickness=1, highlightbackground=BORDER); body.pack(fill="both", expand=True, padx=18, pady=8)
        def action(label, command, detail):
            row = tk.Frame(body, bg=PANEL); row.pack(fill="x", padx=10, pady=5); flat_button(row, label, command, accent=(label == "YouTube")).pack(side="left"); tk.Label(row, text=detail, bg=PANEL, fg=MUTED, anchor="w").pack(side="left", padx=10)
        action("YouTube", lambda: webbrowser.open("https://www.youtube.com/upload"), "Open YouTube Studio upload"); action("Vimeo", lambda: webbrowser.open("https://vimeo.com/upload"), "Open Vimeo upload"); action("TikTok", lambda: webbrowser.open("https://www.tiktok.com/upload"), "Open TikTok upload")
        def reveal():
            try:
                if os.name == "nt": subprocess.Popen(["explorer", "/select,", str(path)])
                elif sys.platform == "darwin": subprocess.Popen(["open", "-R", str(path)])
                else: subprocess.Popen(["xdg-open", str(path.parent)])
            except Exception: pass
        def copy_path(): self.clipboard_clear(); self.clipboard_append(str(path))
        action("Reveal file", reveal, "Show the exported MP4 in its folder"); action("Copy path", copy_path, "Copy the local MP4 path"); endpoint = str(self.settings.get("share_endpoint", "")).strip()
        if endpoint: action("Temporary link", lambda: LegacyApp.share_last(self), "Upload using your configured Cammetry endpoint")
        else:
            row = tk.Frame(body, bg=PANEL); row.pack(fill="x", padx=10, pady=5); tk.Label(row, text="Temporary link", bg=PANEL, fg=MUTED, width=14, anchor="w").pack(side="left"); tk.Label(row, text="Not configured (optional)", bg=PANEL, fg=MUTED).pack(side="left", padx=10)
        flat_button(dialog, "Close", dialog.destroy, accent=True).pack(anchor="e", padx=18, pady=(0, 14))


App = ModernApp
