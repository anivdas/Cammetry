from __future__ import annotations

"""Continuous TeslaCam event timelines.

This module models adjacent one-minute camera groups as one virtual recording.  It
does not modify the source files and is deliberately independent from Tkinter so
both the current UI and a future WinUI shell can consume the same timeline.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Optional, Sequence

from tts_core import ClipGroup


TimestampParser = Callable[[str], Optional[datetime]]
DurationResolver = Callable[[ClipGroup], float]


def parse_clip_timestamp(value: str) -> Optional[datetime]:
    try:
        return datetime.strptime(value, "%Y-%m-%d_%H-%M-%S")
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class SequenceSegment:
    group: ClipGroup
    start: float
    duration: float

    @property
    def end(self) -> float:
        return self.start + self.duration


@dataclass(frozen=True)
class ClipSequence:
    id: str
    source_kind: str
    folder: Path
    segments: tuple[SequenceSegment, ...]

    @property
    def duration(self) -> float:
        return self.segments[-1].end if self.segments else 0.0

    @property
    def cameras(self) -> tuple[str, ...]:
        return tuple(sorted({camera for item in self.segments for camera in item.group.cameras}))

    def locate(self, position: float) -> tuple[SequenceSegment, float]:
        """Map a virtual event position to a source group and local position."""
        if not self.segments:
            raise ValueError("The sequence has no segments")
        position = max(0.0, min(float(position), self.duration))
        for segment in self.segments:
            if position < segment.end or segment is self.segments[-1]:
                return segment, min(segment.duration, max(0.0, position - segment.start))
        return self.segments[-1], self.segments[-1].duration

    def position_of(self, group: ClipGroup, local_position: float = 0.0) -> float:
        for segment in self.segments:
            if segment.group is group or (
                segment.group.timestamp == group.timestamp and segment.group.folder == group.folder
            ):
                return segment.start + min(segment.duration, max(0.0, float(local_position)))
        raise KeyError(group.timestamp)


def _default_duration(_group: ClipGroup) -> float:
    return 60.0


def build_sequences(
    groups: Iterable[ClipGroup],
    *,
    max_gap_seconds: float = 75.0,
    duration_resolver: DurationResolver = _default_duration,
    timestamp_parser: TimestampParser = parse_clip_timestamp,
) -> list[ClipSequence]:
    """Group chronologically adjacent clips without merging unrelated folders.

    Saved and Sentry events normally keep all their minute segments in one folder.
    RecentClips uses one shared folder, so timestamp adjacency provides the boundary.
    """
    ordered = sorted(
        ((timestamp_parser(group.timestamp), group) for group in groups),
        key=lambda item: (item[0] or datetime.min, str(item[1].folder)),
    )
    buckets: list[list[tuple[datetime, ClipGroup]]] = []
    current: list[tuple[datetime, ClipGroup]] = []
    for stamp, group in ordered:
        if stamp is None:
            continue
        if current:
            previous_stamp, previous_group = current[-1]
            gap = (stamp - previous_stamp).total_seconds()
            same_context = (
                group.folder == previous_group.folder
                and group.source_kind == previous_group.source_kind
                and 0.0 < gap <= max_gap_seconds
            )
            if not same_context:
                buckets.append(current)
                current = []
        current.append((stamp, group))
    if current:
        buckets.append(current)

    sequences: list[ClipSequence] = []
    for bucket in buckets:
        offset = 0.0
        segments: list[SequenceSegment] = []
        for _stamp, group in bucket:
            duration = max(0.05, float(duration_resolver(group) or 60.0))
            segments.append(SequenceSegment(group=group, start=offset, duration=duration))
            offset += duration
        first = bucket[0][1]
        sequences.append(
            ClipSequence(
                id=f"{first.source_kind.lower()}:{first.folder}:{first.timestamp}",
                source_kind=first.source_kind,
                folder=first.folder,
                segments=tuple(segments),
            )
        )
    return sequences


def sequence_for_group(sequences: Sequence[ClipSequence], group: ClipGroup) -> Optional[ClipSequence]:
    for sequence in sequences:
        for segment in sequence.segments:
            candidate = segment.group
            if candidate is group or (candidate.timestamp == group.timestamp and candidate.folder == group.folder):
                return sequence
    return None
