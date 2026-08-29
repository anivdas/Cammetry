from __future__ import annotations

import os
import queue
import re
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional, Sequence

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
    """Request cancellation and terminate the currently running FFmpeg process."""
    global _CANCEL_REQUESTED
    with _ACTIVE_LOCK:
        _CANCEL_REQUESTED = True
        proc = _ACTIVE_PROCESS
    if proc is None:
        # Preparation may still be running. guarded_export_video checks the flag
        # between each preparation phase and exits before starting FFmpeg.
        return True
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


def _check_cancelled() -> None:
    if _cancel_requested():
        raise ExportCancelled("Export cancelled.")


def guarded_run_ffmpeg(
    cmd: List[str],
    duration: float,
    progress_cb: Optional[Callable[[float, str], None]],
) -> None:
    """Run FFmpeg with startup/stall watchdogs and cancellation.

    The old implementation iterated directly over proc.stdout. If a hardware
    encoder stalled before emitting its first timestamp, that iterator could
    block indefinitely while Cammetry continued to show "Preparing export...".
    """
    _check_cancelled()
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
                if not saw_progress and now - started > 25.0:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    raise tts_export_v051.FFmpegExportError(
                        "Hardware encoder did not start in time.",
                        "FFmpeg produced no encoding timestamp within 25 seconds.\n" + "\n".join(tail[-24:]),
                    )
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


def guarded_export_video(group, samples: Sequence, telemetry_fps: float, output: Path, options,
                         progress_cb: Optional[Callable[[float, str], None]] = None) -> str:
    """Export with visible preparation phases and the existing CPU fallback."""
    clear_cancel_request()
    m = tts_export_v051
    if progress_cb:
        progress_cb(0.01, "Checking export settings")

    cameras = m._layout_inputs(group, options.layout, options.active_camera)
    if not cameras:
        raise RuntimeError("No camera files are available for this event.")
    _check_cancelled()

    start = max(0.0, options.start)
    info = m.probe_video(group.cameras[cameras[0]])
    default_end = info.duration or (len(samples) / max(telemetry_fps, 1.0) if samples else 60.0)
    end = options.end if options.end > start else default_end
    duration = max(0.1, end - start)

    if progress_cb:
        progress_cb(0.03, "Checking encoder")
    encoder_name, codec = m.resolve_encoder(options.encoder)
    ffmpeg = m.get_ffmpeg_exe()
    _check_cancelled()

    with tempfile.TemporaryDirectory(prefix="cammetry-export-") as td:
        temp = Path(td)
        ass_path = temp / "dashboard.ass"
        if progress_cb:
            progress_cb(0.05, "Preparing telemetry overlay")
        m.write_dashboard_ass(group, samples, telemetry_fps, ass_path, options)
        _check_cancelled()

        route_path = None
        if options.show_minimap:
            if progress_cb:
                progress_cb(0.08, "Preparing map overlay")
            route_path = m.render_route_video(
                samples, telemetry_fps, start, end, temp / "route.mp4", language=options.language
            )
            _check_cancelled()

        if progress_cb:
            progress_cb(0.10, f"Starting {encoder_name}")
        cmd = m._build_command(
            ffmpeg, group, cameras, start, duration, route_path, ass_path, output, options, codec
        )
        try:
            guarded_run_ffmpeg(cmd, duration, progress_cb)
            return encoder_name
        except ExportCancelled:
            try:
                output.unlink(missing_ok=True)
            except Exception:
                pass
            raise
        except m.FFmpegExportError as first_error:
            if codec == "libx264":
                raise RuntimeError(
                    "Cammetry could not export this clip. Open Help > Diagnostics for technical details.\n\n"
                    + first_error.diagnostics[-1800:]
                ) from first_error

            try:
                output.unlink(missing_ok=True)
            except Exception:
                pass
            clear_cancel_request()
            if progress_cb:
                progress_cb(0.10, f"{encoder_name} unavailable; retrying with CPU x264")
            cpu_cmd = m._build_command(
                ffmpeg, group, cameras, start, duration, route_path, ass_path, output, options, "libx264"
            )
            try:
                guarded_run_ffmpeg(cpu_cmd, duration, progress_cb)
                return f"CPU x264 (fallback from {encoder_name})"
            except ExportCancelled:
                try:
                    output.unlink(missing_ok=True)
                except Exception:
                    pass
                raise
            except m.FFmpegExportError as cpu_error:
                raise RuntimeError(
                    "Cammetry could not export this clip with hardware or CPU encoding. "
                    "Open Help > Diagnostics for technical details.\n\n"
                    + cpu_error.diagnostics[-1800:]
                ) from cpu_error


def install_export_guards() -> None:
    # Patch both the export module globals and ReleaseApp's imported export symbol.
    # ReleaseApp imported export_video directly, so changing only the source module
    # would not affect the installed UI.
    tts_export_v051._run_ffmpeg = guarded_run_ffmpeg
    tts_export_v051.export_video = guarded_export_video
    try:
        import tts_release_ui
        tts_release_ui.export_video = guarded_export_video
    except Exception:
        pass
