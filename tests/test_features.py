import unittest
from unittest.mock import patch

from tts_locales import event_reason_key
from tts_export import resolve_encoder
from tts_map import choose_zoom


class FeatureTests(unittest.TestCase):
    def test_event_reason_mapping(self):
        self.assertEqual(event_reason_key("honk"), "event_honk")
        self.assertEqual(event_reason_key("camera_based_detection"), "event_object")
        self.assertEqual(event_reason_key("manual_save"), "event_manual_save")

    def test_apple_encoder_mapping(self):
        with patch("tts_export.available_encoders", return_value=["Apple VideoToolbox", "CPU x264"]):
            display_name, codec = resolve_encoder("Apple VideoToolbox")
        self.assertEqual(display_name, "Apple VideoToolbox")
        self.assertEqual(codec, "h264_videotoolbox")

    def test_map_zoom_selection_is_bounded(self):
        choice = choose_zoom([(30.50, -97.65), (30.51, -97.64)])
        self.assertIsNotNone(choice)
        zoom, x0, x1, y0, y1 = choice
        self.assertGreaterEqual(zoom, 8)
        self.assertLessEqual(zoom, 17)
        self.assertLessEqual(x0, x1)
        self.assertLessEqual(y0, y1)


if __name__ == "__main__":
    unittest.main()
