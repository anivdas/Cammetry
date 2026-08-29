from __future__ import annotations

import math
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import cv2  # type: ignore

from tts_locales import tr, assist_label

from tts_core import (
    CAMERA_ORDER,
    CAMERA_WALL_ORDER,
    ClipGroup,
    TelemetrySample,
    ass_escape,
    ass_time,
    ffmpeg_escape_filter_path,
    get_ffmpeg_exe,
)


@dataclass
class BlurZone:
    x: float
    y: float
    w: float
    h: float
    strength: int = 12


@dataclass
class ExportOptions:
    layout: str = "Six Camera"
    active_camera: str = "front"
    start: float = 0.0
    end: float = 0.0
    units: str = "mph"
    language: str = "English"
    encoder: str = "Auto"
    quality: str = "High"
    dashboard_size: str = "Medium"
    dashboard_style: str = "Default"
    show_dashboard: bool = True
    show_timestamp: bool = True
    timestamp_format: str = "%Y-%m-%d %I:%M:%S %p"
    show_minimap: bool = False
    show_gps_text: bool = False
    show_gforce: bool = True
    blur_zones: List[BlurZone] = field(default_factory=list)


QUALITY_BITRATES = {
    "Mobile": "4M",
    "Medium": "8M",
    "High": "14M",
    "Maximum": "25M",
}
QUALITY_CRF = {"Mobile": 27, "Medium": 23, "High": 19, "Maximum": 16}
DASH_SCALE = {"Small": 0.78, "Medium": 1.0, "Large": 1.22, "X-Large": 1.5}


def available_encoders() -> List[str]:
    ffmpeg = get_ffmpeg_exe()
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        out = subprocess.check_output(
            [ffmpeg, "-hide_banner", "-encoders"], text=True, errors="replace",
            stderr=subprocess.STDOUT, timeout=10, creationflags=creationflags,
        )
    except Exception:
        return ["CPU x264"]
    encoders = []
    if "h264_nvenc" in out:
        encoders.append("NVIDIA NVENC")
    if "h264_qsv" in out:
        encoders.append("Intel QuickSync")
    if "h264_amf" in out:
        encoders.append("AMD AMF")
    if "h264_videotoolbox" in out:
        encoders.append("Apple VideoToolbox")
    encoders.append("CPU x264")
    return encoders


def resolve_encoder(requested: str) -> Tuple[str, str]:
    options = available_encoders()
    if requested == "Auto" or requested not in options:
        requested = options[0]
    mapping = {
        "NVIDIA NVENC": "h264_nvenc",
        "Intel QuickSync": "h264_qsv",
        "AMD AMF": "h264_amf",
        "Apple VideoToolbox": "h264_videotoolbox",
        "CPU x264": "libx264",
    }
    return requested, mapping.get(requested, "libx264")


def _codec_args(codec: str, quality: str) -> List[str]:
    q = quality if quality in QUALITY_BITRATES else "High"
    if codec == "libx264":
        return ["-c:v", codec, "-preset", "medium", "-crf", str(QUALITY_CRF[q])]
    if codec == "h264_nvenc":
        return ["-c:v", codec, "-preset", "p5", "-b:v", QUALITY_BITRATES[q], "-maxrate", QUALITY_BITRATES[q]]
    if codec == "h264_qsv":
        return ["-c:v", codec, "-preset", "medium", "-b:v", QUALITY_BITRATES[q]]
    if codec == "h264_amf":
        return ["-c:v", codec, "-quality", "balanced", "-b:v", QUALITY_BITRATES[q]]
    if codec == "h264_videotoolbox":
        return ["-c:v", codec, "-b:v", QUALITY_BITRATES[q], "-allow_sw", "1"]
    return ["-c:v", "libx264", "-crf", "19"]


def _sample_at(samples: Sequence[TelemetrySample], fps: float, seconds: float) -> TelemetrySample:
    if not samples:
        return TelemetrySample()
    idx = int(round(max(0.0, seconds) * max(fps, 1.0)))
    return samples[min(len(samples) - 1, idx)]


def _timestamp_base(group: ClipGroup) -> Optional[datetime]:
    try:
        return datetime.strptime(group.timestamp, "%Y-%m-%d_%H-%M-%S")
    except Exception:
        return None


