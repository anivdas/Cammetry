from __future__ import annotations

import re

import tts_export_v051


MAP_SIZES = ("Small", "Medium", "Large")
MAP_POSITIONS = ("Top right", "Top left", "Bottom right", "Bottom left")

_MAP_SIZE = "Medium"
_MAP_POSITION = "Top right"
_INSTALLED = False


def configure_map_layout(size: str, position: str) -> None:
    global _MAP_SIZE, _MAP_POSITION
    _MAP_SIZE = size if size in MAP_SIZES else "Medium"
    _MAP_POSITION = position if position in MAP_POSITIONS else "Top right"


def install_export_layout_polish() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original = tts_export_v051._build_command

    def build_command(ffmpeg, group, cameras, start, duration, route_path, ass_path, output, options, codec):
        cmd = original(ffmpeg, group, cameras, start, duration, route_path, ass_path, output, options, codec)
        if route_path is None:
            return cmd
        try:
            idx = cmd.index("-filter_complex") + 1
            graph = cmd[idx]
        except Exception:
            return cmd

        scale_factor = {"Small": 0.78, "Medium": 1.0, "Large": 1.28}.get(_MAP_SIZE, 1.0)

        def scale_match(match: re.Match[str]) -> str:
            w = max(180, int(round(int(match.group(1)) * scale_factor)))
            h = max(120, int(round(int(match.group(2)) * scale_factor)))
            return f"scale={w}:{h}[map]"

        graph = re.sub(r"scale=(\d+):(\d+)\[map\]", scale_match, graph, count=1)

        position = {
            "Top right": "W-w-28:28",
            "Top left": "28:28",
            "Bottom right": "W-w-28:H-h-28",
            "Bottom left": "28:H-h-28",
        }.get(_MAP_POSITION, "W-w-28:28")
        graph = re.sub(r"overlay=W-w-28:28:shortest=1", f"overlay={position}:shortest=1", graph, count=1)
        cmd[idx] = graph
        return cmd

    tts_export_v051._build_command = build_command
