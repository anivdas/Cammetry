#!/usr/bin/env python3
from __future__ import annotations

"""Line-delimited JSON bridge for native presentation shells.

The bridge is intentionally local-only: it reads stdin, writes stdout, opens no
listener, and performs no authentication or network operations.
"""

import json
import sys
from pathlib import Path
from typing import Any

from tts_core import ClipGroup, discover_clips
from tts_library import ClipLibrary
from tts_sequence import build_sequences


BRIDGE_VERSION = 1


def _group_payload(group: ClipGroup) -> dict[str, Any]:
    return {
        "id": f"{group.folder.resolve()}::{group.timestamp}",
        "timestamp": group.timestamp,
        "displayTime": group.display_time(),
        "sourceKind": group.source_kind,
        "folder": str(group.folder.resolve()),
        "cameras": sorted(group.cameras),
    }


class Bridge:
    def __init__(self):
        self.library = ClipLibrary()

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        command = str(request.get("command", ""))
        if command == "ping":
            return {"bridgeVersion": BRIDGE_VERSION, "name": "Cammetry Core", "localOnly": True}
        if command == "discover":
            root = Path(str(request.get("root", ""))).expanduser()
            if not root.is_dir():
                raise ValueError("The selected TeslaCam folder does not exist")
            groups = discover_clips(root)
            sequences = build_sequences(groups)
            self.library.index_groups(groups)
            return {
                "groups": [_group_payload(group) for group in groups],
                "sequences": [
                    {
                        "id": sequence.id,
                        "sourceKind": sequence.source_kind,
                        "duration": sequence.duration,
                        "segmentIds": [_group_payload(segment.group)["id"] for segment in sequence.segments],
                    }
                    for sequence in sequences
                ],
            }
        if command == "library.search":
            records = self.library.search(str(request.get("query", "")), favorites_only=bool(request.get("favoritesOnly", False)))
            return {
                "recordings": [
                    {
                        "id": record.id, "timestamp": record.timestamp, "sourceKind": record.source_kind,
                        "cameraCount": record.camera_count, "title": record.title, "notes": record.notes,
                        "tags": list(record.tags), "favorite": record.favorite, "reviewed": record.reviewed,
                    }
                    for record in records
                ]
            }
        raise ValueError(f"Unsupported bridge command: {command}")


def main() -> int:
    bridge = Bridge()
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("Each request must be a JSON object")
            response = {"id": request.get("id"), "ok": True, "result": bridge.handle(request)}
        except Exception as exc:
            response = {"id": None, "ok": False, "error": str(exc)}
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