def write_dashboard_ass(
    group: ClipGroup,
    samples: Sequence[TelemetrySample],
    fps: float,
    path: Path,
    options: ExportOptions,
) -> None:
    """Generate an original glass-style telemetry overlay. Uses only original Cammetry visual assets."""
    start = max(0.0, options.start)
    end = options.end if options.end > start else len(samples) / max(fps, 1.0)
    duration = max(0.1, end - start)
    hz = 10.0
    steps = max(1, int(math.ceil(duration * hz)))
    scale = DASH_SCALE.get(options.dashboard_size, 1.0)
    speed_size = int(62 * scale)
    text_size = int(27 * scale)
    small_size = int(21 * scale)
    base_dt = _timestamp_base(group)

    header = f"""[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Speed,Segoe UI,{speed_size},&H00FFFFFF,&H000000FF,&H00101820,&HB0182028,-1,0,0,0,100,100,0,0,3,1,0,1,42,42,42,1\nStyle: State,Segoe UI Semibold,{text_size},&H00FFFFFF,&H000000FF,&H00101820,&HB0182028,-1,0,0,0,100,100,0,0,3,1,0,2,42,42,42,1\nStyle: Detail,Segoe UI,{small_size},&H00E8EEF4,&H000000FF,&H00101820,&HB0182028,0,0,0,0,100,100,0,0,3,1,0,3,42,42,42,1\nStyle: Stamp,Segoe UI,{small_size},&H00E8EEF4,&H000000FF,&H00101820,&H80182028,0,0,0,0,100,100,0,0,3,1,0,9,34,34,28,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"""
    lines = [header]
    for i in range(steps):
        rel = i / hz
        rel_end = min(duration, (i + 1) / hz + 0.015)
        sample = _sample_at(samples, fps, start + rel)
        begin_s = ass_time(rel)
        end_s = ass_time(max(rel + 0.05, rel_end))
        speed = sample.speed_mph if options.units == "mph" else sample.speed_kph
        unit = "MPH" if options.units == "mph" else "km/h"
        state = assist_label(options.language, sample.autopilot_state)
        if sample.blinker_on_left:
            state += "   ◀"
        if sample.blinker_on_right:
            state += "   ▶"
        accel = sample.accelerator_pedal_position
        gmag = math.sqrt(
            sample.linear_acceleration_mps2_x ** 2 + sample.linear_acceleration_mps2_y ** 2 + sample.linear_acceleration_mps2_z ** 2
        ) / 9.80665
        gear_label = tr(options.language, "gear")
        steer_label = tr(options.language, "steering")
        accel_label = tr(options.language, "accelerator")
        brake_label = tr(options.language, "brake")
        details = f"{gear_label} {sample.gear}   •   {steer_label} {sample.steering_wheel_angle:+.1f}°   •   {accel_label} {accel:.2f}   •   {brake_label} {tr(options.language, 'on') if sample.brake_applied else tr(options.language, 'off')}"
        if options.show_gforce:
            details += f"   •   {gmag:.2f} g"
        if options.show_gps_text and (abs(sample.latitude_deg) > 1e-8 or abs(sample.longitude_deg) > 1e-8):
            details += f"   •   {sample.latitude_deg:.5f}, {sample.longitude_deg:.5f}"
        if options.show_dashboard:
            if options.dashboard_style == "Compact":
                compact = f"{speed:0.0f} {unit}   •   {gear_label} {sample.gear}   •   {state}   •   {steer_label} {sample.steering_wheel_angle:+.1f}°"
                lines.append(f"Dialogue: 0,{begin_s},{end_s},State,0,0,0,{ass_escape(compact)}\n")
            else:
                lines.append(f"Dialogue: 0,{begin_s},{end_s},Speed,0,0,0,{speed:0.0f} {unit}\n")
                lines.append(f"Dialogue: 0,{begin_s},{end_s},State,0,0,0,{ass_escape(state)}\n")
                lines.append(f"Dialogue: 0,{begin_s},{end_s},Detail,0,0,0,{ass_escape(details)}\n")
        if options.show_timestamp and base_dt:
            stamp = (base_dt + timedelta(seconds=start + rel)).strftime(options.timestamp_format)
            lines.append(f"Dialogue: 0,{begin_s},{end_s},Stamp,0,0,0,{ass_escape(stamp)}\n")
    path.write_text("".join(lines), encoding="utf-8-sig")


