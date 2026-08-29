from __future__ import annotations

import math
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path
from typing import Optional, Sequence, Tuple

import cv2  # type: ignore
import numpy as np
from PIL import Image

from tts_core import TelemetrySample
from tts_map import (
    MapMosaic,
    OSM_ATTRIBUTION,
    TILE_SIZE,
    _world_xy,
    build_osm_mosaic,
    choose_zoom,
)


_EXPORT_MAP_STYLE = "Route only"
_EXPORT_MAPTILER_KEY = ""
_EXPORT_CACHE_DIR: Optional[Path] = None

MAP_STYLES = ("Off", "Route only", "Street map", "Satellite")


def configure_export_map(style: str, maptiler_key: str = "", cache_dir: Optional[Path] = None) -> None:
    global _EXPORT_MAP_STYLE, _EXPORT_MAPTILER_KEY, _EXPORT_CACHE_DIR
    value = str(style or "Route only")
    _EXPORT_MAP_STYLE = value if value in MAP_STYLES else "Route only"
    _EXPORT_MAPTILER_KEY = str(maptiler_key or "").strip()
    _EXPORT_CACHE_DIR = cache_dir


def _route_points(samples: Sequence[TelemetrySample]) -> list[Tuple[float, float]]:
    return [
        (s.longitude_deg, s.latitude_deg)
        for s in samples
        if abs(s.latitude_deg) > 1e-8 or abs(s.longitude_deg) > 1e-8
    ]


