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

from tts_core import (
    CAMERA_WALL_ORDER,
    ClipGroup,
    TelemetrySample,
    ass_escape,
    ass_time,
    ffmpeg_escape_filter_path,
    get_ffmpeg_exe,
    probe_video,
)
from tts_locales import assist_label, tr
from tts_export import BlurZone, render_route_video


@dataclass
class ExportOptions:
    layout: str = "Single Camera"
    active_camera: str = "front"
    start: float = 0.0
    end: float = 0.0
    units: str = "mph"
    language: str = "English"
    encoder: str = "Auto"
    quality: str = "High"
    frame_mode: str = "Preserve Source"
    dashboard_size: str = "Medium"
    dashboard_style: str = "Full"
    dashboard_opacity: int = 78
    dashboard_position: str = "Bottom"
    show_dashboard: bool = True
    show_speed: bool = True
    show_state: bool = True
    show_gear: bool = True
    show_steering: bool = True
    show_accelerator: bool = True
    show_brake: bool = True
    show_blinkers: bool = True
    show_gforce: bool = False
    show_timestamp: bool = True
    timestamp_format: str = "%Y-%m-%d %I:%M:%S %p"
    show_minimap: bool = False
    show_gps_text: bool = False
    apply_image_adjustments: bool = True
    exposure: float = 0.0
    contrast: float = 1.0
    saturation: float = 1.0
    gamma: float = 1.0
    blur_zones: List[BlurZone] = field(default_factory=list)


QUALITY_BITRATES = {"Mobile": "4M", "Medium": "8M", "High": "14M", "Maximum": "25M"}
QUALITY_CRF = {"Mobile": 27, "Medium": 23, "High": 19, "Maximum": 16}
DASH_SCALE = {"Small": 0.78, "Medium": 1.0, "Large": 1.22, "X-Large": 1.5}
ENCODER_CODECS = {
    "NVIDIA NVENC": "h264_nvenc",
    "Intel QuickSync": "h264_qsv",
    "AMD AMF": "h264_amf",
    "Apple VideoToolbox": "h264_videotoolbox",
    "CPU x264": "libx264",
}
_ENCODER_SMOKE_CACHE: Dict[Tuple[str, str], bool] = {}


class FFmpegExportError(RuntimeError):
    def __init__(self, message: str, diagnostics: str = ""):
        super().__init__(message)
        self.diagnostics = diagnostics


def _creationflags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def _compiled_encoders() -> str:
    ffmpeg = get_ffmpeg_exe()
    try:
        return subprocess.check_output([ffmpeg, "-hide_banner", "-encoders"], text=True, errors="replace", stderr=subprocess.STDOUT, timeout=10, creationflags=_creationflags())
    except Exception:
        return ""


def _encoder_smoke_test(codec: str) -> bool:
    if codec == "libx264":
        return True
    ffmpeg = get_ffmpeg_exe()
    key = (ffmpeg, codec)
    cached = _ENCODER_SMOKE_CACHE.get(key)
    if cached is not None:
        return cached
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.08", "-frames:v", "1", "-an", "-c:v", codec, "-f", "null", "-"]
    try:
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8, creationflags=_creationflags())
        ok = result.returncode == 0
    except Exception:
        ok = False
    _ENCODER_SMOKE_CACHE[key] = ok
    return ok


def available_encoders() -> List[str]:
    compiled = _compiled_encoders()
    result: List[str] = []
    for display, codec in ENCODER_CODECS.items():
        if codec == "libx264":
            continue
        if codec in compiled and _encoder_smoke_test(codec):
            result.append(display)
    result.append("CPU x264")
    return result


def encoder_status() -> Dict[str, bool]:
    compiled = _compiled_encoders()
    return {display: (codec == "libx264" or (codec in compiled and _encoder_smoke_test(codec))) for display, codec in ENCODER_CODECS.items()}


def resolve_encoder(requested: str) -> Tuple[str, str]:
    usable = available_encoders()
    if requested == "Auto":
        chosen = usable[0]
    elif requested in usable:
        chosen = requested
    else:
        chosen = "CPU x264"
    return chosen, ENCODER_CODECS[chosen]


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
    return ["-c:v", "libx264", "-preset", "medium", "-crf", str(QUALITY_CRF[q])]


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


def _ass_alpha(opacity_percent: int) -> str:
    opacity = max(0, min(100, int(opacity_percent))) / 100.0
    return f"{int(round((1.0 - opacity) * 255.0)):02X}"


def _dialogue(start: str, end: str, style: str, text: str) -> str:
    # ASS requires Name and Effect fields even when both are empty.
    return f"Dialogue: 0,{start},{end},{style},,0,0,0,,{ass_escape(text)}\n"