def render_route_video(
    samples: Sequence[TelemetrySample], fps: float, start: float, end: float, output: Path,
    size: Tuple[int, int] = (360, 240), route_fps: float = 10.0, language: str = "English",
) -> Optional[Path]:
    valid = [(s.longitude_deg, s.latitude_deg, s.autopilot_state) for s in samples if abs(s.latitude_deg) > 1e-8 or abs(s.longitude_deg) > 1e-8]
    if len(valid) < 2:
        return None
    w, h = size
    pad = 24
    xs = [p[0] for p in valid]; ys = [p[1] for p in valid]
    minx, maxx = min(xs), max(xs); miny, maxy = min(ys), max(ys)
    dx = max(maxx - minx, 1e-8); dy = max(maxy - miny, 1e-8)

    def pt(lon: float, lat: float) -> Tuple[int, int]:
        x = pad + int((lon - minx) / dx * (w - 2 * pad))
        y = h - pad - int((lat - miny) / dy * (h - 2 * pad))
        return x, y

    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), route_fps, (w, h))
    if not writer.isOpened():
        return None
    duration = max(0.1, end - start)
    count = max(1, int(math.ceil(duration * route_fps)))
    all_pts = [pt(lon, lat) for lon, lat, _ in valid]
    for frame_idx in range(count):
        t = start + frame_idx / route_fps
        sample_idx = min(len(samples) - 1, max(0, int(round(t * fps)))) if samples else 0
        img = __import__('numpy').zeros((h, w, 3), dtype='uint8')
        img[:] = (27, 31, 36)
        for gx in range(0, w, 60): cv2.line(img, (gx, 0), (gx, h), (38, 45, 53), 1)
        for gy in range(0, h, 60): cv2.line(img, (0, gy), (w, gy), (38, 45, 53), 1)
        for i in range(1, len(valid)):
            p1, p2 = all_pts[i-1], all_pts[i]
            color = (238, 143, 62) if valid[i][2] else (120, 126, 133)
            cv2.line(img, p1, p2, color, 3, cv2.LINE_AA)
        if samples:
            s = samples[sample_idx]
            if abs(s.latitude_deg) > 1e-8 or abs(s.longitude_deg) > 1e-8:
                cp = pt(s.longitude_deg, s.latitude_deg)
                cv2.circle(img, cp, 8, (255,255,255), -1, cv2.LINE_AA)
                cv2.circle(img, cp, 5, (238,143,62) if s.autopilot_state else (120,126,133), -1, cv2.LINE_AA)
        cv2.putText(img, tr(language, "local_gps_route"), (18, 25), cv2.FONT_HERSHEY_SIMPLEX, .48, (220,225,232), 1, cv2.LINE_AA)
        writer.write(img)
    writer.release()
    return output if output.exists() and output.stat().st_size else None


def _layout_inputs(group: ClipGroup, layout: str, active_camera: str) -> List[str]:
    if layout == "Single Camera":
        return [active_camera] if active_camera in group.cameras else [next(iter(group.cameras))]
    if layout == "Four Camera":
        cams = [c for c in ("front", "back", "left_repeater", "right_repeater") if c in group.cameras]
        return cams
    return [c for c in CAMERA_WALL_ORDER if c in group.cameras]


def _compose_layout_filter(cameras: List[str], layout: str) -> Tuple[List[str], str, Tuple[int, int]]:
    filters: List[str] = []
    if len(cameras) == 1 or layout == "Single Camera":
        filters.append("[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black[wall]")
        return filters, "wall", (1920, 1080)

    if layout == "Four Camera" and len(cameras) >= 4:
        for i in range(4):
            filters.append(f"[{i}:v]scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2:color=black[v{i}]")
        filters += ["[v0][v1]hstack=inputs=2[top]", "[v2][v3]hstack=inputs=2[bottom]", "[top][bottom]vstack=inputs=2[wall]"]
        return filters, "wall", (1920, 1080)

    n = min(6, len(cameras))
    for i in range(n):
        filters.append(f"[{i}:v]scale=640:540:force_original_aspect_ratio=decrease,pad=640:540:(ow-iw)/2:(oh-ih)/2:color=black[v{i}]")
    for i in range(n, 6):
        filters.append(f"color=c=black:s=640x540:d=86400[v{i}]")
    filters += [
        "[v0][v1][v2]hstack=inputs=3[row0]",
        "[v3][v4][v5]hstack=inputs=3[row1]",
        "[row0][row1]vstack=inputs=2[wall]",
    ]
    return filters, "wall", (1920, 1080)


