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

    def test_development_entrypoint_uses_v060_ui_layer(self):
        text = (ROOT / "cammetry.py").read_text(encoding="utf-8")
        self.assertIn('APP_VERSION = "0.6.0-dev"', text)
        self.assertIn("from tts_v060_ui import App", text)

    def test_event_browser_tree_and_scrollbar_share_the_same_parent(self):
        text = (ROOT / "tts_final_ui.py").read_text(encoding="utf-8")
        self.assertIn("self.event_tree = ttk.Treeview(\n            treebox,", text)
        self.assertIn("scroll = ttk.Scrollbar(treebox", text)

    def test_final_ui_uses_accessible_checkbox_indicators(self):
        text = (ROOT / "tts_final_ui.py").read_text(encoding="utf-8")
        self.assertIn("AccessibleCheck", text)
        self.assertIn("upgrade_native_checkbuttons(export_dialog)", text)
        self.assertIn("Apply image adjustments to exported video", text)

    def test_tools_and_vehicle_view_are_in_app_single_instance_overlays(self):
        text = (ROOT / "tts_beta_ui.py").read_text(encoding="utf-8")
        self.assertIn("self._tools_overlay", text)
        self.assertIn("self._vehicle_overlay", text)
        self.assertIn('panel = tk.Frame(', text)
        self.assertNotIn('panel = tk.Toplevel(', text)
        self.assertIn('panel.tkraise()', text)
        self.assertIn('Recording profile:', text)
        self.assertIn('pseudo-isometric EV silhouette', text)

    def test_transport_is_actually_wired_into_active_hotfix_layer(self):
        transport = (ROOT / "tts_transport_polish.py").read_text(encoding="utf-8")
        live = (ROOT / "tts_transport_live.py").read_text(encoding="utf-8")
        hotfix = (ROOT / "tts_hotfix_ui.py").read_text(encoding="utf-8")
        self.assertIn("class TransportSeekButton", transport)
        self.assertIn("Curved seek glyph", transport)
        self.assertIn("0.025", transport)
        self.assertIn("<ButtonRelease-1>", transport)
        self.assertIn("class PlaybackSpeedButton", live)
        self.assertIn('f"Speed  {_format_speed', live)
        self.assertIn("SPEEDS = (0.5, 1.0, 2.0, 4.0)", live)
        self.assertIn("modernize_transport_row(self)", hotfix)
        self.assertIn("install_button_interaction_polish()", hotfix)

    def test_hardware_encoder_probe_uses_normal_video_dimensions(self):
        text = (ROOT / "tts_ui_polish.py").read_text(encoding="utf-8")
        self.assertIn("s=640x360", text)
        self.assertNotIn("s=64x64", text)
        self.assertIn("tts_export_v051._encoder_smoke_test = robust_encoder_smoke_test", text)

    def test_export_progress_is_integrated_in_main_window(self):
        text = (ROOT / "tts_next_ui.py").read_text(encoding="utf-8")
        self.assertIn("self.export_inline", text)
        self.assertIn('"Open file"', text)
        self.assertIn('"Show in folder"', text)
        self.assertIn('"Diagnostics"', text)
        self.assertIn("def _poll_worker", text)
        self.assertNotIn("messagebox.showinfo", text)
        self.assertNotIn("messagebox.showerror", text)

    def test_export_has_watchdog_phase_progress_and_cancel(self):
        guard = (ROOT / "tts_export_guard.py").read_text(encoding="utf-8")
        ui = (ROOT / "tts_hotfix_ui.py").read_text(encoding="utf-8")
        self.assertIn("no encoding timestamp within 25 seconds", guard)
        self.assertIn("made no progress for 45 seconds", guard)
        self.assertIn('progress_cb(0.03, "Checking encoder")', guard)
        self.assertIn('progress_cb(0.08, "Preparing map overlay")', guard)
        self.assertIn("tts_release_ui.export_video = guarded_export_video", guard)
        self.assertIn('"Cancel export"', ui)
        self.assertIn("cancel_active_export()", ui)

    def test_hud_uses_fixed_positions_and_nonoverlapping_intervals(self):
        text = (ROOT / "tts_hud.py").read_text(encoding="utf-8")
        self.assertIn("\\\\pos(", text)
        self.assertIn("Do not overlap adjacent events", text)
        self.assertNotIn("+ 0.015", text)
        self.assertIn("_gear_name", text)
        self.assertIn("BLUE if assist_active", text)

    def test_export_map_modes_include_off_streets_and_satellite(self):
        text = (ROOT / "tts_map_export.py").read_text(encoding="utf-8")
        self.assertIn('MAP_STYLES = ("Off", "Route only", "Street map", "Satellite")', text)
        self.assertIn("build_osm_mosaic", text)
        self.assertIn("satellite-v4", text)
        self.assertIn("© MapTiler", text)

    def test_export_map_size_and_position_controls_are_wired(self):
        layout = (ROOT / "tts_export_layout_polish.py").read_text(encoding="utf-8")
        ui = (ROOT / "tts_hotfix_ui.py").read_text(encoding="utf-8")
        self.assertIn('MAP_SIZES = ("Small", "Medium", "Large")', layout)
        self.assertIn('MAP_POSITIONS = ("Top right", "Top left", "Bottom right", "Bottom left")', layout)
        self.assertIn('"Map size"', ui)
        self.assertIn('"Map position"', ui)
        self.assertIn("configure_map_layout(size, position)", ui)

    def test_encrypted_clips_are_not_treated_as_playable(self):
        text = (ROOT / "tts_next_ui.py").read_text(encoding="utf-8")
        self.assertIn('"encryptedclips" not in', text)
        self.assertIn("Decrypt with Tesla", text)
        self.assertIn("https://dashcam.tesla.com", text)
        self.assertIn("does not request or store", text)

    def test_ci_compiles_all_beta_layers(self):
        text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        for module in (
            "tts_ui_polish.py", "tts_hud.py", "tts_map_export.py", "tts_next_ui.py",
            "tts_beta_ui.py", "tts_export_guard.py", "tts_hotfix_ui.py", "tts_transport_polish.py",
            "tts_transport_live.py", "tts_export_layout_polish.py",
        ):
            self.assertIn(module, text)


if __name__ == "__main__":
    unittest.main()
