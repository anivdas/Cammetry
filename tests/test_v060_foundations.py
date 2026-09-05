from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest import mock
from pathlib import Path

from tts_core import ClipGroup, TelemetrySample
from tts_event_detection import detect_events
from tts_incident import create_incident_package
from tts_library import ClipLibrary, copy_verified, sha256_file
from tts_privacy import PRIVACY_PRESETS
from tts_sequence import build_sequences
import tts_export_v051 as export


def group(root: Path, stamp: str, source: str = "Sentry") -> ClipGroup:
    folder = root / source / "event-a"
    folder.mkdir(parents=True, exist_ok=True)
    video = folder / f"{stamp}-front.mp4"
    video.write_bytes((stamp * 8).encode())
    return ClipGroup(stamp, folder, {"front": video}, source)


class SequenceTests(unittest.TestCase):
    def test_adjacent_groups_share_virtual_timeline(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            groups = [group(root, "2026-09-05_10-00-00"), group(root, "2026-09-05_10-01-00")]
            sequence = build_sequences(groups)[0]
            self.assertEqual(len(sequence.segments), 2)
            self.assertEqual(sequence.duration, 120.0)
            segment, local = sequence.locate(75.0)
            self.assertIs(segment.group, groups[1])
            self.assertEqual(local, 15.0)

    def test_non_adjacent_groups_are_separate(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            groups = [group(root, "2026-09-05_10-00-00"), group(root, "2026-09-05_10-05-00")]
            self.assertEqual(len(build_sequences(groups)), 2)


class EventDetectionTests(unittest.TestCase):
    def test_detects_braking_and_assistance_transition(self):
        samples = []
        for index in range(40):
            speed = max(0.0, 20.0 - max(0, index - 10) * 0.8)
            samples.append(TelemetrySample(vehicle_speed_mps=speed, autopilot_state=1 if index < 20 else 0))
        kinds = {event.kind for event in detect_events(samples, 10.0)}
        self.assertIn("hard_braking", kinds)
        self.assertIn("driver_assistance", kinds)


class LibraryTests(unittest.TestCase):
    def test_index_notes_bookmarks_and_verified_copy(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            clip = group(root, "2026-09-05_10-00-00")
            library = ClipLibrary(root / "library.sqlite3")
            recording_id = library.index_group(clip)
            library.update_recording(recording_id, title="Near miss", tags=["insurance", "review"], favorite=True)
            library.add_bookmark(recording_id, 12.5, "Brake")
            found = library.search("Near miss")
            self.assertEqual(found[0].tags, ("insurance", "review"))
            self.assertTrue(found[0].favorite)
            self.assertEqual(library.bookmarks(recording_id)[0].seconds, 12.5)
            copied = root / "copy.mp4"
            copy_verified(next(iter(clip.cameras.values())), copied)
            self.assertEqual(sha256_file(copied), sha256_file(next(iter(clip.cameras.values()))))


class IncidentTests(unittest.TestCase):
    def test_package_contains_manifest_report_and_hashes(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            clip = group(root, "2026-09-05_10-00-00")
            result = create_incident_package(root / "cases", "Road incident", "Test note", clip)
            manifest = json.loads(result.manifest.read_text(encoding="utf-8"))
            self.assertEqual(manifest["format"], "cammetry-incident-v1")
            self.assertEqual(len(manifest["files"][0]["sha256"]), 64)
            self.assertTrue(result.report.is_file())
            self.assertTrue(result.archive and result.archive.is_file())


class PrivacyTests(unittest.TestCase):
    def test_share_safe_removes_location_and_timestamp(self):
        class Options:
            show_timestamp = True
            show_minimap = True
            show_gps_text = True
            strip_metadata = False

        options = Options()
        PRIVACY_PRESETS["Share Safe"].apply(options)
        self.assertFalse(options.show_timestamp)
        self.assertFalse(options.show_minimap)
        self.assertFalse(options.show_gps_text)
        self.assertTrue(options.strip_metadata)

    def test_export_command_strips_metadata_by_default(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            clip = group(root, "2026-09-05_10-00-00")
            options = export.ExportOptions()
            with mock.patch.object(export, "probe_video", return_value=type("Info", (), {"width": 1280, "height": 960})()):
                command = export._build_command("ffmpeg", clip, ["front"], 0.0, 10.0, None, root / "hud.ass", root / "out.mp4", options, "libx264")
            self.assertIn("-map_metadata", command)
            self.assertIn("-map_chapters", command)


class BridgeAndWinUITests(unittest.TestCase):
    def test_bridge_ping_is_local_only(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, str(root / "cammetry_bridge.py")],
            input='{"id":9,"command":"ping"}\n', text=True, capture_output=True, check=True,
        )
        response = json.loads(result.stdout)
        self.assertTrue(response["ok"])
        self.assertTrue(response["result"]["localOnly"])

    def test_winui_shell_is_a_real_windows_app_sdk_project(self):
        root = Path(__file__).resolve().parents[1]
        project = root / "windows" / "Cammetry.WinUI" / "Cammetry.WinUI.csproj"
        text = project.read_text(encoding="utf-8")
        self.assertIn("<UseWinUI>true</UseWinUI>", text)
        self.assertIn("Microsoft.WindowsAppSDK", text)
        ET.parse(root / "windows" / "Cammetry.WinUI" / "Package.appxmanifest")


if __name__ == "__main__":
    unittest.main()
