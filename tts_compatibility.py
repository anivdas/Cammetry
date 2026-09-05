from __future__ import annotations

"""Release-safe compatibility and export preflight reporting."""

import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

from tts_core import ClipGroup, TelemetrySample, get_ffmpeg_exe, probe_video
from tts_export_v051 import encoder_status


@dataclass(frozen=True)
class CompatibilityCheck:
    key: str
    label: str
    status: str
    detail: str


@dataclass(frozen=True)
class CompatibilityReport:
    checks: tuple[CompatibilityCheck, ...]
    estimated_output_bytes: int = 0

    @property
    def ready(self) -> bool:
        return not any(check.status == "error" for check in self.checks)

    def safe_text(self) -> str:
        lines = [f"Cammetry compatibility report — {'READY' if self.ready else 'ACTION NEEDED'}"]
        for check in self.checks:
            lines.append(f"[{check.status.upper()}] {check.label}: {check.detail}")
        lines.append("This report omits filenames, file paths, video contents, and GPS coordinates.")
        return "\n".join(lines)


def _check(key: str, label: str, status: str, detail: str) -> CompatibilityCheck:
    return CompatibilityCheck(key=key, label=label, status=status, detail=detail)


def inspect_group(
    group: Optional[ClipGroup],
    samples: Sequence[TelemetrySample] = (),
    *,
    output_folder: Optional[Path] = None,
    expected_duration: float = 0.0,
) -> CompatibilityReport:
    checks: list[CompatibilityCheck] = []
    checks.append(_check("os", "Operating system", "ok", f"{platform.system()} {platform.release()}"))
    try:
        ffmpeg = get_ffmpeg_exe()
        checks.append(_check("ffmpeg", "FFmpeg", "ok", Path(ffmpeg).name))
    except Exception as exc:
        checks.append(_check("ffmpeg", "FFmpeg", "error", str(exc)))

    try:
        encoders = encoder_status()
    except Exception:
        encoders = {"CPU x264": True}
    ready_encoders = [name for name, ready in encoders.items() if ready]
    checks.append(
        _check(
            "encoders",
            "Video encoder",
            "ok" if ready_encoders else "error",
            ", ".join(ready_encoders) if ready_encoders else "No working encoder detected",
        )
    )

    estimate = 0
    if group is None:
        checks.append(_check("recording", "Recording", "warning", "No recording selected"))
    else:
        missing = [camera for camera, path in group.cameras.items() if not path.is_file()]
        checks.append(
            _check(
                "cameras",
                "Camera streams",
                "error" if missing else "ok",
                f"{len(group.cameras)} found" if not missing else f"{len(missing)} source files are unavailable",
            )
        )
        infos = []
        for path in group.cameras.values():
            if not path.is_file():
                continue
            try:
                infos.append(probe_video(path))
            except Exception:
                pass
        usable = [info for info in infos if info.width and info.height and info.fps]
        checks.append(
            _check(
                "video",
                "Video decoding",
                "ok" if usable else "error",
                f"{len(usable)}/{len(group.cameras)} streams probed successfully",
            )
        )
        checks.append(
            _check(
                "telemetry",
                "Embedded telemetry",
                "ok" if samples else "warning",
                f"{len(samples)} samples" if samples else "Not present in this recording",
            )
        )
        duration = expected_duration or max((info.duration for info in usable), default=60.0)
        # High preset is approximately 14 Mbit/s plus a conservative margin.
        estimate = int(max(duration, 1.0) * 14_000_000 / 8 * 1.15)

    if output_folder:
        try:
            free = shutil.disk_usage(output_folder).free
            status = "ok" if not estimate or free >= estimate * 1.5 else "error"
            detail = f"{free / (1024 ** 3):.1f} GB available"
            if estimate:
                detail += f"; estimated export {estimate / (1024 ** 2):.0f} MB"
            checks.append(_check("storage", "Output storage", status, detail))
        except Exception:
            checks.append(_check("storage", "Output storage", "warning", "Could not determine free space"))

    return CompatibilityReport(tuple(checks), estimate)
