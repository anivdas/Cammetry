#!/usr/bin/env python3
"""Cammetry

Free and open-source desktop utility for TeslaCam clips with embedded SEI telemetry.
Reads MP4 metadata directly, exports CSV, and renders a telemetry HUD with FFmpeg.

No Tesla account or credentials are required. Video and telemetry processing are local by default.
"""

from __future__ import annotations

import csv
import json
import math
import os
import queue
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_NAME = "Cammetry"
APP_VERSION = "0.5.0"

CAMERA_LABELS = {
    "front": "Front",
    "back": "Rear",
    "left_repeater": "Left Repeater",
    "right_repeater": "Right Repeater",
    "left_pillar": "Left Pillar",
    "right_pillar": "Right Pillar",
}
CAMERA_ORDER = ("front", "back", "left_repeater", "right_repeater", "left_pillar", "right_pillar")
CAMERA_WALL_ORDER = ("left_pillar", "front", "right_pillar", "left_repeater", "back", "right_repeater")
CLIP_RE = re.compile(
    r"(?P<stamp>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})-(?P<camera>front|back|left_repeater|right_repeater|left_pillar|right_pillar)\.mp4$",
    re.IGNORECASE,
)

GEAR_NAMES = {0: "P", 1: "D", 2: "R", 3: "N"}
AUTOPILOT_NAMES = {0: "Manual", 1: "FSD / Self-Driving", 2: "Autosteer", 3: "TACC"}


@dataclass
class TelemetrySample:
    version: int = 0
    gear_state: int = 0
    frame_seq_no: int = 0
    vehicle_speed_mps: float = 0.0
    accelerator_pedal_position: float = 0.0
    steering_wheel_angle: float = 0.0
    blinker_on_left: bool = False
    blinker_on_right: bool = False
    brake_applied: bool = False
    autopilot_state: int = 0
    latitude_deg: float = 0.0
    longitude_deg: float = 0.0
    heading_deg: float = 0.0
    linear_acceleration_mps2_x: float = 0.0
    linear_acceleration_mps2_y: float = 0.0
    linear_acceleration_mps2_z: float = 0.0

    @property
    def speed_mph(self) -> float:
        return self.vehicle_speed_mps * 2.2369362921

    @property
    def speed_kph(self) -> float:
        return self.vehicle_speed_mps * 3.6

    @property
    def gear(self) -> str:
        return GEAR_NAMES.get(self.gear_state, str(self.gear_state))

    @property
    def autopilot(self) -> str:
        return AUTOPILOT_NAMES.get(self.autopilot_state, f"State {self.autopilot_state}")


@dataclass
class ClipGroup:
    timestamp: str
    folder: Path
    cameras: Dict[str, Path]
    source_kind: str = "Other"
    event_info: Optional[dict] = None

    def display_time(self) -> str:
        try:
            date_part, time_part = self.timestamp.split("_")
            return f"{date_part} {time_part.replace('-', ':')}"
        except Exception:
            return self.timestamp


@dataclass
class VideoInfo:
    fps: float = 36.0
    duration: float = 0.0
    frames: int = 0
    width: int = 0
    height: int = 0
    codec: str = "unknown"

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}" if self.width and self.height else "unknown"


FIELD_MAP = {
    1: ("version", "varint"), 2: ("gear_state", "varint"), 3: ("frame_seq_no", "varint"),
    4: ("vehicle_speed_mps", "float"), 5: ("accelerator_pedal_position", "float"),
    6: ("steering_wheel_angle", "float"), 7: ("blinker_on_left", "bool"),
    8: ("blinker_on_right", "bool"), 9: ("brake_applied", "bool"), 10: ("autopilot_state", "varint"),
    11: ("latitude_deg", "double"), 12: ("longitude_deg", "double"), 13: ("heading_deg", "double"),
    14: ("linear_acceleration_mps2_x", "double"), 15: ("linear_acceleration_mps2_y", "double"),
    16: ("linear_acceleration_mps2_z", "double"),
}


def _read_varint(data: bytes, pos: int) -> Tuple[int, int]:
    value = 0; shift = 0
    while pos < len(data) and shift <= 63:
        b = data[pos]; pos += 1; value |= (b & 0x7F) << shift
        if not (b & 0x80): return value, pos
        shift += 7
    raise ValueError("Malformed varint")


