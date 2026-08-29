from __future__ import annotations

import os
import queue
import re
import subprocess
import threading
import time
from typing import Callable, List, Optional

import tts_export_v051


_ACTIVE_LOCK = threading.Lock()
_ACTIVE_PROCESS: Optional[subprocess.Popen] = None
_CANCEL_REQUESTED = False


class ExportCancelled(RuntimeError):
    pass


def _creationflags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def _set_active(proc: Optional[subprocess.Popen]) -> None:
    global _ACTIVE_PROCESS
    with _ACTIVE_LOCK:
        _ACTIVE_PROCESS = proc


def cancel_active_export() -> bool:
    """Cancel the currently running FFmpeg process, if any."""
    global _CANCEL_REQUESTED
    with _ACTIVE_LOCK:
        _CANCEL_REQUESTED = True
        proc = _ACTIVE_PROCESS
    if proc is None:
        return False
    try:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        return True
    except Exception:
        return False


def clear_cancel_request() -> None:
    global _CANCEL_REQUESTED
    with _ACTIVE_LOCK:
        _CANCEL_REQUESTED = False


def _cancel_requested() -> bool:
    with _ACTIVE_LOCK:
        return _CANCEL_REQUESTED


def guarded_run_ffmpeg(
    cmd: List[str],
    duration: float,
    progress_cb: Optional[Callable[[float, str], None]],
) -> None:
    """Run FFmpeg without allowing a silent hardware-start hang.

    The old implementation iterated directly over proc.stdout. If a hardware
    encoder stalled before emitting its first progress line, that iterator could
    block forever and the UI remained on "Preparing export...". A reader thread
    plus a watchdog keeps the GUI responsive and gives the caller a chance to
    fall back to CPU encoding.
    """
    clear_cancel_request()
    if progress_cb:
        progress_cb(0.12, "Starting encoder")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        bufsize=1,
        creationflags=_creationflags(),
    )
    _set_active(proc)
    lines: "queue.Queue[Optional[str]]" = queue.Queue()
    tail: List[str] = []

    def reader() -> None:
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                lines.put(line)
        finally:
            lines.put(None)

    threading.Thread(target=reader, daemon=True).start()
    started = time.monotonic()
    last_activity = started
    saw_progress = False

    try:
        while True:
            if _cancel_requested():
                try:
                    proc.terminate()
                except Exception:
                    pass
                raise ExportCancelled("Export cancelled.")

            try:
                item = lines.get(timeout=0.25)
            except queue.Empty:
                now = time.monotonic()
                if proc.poll() is not None:
                    break
                # Hardware initialization should be fast for TeslaCam-sized clips.
                # If FFmpeg cannot emit its first timestamp in 25 seconds, abort so
                # the existing export path can retry with CPU x264.
                if not saw_progress and now - started > 25.0:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    raise tts_export_v051.FFmpegExportError(
                        "Hardware encoder did not start in time.",
                        "FFmpeg produced no encoding timestamp within 25 seconds.\n" + "\n".join(tail[-24:]),
                    )
                # Once encoding starts, a long silent stall is also abnormal for a
                # short dashcam clip. Do not leave an export stuck forever.
                if saw_progress and now - last_activity > 45.0:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    raise tts_export_v051.FFmpegExportError(
                        "Video encoder stopped responding.",
                        "FFmpeg made no progress for 45 seconds.\n" + "\n".join(tail[-24:]),
                    )
                continue

            if item is None:
                break
            text = item.rstrip()
            last_activity = time.monotonic()
            tail.append(text)
            if len(tail) > 80:
                tail.pop(0)
            match = re.search(r"time=(\d+):(\d+):([0-9.]+)", text)
            if match:
                saw_progress = True
                elapsed = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))
                if progress_cb:
                    # Reserve the first 12% for preparation so users can tell the
                    # difference between preparation and actual video encoding.
                    fraction = 0.12 + 0.88 * min(1.0, elapsed / max(duration, 0.1))
                    progress_cb(fraction, "Encoding video")

        code = proc.wait()
        if _cancel_requested():
            raise ExportCancelled("Export cancelled.")
        if code != 0:
            raise tts_export_v051.FFmpegExportError(
                "Video export could not be completed.", "\n".join(tail[-24:])
            )
        if progress_cb:
            progress_cb(1.0, "Export complete")
    finally:
        _set_active(None)


def install_export_guards() -> None:
    # tts_export_v051.export_video resolves _run_ffmpeg from its module globals at
    # runtime, so this protects both hardware and CPU fallback attempts without
    # duplicating the export implementation.
    tts_export_v051._run_ffmpeg = guarded_run_ffmpeg