def _add_blur_filters(filters: List[str], input_label: str, zones: Sequence[BlurZone], canvas: Tuple[int, int]) -> str:
    current = input_label
    cw, ch = canvas
    for idx, z in enumerate(zones):
        x = max(0, min(cw - 2, int(z.x * cw)))
        y = max(0, min(ch - 2, int(z.y * ch)))
        w = max(2, min(cw - x, int(z.w * cw)))
        h = max(2, min(ch - y, int(z.h * ch)))
        strength = max(2, min(40, int(z.strength)))
        filters.append(f"[{current}]split=2[b{idx}a][b{idx}b]")
        filters.append(f"[b{idx}b]crop={w}:{h}:{x}:{y},boxblur={strength}:{strength}[b{idx}blur]")
        out = f"b{idx}out"
        filters.append(f"[b{idx}a][b{idx}blur]overlay={x}:{y}[{out}]")
        current = out
    return current


def export_video(
    group: ClipGroup,
    samples: Sequence[TelemetrySample],
    telemetry_fps: float,
    output: Path,
    options: ExportOptions,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> str:
    cameras = _layout_inputs(group, options.layout, options.active_camera)
    if not cameras:
        raise RuntimeError("No camera files are available for this event.")
    start = max(0.0, options.start)
    default_end = len(samples) / max(telemetry_fps, 1.0) if samples else 60.0
    end = options.end if options.end > start else default_end
    duration = max(0.1, end - start)
    encoder_name, codec = resolve_encoder(options.encoder)
    ffmpeg = get_ffmpeg_exe()

    with tempfile.TemporaryDirectory(prefix="tts-export-") as td:
        temp = Path(td)
        ass_path = temp / "dashboard.ass"
        write_dashboard_ass(group, samples, telemetry_fps, ass_path, options)
        route_path: Optional[Path] = None
        if options.show_minimap:
            route_path = render_route_video(samples, telemetry_fps, start, end, temp / "route.mp4", language=options.language)

        cmd: List[str] = [ffmpeg, "-y"]
        for camera in cameras:
            cmd += ["-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(group.cameras[camera])]
        route_input_index = None
        if route_path:
            route_input_index = len(cameras)
            cmd += ["-stream_loop", "-1", "-i", str(route_path)]

        filters, wall_label, canvas = _compose_layout_filter(cameras, options.layout)
        current = _add_blur_filters(filters, wall_label, options.blur_zones, canvas)
        ass_arg = ffmpeg_escape_filter_path(ass_path)
        filters.append(f"[{current}]ass='{ass_arg}'[hud]")
        current = "hud"
        if route_input_index is not None:
            filters.append(f"[{route_input_index}:v]scale=360:240[map]")
            filters.append(f"[{current}][map]overlay=W-w-28:28:shortest=1[final]")
            current = "final"

        cmd += ["-filter_complex", ";".join(filters), "-map", f"[{current}]", "-an"]
        cmd += _codec_args(codec, options.quality)
        cmd += ["-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)]
        _run_ffmpeg(cmd, duration, progress_cb)
    return encoder_name


def _run_ffmpeg(cmd: List[str], duration: float, progress_cb: Optional[Callable[[float, str], None]]) -> None:
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", bufsize=1, creationflags=creationflags)
    tail: List[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        text = line.rstrip()
        tail.append(text)
        if len(tail) > 40:
            tail.pop(0)
        m = re.search(r"time=(\d+):(\d+):([0-9.]+)", text)
        if m and progress_cb:
            elapsed = int(m.group(1))*3600 + int(m.group(2))*60 + float(m.group(3))
            progress_cb(min(1.0, elapsed / max(duration, .1)), text)
    code = proc.wait()
    if code != 0:
        raise RuntimeError("FFmpeg export failed.\n\n" + "\n".join(tail[-18:]))
    if progress_cb:
        progress_cb(1.0, "Export complete")