def decode_sei_metadata(data: bytes) -> TelemetrySample:
    sample = TelemetrySample(); pos = 0
    while pos < len(data):
        tag, pos = _read_varint(data, pos); field_no = tag >> 3; wire = tag & 0x07; spec = FIELD_MAP.get(field_no)
        if wire == 0:
            value, pos = _read_varint(data, pos)
            if spec: setattr(sample, spec[0], bool(value) if spec[1] == "bool" else int(value))
        elif wire == 1:
            if pos + 8 > len(data): raise ValueError("Truncated 64-bit field")
            raw = data[pos:pos+8]; pos += 8
            if spec and spec[1] == "double": setattr(sample, spec[0], struct.unpack("<d", raw)[0])
        elif wire == 2:
            size, pos = _read_varint(data, pos); pos += size
            if pos > len(data): raise ValueError("Truncated length-delimited field")
        elif wire == 5:
            if pos + 4 > len(data): raise ValueError("Truncated 32-bit field")
            raw = data[pos:pos+4]; pos += 4
            if spec and spec[1] == "float": setattr(sample, spec[0], struct.unpack("<f", raw)[0])
        else: raise ValueError(f"Unsupported protobuf wire type {wire}")
    return sample


def _iter_mp4_atoms(fp) -> Iterator[Tuple[bytes, int, int]]:
    fp.seek(0, os.SEEK_END); file_size = fp.tell(); fp.seek(0)
    while fp.tell() + 8 <= file_size:
        start = fp.tell(); header = fp.read(8); size32, atom_type = struct.unpack(">I4s", header); header_size = 8
        if size32 == 1:
            ext = fp.read(8)
            if len(ext) != 8: break
            atom_size = struct.unpack(">Q", ext)[0]; header_size = 16
        elif size32 == 0: atom_size = file_size - start
        else: atom_size = size32
        if atom_size < header_size or start + atom_size > file_size: break
        yield atom_type, start + header_size, atom_size - header_size
        fp.seek(start + atom_size)


def _strip_epb(data: bytes) -> bytes:
    out = bytearray(); zeros = 0
    for b in data:
        if zeros >= 2 and b == 0x03: zeros = 0; continue
        out.append(b); zeros = zeros + 1 if b == 0 else 0
    return bytes(out)


def _tesla_payload_from_sei_nal(nal: bytes) -> Optional[bytes]:
    if len(nal) < 6: return None
    i = 3
    while i < len(nal) - 1 and nal[i] == 0x42: i += 1
    if i < len(nal) - 1 and nal[i] == 0x69: return _strip_epb(nal[i + 1:-1])
    return None


def iter_telemetry(path: Path) -> Iterator[TelemetrySample]:
    with path.open("rb") as fp:
        mdats = [(off, size) for typ, off, size in _iter_mp4_atoms(fp) if typ == b"mdat"]
        if not mdats: raise RuntimeError("No MP4 mdat atom found")
        for offset, size in mdats:
            fp.seek(offset); end = offset + size
            while fp.tell() + 4 <= end:
                hdr = fp.read(4)
                if len(hdr) != 4: break
                nal_size = struct.unpack(">I", hdr)[0]
                if nal_size <= 0 or fp.tell() + nal_size > end: break
                nal = fp.read(nal_size)
                if len(nal) < 2 or (nal[0] & 0x1F) != 6 or nal[1] != 5: continue
                payload = _tesla_payload_from_sei_nal(nal)
                if not payload: continue
                try: yield decode_sei_metadata(payload)
                except (ValueError, struct.error): continue


def load_telemetry(path: Path, max_samples: Optional[int] = None) -> List[TelemetrySample]:
    samples: List[TelemetrySample] = []
    for sample in iter_telemetry(path):
        samples.append(sample)
        if max_samples is not None and len(samples) >= max_samples: break
    return samples


def _source_kind_for_path(path: Path) -> str:
    parts = {part.lower() for part in path.parts}
    if "sentryclips" in parts: return "Sentry"
    if "savedclips" in parts: return "Saved"
    if "recentclips" in parts: return "Recent"
    return "Other"


def _event_info_for_folder(folder: Path) -> Optional[dict]:
    for name in ("event.json", "Event.json"):
        candidate = folder / name
        if candidate.exists():
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8", errors="replace"))
                if isinstance(payload, dict): return payload
            except Exception: return None
    return None


