from __future__ import annotations

"""Privacy-export presets and optional local frame detectors."""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class PrivacyPreset:
    name: str
    show_timestamp: bool
    show_minimap: bool
    show_gps_text: bool
    strip_metadata: bool
    detect_faces: bool = False
    detect_plates: bool = False

    def apply(self, options) -> None:
        options.show_timestamp = self.show_timestamp
        options.show_minimap = self.show_minimap
        options.show_gps_text = self.show_gps_text
        options.strip_metadata = self.strip_metadata


PRIVACY_PRESETS = {
    "Standard": PrivacyPreset("Standard", True, False, False, True),
    "Share Safe": PrivacyPreset("Share Safe", False, False, False, True, True, True),
    "Keep Location": PrivacyPreset("Keep Location", True, True, False, True),
}


@dataclass(frozen=True)
class PrivacyRegion:
    kind: str
    x: float
    y: float
    width: float
    height: float
    confidence: float


class LocalPrivacyDetector:
    """OpenCV detectors that never transmit a frame.

    The bundled OpenCV cascades provide a useful first-pass review queue. Users
    must review the resulting regions before export because no detector is
    complete enough to guarantee anonymization.
    """

    def __init__(self):
        import cv2  # type: ignore

        self.cv2 = cv2
        root = Path(cv2.data.haarcascades)
        self.face = self._load(root / "haarcascade_frontalface_default.xml")
        self.plate = self._load(root / "haarcascade_russian_plate_number.xml")

    def _load(self, path: Path):
        if not path.is_file():
            return None
        cascade = self.cv2.CascadeClassifier(str(path))
        return None if cascade.empty() else cascade

    def detect(self, frame, *, faces: bool = True, plates: bool = True) -> list[PrivacyRegion]:
        if frame is None or not getattr(frame, "shape", None):
            return []
        height, width = frame.shape[:2]
        gray = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2GRAY)
        gray = self.cv2.equalizeHist(gray)
        found: list[PrivacyRegion] = []
        detectors = (("face", self.face, faces, 1.08, 4), ("plate", self.plate, plates, 1.06, 3))
        for kind, detector, enabled, scale, neighbors in detectors:
            if not enabled or detector is None:
                continue
            for x, y, w, h in detector.detectMultiScale(gray, scaleFactor=scale, minNeighbors=neighbors, minSize=(24, 16)):
                pad_x = int(w * 0.08)
                pad_y = int(h * 0.12)
                left, top = max(0, x - pad_x), max(0, y - pad_y)
                right, bottom = min(width, x + w + pad_x), min(height, y + h + pad_y)
                found.append(PrivacyRegion(kind, left / width, top / height, (right - left) / width, (bottom - top) / height, 0.5))
        return found
