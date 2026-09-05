from __future__ import annotations

"""Portable incident packages with integrity hashes and human-readable reports."""

import html
import json
import shutil
import time
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

from tts_core import ClipGroup
from tts_event_detection import DetectedEvent
from tts_library import Bookmark, copy_verified, sha256_file


@dataclass(frozen=True)
class IncidentFile:
    camera: str
    filename: str
    sha256: str
    size: int
    included: bool


@dataclass(frozen=True)
class IncidentPackageResult:
    folder: Path
    archive: Optional[Path]
    manifest: Path
    report: Path


def _report_html(title: str, notes: str, group: ClipGroup, start: float, end: float, files: Sequence[IncidentFile], bookmarks: Sequence[Bookmark], events: Sequence[DetectedEvent]) -> str:
    rows = "".join(
        f"<tr><td>{html.escape(item.camera)}</td><td>{html.escape(item.filename)}</td><td><code>{item.sha256}</code></td><td>{item.size}</td></tr>"
        for item in files
    )
    marks = "".join(f"<li>{item.seconds:.2f}s — {html.escape(item.label)}{': ' + html.escape(item.note) if item.note else ''}</li>" for item in bookmarks)
    detected = "".join(f"<li>{item.seconds:.2f}s — {html.escape(item.label)}</li>" for item in events)
    return f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>body{{font:15px Segoe UI,Arial,sans-serif;max-width:1000px;margin:40px auto;color:#17202a}}h1,h2{{color:#0b4f7c}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccd4dc;padding:7px;text-align:left}}code{{font-size:11px;word-break:break-all}}.note{{background:#eef6fb;padding:12px;border-left:4px solid #177ddc}}</style>
<h1>{html.escape(title)}</h1>
<p class="note">Generated locally by Cammetry. Telemetry and detected events are review aids and should not be treated as authoritative forensic conclusions.</p>
<p><b>Recording:</b> {html.escape(group.timestamp)} · {html.escape(group.source_kind)} · {len(group.cameras)} cameras<br><b>Selected range:</b> {start:.2f}s–{end:.2f}s</p>
<h2>Notes</h2><p>{html.escape(notes) if notes else 'None'}</p>
<h2>Bookmarks</h2><ul>{marks or '<li>None</li>'}</ul>
<h2>Detected review markers</h2><ul>{detected or '<li>None</li>'}</ul>
<h2>Source integrity</h2><table><thead><tr><th>Camera</th><th>File</th><th>SHA-256</th><th>Bytes</th></tr></thead><tbody>{rows}</tbody></table>
<p>Cammetry is independent software and is not affiliated with or endorsed by Tesla, Inc.</p>
</html>"""


def create_incident_package(
    destination_root: Path,
    title: str,
    notes: str,
    group: ClipGroup,
    *,
    start: float = 0.0,
    end: float = 0.0,
    bookmarks: Sequence[Bookmark] = (),
    detected_events: Sequence[DetectedEvent] = (),
    include_sources: bool = False,
    exported_video: Optional[Path] = None,
    create_zip: bool = True,
) -> IncidentPackageResult:
    safe_name = "".join(char if char.isalnum() or char in "-_ " else "_" for char in title).strip() or "Incident"
    folder = destination_root / f"{group.timestamp}-{safe_name}"
    suffix = 2
    while folder.exists():
        folder = destination_root / f"{group.timestamp}-{safe_name}-{suffix}"
        suffix += 1
    sources = folder / "sources"
    exports = folder / "exports"
    folder.mkdir(parents=True)
    files: list[IncidentFile] = []
    for camera, source in sorted(group.cameras.items()):
        digest = sha256_file(source)
        if include_sources:
            copy_verified(source, sources / source.name)
        files.append(IncidentFile(camera, source.name, digest, source.stat().st_size, include_sources))
    if exported_video and exported_video.is_file():
        copy_verified(exported_video, exports / exported_video.name)
    manifest_payload = {
        "format": "cammetry-incident-v1",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "title": title,
        "notes": notes,
        "recording": {"timestamp": group.timestamp, "source_kind": group.source_kind, "camera_count": len(group.cameras)},
        "range_seconds": {"start": max(0.0, start), "end": max(start, end)},
        "files": [asdict(item) for item in files],
        "bookmarks": [asdict(item) for item in bookmarks],
        "detected_events": [asdict(item) for item in detected_events],
    }
    manifest = folder / "manifest.json"
    manifest.write_text(json.dumps(manifest_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    report = folder / "incident-report.html"
    report.write_text(_report_html(title, notes, group, start, end, files, bookmarks, detected_events), encoding="utf-8")
    archive = None
    if create_zip:
        archive = folder.with_suffix(".zip")
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as output:
            for path in folder.rglob("*"):
                if path.is_file():
                    output.write(path, path.relative_to(folder.parent))
    return IncidentPackageResult(folder, archive, manifest, report)
