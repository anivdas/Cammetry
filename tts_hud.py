from __future__ import annotations

import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Sequence

from tts_core import ClipGroup, TelemetrySample, ass_escape, ass_time
from tts_locales import assist_label


# ASS colors are BGR. These are Cammetry's own UI colors, not copied artwork.
BLUE = "&H00F6823B"      # RGB #3b82f6
WHITE = "&H00FFFFFF"
MUTED = "&H00B5A79A"     # RGB #9aa7b5
AMBER = "&H004BB8F2"     # RGB #f2b84b
RED = "&H005C5CFF"       # RGB #ff5c5c
DARK = "&H0016110D"      # RGB #0d1116
BORDER = "&H0041362D"    # RGB #2d3641

DASH_SCALE = {"Small": 0.78, "Medium": 1.0, "Large": 1.22, "X-Large": 1.5}


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


def _alpha(opacity_percent: int) -> str:
    opacity = max(0, min(100, int(opacity_percent))) / 100.0
    return f"{int(round((1.0 - opacity) * 255.0)):02X}"


def _raw_dialogue(start: str, end: str, style: str, text: str, layer: int = 10) -> str:
    return f"Dialogue: {layer},{start},{end},{style},,0,0,0,,{text}\n"


def _text(start: str, end: str, style: str, x: int, y: int, value: str, *,
          align: int = 5, size: Optional[int] = None, color: Optional[str] = None,
          bold: bool = False, layer: int = 10) -> str:
    tags = [f"\\an{align}", f"\\pos({x},{y})"]
    if size:
        tags.append(f"\\fs{size}")
    if color:
        tags.append(f"\\1c{color}")
    if bold:
        tags.append("\\b1")
    return _raw_dialogue(start, end, style, "{" + "".join(tags) + "}" + ass_escape(value), layer)


def _panel(start: str, end: str, x1: int, y1: int, x2: int, y2: int, opacity: int) -> str:
    # One fixed panel per telemetry interval. Explicit positioning prevents libass
    # subtitle collision logic from moving the HUD vertically between samples.
    fill_alpha = _alpha(opacity)
    path = f"m {x1} {y1} l {x2} {y1} l {x2} {y2} l {x1} {y2}"
    tags = (
        "{\\an7\\pos(0,0)\\p1"
        f"\\1c{DARK}\\1a&H{fill_alpha}&\\3c{BORDER}\\3a&H20&\\bord2\\shad0}"
    )
    return _raw_dialogue(start, end, "HUD", tags + path + "{\\p0}", layer=1)


def _gear_name(gear: object) -> str:
    value = str(gear or "-").strip().upper()
    return {"D": "DRIVE", "R": "REVERSE", "N": "NEUTRAL", "P": "PARK"}.get(value, value or "-")


def _bounds(style_name: str, position: str) -> tuple[int, int, int, int]:
    style = style_name.lower()
    if style == "minimal":
        x1, x2, height = 545, 1375, 104
    elif style == "compact":
        x1, x2, height = 360, 1560, 126
    else:
        x1, x2, height = 250, 1670, 164
    if position.lower() == "top":
        y1 = 34
        y2 = y1 + height
    else:
        y2 = 1055
        y1 = y2 - height
    return x1, y1, x2, y2


