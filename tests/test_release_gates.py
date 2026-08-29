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

    def test_event_browser_tree_and_scrollbar_share_the_same_parent(self):
        text = (ROOT / "tts_final_ui.py").read_text(encoding="utf-8")
        self.assertIn("self.event_tree = ttk.Treeview(\n            treebox,", text)
        self.assertIn("scroll = ttk.Scrollbar(treebox", text)

    def test_final_ui_uses_accessible_checkbox_indicators(self):
        text = (ROOT / "tts_final_ui.py").read_text(encoding="utf-8")
        self.assertIn("AccessibleCheck", text)
        self.assertIn("upgrade_native_checkbuttons(export_dialog)", text)
        self.assertIn("Apply image adjustments to exported video", text)

    def test_final_ui_replaces_classic_more_menu(self):
        text = (ROOT / "tts_final_ui.py").read_text(encoding="utf-8")
        self.assertIn('flat_button(parent, "Settings", self.open_settings)', text)
        self.assertIn('flat_button(parent, "Tools", self.show_tools_panel)', text)
        self.assertNotIn("tk.Menu(", text)

    def test_hardware_encoder_probe_uses_normal_video_dimensions(self):
        text = (ROOT / "tts_ui_polish.py").read_text(encoding="utf-8")
        self.assertIn("s=640x360", text)
        self.assertNotIn("s=64x64", text)
        self.assertIn("tts_export_v051._encoder_smoke_test = robust_encoder_smoke_test", text)

    def test_export_progress_is_integrated_not_a_floating_toast(self):
        text = (ROOT / "tts_ui_polish.py").read_text(encoding="utf-8")
        self.assertIn("def build_inline_status", text)
        self.assertIn('flat_button(self._export_inline, "Open file"', text)
        self.assertIn('flat_button(self._export_inline, "Show in folder"', text)
        self.assertIn("tts_ui.App._show_export_toast = show_export_inline", text)
        self.assertIn("tts_ui.App._poll_worker = inline_poll_worker", text)
        self.assertNotIn("messagebox.showinfo", text)
        self.assertNotIn("messagebox.showerror", text)

    def test_ci_compiles_ui_polish_module(self):
        text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("tts_ui_polish.py", text)


if __name__ == "__main__":
    unittest.main()
