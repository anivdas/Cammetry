from __future__ import annotations

import unittest
from unittest.mock import patch

import tts_export_v051 as export


class V051ExportRegressionTests(unittest.TestCase):
    def test_ass_dialogue_includes_name_and_effect_fields(self):
        line = export._dialogue("0:00:00.00", "0:00:00.10", "Speed", "34 MPH")
        self.assertEqual(
            line,
            "Dialogue: 0,0:00:00.00,0:00:00.10,Speed,,0,0,0,,34 MPH\n",
        )
        # This exact field shape prevents telemetry text from being interpreted
        # as an ASS margin/effect value and silently disappearing.
        self.assertEqual(line.split(",", 9)[-1], "34 MPH\n")

    @patch.object(export, "available_encoders", return_value=["CPU x264"])
    def test_auto_falls_back_to_cpu_when_no_hardware_encoder_is_usable(self, _mock):
        display, codec = export.resolve_encoder("Auto")
        self.assertEqual(display, "CPU x264")
        self.assertEqual(codec, "libx264")

    @patch.object(export, "available_encoders", return_value=["NVIDIA NVENC", "CPU x264"])
    def test_auto_prefers_a_runtime_verified_hardware_encoder(self, _mock):
        display, codec = export.resolve_encoder("Auto")
        self.assertEqual(display, "NVIDIA NVENC")
        self.assertEqual(codec, "h264_nvenc")

    @patch.object(export, "available_encoders", return_value=["CPU x264"])
    def test_explicit_unusable_hardware_request_degrades_to_cpu(self, _mock):
        display, codec = export.resolve_encoder("NVIDIA NVENC")
        self.assertEqual(display, "CPU x264")
        self.assertEqual(codec, "libx264")


if __name__ == "__main__":
    unittest.main()