def write_dashboard_ass(group: ClipGroup, samples: Sequence[TelemetrySample], fps: float,
                        path: Path, options) -> None:
    """Generate Cammetry's stable instrument-cluster HUD.

    It intentionally uses fixed positions and non-overlapping 100 ms intervals.
    The previous beta allowed adjacent subtitle events to overlap slightly; libass
    could treat those as collisions and nudge them up/down, producing visible bounce.
    """
    start = max(0.0, float(options.start))
    end = float(options.end) if float(options.end) > start else (
        len(samples) / max(float(fps), 1.0) if samples else start + 60.0
    )
    duration = max(0.1, end - start)
    hz = 10.0
    steps = max(1, int(math.ceil(duration * hz)))
    scale = DASH_SCALE.get(str(options.dashboard_size), 1.0)
    style_name = str(options.dashboard_style or "Full")
    x1, y1, x2, y2 = _bounds(style_name, str(options.dashboard_position or "Bottom"))
    full = style_name.lower() == "full"
    minimal = style_name.lower() == "minimal"
    main_y = y1 + (56 if full else (y2 - y1) // 2)
    detail_y = y2 - 32
    base_dt = _timestamp_base(group)

    speed_size = max(30, int(58 * scale))
    unit_size = max(12, int(17 * scale))
    state_size = max(17, int(25 * scale))
    gear_size = max(17, int(24 * scale))
    detail_size = max(12, int(16 * scale))
    icon_size = max(22, int(34 * scale))
    stamp_size = max(12, int(16 * scale))

    header = f"""[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nScaledBorderAndShadow: yes\nWrapStyle: 2\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: HUD,Segoe UI Semibold,28,{WHITE},{WHITE},{DARK},{DARK},0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1\nStyle: HUDSmall,Segoe UI,16,{MUTED},{MUTED},{DARK},{DARK},0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1\nStyle: HUDIcon,Segoe UI Symbol,32,{MUTED},{MUTED},{DARK},{DARK},0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"""
    lines = [header]

    for i in range(steps):
        rel = i / hz
        # Do not overlap adjacent events. This is important for stable subtitle placement.
        rel_end = min(duration, (i + 1) / hz)
        if rel_end <= rel:
            rel_end = min(duration, rel + 1.0 / hz)
        begin_s, end_s = ass_time(rel), ass_time(rel_end)
        sample = _sample_at(samples, fps, start + rel)
        gps_valid = abs(sample.latitude_deg) > 1e-8 or abs(sample.longitude_deg) > 1e-8
        speed = sample.speed_mph if options.units == "mph" else sample.speed_kph
        unit = "MPH" if options.units == "mph" else "KM/H"
        assist = assist_label(options.language, sample.autopilot_state)
        assist_active = int(getattr(sample, "autopilot_state", 0) or 0) != 0

        if options.show_dashboard and samples:
            lines.append(_panel(begin_s, end_s, x1, y1, x2, y2, int(options.dashboard_opacity)))
            width = x2 - x1

            # Fixed instrument slots: gear / signal / speed / assist / signal / steering state.
            gear_x = x1 + int(width * 0.10)
            left_x = x1 + int(width * 0.20)
            speed_x = x1 + int(width * 0.34)
            assist_x = x1 + int(width * 0.55)
            right_x = x1 + int(width * 0.73)
            wheel_x = x1 + int(width * 0.86)

            if options.show_gear and not minimal:
                lines.append(_text(begin_s, end_s, "HUD", gear_x, main_y,
                                   _gear_name(sample.gear), size=gear_size, color=BLUE, bold=True))

            if options.show_blinkers and not minimal:
                left_color = BLUE if sample.blinker_on_left else MUTED
                right_color = BLUE if sample.blinker_on_right else MUTED
                lines.append(_text(begin_s, end_s, "HUDIcon", left_x, main_y, "◀",
                                   size=icon_size, color=left_color))
                lines.append(_text(begin_s, end_s, "HUDIcon", right_x, main_y, "▶",
                                   size=icon_size, color=right_color))

            if options.show_speed:
                lines.append(_text(begin_s, end_s, "HUD", speed_x, main_y - 5,
                                   f"{speed:.0f}", size=speed_size, color=WHITE, bold=True))
                lines.append(_text(begin_s, end_s, "HUDSmall", speed_x, main_y + int(32 * scale),
                                   unit, size=unit_size, color=MUTED))

            if options.show_state:
                lines.append(_text(begin_s, end_s, "HUD", assist_x, main_y,
                                   assist, size=state_size, color=BLUE if assist_active else MUTED,
                                   bold=assist_active))

            if options.show_steering and not minimal:
                # Neutral, original wheel-like symbol; blue while driver-assist is active.
                lines.append(_text(begin_s, end_s, "HUDIcon", wheel_x, main_y, "◎",
                                   size=icon_size + 2, color=BLUE if assist_active else MUTED, bold=True))

            if full:
                details = []
                if options.show_steering:
                    details.append(f"Steering {sample.steering_wheel_angle:+.1f}°")
                if options.show_accelerator:
                    details.append(f"Accelerator {sample.accelerator_pedal_position:.2f}")
                if options.show_brake:
                    details.append("Brake ON" if sample.brake_applied else "Brake OFF")
                if options.show_gforce:
                    gmag = math.sqrt(
                        sample.linear_acceleration_mps2_x ** 2
                        + sample.linear_acceleration_mps2_y ** 2
                        + sample.linear_acceleration_mps2_z ** 2
                    ) / 9.80665
                    details.append(f"{gmag:.2f} g")
                if options.show_gps_text and gps_valid:
                    details.append(f"{sample.latitude_deg:.5f}, {sample.longitude_deg:.5f}")
                if details:
                    lines.append(_text(begin_s, end_s, "HUDSmall", x1 + 24, detail_y,
                                       "   •   ".join(details), align=4,
                                       size=detail_size, color=MUTED))

            if options.show_timestamp and base_dt:
                stamp = (base_dt + timedelta(seconds=start + rel)).strftime(options.timestamp_format)
                lines.append(_text(begin_s, end_s, "HUDSmall", x2 - 24, detail_y if full else main_y,
                                   stamp, align=6, size=stamp_size, color=WHITE))

        elif options.show_timestamp and base_dt:
            stamp = (base_dt + timedelta(seconds=start + rel)).strftime(options.timestamp_format)
            lines.append(_text(begin_s, end_s, "HUDSmall", 1880, 1040,
                               stamp, align=6, size=stamp_size, color=WHITE))

    path.write_text("".join(lines), encoding="utf-8-sig")
