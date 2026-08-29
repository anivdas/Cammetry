from __future__ import annotations

import math
import urllib.request
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple

from PIL import Image

from tts_core import APP_NAME, APP_VERSION, TelemetrySample

OSM_ATTRIBUTION = "© OpenStreetMap contributors"
TILE_SIZE = 256


def _world_xy(lon: float, lat: float, zoom: int) -> Tuple[float, float]:
    lat = max(-85.05112878, min(85.05112878, lat))
    n = 2.0 ** zoom
    x = (lon + 180.0) / 360.0 * n
    lat_rad = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return x, y


@dataclass
class MapMosaic:
    image: Image.Image
    zoom: int
    x0: int
    y0: int

    def pixel(self, lon: float, lat: float) -> Tuple[float, float]:
        x, y = _world_xy(lon, lat, self.zoom)
        return (x - self.x0) * TILE_SIZE, (y - self.y0) * TILE_SIZE


def _route_points(samples: Sequence[TelemetrySample]) -> list[Tuple[float, float]]:
    return [
        (s.longitude_deg, s.latitude_deg)
        for s in samples
        if abs(s.latitude_deg) > 1e-8 or abs(s.longitude_deg) > 1e-8
    ]


def choose_zoom(points: Sequence[Tuple[float, float]], max_tiles: int = 16) -> Optional[Tuple[int, int, int, int, int]]:
    if not points:
        return None
    for zoom in range(17, 7, -1):
        xy = [_world_xy(lon, lat, zoom) for lon, lat in points]
        xs = [int(math.floor(x)) for x, _ in xy]
        ys = [int(math.floor(y)) for _, y in xy]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        # One-tile padding provides useful street context.
        n = 2 ** zoom
        x0, x1 = max(0, x0 - 1), min(n - 1, x1 + 1)
        y0, y1 = max(0, y0 - 1), min(n - 1, y1 + 1)
        if (x1 - x0 + 1) * (y1 - y0 + 1) <= max_tiles:
            return zoom, x0, x1, y0, y1
    return None


def _tile_path(cache_dir: Path, zoom: int, x: int, y: int) -> Path:
    return cache_dir / str(zoom) / str(x) / f"{y}.png"


def _get_tile(cache_dir: Path, zoom: int, x: int, y: int, timeout: int = 8) -> Image.Image:
    path = _tile_path(cache_dir, zoom, x, y)
    if path.exists():
        try:
            return Image.open(path).convert("RGB")
        except Exception:
            path.unlink(missing_ok=True)
    url = f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"{APP_NAME}/{APP_VERSION} open-source TeslaCam viewer",
            "Accept": "image/png,image/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read()
    image = Image.open(BytesIO(raw)).convert("RGB")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_bytes(raw)
    except OSError:
        pass
    return image


def build_osm_mosaic(samples: Sequence[TelemetrySample], cache_dir: Path, max_tiles: int = 16) -> Optional[MapMosaic]:
    """Build a small cached OSM mosaic around the clip route.

    This performs network access only when explicitly enabled by the user. Tile
    requests disclose the approximate map area to OpenStreetMap's tile service;
    no video or SEI payload is uploaded.
    """
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
                tile = _get_tile(cache_dir, zoom, tx, ty)
            except Exception:
                tile = Image.new("RGB", (TILE_SIZE, TILE_SIZE), (35, 42, 49))
            mosaic.paste(tile, ((tx - x0) * TILE_SIZE, (ty - y0) * TILE_SIZE))
    return MapMosaic(mosaic, zoom, x0, y0)
