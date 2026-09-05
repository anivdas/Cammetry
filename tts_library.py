from __future__ import annotations

"""Local, account-free recording library.

The database stores only user-authored organization metadata and source paths.
Importing uses verified copies and never edits the TeslaCam source drive.
"""

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from tts_core import ClipGroup
from tts_settings import settings_dir


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class LibraryRecording:
    id: int
    timestamp: str
    source_kind: str
    folder: str
    camera_count: int
    title: str
    notes: str
    tags: tuple[str, ...]
    favorite: bool
    reviewed: bool
    imported_folder: str


@dataclass(frozen=True)
class Bookmark:
    id: int
    recording_id: int
    seconds: float
    label: str
    note: str


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def copy_verified(source: Path, destination: Path) -> str:
    """Atomically copy a source file and verify its SHA-256 hash."""
    source = source.resolve()
    if source == destination.resolve():
        return sha256_file(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".partial", dir=destination.parent)
    os.close(fd)
    temp = Path(temp_name)
    try:
        shutil.copy2(source, temp)
        source_hash = sha256_file(source)
        if sha256_file(temp) != source_hash:
            raise IOError(f"Verification failed while copying {source.name}")
        temp.replace(destination)
        return source_hash
    finally:
        temp.unlink(missing_ok=True)


class ClipLibrary:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else settings_dir() / "library.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS recordings (
                    id INTEGER PRIMARY KEY,
                    source_key TEXT NOT NULL UNIQUE,
                    timestamp TEXT NOT NULL,
                    source_kind TEXT NOT NULL,
                    folder TEXT NOT NULL,
                    camera_count INTEGER NOT NULL,
                    cameras_json TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    favorite INTEGER NOT NULL DEFAULT 0,
                    reviewed INTEGER NOT NULL DEFAULT 0,
                    imported_folder TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS recordings_timestamp ON recordings(timestamp DESC);
                CREATE TABLE IF NOT EXISTS bookmarks (
                    id INTEGER PRIMARY KEY,
                    recording_id INTEGER NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
                    seconds REAL NOT NULL,
                    label TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS bookmarks_recording ON bookmarks(recording_id, seconds);
                CREATE TABLE IF NOT EXISTS incidents (
                    id INTEGER PRIMARY KEY,
                    recording_id INTEGER NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    start_seconds REAL NOT NULL DEFAULT 0,
                    end_seconds REAL NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                PRAGMA user_version=1;
                """
            )

    @staticmethod
    def source_key(group: ClipGroup) -> str:
        raw = f"{group.folder.resolve()}\0{group.timestamp}".encode("utf-8", "surrogatepass")
        return hashlib.sha256(raw).hexdigest()

    def index_group(self, group: ClipGroup) -> int:
        now = time.time()
        cameras = {name: str(path.resolve()) for name, path in group.cameras.items()}
        key = self.source_key(group)
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO recordings (
                    source_key, timestamp, source_kind, folder, camera_count,
                    cameras_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_key) DO UPDATE SET
                    source_kind=excluded.source_kind,
                    folder=excluded.folder,
                    camera_count=excluded.camera_count,
                    cameras_json=excluded.cameras_json,
                    updated_at=excluded.updated_at
                """,
                (key, group.timestamp, group.source_kind, str(group.folder.resolve()), len(cameras), json.dumps(cameras), now, now),
            )
            row = db.execute("SELECT id FROM recordings WHERE source_key=?", (key,)).fetchone()
            return int(row["id"])

    def index_groups(self, groups: Iterable[ClipGroup]) -> int:
        count = 0
        for group in groups:
            self.index_group(group)
            count += 1
        return count

    def recording_id(self, group: ClipGroup) -> Optional[int]:
        with self._connect() as db:
            row = db.execute("SELECT id FROM recordings WHERE source_key=?", (self.source_key(group),)).fetchone()
            return int(row["id"]) if row else None

    @staticmethod
    def _recording(row: sqlite3.Row) -> LibraryRecording:
        try:
            tags = tuple(str(item) for item in json.loads(row["tags_json"]) if str(item).strip())
        except Exception:
            tags = ()
        return LibraryRecording(
            id=int(row["id"]), timestamp=str(row["timestamp"]), source_kind=str(row["source_kind"]),
            folder=str(row["folder"]), camera_count=int(row["camera_count"]), title=str(row["title"]),
            notes=str(row["notes"]), tags=tags, favorite=bool(row["favorite"]),
            reviewed=bool(row["reviewed"]), imported_folder=str(row["imported_folder"]),
        )

    def search(self, query: str = "", *, favorites_only: bool = False, limit: int = 500) -> list[LibraryRecording]:
        clauses = []
        values: list[object] = []
        if query.strip():
            clauses.append("(timestamp LIKE ? OR source_kind LIKE ? OR title LIKE ? OR notes LIKE ? OR tags_json LIKE ?)")
            needle = f"%{query.strip()}%"
            values.extend([needle] * 5)
        if favorites_only:
            clauses.append("favorite=1")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        values.append(max(1, min(int(limit), 5000)))
        with self._connect() as db:
            rows = db.execute(f"SELECT * FROM recordings{where} ORDER BY timestamp DESC LIMIT ?", values).fetchall()
        return [self._recording(row) for row in rows]

    def update_recording(
        self,
        recording_id: int,
        *,
        title: Optional[str] = None,
        notes: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        favorite: Optional[bool] = None,
        reviewed: Optional[bool] = None,
    ) -> None:
        changes: dict[str, object] = {"updated_at": time.time()}
        if title is not None:
            changes["title"] = title.strip()
        if notes is not None:
            changes["notes"] = notes.strip()
        if tags is not None:
            changes["tags_json"] = json.dumps(sorted({str(tag).strip() for tag in tags if str(tag).strip()}))
        if favorite is not None:
            changes["favorite"] = int(favorite)
        if reviewed is not None:
            changes["reviewed"] = int(reviewed)
        assignments = ", ".join(f"{name}=?" for name in changes)
        with self._connect() as db:
            db.execute(f"UPDATE recordings SET {assignments} WHERE id=?", (*changes.values(), int(recording_id)))

    def add_bookmark(self, recording_id: int, seconds: float, label: str, note: str = "") -> int:
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO bookmarks(recording_id, seconds, label, note, created_at) VALUES (?, ?, ?, ?, ?)",
                (int(recording_id), max(0.0, float(seconds)), label.strip() or "Bookmark", note.strip(), time.time()),
            )
            return int(cursor.lastrowid)

    def bookmarks(self, recording_id: int) -> list[Bookmark]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM bookmarks WHERE recording_id=? ORDER BY seconds", (int(recording_id),)).fetchall()
        return [Bookmark(int(row["id"]), int(row["recording_id"]), float(row["seconds"]), str(row["label"]), str(row["note"])) for row in rows]

    def create_incident(self, recording_id: int, title: str, start: float, end: float, notes: str = "") -> int:
        now = time.time()
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO incidents(recording_id,title,notes,start_seconds,end_seconds,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                (int(recording_id), title.strip() or "Incident", notes.strip(), max(0.0, start), max(start, end), now, now),
            )
            return int(cursor.lastrowid)

    def import_group(self, group: ClipGroup, destination_root: Path) -> tuple[Path, dict[str, str]]:
        destination = destination_root / group.source_kind / group.timestamp
        hashes: dict[str, str] = {}
        for camera, source in group.cameras.items():
            hashes[camera] = copy_verified(source, destination / source.name)
        recording_id = self.index_group(group)
        with self._connect() as db:
            db.execute("UPDATE recordings SET imported_folder=?, updated_at=? WHERE id=?", (str(destination), time.time(), recording_id))
        return destination, hashes