def discover_clips(root: Path) -> List[ClipGroup]:
    grouped: Dict[Tuple[Path, str], Dict[str, Path]] = {}
    for path in root.rglob("*.mp4"):
        m = CLIP_RE.match(path.name)
        if not m: continue
        grouped.setdefault((path.parent, m.group("stamp")), {})[m.group("camera").lower()] = path
    event_cache: Dict[Path, Optional[dict]] = {}; groups: List[ClipGroup] = []
    for (folder, stamp), cams in grouped.items():
        if folder not in event_cache: event_cache[folder] = _event_info_for_folder(folder)
        groups.append(ClipGroup(stamp, folder, cams, source_kind=_source_kind_for_path(folder), event_info=event_cache[folder]))
    groups.sort(key=lambda g: (g.timestamp, str(g.folder)), reverse=True)
    return groups


def choose_telemetry_source(group: ClipGroup) -> Optional[Path]:
    for cam in CAMERA_ORDER:
        if cam in group.cameras: return group.cameras[cam]
    return next(iter(group.cameras.values()), None)


def _runtime_roots() -> list[Path]:
    roots: list[Path] = []; bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root: roots.append(Path(bundle_root))
    if getattr(sys, "frozen", False): roots.append(Path(sys.executable).resolve().parent)
    roots.append(Path(__file__).resolve().parent)
    seen: set[str] = set(); unique: list[Path] = []
    for root in roots:
        key = str(root).lower() if os.name == "nt" else str(root)
        if key not in seen: seen.add(key); unique.append(root)
    return unique


def get_ffmpeg_exe() -> str:
    env = os.environ.get("FFMPEG_BINARY")
    if env and Path(env).exists(): return env
    ffmpeg_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    for root in _runtime_roots():
        for candidate in (root / "ffmpeg_bin" / ffmpeg_name, root / ffmpeg_name):
            if candidate.exists(): return str(candidate)
    found = shutil.which("ffmpeg")
    if found: return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc: raise RuntimeError("FFmpeg was not found. Reinstall Cammetry or provide FFMPEG_BINARY.") from exc


def get_ffprobe_exe(ffmpeg: str) -> Optional[str]:
    p = Path(ffmpeg); name = "ffprobe.exe" if os.name == "nt" else "ffprobe"; sibling = p.with_name(name)
    if sibling.exists(): return str(sibling)
    return shutil.which("ffprobe")


def _parse_rate(value: str) -> float:
    value = (value or "").strip()
    if not value: return 0.0
    try:
        if "/" in value:
            a, b = value.split("/", 1); bval = float(b); return float(a) / bval if bval else 0.0
        return float(value)
    except Exception: return 0.0


def _probe_video_with_ffmpeg(path: Path, ffmpeg: str) -> VideoInfo:
    cmd = [ffmpeg, "-hide_banner", "-i", str(path), "-map", "0:v:0", "-c:v", "copy", "-an", "-f", "null", "-"]
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try: out = subprocess.check_output(cmd, text=True, errors="replace", stderr=subprocess.STDOUT, timeout=30, creationflags=creationflags)
    except subprocess.CalledProcessError as exc: out = exc.output or ""
    except Exception: return VideoInfo()
    duration = 0.0; m = re.search(r"Duration:\s*(\d+):(\d+):([0-9.]+)", out)
    if m: duration = int(m.group(1))*3600 + int(m.group(2))*60 + float(m.group(3))
    codec = "unknown"; width = height = 0; fps = 0.0
    for line in out.splitlines():
        if "Video:" not in line: continue
        cm = re.search(r"Video:\s*([^,\s]+)", line); rm = re.search(r"\b(\d{2,5})x(\d{2,5})\b", line); fm = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*fps\b", line)
        if cm: codec = cm.group(1)
        if rm: width, height = int(rm.group(1)), int(rm.group(2))
        if fm:
            candidate = float(fm.group(1))
            if 1 <= candidate <= 240: fps = candidate
        if width and height and fps: break
    frame_matches = re.findall(r"frame=\s*(\d+)", out); frames = int(frame_matches[-1]) if frame_matches else 0
    if not fps and duration > 0 and frames > 0: fps = frames / duration
    if not fps: fps = 36.0
    return VideoInfo(fps=fps, duration=duration, frames=frames, width=width, height=height, codec=codec)