def write_dashboard_ass(group: ClipGroup, samples: Sequence[TelemetrySample], fps: float, path: Path, options: ExportOptions) -> None:
    start = max(0.0, options.start)
    end = options.end if options.end > start else (len(samples) / max(fps, 1.0) if samples else start + 60.0)
    duration = max(0.1, end - start)
    hz = 10.0
    steps = max(1, int(math.ceil(duration * hz)))
    scale = DASH_SCALE.get(options.dashboard_size, 1.0)
    speed_size, state_size, detail_size, stamp_size = int(64 * scale), int(27 * scale), int(20 * scale), int(19 * scale)
    back = f"&H{_ass_alpha(options.dashboard_opacity)}182028"
    base_dt = _timestamp_base(group)
    bottom = options.dashboard_position.lower() != "top"
    speed_align, state_align, detail_align, stamp_align = ((1, 2, 3, 9) if bottom else (7, 8, 9, 3))
    margin = 38 if bottom else 34
    header = f"""[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Speed,Segoe UI,{speed_size},&H00FFFFFF,&H000000FF,&H00101820,{back},-1,0,0,0,100,100,0,0,3,1,0,{speed_align},42,42,{margin},1\nStyle: State,Segoe UI Semibold,{state_size},&H00FFFFFF,&H000000FF,&H00101820,{back},-1,0,0,0,100,100,0,0,3,1,0,{state_align},42,42,{margin},1\nStyle: Detail,Segoe UI,{detail_size},&H00E8EEF4,&H000000FF,&H00101820,{back},0,0,0,0,100,100,0,0,3,1,0,{detail_align},42,42,{margin},1\nStyle: Stamp,Segoe UI,{stamp_size},&H00E8EEF4,&H000000FF,&H00101820,&H80182028,0,0,0,0,100,100,0,0,3,1,0,{stamp_align},34,34,28,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"""
    lines = [header]
    for i in range(steps):
        rel = i / hz
        begin_s = ass_time(rel)
        end_s = ass_time(max(rel + 0.05, min(duration, (i + 1) / hz + 0.015)))
        sample = _sample_at(samples, fps, start + rel)
        gps_valid = abs(sample.latitude_deg) > 1e-8 or abs(sample.longitude_deg) > 1e-8
        if options.show_dashboard and samples:
            speed = sample.speed_mph if options.units == "mph" else sample.speed_kph
            unit = "MPH" if options.units == "mph" else "km/h"
            state = assist_label(options.language, sample.autopilot_state)
            if options.show_blinkers:
                if sample.blinker_on_left:
                    state += "   LEFT SIGNAL"
                if sample.blinker_on_right:
                    state += "   RIGHT SIGNAL"
            gear_label, steer_label = tr(options.language, "gear"), tr(options.language, "steering")
            accel_label, brake_label = tr(options.language, "accelerator"), tr(options.language, "brake")
            brake_value = tr(options.language, "on") if sample.brake_applied else tr(options.language, "off")
            gmag = math.sqrt(sample.linear_acceleration_mps2_x ** 2 + sample.linear_acceleration_mps2_y ** 2 + sample.linear_acceleration_mps2_z ** 2) / 9.80665
            details: List[str] = []
            if options.show_gear: details.append(f"{gear_label} {sample.gear}")
            if options.show_steering: details.append(f"{steer_label} {sample.steering_wheel_angle:+.1f} deg")
            if options.show_accelerator: details.append(f"{accel_label} {sample.accelerator_pedal_position:.2f}")
            if options.show_brake: details.append(f"{brake_label} {brake_value}")
            if options.show_gforce: details.append(f"{gmag:.2f} g")
            if options.show_gps_text and gps_valid: details.append(f"{sample.latitude_deg:.5f}, {sample.longitude_deg:.5f}")
            style = options.dashboard_style.lower()
            if style == "minimal":
                parts: List[str] = []
                if options.show_speed: parts.append(f"{speed:.0f} {unit}")
                if options.show_state: parts.append(state)
                if parts: lines.append(_dialogue(begin_s, end_s, "State", "   |   ".join(parts)))
            elif style == "compact":
                parts = []
                if options.show_speed: parts.append(f"{speed:.0f} {unit}")
                if options.show_gear: parts.append(f"{gear_label} {sample.gear}")
                if options.show_state: parts.append(state)
                parts.extend(details)
                if parts: lines.append(_dialogue(begin_s, end_s, "State", "   |   ".join(parts)))
            else:
                if options.show_speed: lines.append(_dialogue(begin_s, end_s, "Speed", f"{speed:.0f} {unit}"))
                if options.show_state: lines.append(_dialogue(begin_s, end_s, "State", state))
                if details: lines.append(_dialogue(begin_s, end_s, "Detail", "   |   ".join(details)))
        if options.show_timestamp and base_dt:
            lines.append(_dialogue(begin_s, end_s, "Stamp", (base_dt + timedelta(seconds=start + rel)).strftime(options.timestamp_format)))
    path.write_text("".join(lines), encoding="utf-8-sig")


