from __future__ import annotations

"""Deterministic, local telemetry event detection for timeline navigation."""

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

from tts_core import TelemetrySample


@dataclass(frozen=True)
class DetectedEvent:
    seconds: float
    kind: str
    label: str
    severity: int = 1
    value: float | None = None


def _horizontal_g(sample: TelemetrySample) -> float:
    return math.hypot(sample.linear_acceleration_mps2_x, sample.linear_acceleration_mps2_y) / 9.80665


def _dedupe(events: Iterable[DetectedEvent], minimum_spacing: float = 1.5) -> list[DetectedEvent]:
    accepted: list[DetectedEvent] = []
    last_by_kind: dict[str, float] = {}
    for event in sorted(events, key=lambda item: (item.seconds, -item.severity)):
        if event.seconds - last_by_kind.get(event.kind, -10_000.0) < minimum_spacing:
            continue
        accepted.append(event)
        last_by_kind[event.kind] = event.seconds
    return accepted


def detect_events(
    samples: Sequence[TelemetrySample],
    fps: float,
    *,
    hard_brake_mps2: float = 4.0,
    hard_accel_mps2: float = 3.5,
    high_g: float = 0.55,
) -> list[DetectedEvent]:
    """Detect review markers without cloud services or probabilistic claims.

    Speed deltas are used for longitudinal events because camera-axis conventions
    can vary. Acceleration vectors are used only for a direction-neutral high-G
    marker. Results are navigation hints, not forensic conclusions.
    """
    if len(samples) < 2:
        return []
    rate = max(1.0, float(fps or 1.0))
    events: list[DetectedEvent] = []
    window = max(1, int(round(rate * 0.5)))
    previous = samples[0]
    for index, sample in enumerate(samples):
        seconds = index / rate
        if index >= window:
            delta_t = window / rate
            acceleration = (sample.vehicle_speed_mps - samples[index - window].vehicle_speed_mps) / delta_t
            if acceleration <= -abs(hard_brake_mps2):
                events.append(DetectedEvent(seconds, "hard_braking", "Hard braking", 3, acceleration))
            elif acceleration >= abs(hard_accel_mps2):
                events.append(DetectedEvent(seconds, "rapid_acceleration", "Rapid acceleration", 2, acceleration))
        g_force = _horizontal_g(sample)
        if g_force >= high_g:
            severity = 3 if g_force >= 0.8 else 2
            events.append(DetectedEvent(seconds, "high_g", "High G-force", severity, g_force))
        if index and sample.autopilot_state != previous.autopilot_state:
            label = "Driver assistance disengaged" if sample.autopilot_state == 0 else "Driver assistance changed"
            events.append(DetectedEvent(seconds, "driver_assistance", label, 2, float(sample.autopilot_state)))
        if index and sample.brake_applied and not previous.brake_applied:
            events.append(DetectedEvent(seconds, "brake_applied", "Brake applied", 1))
        if index and sample.blinker_on_left and not previous.blinker_on_left:
            events.append(DetectedEvent(seconds, "left_signal", "Left signal", 1))
        if index and sample.blinker_on_right and not previous.blinker_on_right:
            events.append(DetectedEvent(seconds, "right_signal", "Right signal", 1))
        previous = sample
    return _dedupe(events)