def probe_video(path: Path) -> VideoInfo:
    ffmpeg = get_ffmpeg_exe(); ffprobe = get_ffprobe_exe(ffmpeg)
    if ffprobe:
        cmd = [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,width,height,avg_frame_rate,r_frame_rate,nb_frames,duration", "-of", "json", str(path)]
        try:
            out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, timeout=15); payload = json.loads(out); stream = (payload.get("streams") or [{}])[0]
            avg = _parse_rate(str(stream.get("avg_frame_rate", ""))); raw = _parse_rate(str(stream.get("r_frame_rate", "")))
            fps = avg if 1 <= avg <= 240 else raw if 1 <= raw <= 240 else 0.0
            try: duration = float(stream.get("duration") or 0.0)
            except Exception: duration = 0.0
            try: frames = int(stream.get("nb_frames") or 0)
            except Exception: frames = 0
            if fps: return VideoInfo(fps=fps, duration=duration, frames=frames, width=int(stream.get("width") or 0), height=int(stream.get("height") or 0), codec=str(stream.get("codec_name") or "unknown"))
        except Exception: pass
    return _probe_video_with_ffmpeg(path, ffmpeg)


def probe_fps(path: Path) -> float: return probe_video(path).fps

def ass_escape(text: str) -> str: return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")

def ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds); h = int(seconds // 3600); m = int((seconds % 3600) // 60); s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def build_hud_text(s: TelemetrySample, units: str, show_speed: bool, show_ap: bool, show_steering: bool, show_pedals: bool, show_gps: bool, show_gforce: bool) -> str:
    chunks: List[str] = []
    if show_speed: chunks.append(f"{s.speed_mph:5.1f} MPH" if units == "mph" else f"{s.speed_kph:5.1f} km/h")
    chunks.append(f"Gear {s.gear}")
    if show_ap: chunks.append(s.autopilot)
    if show_steering: chunks.append(f"Steer {s.steering_wheel_angle:+.1f} deg")
    if show_pedals:
        chunks.append(f"Accel {s.accelerator_pedal_position:.2f}"); chunks.append("BRAKE" if s.brake_applied else "Brake off")
    if s.blinker_on_left: chunks.append("LEFT SIGNAL")
    if s.blinker_on_right: chunks.append("RIGHT SIGNAL")
    if show_gps and (abs(s.latitude_deg) > 1e-8 or abs(s.longitude_deg) > 1e-8):
        chunks.append(f"GPS {s.latitude_deg:.5f}, {s.longitude_deg:.5f}"); chunks.append(f"Head {s.heading_deg:.0f} deg")
    if show_gforce:
        mag = math.sqrt(s.linear_acceleration_mps2_x ** 2 + s.linear_acceleration_mps2_y ** 2 + s.linear_acceleration_mps2_z ** 2) / 9.80665; chunks.append(f"|a| {mag:.2f} g")
    return "   |   ".join(chunks)


def write_ass(samples: List[TelemetrySample], fps: float, path: Path, units: str, options: Dict[str, bool], max_overlay_hz: float = 10.0) -> None:
    if not samples: raise RuntimeError("No telemetry samples to render")
    fps = fps if fps > 0 else 36.0; stride = max(1, round(fps / max_overlay_hz)); selected = list(range(0, len(samples), stride))
    if selected[-1] != len(samples) - 1: selected.append(len(samples) - 1)
    header = """[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: HUD,Segoe UI,38,&H00FFFFFF,&H000000FF,&H00101010,&H90000000,-1,0,0,0,100,100,0,0,3,1,0,2,30,30,36,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"""
    lines = [header]
    for idx_pos, i in enumerate(selected):
        j = selected[idx_pos + 1] if idx_pos + 1 < len(selected) else i + stride; start = i / fps; end = max(start + 0.05, j / fps)
        text = build_hud_text(samples[i], units, options.get("speed", True), options.get("autopilot", True), options.get("steering", True), options.get("pedals", True), options.get("gps", False), options.get("gforce", False))
        lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},HUD,,0,0,0,,{ass_escape(text)}\n")
    path.write_text("".join(lines), encoding="utf-8-sig")


def ffmpeg_escape_filter_path(path: Path) -> str:
    p = str(path.resolve()).replace("\\", "/"); return p.replace(":", r"\:").replace("'", r"\'")