def _satellite_tile(cache_dir: Path, key: str, zoom: int, x: int, y: int, timeout: int = 8) -> Image.Image:
    path = cache_dir / "maptiler-satellite" / str(zoom) / str(x) / f"{y}.img"
    if path.exists():
        try:
            return Image.open(path).convert("RGB")
        except Exception:
            path.unlink(missing_ok=True)
    url = (
        f"https://api.maptiler.com/tiles/satellite-v4/{zoom}/{x}/{y}"
        f"?key={urllib.parse.quote(key, safe='')}"
    )
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Cammetry open-source dashcam viewer", "Accept": "image/*"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    image = Image.open(BytesIO(raw)).convert("RGB")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_bytes(raw)
    except OSError:
        pass
    return image


def _build_satellite_mosaic(samples: Sequence[TelemetrySample], cache_dir: Path, key: str,
                            max_tiles: int = 16) -> Optional[MapMosaic]:
    points = _route_points(samples)
    choice = choose_zoom(points, max_tiles=max_tiles)
    if choice is None:
        return None
    zoom, x0, x1, y0, y1 = choice
    width = (x1 - x0 + 1) * TILE_SIZE
    height = (y1 - y0 + 1) * TILE_SIZE
    mosaic = Image.new("RGB", (width, height), (24, 30, 36))
    for ty in range(y0, y1 + 1):
        for tx in range(x0, x1 + 1):
            try:
                tile = _satellite_tile(cache_dir, key, zoom, tx, ty)
            except Exception:
                tile = Image.new("RGB", (TILE_SIZE, TILE_SIZE), (35, 42, 49))
            mosaic.paste(tile, ((tx - x0) * TILE_SIZE, (ty - y0) * TILE_SIZE))
    return MapMosaic(mosaic, zoom, x0, y0)


def _fit_mosaic(mosaic: MapMosaic, w: int, h: int):
    mw, mh = mosaic.image.size
    scale = max(w / max(1, mw), h / max(1, mh))
    rw, rh = max(1, int(round(mw * scale))), max(1, int(round(mh * scale)))
    resized = mosaic.image.resize((rw, rh), Image.Resampling.LANCZOS)
    left = max(0, (rw - w) // 2)
    top = max(0, (rh - h) // 2)
    crop = resized.crop((left, top, left + w, top + h))
    off_x, off_y = -left, -top

    def point(lon: float, lat: float) -> Tuple[int, int]:
        px, py = mosaic.pixel(lon, lat)
        return int(round(px * scale + off_x)), int(round(py * scale + off_y))

    return cv2.cvtColor(np.asarray(crop), cv2.COLOR_RGB2BGR), point


def _route_only_background(w: int, h: int):
    image = np.zeros((h, w, 3), dtype=np.uint8)
    image[:] = (27, 31, 36)
    for gx in range(0, w, 60):
        cv2.line(image, (gx, 0), (gx, h), (38, 45, 53), 1)
    for gy in range(0, h, 60):
        cv2.line(image, (0, gy), (w, gy), (38, 45, 53), 1)
    return image


def render_route_video(samples: Sequence[TelemetrySample], fps: float, start: float, end: float,
                       output: Path, size: Tuple[int, int] = (420, 270), route_fps: float = 10.0,
                       language: str = "English") -> Optional[Path]:
    """Render route-only, street, or optional satellite minimap video.

    Online map styles are opt-in. Street map requests disclose only the approximate
    map tile area to OpenStreetMap. Satellite requests use the user's own MapTiler
    key; video and telemetry payloads are never uploaded.
    """
    style = _EXPORT_MAP_STYLE
    if style == "Off":
        return None
    valid = [
        (s.longitude_deg, s.latitude_deg, s.autopilot_state)
        for s in samples
        if abs(s.latitude_deg) > 1e-8 or abs(s.longitude_deg) > 1e-8
    ]
    if len(valid) < 2:
        return None

    w, h = size
    cache_dir = _EXPORT_CACHE_DIR or (Path.home() / ".cammetry-map-cache")
    mosaic: Optional[MapMosaic] = None
    attribution = ""
    if style == "Street map":
        try:
            mosaic = build_osm_mosaic(samples, cache_dir / "osm", max_tiles=16)
            attribution = OSM_ATTRIBUTION
        except Exception:
            mosaic = None
    elif style == "Satellite" and _EXPORT_MAPTILER_KEY:
        try:
            mosaic = _build_satellite_mosaic(samples, cache_dir, _EXPORT_MAPTILER_KEY, max_tiles=16)
            attribution = "© MapTiler • © OpenStreetMap contributors"
        except Exception:
            mosaic = None

    if mosaic is not None:
        background, point = _fit_mosaic(mosaic, w, h)
    else:
        background = _route_only_background(w, h)
        xs = [p[0] for p in valid]
        ys = [p[1] for p in valid]
        minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
        dx, dy = max(maxx - minx, 1e-8), max(maxy - miny, 1e-8)
        pad = 24

        def point(lon: float, lat: float) -> Tuple[int, int]:
            x = pad + int((lon - minx) / dx * (w - 2 * pad))
            y = h - pad - int((lat - miny) / dy * (h - 2 * pad))
            return x, y

        if style == "Satellite" and not _EXPORT_MAPTILER_KEY:
            attribution = "Satellite map key not configured • route-only fallback"
        elif style == "Street map":
            attribution = "Street tiles unavailable • route-only fallback"

    all_points = [point(lon, lat) for lon, lat, _ in valid]
    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), route_fps, (w, h))
    if not writer.isOpened():
        return None

    duration = max(0.1, end - start)
    count = max(1, int(math.ceil(duration * route_fps)))
    for frame_idx in range(count):
        t = start + frame_idx / route_fps
        sample_idx = min(len(samples) - 1, max(0, int(round(t * fps)))) if samples else 0
        image = background.copy()
        # Darken imagery slightly so route and marker remain readable at night/day.
        if mosaic is not None:
            shade = np.zeros_like(image)
            image = cv2.addWeighted(image, 0.78, shade, 0.22, 0)
        for i in range(1, len(valid)):
            p1, p2 = all_points[i - 1], all_points[i]
            color = (246, 130, 59) if valid[i][2] else (145, 151, 160)
            cv2.line(image, p1, p2, color, 4, cv2.LINE_AA)
        if samples:
            current = samples[sample_idx]
            if abs(current.latitude_deg) > 1e-8 or abs(current.longitude_deg) > 1e-8:
                cp = point(current.longitude_deg, current.latitude_deg)
                cv2.circle(image, cp, 9, (255, 255, 255), -1, cv2.LINE_AA)
                cv2.circle(image, cp, 6, (246, 130, 59) if current.autopilot_state else (145, 151, 160), -1, cv2.LINE_AA)
        label = "ROUTE" if style == "Route only" else style.upper()
        cv2.putText(image, label, (14, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (238, 243, 248), 1, cv2.LINE_AA)
        if attribution:
            cv2.putText(image, attribution, (10, h - 9), cv2.FONT_HERSHEY_SIMPLEX, 0.28, (222, 226, 231), 1, cv2.LINE_AA)
        writer.write(image)
    writer.release()
    return output if output.exists() and output.stat().st_size else None
