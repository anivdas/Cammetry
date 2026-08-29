from __future__ import annotations

import os
import platform
import shutil
import subprocess
import time
from datetime import date, timedelta
from typing import Optional, Sequence

import tkinter as tk
from tkinter import ttk

from tts_core import APP_NAME, APP_VERSION, ClipGroup, get_ffmpeg_exe
from tts_export_v051 import encoder_status
from tts_modern_ui import CalendarPicker, ModernApp
from tts_ui import BG, PANEL, TEXT, flat_button


_DATE_FORMATS = {
    "YYYY-MM-DD": "%Y-%m-%d",
    "MM/DD/YYYY": "%m/%d/%Y",
    "DD/MM/YYYY": "%d/%m/%Y",
    "DD Mon YYYY": "%d %b %Y",
}


class ReleaseCalendarPicker(CalendarPicker):
    """Final v0.5.1 calendar polish layered over the modern beta picker."""

    def __init__(self, parent, groups: Sequence[ClipGroup], callback):
        self._owner = parent
        super().__init__(parent, groups, callback)
        self._add_yesterday_button()

    def _add_yesterday_button(self) -> None:
        # CalendarPicker intentionally keeps its quick-range row private. Find
        # the row containing Today so this small release layer stays isolated.
        for child in self.winfo_children():
            if not isinstance(child, tk.Frame) or child is self.grid_frame:
                continue
            buttons = [w for w in child.winfo_children() if isinstance(w, tk.Button)]
            if any(str(w.cget("text")) == "Today" for w in buttons):
                flat_button(child, "Yesterday", self._yesterday).pack(side="left", padx=2)
                break

    def _yesterday(self) -> None:
        day = date.today() - timedelta(days=1)
        self._apply(day, day, "Yesterday")

    def _format_date(self, value: date) -> str:
        settings = getattr(self._owner, "settings", {}) or {}
        fmt = _DATE_FORMATS.get(str(settings.get("date_format", "YYYY-MM-DD")), "%Y-%m-%d")
        return value.strftime(fmt)

    def _apply(self, start: Optional[date], end: Optional[date], label: str) -> None:
        if start is not None and end is not None and label not in {
            "Today", "Yesterday", "Last 7 days", "Last 30 days", "All dates"
        }:
            if start == end:
                label = self._format_date(start)
            else:
                label = f"{self._format_date(start)} to {self._format_date(end)}"
        super()._apply(start, end, label)


