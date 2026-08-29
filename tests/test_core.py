import unittest

from tts_core import TelemetrySample


class TelemetrySampleTests(unittest.TestCase):
    def test_speed_conversion(self):
        sample = TelemetrySample(vehicle_speed_mps=20.0)
        self.assertAlmostEqual(sample.speed_mph, 44.7387, places=3)
        self.assertAlmostEqual(sample.speed_kph, 72.0, places=3)


if __name__ == "__main__":
    unittest.main()
