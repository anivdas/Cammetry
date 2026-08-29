from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

import cv2  # type: ignore

from tts_core import ClipGroup, CAMERA_ORDER, probe_video


class MultiCameraPlayer:
    """Lightweight local synchronized TeslaCam preview engine using OpenCV.

    TeslaCam files do not contain useful audio, so synchronization is driven by a shared
    playback clock and each camera is decoded to the closest source frame.
    """

    def __init__(self) -> None:
        self.group: Optional[ClipGroup] = None
        self.captures: Dict[str, cv2.VideoCapture] = {}
        self.fps: Dict[str, float] = {}
        self.frame_index: Dict[str, int] = {}
        self.frame_cache: Dict[str, object] = {}
        self.position = 0.0
        self.duration = 0.0
        self.speed = 1.0
        self.playing = False
        self._clock_started = 0.0
        self._position_at_clock_start = 0.0

    def release(self) -> None:
        for cap in self.captures.values():
            try:
                cap.release()
            except Exception:
                pass
        self.captures.clear()
        self.fps.clear()
        self.frame_index.clear()
        self.frame_cache.clear()
        self.group = None
        self.position = 0.0
        self.duration = 0.0
        self.playing = False

    def load_group(self, group: ClipGroup) -> None:
        self.release()
        self.group = group
        durations = []
        for camera, path in group.cameras.items():
            cap = cv2.VideoCapture(str(path))
            if not cap.isOpened():
                cap.release()
                continue
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            if not (1 <= fps <= 240):
                try:
                    fps = probe_video(path).fps
                except Exception:
                    fps = 36.0
            frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            duration = frames / fps if frames > 0 and fps > 0 else 0.0
            if duration <= 0:
                try:
                    duration = probe_video(path).duration
                except Exception:
                    pass
            if duration > 0:
                durations.append(duration)
            self.captures[camera] = cap
            self.fps[camera] = fps
            self.frame_index[camera] = -1
        self.duration = max(durations) if durations else 0.0
        self.seek(0.0)

    def set_speed(self, speed: float) -> None:
        speed = max(0.1, min(float(speed), 10.0))
        self._sync_clock()
        self.speed = speed
        if self.playing:
            self._clock_started = time.perf_counter()
            self._position_at_clock_start = self.position

    def _sync_clock(self) -> None:
        if not self.playing:
            return
        now = time.perf_counter()
        elapsed = max(0.0, now - self._clock_started)
        self.position = self._position_at_clock_start + elapsed * self.speed
        if self.duration and self.position >= self.duration:
            self.position = self.duration
            self.playing = False

    def play(self) -> None:
        if not self.captures:
            return
        if self.duration and self.position >= self.duration - 0.02:
            self.seek(0.0)
        self._clock_started = time.perf_counter()
        self._position_at_clock_start = self.position
        self.playing = True

    def pause(self) -> None:
        self._sync_clock()
        self.playing = False

    def toggle(self) -> bool:
        if self.playing:
            self.pause()
        else:
            self.play()
        return self.playing

    def tick(self) -> float:
        self._sync_clock()
        return self.position

    def seek(self, seconds: float) -> None:
        if self.duration:
            seconds = min(max(0.0, float(seconds)), self.duration)
        else:
            seconds = max(0.0, float(seconds))
        self.position = seconds
        for camera, cap in self.captures.items():
            fps = self.fps.get(camera, 36.0)
            target = max(0, int(round(seconds * fps)))
            cap.set(cv2.CAP_PROP_POS_FRAMES, target)
            self.frame_index[camera] = target - 1
            self.frame_cache.pop(camera, None)
        if self.playing:
            self._clock_started = time.perf_counter()
            self._position_at_clock_start = self.position

    def skip(self, seconds: float) -> None:
        self._sync_clock()
        self.seek(self.position + seconds)

    def _read_camera_frame(self, camera: str, target_seconds: float):
        cap = self.captures.get(camera)
        if cap is None:
            return None
        fps = self.fps.get(camera, 36.0)
        target = max(0, int(round(target_seconds * fps)))
        current = self.frame_index.get(camera, -1)
        if current == target and camera in self.frame_cache:
            return self.frame_cache[camera]

        # Small forward gaps are cheaper to decode sequentially. Larger jumps use a seek.
        if current < 0 or target < current or target - current > max(6, int(fps * 0.4)):
            cap.set(cv2.CAP_PROP_POS_FRAMES, target)
            current = target - 1

        frame = None
        while current < target:
            ok, f = cap.read()
            if not ok:
                break
            current += 1
            frame = f
        if frame is None and current == target and camera in self.frame_cache:
            frame = self.frame_cache[camera]
        elif frame is None:
            ok, f = cap.read()
            if ok:
                frame = f
                current += 1
        if frame is not None:
            self.frame_index[camera] = current
            self.frame_cache[camera] = frame
        return frame

    def get_frames(
        self,
        target_seconds: Optional[float] = None,
        cameras: Optional[Iterable[str]] = None,
    ) -> Dict[str, object]:
        """Return synchronized frames, optionally decoding only requested cameras.

        Restricting decode to visible camera tiles avoids spending CPU time advancing
        hidden streams while the user is in Single Camera or a reduced layout. A
        hidden stream automatically seeks to the current timestamp the next time it
        becomes visible, preserving synchronization without continuous decode cost.
        """
        if target_seconds is None:
            target_seconds = self.tick()
        requested = set(cameras) if cameras is not None else None
        frames: Dict[str, object] = {}
        for camera in CAMERA_ORDER:
            if camera not in self.captures:
                continue
            if requested is not None and camera not in requested:
                continue
            frame = self._read_camera_frame(camera, target_seconds)
            if frame is not None:
                frames[camera] = frame
        return frames

    def current_frame_number(self, camera: str) -> int:
        return max(0, int(round(self.position * self.fps.get(camera, 36.0))))

    def camera_size(self, camera: str) -> Tuple[int, int]:
        cap = self.captures.get(camera)
        if cap is None:
            return 0, 0
        return int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