class ReleaseApp(ModernApp):
    """Release-gate refinements that keep the parser/player core untouched."""

    def __init__(self):
        self._preview_render_count = 0
        self._preview_skip_resize = 0
        self._preview_skip_hidden = 0
        self._preview_metric_started = time.perf_counter()
        self._clip_action_buttons: list[tk.Widget] = []
        super().__init__()
        self._stabilize_camera_tiles()
        self._capture_clip_action_buttons()
        self._set_clip_action_state(bool(getattr(self, "selected_group", None)))

    def _stabilize_camera_tiles(self) -> None:
        # Tk Labels normally request the full PhotoImage size. During a live
        # window shrink that old requested size can temporarily push the fixed
        # transport/timeline out of view. Let the grid own tile geometry instead.
        for tile in getattr(self, "tiles", {}).values():
            try:
                tile.pack_propagate(False)
                tile.image.configure(width=1, height=1)
            except Exception:
                pass

    def open_calendar(self):
        ReleaseCalendarPicker(self, self.groups, self._set_date_filter)

    def refresh_event_list(self):
        # Preserve the selected recording when it remains visible after a type,
        # date, or search filter change.
        selected = getattr(self, "selected_group", None)
        selected_key = None
        if selected is not None:
            selected_key = (selected.timestamp, str(selected.folder))
        super().refresh_event_list()
        if selected_key is None or not hasattr(self, "event_tree"):
            return
        for index, group in enumerate(getattr(self, "filtered_groups", [])):
            if (group.timestamp, str(group.folder)) == selected_key:
                iid = str(index)
                if self.event_tree.exists(iid):
                    self.event_tree.selection_set(iid)
                    self.event_tree.focus(iid)
                    self.event_tree.see(iid)
                break

    def _walk_widgets(self, parent):
        for child in parent.winfo_children():
            yield child
            yield from self._walk_widgets(child)

    def _capture_clip_action_buttons(self) -> None:
        target_labels = {
            "Play", "Vehicle View", "Start", "End", "Clear", "Export", "Publish",
            str(self.t("snapshot")),
        }
        self._clip_action_buttons = []
        for widget in self._walk_widgets(self):
            if isinstance(widget, (tk.Button, ttk.Button)):
                try:
                    label = str(widget.cget("text"))
                    is_seek = (label.startswith("-") or label.startswith("+")) and label.endswith("s")
                    if label in target_labels or is_seek:
                        self._clip_action_buttons.append(widget)
                except Exception:
                    pass

    def _set_clip_action_state(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in self._clip_action_buttons:
            try:
                button.configure(state=state)
            except Exception:
                pass

    def load_group(self, group: ClipGroup):
        super().load_group(group)
        self._set_clip_action_state(
            bool(getattr(self, "selected_group", None) is group and getattr(self, "video_duration", 0.0) > 0.0)
        )

    def _tick(self):
        playing = bool(getattr(getattr(self, "player", None), "playing", False))
        visible = False
        try:
            visible = self.state() != "iconic" and self.winfo_viewable()
        except Exception:
            pass
        now = time.perf_counter()
        resizing = now < float(getattr(self, "_resize_until", 0.0))
        previous_render = float(getattr(self, "_last_preview_update", 0.0))
        super()._tick()
        current_render = float(getattr(self, "_last_preview_update", 0.0))
        if playing:
            if not visible:
                self._preview_skip_hidden += 1
            elif resizing:
                self._preview_skip_resize += 1
            elif current_render > previous_render:
                self._preview_render_count += 1

    def _gpu_diagnostics(self) -> list[str]:
        if os.name != "nt":
            return []
        candidates = [shutil.which("nvidia-smi"), r"C:\Windows\System32\nvidia-smi.exe"]
        for candidate in candidates:
            if not candidate or not os.path.exists(candidate):
                continue
            try:
                output = subprocess.check_output(
                    [candidate, "--query-gpu=name,driver_version", "--format=csv,noheader"],
                    text=True,
                    errors="replace",
                    stderr=subprocess.STDOUT,
                    timeout=4,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                ).strip()
                if output:
                    return [f"NVIDIA GPU: {line}" for line in output.splitlines()]
            except Exception:
                pass
        return []

    def open_diagnostics(self):
        dialog = tk.Toplevel(self)
        dialog.title("Cammetry diagnostics")
        dialog.geometry("720x560")
        dialog.configure(bg=BG)
        dialog.transient(self)

        try:
            ffmpeg = get_ffmpeg_exe()
            version_line = subprocess.check_output(
                [ffmpeg, "-hide_banner", "-version"],
                text=True,
                errors="replace",
                stderr=subprocess.STDOUT,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            ).splitlines()[0]
        except Exception as exc:
            ffmpeg = f"Unavailable: {exc}"
            version_line = "Unavailable"
        try:
            status = encoder_status()
        except Exception:
            status = {"CPU x264": True}

        elapsed = max(0.001, time.perf_counter() - self._preview_metric_started)
        avg_preview_fps = self._preview_render_count / elapsed
        lines = [
            f"Cammetry: {APP_VERSION}",
            f"OS: {platform.platform()}",
            f"Python: {platform.python_version()}",
            f"FFmpeg: {ffmpeg}",
            f"FFmpeg build: {version_line}",
        ]
        lines.extend(self._gpu_diagnostics())
        lines.extend([
            "",
            "Encoder readiness:",
            *[f"  {name}: {'available' if ok else 'unavailable'}" for name, ok in status.items()],
            "",
            "Preview/UI metrics:",
            f"  rendered preview updates: {self._preview_render_count}",
            f"  average rendered preview FPS since launch: {avg_preview_fps:.1f}",
            f"  render ticks skipped while resizing: {self._preview_skip_resize}",
            f"  render ticks skipped while minimized/hidden: {self._preview_skip_hidden}",
            "",
            f"Selected recording: {self.selected_group.timestamp if self.selected_group else 'none'}",
            f"Camera streams: {len(self.selected_group.cameras) if self.selected_group else 0}",
            f"Telemetry samples: {len(self.samples)}",
            "",
            "Diagnostics intentionally omit GPS coordinates and video contents.",
        ])
        text = "\n".join(lines)

        box = tk.Text(dialog, bg=PANEL, fg=TEXT, insertbackground="white", relief="flat", wrap="word")
        box.pack(fill="both", expand=True, padx=14, pady=14)
        box.insert("1.0", text)
        box.configure(state="disabled")
        bar = tk.Frame(dialog, bg=BG)
        bar.pack(fill="x", padx=14, pady=(0, 14))

        def copy():
            self.clipboard_clear()
            self.clipboard_append(text)

        flat_button(bar, "Copy diagnostics", copy).pack(side="left")
        flat_button(bar, "Close", dialog.destroy, accent=True).pack(side="right")


App = ReleaseApp