def _layout_inputs(group: ClipGroup, layout: str, active_camera: str) -> List[str]:
    if layout == "Single Camera":
        return [active_camera] if active_camera in group.cameras else [next(iter(group.cameras))]
    if layout == "Four Camera":
        return [c for c in ("front", "back", "left_repeater", "right_repeater") if c in group.cameras]
    return [c for c in CAMERA_WALL_ORDER if c in group.cameras]


def _image_filter(options: ExportOptions) -> str:
    if not options.apply_image_adjustments:
        return ""
    brightness = max(-1.0, min(1.0, float(options.exposure) * 0.12))
    contrast = max(0.25, min(3.0, float(options.contrast)))
    saturation = max(0.0, min(3.0, float(options.saturation)))
    gamma = max(0.1, min(4.0, float(options.gamma)))
    if abs(brightness) < 1e-4 and abs(contrast - 1.0) < 1e-4 and abs(saturation - 1.0) < 1e-4 and abs(gamma - 1.0) < 1e-4:
        return ""
    return f"eq=brightness={brightness:.4f}:contrast={contrast:.4f}:saturation={saturation:.4f}:gamma={gamma:.4f}"


def _compose_layout_filter(group: ClipGroup, cameras: List[str], options: ExportOptions) -> Tuple[List[str], str, Tuple[int, int]]:
    filters: List[str] = []
    image_filter = _image_filter(options)
    sources: List[str] = []
    for i in range(len(cameras)):
        if image_filter:
            filters.append(f"[{i}:v]{image_filter}[src{i}]")
            sources.append(f"[src{i}]")
        else:
            sources.append(f"[{i}:v]")
    if len(cameras) == 1 or options.layout == "Single Camera":
        info = probe_video(group.cameras[cameras[0]])
        sw, sh = max(2, info.width or 1280), max(2, info.height or 960)
        if options.frame_mode == "Fill 16:9":
            filters.append(f"{sources[0]}scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080[wall]")
            return filters, "wall", (1920, 1080)
        if options.frame_mode == "Fit 16:9":
            filters.append(f"{sources[0]}scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black[wall]")
            return filters, "wall", (1920, 1080)
        filters.append(f"{sources[0]}null[wall]")
        return filters, "wall", (sw, sh)
    if options.layout == "Four Camera" and len(cameras) >= 4:
        for i in range(4): filters.append(f"{sources[i]}scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2:color=black[v{i}]")
        filters.extend(["[v0][v1]hstack=inputs=2[top]", "[v2][v3]hstack=inputs=2[bottom]", "[top][bottom]vstack=inputs=2[wall]"])
        return filters, "wall", (1920, 1080)
    n = min(6, len(cameras))
    for i in range(n): filters.append(f"{sources[i]}scale=640:540:force_original_aspect_ratio=decrease,pad=640:540:(ow-iw)/2:(oh-ih)/2:color=black[v{i}]")
    for i in range(n, 6): filters.append(f"color=c=black:s=640x540:d=86400[v{i}]")
    filters.extend(["[v0][v1][v2]hstack=inputs=3[row0]", "[v3][v4][v5]hstack=inputs=3[row1]", "[row0][row1]vstack=inputs=2[wall]"])
    return filters, "wall", (1920, 1080)


def _add_blur_filters(filters: List[str], input_label: str, zones: Sequence[BlurZone], canvas: Tuple[int, int]) -> str:
    current, cw, ch = input_label, canvas[0], canvas[1]
    for idx, zone in enumerate(zones):
        x, y = max(0, min(cw - 2, int(zone.x * cw))), max(0, min(ch - 2, int(zone.y * ch)))
        w, h = max(2, min(cw - x, int(zone.w * cw))), max(2, min(ch - y, int(zone.h * ch)))
        strength = max(2, min(40, int(zone.strength)))
        filters.append(f"[{current}]split=2[b{idx}a][b{idx}b]")
        filters.append(f"[b{idx}b]crop={w}:{h}:{x}:{y},boxblur={strength}:{strength}[b{idx}blur]")
        out = f"b{idx}out"
        filters.append(f"[b{idx}a][b{idx}blur]overlay={x}:{y}[{out}]")
        current = out
    return current


