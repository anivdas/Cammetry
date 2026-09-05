from __future__ import annotations

"""Cammetry 0.6 workflow layer.

This keeps the proven media/export engine intact while exposing the new library,
incident, compatibility, privacy, sequence, and event-review services.  The
services contain no Tk dependencies so a WinUI 3 shell can consume them through
the planned local bridge.
"""

import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from tts_compatibility import inspect_group
from tts_core import APP_NAME, ClipGroup, detect_teslacam_roots
from tts_event_detection import DetectedEvent, detect_events
from tts_hotfix_ui import HotfixApp
from tts_incident import create_incident_package
from tts_library import ClipLibrary
from tts_privacy import LocalPrivacyDetector, PRIVACY_PRESETS
from tts_sequence import ClipSequence, build_sequences, sequence_for_group
from tts_settings import save_settings, settings_dir
from tts_ui import ACCENT, BG, BORDER, CARD2, DANGER, GOOD, MUTED, PANEL, TEXT, WARN
from tts_ui_polish import flat_button


class V060App(HotfixApp):
    """Integrated 0.6 UX while the native Windows shell is developed."""

    def __init__(self):
        self.library = ClipLibrary()
        self.sequences: list[ClipSequence] = []
        self.detected_events: list[DetectedEvent] = []
        self._event_detection_signature: tuple[int, float] | None = None
        self._pending_privacy_preset = None
        self._advancing_sequence = False
        self.continuous_playback = None
        self.sequence_label = None
        super().__init__()

    # ------------------------------------------------------------------
    # First run and main navigation.
    # ------------------------------------------------------------------
    def _first_run_notice(self):
        dialog = tk.Toplevel(self)
        dialog.title("Welcome to Cammetry")
        dialog.geometry("650x430")
        dialog.configure(bg=BG)
        dialog.transient(self)
        dialog.grab_set()
        tk.Label(dialog, text="WELCOME TO CAMMETRY", bg=BG, fg=TEXT,
                 font=("Segoe UI Semibold", 18)).pack(anchor="w", padx=24, pady=(24, 4))
        tk.Label(
            dialog,
            text=("Review, understand, preserve, and export TeslaCam recordings locally. "
                  "Cammetry does not require a Tesla account and does not upload footage or analytics."),
            bg=BG, fg=MUTED, justify="left", wraplength=590, font=("Segoe UI", 10),
        ).pack(anchor="w", padx=24, pady=(0, 18))
        card = tk.Frame(dialog, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", padx=24, pady=4)

        def finish(action=None):
            self.settings["privacy_notice_seen"] = True
            self.settings["onboarding_completed"] = True
            save_settings(self.settings)
            dialog.destroy()
            if action:
                self.after(40, action)

        roots = detect_teslacam_roots()
        if roots:
            def open_drive():
                self.root_path.set(str(roots[0]))
                self.scan()
            flat_button(card, "Open detected TeslaCam drive", lambda: finish(open_drive), accent=True).pack(fill="x", padx=16, pady=(16, 6))
        flat_button(card, "Open TeslaCam folder", lambda: finish(self.browse_root), accent=not roots).pack(fill="x", padx=16, pady=6)
        flat_button(card, "Open local clip library", lambda: finish(self.open_library)).pack(fill="x", padx=16, pady=6)
        flat_button(card, "Explore the interface first", lambda: finish()).pack(fill="x", padx=16, pady=(6, 16))
        tk.Label(
            dialog,
            text="Always preserve the original recordings. Detected events and telemetry are review aids, not forensic conclusions.",
            bg=BG, fg=WARN, justify="left", wraplength=590, font=("Segoe UI", 8),
        ).pack(anchor="w", padx=24, pady=14)

    def _build_topbar(self):
        super()._build_topbar()
        bar = self.winfo_children()[-1]
        flat_button(bar, "Health", self.open_compatibility_center).pack(side="right", padx=3, pady=8)
        flat_button(bar, "Library", self.open_library).pack(side="right", padx=3, pady=8)

    def _build_center(self):
        super()._build_center()
        sequence_bar = tk.Frame(self.center, bg=BG)
        sequence_bar.pack(fill="x", pady=(0, 6), before=self.wall)
        self.sequence_label = tk.Label(sequence_bar, text="EVENT  —", bg=BG, fg=MUTED,
                                       font=("Segoe UI Semibold", 8), anchor="w")
        self.sequence_label.pack(side="left", fill="x", expand=True)
        self.continuous_playback = tk.BooleanVar(value=bool(self.settings.get("continuous_event_playback", True)))
        tk.Checkbutton(
            sequence_bar, text="Continuous event", variable=self.continuous_playback,
            command=self._save_continuous_preference, bg=BG, fg=TEXT,
            selectcolor=CARD2, activebackground=BG, activeforeground=TEXT,
        ).pack(side="right", padx=(8, 0))
        flat_button(sequence_bar, "Next segment", lambda: self._move_segment(1)).pack(side="right", padx=2)
        flat_button(sequence_bar, "Previous segment", lambda: self._move_segment(-1)).pack(side="right", padx=2)

    def _save_continuous_preference(self):
        self.settings["continuous_event_playback"] = bool(self.continuous_playback.get())
        save_settings(self.settings)

    # ------------------------------------------------------------------
    # Scan, sequence playback, local indexing, and review markers.
    # ------------------------------------------------------------------
    def scan(self):
        result = super().scan()
        self.sequences = build_sequences(self.groups)
        self._refresh_sequence_label()
        groups = list(self.groups)
        threading.Thread(target=lambda: self.library.index_groups(groups), daemon=True).start()
        return result

    def load_group(self, group: ClipGroup):
        self.detected_events = []
        self._event_detection_signature = None
        if hasattr(self, "timeline"):
            self.timeline.set_review_events([])
        result = super().load_group(group)
        self._refresh_sequence_label()
        return result

    def _current_sequence(self) -> ClipSequence | None:
        return sequence_for_group(self.sequences, self.selected_group) if self.selected_group else None

    def _refresh_sequence_label(self):
        if self.sequence_label is None:
            return
        sequence = self._current_sequence()
        if not sequence or not self.selected_group:
            self.sequence_label.configure(text="EVENT  —")
            return
        index = next((i for i, segment in enumerate(sequence.segments) if segment.group.timestamp == self.selected_group.timestamp), 0)
        self.sequence_label.configure(
            text=f"EVENT  {index + 1}/{len(sequence.segments)} segments  •  approximately {sequence.duration / 60:.1f} min"
        )

    def _move_segment(self, direction: int, autoplay: bool = False) -> bool:
        sequence = self._current_sequence()
        if not sequence or not self.selected_group:
            return False
        index = next((i for i, segment in enumerate(sequence.segments) if segment.group.timestamp == self.selected_group.timestamp), -1)
        target = index + int(direction)
        if target < 0 or target >= len(sequence.segments):
            return False
        self._advancing_sequence = True
        self.load_group(sequence.segments[target].group)
        self._select_group_in_tree(sequence.segments[target].group)
        if autoplay:
            def resume():
                self.player.play()
                self.play_button.configure(text="⏸  " + self.t("pause"))
                self._advancing_sequence = False
            self.after(120, resume)
        else:
            self._advancing_sequence = False
        return True

    def _select_group_in_tree(self, group: ClipGroup):
        for index, candidate in enumerate(self.filtered_groups):
            if candidate.timestamp == group.timestamp and candidate.folder == group.folder:
                iid = str(index)
                if self.event_tree.exists(iid):
                    self.event_tree.selection_set(iid)
                    self.event_tree.focus(iid)
                    self.event_tree.see(iid)
                return

    def _tick(self):
        was_playing = bool(getattr(self.player, "playing", False))
        super()._tick()
        at_end = bool(self.video_duration and self.player.position >= self.video_duration - 0.08)
        if (
            was_playing and at_end and not self.player.playing and not self._advancing_sequence
            and self.continuous_playback is not None and self.continuous_playback.get()
        ):
            self._move_segment(1, autoplay=True)

    def _update_insights(self):
        super()._update_insights()
        signature = (len(self.samples), float(self.telemetry_fps))
        if self.samples and signature != self._event_detection_signature:
            self.detected_events = detect_events(self.samples, self.telemetry_fps)
            self._event_detection_signature = signature
            self.timeline.set_review_events(self.detected_events)
        if self.detected_events:
            current = str(self.insights.cget("text"))
            self.insights.configure(text=current + f"\nReview markers   {len(self.detected_events)}")

    def open_review_markers(self):
        if not self.selected_group:
            messagebox.showinfo(APP_NAME, "Open a recording first.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Review markers")
        dialog.geometry("600x480")
        dialog.configure(bg=BG)
        dialog.transient(self)
        tk.Label(dialog, text="LOCAL REVIEW MARKERS", bg=BG, fg=TEXT,
                 font=("Segoe UI Semibold", 14)).pack(anchor="w", padx=16, pady=(16, 4))
        tk.Label(dialog, text="Generated locally from telemetry. Double-click a marker to jump to it.",
                 bg=BG, fg=MUTED).pack(anchor="w", padx=16, pady=(0, 10))
        tree = ttk.Treeview(dialog, columns=("time", "event", "severity"), show="headings", style="Dark.Treeview")
        for key, label, width in (("time", "TIME", 90), ("event", "EVENT", 330), ("severity", "LEVEL", 90)):
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor="w")
        for index, event in enumerate(self.detected_events):
            tree.insert("", "end", iid=str(index), values=(f"{event.seconds:.2f}s", event.label, event.severity))
        tree.pack(fill="both", expand=True, padx=16, pady=8)
        def jump(_event=None):
            selection = tree.selection()
            if selection:
                self.seek(self.detected_events[int(selection[0])].seconds)
                dialog.destroy()
        tree.bind("<Double-1>", jump)
        bar = tk.Frame(dialog, bg=BG)
        bar.pack(fill="x", padx=16, pady=(0, 14))
        flat_button(bar, "Jump", jump, accent=True).pack(side="left")
        flat_button(bar, "Close", dialog.destroy).pack(side="right")

    # ------------------------------------------------------------------
    # Tools surface.
    # ------------------------------------------------------------------
    def show_tools_panel(self):
        self._close_overlay("_tools_overlay")
        panel = tk.Frame(self, bg=BG, highlightthickness=1, highlightbackground="#46627f")
        self._tools_overlay = panel
        panel.place(relx=1.0, rely=1.0, x=-22, y=-72, anchor="se", width=410, height=430)
        panel.tkraise()
        head = tk.Frame(panel, bg=BG)
        head.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(head, text="TOOLS", bg=BG, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(side="left")
        flat_button(head, "Close", lambda: self._close_overlay("_tools_overlay")).pack(side="right")
        card = tk.Frame(panel, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        def action(callback):
            def run():
                self._close_overlay("_tools_overlay")
                self.after(20, callback)
            return run
        entries = (
            ("Review markers", self.open_review_markers, True),
            ("Incident workspace", self.open_incident_workspace, True),
            ("Privacy Export", self.open_privacy_export, True),
            ("Compatibility center", self.open_compatibility_center, False),
            ("Local clip library", self.open_library, False),
            ("Jump to recorded event", self.jump_to_event, False),
            ("Manual privacy zones", self.edit_blur_zones, False),
            ("Export telemetry CSV", self.export_csv_ui, False),
        )
        for index, (label, callback, accent) in enumerate(entries):
            flat_button(card, label, action(callback), accent=accent).pack(fill="x", padx=12, pady=(10 if index == 0 else 4, 4))
        panel.focus_set()
        panel.bind("<Escape>", lambda _e: self._close_overlay("_tools_overlay"))

    # ------------------------------------------------------------------
    # Compatibility center.
    # ------------------------------------------------------------------
    def open_compatibility_center(self):
        dialog = tk.Toplevel(self)
        dialog.title("Cammetry compatibility center")
        dialog.geometry("760x580")
        dialog.configure(bg=BG)
        dialog.transient(self)
        tk.Label(dialog, text="COMPATIBILITY CENTER", bg=BG, fg=TEXT,
                 font=("Segoe UI Semibold", 15)).pack(anchor="w", padx=18, pady=(18, 4))
        status = tk.Label(dialog, text="Checking video, telemetry, encoders, and storage…", bg=BG, fg=MUTED)
        status.pack(anchor="w", padx=18, pady=(0, 10))
        box = tk.Text(dialog, bg=PANEL, fg=TEXT, insertbackground="white", relief="flat", wrap="word")
        box.pack(fill="both", expand=True, padx=18, pady=8)
        box.insert("1.0", "Running local checks…")
        box.configure(state="disabled")
        report_text = {"value": ""}
        def copy():
            self.clipboard_clear()
            self.clipboard_append(report_text["value"])
        bar = tk.Frame(dialog, bg=BG)
        bar.pack(fill="x", padx=18, pady=(0, 14))
        flat_button(bar, "Copy safe report", copy).pack(side="left")
        flat_button(bar, "Close", dialog.destroy, accent=True).pack(side="right")
        def work():
            output = Path.home() / "Videos"
            if not output.exists():
                output = Path.home()
            report = inspect_group(self.selected_group, list(self.samples), output_folder=output, expected_duration=self.video_duration)
            text = report.safe_text()
            def done():
                report_text["value"] = text
                status.configure(text="Ready to export" if report.ready else "Review the items marked ACTION NEEDED", fg=GOOD if report.ready else WARN)
                box.configure(state="normal")
                box.delete("1.0", "end")
                box.insert("1.0", text)
                box.configure(state="disabled")
            self.after(0, done)
        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------------
    # Local library.
    # ------------------------------------------------------------------
    def open_library(self):
        dialog = tk.Toplevel(self)
        dialog.title("Cammetry clip library")
        dialog.geometry("940x650")
        dialog.configure(bg=BG)
        dialog.transient(self)
        tk.Label(dialog, text="LOCAL CLIP LIBRARY", bg=BG, fg=TEXT,
                 font=("Segoe UI Semibold", 15)).pack(anchor="w", padx=18, pady=(18, 4))
        tk.Label(dialog, text="Notes, tags, favorites, and bookmarks stay on this computer.", bg=BG, fg=MUTED).pack(anchor="w", padx=18, pady=(0, 10))
        search = tk.StringVar()
        entry = tk.Entry(dialog, textvariable=search, bg=CARD2, fg=TEXT, insertbackground="white", relief="flat")
        entry.pack(fill="x", padx=18, pady=(0, 8), ipady=7)
        tree = ttk.Treeview(dialog, columns=("time", "type", "title", "tags", "cams"), show="headings", style="Dark.Treeview")
        for key, label, width in (("time", "RECORDED", 155), ("type", "TYPE", 75), ("title", "TITLE", 300), ("tags", "TAGS", 230), ("cams", "CAMS", 55)):
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor="w")
        tree.pack(fill="both", expand=True, padx=18, pady=8)
        rows = []
        def refresh(*_args):
            nonlocal rows
            rows = self.library.search(search.get())
            tree.delete(*tree.get_children())
            for index, record in enumerate(rows):
                tree.insert("", "end", iid=str(index), values=(record.timestamp, record.source_kind, ("★ " if record.favorite else "") + record.title, ", ".join(record.tags), record.camera_count))
        search.trace_add("write", refresh)
        refresh()
        def edit():
            selected = tree.selection()
            if not selected:
                return
            record = rows[int(selected[0])]
            title = simpledialog.askstring("Library title", "Title", initialvalue=record.title, parent=dialog)
            if title is None:
                return
            tags = simpledialog.askstring("Library tags", "Comma-separated tags", initialvalue=", ".join(record.tags), parent=dialog)
            if tags is None:
                return
            self.library.update_recording(record.id, title=title, tags=tags.split(","))
            refresh()
        def open_recording():
            selected = tree.selection()
            if not selected:
                return
            record = rows[int(selected[0])]
            group = next((item for item in self.groups if item.timestamp == record.timestamp and str(item.folder.resolve()) == record.folder), None)
            if group:
                dialog.destroy()
                self.load_group(group)
                self._select_group_in_tree(group)
            else:
                messagebox.showinfo(APP_NAME, "The indexed source is not in the currently open TeslaCam folder.")
        tree.bind("<Double-1>", lambda _e: open_recording())
        bar = tk.Frame(dialog, bg=BG)
        bar.pack(fill="x", padx=18, pady=(0, 14))
        flat_button(bar, "Edit title and tags", edit).pack(side="left")
        flat_button(bar, "Open recording", open_recording, accent=True).pack(side="left", padx=5)
        flat_button(bar, "Close", dialog.destroy).pack(side="right")

    # ------------------------------------------------------------------
    # Incident workspace.
    # ------------------------------------------------------------------
    def open_incident_workspace(self):
        if not self.selected_group:
            messagebox.showinfo(APP_NAME, "Open a recording first.")
            return
        recording_id = self.library.index_group(self.selected_group)
        dialog = tk.Toplevel(self)
        dialog.title("Cammetry incident workspace")
        dialog.geometry("700x620")
        dialog.configure(bg=BG)
        dialog.transient(self)
        tk.Label(dialog, text="INCIDENT WORKSPACE", bg=BG, fg=TEXT,
                 font=("Segoe UI Semibold", 15)).pack(anchor="w", padx=18, pady=(18, 4))
        tk.Label(dialog, text=f"{self.selected_group.display_time()} · {len(self.selected_group.cameras)} cameras",
                 bg=BG, fg=MUTED).pack(anchor="w", padx=18, pady=(0, 12))
        title = tk.StringVar(value=f"Incident {self.selected_group.display_time()}")
        tk.Label(dialog, text="Title", bg=BG, fg=MUTED).pack(anchor="w", padx=18)
        tk.Entry(dialog, textvariable=title, bg=PANEL, fg=TEXT, insertbackground="white", relief="flat").pack(fill="x", padx=18, pady=(3, 10), ipady=7)
        tk.Label(dialog, text="Notes", bg=BG, fg=MUTED).pack(anchor="w", padx=18)
        notes = tk.Text(dialog, height=7, bg=PANEL, fg=TEXT, insertbackground="white", relief="flat", wrap="word")
        notes.pack(fill="x", padx=18, pady=(3, 10))
        bookmarks_box = tk.Listbox(dialog, bg=PANEL, fg=TEXT, selectbackground=ACCENT, relief="flat", height=7)
        bookmarks_box.pack(fill="both", expand=True, padx=18, pady=8)
        def refresh_bookmarks():
            bookmarks_box.delete(0, "end")
            for bookmark in self.library.bookmarks(recording_id):
                bookmarks_box.insert("end", f"{bookmark.seconds:7.2f}s  {bookmark.label}")
        def add_bookmark():
            label = simpledialog.askstring("Bookmark", "Bookmark label", initialvalue="Important moment", parent=dialog)
            if label:
                self.library.add_bookmark(recording_id, self.player.position, label)
                refresh_bookmarks()
        refresh_bookmarks()
        include_sources = tk.BooleanVar(value=False)
        tk.Checkbutton(dialog, text="Include verified copies of original camera files", variable=include_sources,
                       bg=BG, fg=TEXT, selectcolor=CARD2, activebackground=BG, activeforeground=TEXT).pack(anchor="w", padx=18, pady=6)
        status = tk.Label(dialog, text="Original files are hashed and never modified.", bg=BG, fg=MUTED)
        status.pack(anchor="w", padx=18, pady=(0, 8))
        def create():
            root = filedialog.askdirectory(title="Choose incident package destination", parent=dialog)
            if not root:
                return
            incident_title = title.get().strip() or "Incident"
            incident_notes = notes.get("1.0", "end").strip()
            start, end = self.in_point, self.out_point or self.video_duration
            group = self.selected_group
            copy_sources = bool(include_sources.get())
            exported_video = self.last_output
            review_events = list(self.detected_events)
            self.library.create_incident(recording_id, incident_title, start, end, incident_notes)
            status.configure(text="Hashing source files and creating incident package…", fg=WARN)
            def work():
                try:
                    result = create_incident_package(
                        Path(root), incident_title, incident_notes, group,
                        start=start, end=end, bookmarks=self.library.bookmarks(recording_id),
                        detected_events=review_events, include_sources=copy_sources,
                        exported_video=exported_video,
                    )
                    self.after(0, lambda: done(result.archive or result.folder))
                except Exception as exc:
                    self.after(0, lambda error=str(exc): failed(error))
            def done(path):
                status.configure(text=f"Incident package created: {path}", fg=GOOD)
                messagebox.showinfo(APP_NAME, f"Incident package created.\n\n{path}", parent=dialog)
            def failed(error):
                status.configure(text="Incident package could not be created.", fg=DANGER)
                messagebox.showerror(APP_NAME, error, parent=dialog)
            threading.Thread(target=work, daemon=True).start()
        bar = tk.Frame(dialog, bg=BG)
        bar.pack(fill="x", padx=18, pady=(0, 14))
        flat_button(bar, "Add bookmark here", add_bookmark).pack(side="left")
        flat_button(bar, "Create package", create, accent=True).pack(side="left", padx=5)
        flat_button(bar, "Close", dialog.destroy).pack(side="right")

    # ------------------------------------------------------------------
    # One-click privacy export.
    # ------------------------------------------------------------------
    def open_privacy_export(self):
        if not self.selected_group:
            messagebox.showinfo(APP_NAME, "Open a recording first.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Privacy Export")
        dialog.geometry("590x430")
        dialog.configure(bg=BG)
        dialog.transient(self)
        dialog.grab_set()
        tk.Label(dialog, text="PRIVACY EXPORT", bg=BG, fg=TEXT,
                 font=("Segoe UI Semibold", 15)).pack(anchor="w", padx=18, pady=(18, 4))
        tk.Label(dialog, text="Choose a local-only privacy preset. Always review detected regions before publishing.",
                 bg=BG, fg=MUTED, wraplength=545, justify="left").pack(anchor="w", padx=18, pady=(0, 12))
        preset_name = tk.StringVar(value="Share Safe")
        ttk.Combobox(dialog, textvariable=preset_name, values=tuple(PRIVACY_PRESETS), state="readonly",
                     style="Dark.TCombobox").pack(fill="x", padx=18, pady=6)
        detect_regions = tk.BooleanVar(value=True)
        tk.Checkbutton(dialog, text="Find faces and license plates in the current frame locally", variable=detect_regions,
                       bg=BG, fg=TEXT, selectcolor=CARD2, activebackground=BG, activeforeground=TEXT).pack(anchor="w", padx=18, pady=8)
        explanation = tk.Label(
            dialog,
            text=("Share Safe removes timestamps, maps, coordinate text, and MP4 metadata. "
                  "First-pass face/plate boxes are added to the manual privacy-zone editor; detection may miss objects."),
            bg=PANEL, fg=TEXT, justify="left", wraplength=520, padx=12, pady=12,
        )
        explanation.pack(fill="x", padx=18, pady=10)
        def continue_export():
            self._pending_privacy_preset = PRIVACY_PRESETS[preset_name.get()]
            original_zones = list(self.blur_zones)
            if detect_regions.get():
                self.player.pause()
                self._refresh_frames()
                try:
                    import cv2  # type: ignore
                    import numpy as np
                    from tts_export import BlurZone
                    preview = self._compose_preview_image()
                    frame = cv2.cvtColor(np.asarray(preview), cv2.COLOR_RGB2BGR)
                    for region in LocalPrivacyDetector().detect(frame):
                        self.blur_zones.append(BlurZone(region.x, region.y, region.width, region.height, 18))
                except Exception as exc:
                    self.status_var.set(f"Local privacy detection unavailable: {exc}")
            dialog.destroy()
            if self.blur_zones:
                def review_then_export():
                    proposed = self.blur_zones
                    self.edit_blur_zones()
                    if self.blur_zones is proposed:
                        self.blur_zones = original_zones
                        self._pending_privacy_preset = None
                        self.status_var.set("Privacy Export cancelled; no detected regions were retained.")
                        return
                    self.open_export()
                self.after(40, review_then_export)
            else:
                self.after(40, self.open_export)
        bar = tk.Frame(dialog, bg=BG)
        bar.pack(fill="x", padx=18, pady=(10, 14))
        flat_button(bar, "Cancel", dialog.destroy).pack(side="right", padx=4)
        flat_button(bar, "Review and export", continue_export, accent=True).pack(side="right", padx=4)

    def open_export(self):
        super().open_export()
        if self._pending_privacy_preset is None:
            return
        dialog = self._find_dialog("Export clip")
        if dialog is None:
            self._pending_privacy_preset = None
            return
        def clear_if_cancelled():
            if self._pending_privacy_preset is not None:
                self._pending_privacy_preset = None
        dialog.bind("<Destroy>", lambda event: self.after_idle(clear_if_cancelled) if event.widget is dialog else None, add="+")

    def start_export(self, dest, options):
        if self._pending_privacy_preset is not None:
            self._pending_privacy_preset.apply(options)
            self._pending_privacy_preset = None
        return super().start_export(dest, options)


App = V060App
