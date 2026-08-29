import unittest
from pathlib import Path

from tts_player import MultiCameraPlayer


ROOT = Path(__file__).resolve().parents[1]


class V051PreviewPerformanceTests(unittest.TestCase):
    def test_player_can_decode_only_requested_visible_cameras(self):
        player = MultiCameraPlayer()
        player.captures = {"front": object(), "back": object(), "left_repeater": object()}
        called = []

        def fake_read(camera, target_seconds):
            called.append((camera, target_seconds))
            return f"frame-{camera}"

        player._read_camera_frame = fake_read  # type: ignore[method-assign]
        frames = player.get_frames(3.25, cameras=["front"])

        self.assertEqual(frames, {"front": "frame-front"})
        self.assertEqual(called, [("front", 3.25)])

    def test_final_ui_exposes_image_adjustment_export_toggle(self):
        text = (ROOT / "tts_final_ui.py").read_text(encoding="utf-8")
        self.assertIn("Apply image adjustments to exported video", text)
        self.assertIn("options.apply_image_adjustments = enabled", text)

    def test_final_ui_requests_only_visible_camera_frames(self):
        text = (ROOT / "tts_final_ui.py").read_text(encoding="utf-8")
        self.assertIn("visible_cameras = [", text)
        self.assertIn("cameras=visible_cameras", text)


if __name__ == "__main__":
    unittest.main()