def _build_command(ffmpeg: str, group: ClipGroup, cameras: List[str], start: float, duration: float, route_path: Optional[Path], ass_path: Path, output: Path, options: ExportOptions, codec: str) -> List[str]:
    cmd: List[str] = [ffmpeg, "-y"]
    for camera in cameras: cmd.extend(["-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(group.cameras[camera])])
    route_input_index: Optional[int] = None
    if route_path:
        route_input_index = len(cameras)
        cmd.extend(["-stream_loop", "-1", "-i", str(route_path)])
    filters, wall_label, canvas = _compose_layout_filter(group, cameras, options)
    current = _add_blur_filters(filters, wall_label, options.blur_zones, canvas)
    filters.append(f"[{current}]ass='{ffmpeg_escape_filter_path(ass_path)}'[hud]")
    current = "hud"
    if route_input_index is not None:
        map_w = 360 if canvas[0] >= 1280 else max(220, int(canvas[0] * 0.24))
        map_h = 240 if canvas[1] >= 720 else max(150, int(canvas[1] * 0.24))
        filters.append(f"[{route_input_index}:v]scale={map_w}:{map_h}[map]")
        filters.append(f"[{current}][map]overlay=W-w-28:28:shortest=1[final]")
        current = "final"
    cmd.extend(["-filter_complex", ";".join(filters), "-map", f"[{current}]", "-an"])
    cmd.extend(_codec_args(codec, options.quality))
    cmd.extend(["-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)])
    return cmd


def _run_ffmpeg(cmd: List[str], duration: float, progress_cb: Optional[Callable[[float, str], None]]) -> None:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", bufsize=1, creationflags=_creationflags())
    tail: List[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        text = line.rstrip(); tail.append(text)
        if len(tail) > 60: tail.pop(0)
        match = re.search(r"time=(\d+):(\d+):([0-9.]+)", text)
        if match and progress_cb:
            elapsed = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))
            progress_cb(min(1.0, elapsed / max(duration, 0.1)), "Encoding video")
    if proc.wait() != 0:
        raise FFmpegExportError("Video export could not be completed.", "\n".join(tail[-24:]))
    if progress_cb: progress_cb(1.0, "Export complete")


def export_video(group: ClipGroup, samples: Sequence[TelemetrySample], telemetry_fps: float, output: Path, options: ExportOptions, progress_cb: Optional[Callable[[float, str], None]] = None) -> str:
    cameras = _layout_inputs(group, options.layout, options.active_camera)
    if not cameras: raise RuntimeError("No camera files are available for this event.")
    start = max(0.0, options.start)
    info = probe_video(group.cameras[cameras[0]])
    default_end = info.duration or (len(samples) / max(telemetry_fps, 1.0) if samples else 60.0)
    end = options.end if options.end > start else default_end
    duration = max(0.1, end - start)
    encoder_name, codec = resolve_encoder(options.encoder)
    ffmpeg = get_ffmpeg_exe()
    with tempfile.TemporaryDirectory(prefix="cammetry-export-") as td:
        temp = Path(td)
        ass_path = temp / "dashboard.ass"
        write_dashboard_ass(group, samples, telemetry_fps, ass_path, options)
        route_path: Optional[Path] = None
        if options.show_minimap:
            route_path = render_route_video(samples, telemetry_fps, start, end, temp / "route.mp4", language=options.language)
        cmd = _build_command(ffmpeg, group, cameras, start, duration, route_path, ass_path, output, options, codec)
        try:
            _run_ffmpeg(cmd, duration, progress_cb)
            return encoder_name
        except FFmpegExportError as first_error:
            if codec == "libx264":
                raise RuntimeError("Cammetry could not export this clip. Open Help > Diagnostics for technical details.\n\n" + first_error.diagnostics[-1800:]) from first_error
            try: output.unlink(missing_ok=True)
            except Exception: pass
            if progress_cb: progress_cb(0.0, f"{encoder_name} was unavailable. Retrying with CPU x264.")
            cpu_cmd = _build_command(ffmpeg, group, cameras, start, duration, route_path, ass_path, output, options, "libx264")
            try:
                _run_ffmpeg(cpu_cmd, duration, progress_cb)
                return f"CPU x264 (fallback from {encoder_name})"
            except FFmpegExportError as cpu_error:
                raise RuntimeError("Cammetry could not export this clip with either hardware or CPU encoding. Open Help > Diagnostics for technical details.\n\n" + cpu_error.diagnostics[-1800:]) from cpu_error
