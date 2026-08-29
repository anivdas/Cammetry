import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReleaseGateTests(unittest.TestCase):
    def test_windows_ffmpeg_is_pinned_not_moving_master(self):
        text = (ROOT / "Build-Release.ps1").read_text(encoding="utf-8")
        self.assertIn("n7.1-62-gb168ed9b14", text)
        self.assertIn("autobuild-2024-12-31-13-02", text)
        self.assertNotIn("ffmpeg-master-latest", text)
        self.assertIn("makensis /WX".lower(), text.lower().replace('"', ''))

    def test_installer_has_all_component_description_fallbacks(self):
        text = (ROOT / "installer" / "Cammetry.nsi").read_text(encoding="utf-8")
        languages = (
            "ENGLISH", "SPANISH", "FRENCH", "GERMAN", "SIMPCHINESE", "JAPANESE",
            "KOREAN", "PORTUGUESE", "RUSSIAN", "ITALIAN", "DUTCH", "POLISH", "TURKISH",
        )
        for language in languages:
            self.assertIn(f"LangString DESC_SecMain ${{LANG_{language}}}", text)
            self.assertIn(f"LangString DESC_SecDesktop ${{LANG_{language}}}", text)
        self.assertIn("tasklist.exe", text)
        self.assertIn("taskkill.exe", text)

    def test_windows_beta_artifacts_are_split(self):
        text = (ROOT / ".github" / "workflows" / "windows-release.yml").read_text(encoding="utf-8")
        self.assertIn("Cammetry-Setup-v0.5.1-UNSIGNED-BETA", text)
        self.assertIn("Cammetry-Portable-EXE-v0.5.1-UNSIGNED-BETA", text)
        self.assertIn("Cammetry-Portable-ZIP-v0.5.1-UNSIGNED-BETA", text)
        self.assertNotIn("name: Cammetry-Windows-v0.5.1-UNSIGNED-BETA", text)

    def test_release_entrypoint_uses_final_ui_layer(self):
        text = (ROOT / "cammetry.py").read_text(encoding="utf-8")
        self.assertIn('APP_VERSION = "0.5.1"', text)
        self.assertIn("from tts_final_ui import App", text)


if __name__ == "__main__":
    unittest.main()