def export_single_camera(source: Path, output: Path, ass_path: Path, encoder: str, progress_cb) -> None:
    ffmpeg = get_ffmpeg_exe(); ass_arg = ffmpeg_escape_filter_path(ass_path); codec_args = ["-c:v", encoder]
    if encoder == "libx264": codec_args += ["-preset", "medium", "-crf", "18"]
    elif encoder == "h264_nvenc": codec_args += ["-preset", "p5", "-cq", "19", "-b:v", "0"]
    cmd = [ffmpeg, "-y", "-i", str(source), "-vf", f"ass='{ass_arg}'", *codec_args, "-c:a", "copy", "-movflags", "+faststart", str(output)]
    run_ffmpeg(cmd, progress_cb)


def export_mosaic(group: ClipGroup, output: Path, ass_path: Path, encoder: str, progress_cb) -> None:
    missing = [cam for cam in CAMERA_ORDER if cam not in group.cameras]
    if missing: raise RuntimeError("4-camera mosaic requires Front, Rear, Left Repeater, and Right Repeater clips")
    ffmpeg = get_ffmpeg_exe(); cmd: List[str] = [ffmpeg, "-y"]
    for cam in CAMERA_ORDER: cmd += ["-i", str(group.cameras[cam])]
    ass_arg = ffmpeg_escape_filter_path(ass_path)
    fc = "[0:v]scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2[v0];[1:v]scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2[v1];[2:v]scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2[v2];[3:v]scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2[v3];[v0][v1]hstack=inputs=2[top];[v2][v3]hstack=inputs=2[bottom];" + f"[top][bottom]vstack=inputs=2,ass='{ass_arg}'[outv]"
    codec_args = ["-c:v", encoder]
    if encoder == "libx264": codec_args += ["-preset", "medium", "-crf", "18"]
    elif encoder == "h264_nvenc": codec_args += ["-preset", "p5", "-cq", "19", "-b:v", "0"]
    cmd += ["-filter_complex", fc, "-map", "[outv]", "-map", "0:a?", *codec_args, "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(output)]
    run_ffmpeg(cmd, progress_cb)


def run_ffmpeg(cmd: List[str], progress_cb) -> None:
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", bufsize=1, creationflags=creationflags); tail: List[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        tail.append(line.rstrip())
        if len(tail) > 30: tail.pop(0)
        if "frame=" in line: progress_cb(line.strip())
    code = proc.wait()
    if code != 0: raise RuntimeError("FFmpeg export failed.\n\n" + "\n".join(tail[-15:]))


def detect_nvenc() -> bool:
    try:
        ffmpeg = get_ffmpeg_exe(); creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        out = subprocess.check_output([ffmpeg, "-hide_banner", "-encoders"], text=True, errors="replace", stderr=subprocess.STDOUT, timeout=10, creationflags=creationflags)
        return "h264_nvenc" in out
    except Exception: return False


def export_csv(samples: List[TelemetrySample], path: Path, fps: float) -> None:
    cols = [f.name for f in fields(TelemetrySample)]; extra = ["time_seconds", "speed_mph", "speed_kph", "gear", "autopilot"]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=extra + cols); w.writeheader()
        for i, s in enumerate(samples):
            row = {name: getattr(s, name) for name in cols}; row.update({"time_seconds": i / fps, "speed_mph": s.speed_mph, "speed_kph": s.speed_kph, "gear": s.gear, "autopilot": s.autopilot}); w.writerow(row)


def detect_teslacam_roots() -> List[Path]:
    candidates: List[Path] = []
    if os.name == "nt":
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = Path(f"{letter}:\\")
            try:
                if drive.exists(): candidates.extend((drive / "TeslaCam", drive))
            except OSError: continue
    else:
        for base in [Path("/Volumes"), Path("/media"), Path("/run/media"), Path("/mnt")]:
            if not base.exists(): continue
            try:
                for child in list(base.iterdir()):
                    if child.is_dir():
                        candidates.extend((child / "TeslaCam", child))
                        try:
                            for grand in child.iterdir():
                                if grand.is_dir(): candidates.append(grand / "TeslaCam")
                        except OSError: pass
            except OSError: pass
    found: List[Path] = []; seen = set()
    for candidate in candidates:
        try: p = candidate.resolve()
        except OSError: p = candidate
        key = str(p).lower() if os.name == "nt" else str(p)
        if key in seen or not p.exists() or not p.is_dir(): continue
        if any((p / name).is_dir() for name in ("RecentClips", "SavedClips", "SentryClips")):
            seen.add(key); found.append(p)
    return found
