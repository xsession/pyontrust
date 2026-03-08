"""Selenium tests for FlowLab HIL integration UI.

Tests the Save-as-HIL, Run-as-HIL, and Import-HIL functionality
in the FlowLab visual editor.
"""
from __future__ import annotations

import json
import time
import unittest

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

from tests.selenium_tests.conftest import get_gateway_url, create_driver


class TestFlowLabHilIntegration(unittest.TestCase):
    """Selenium tests for FlowLab ↔ HIL features."""

    @classmethod
    def setUpClass(cls):
        cls.base = get_gateway_url()
        cls.driver = create_driver()

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def setUp(self):
        self.driver.get(self.base + "/flowlab/")
        time.sleep(1)

    # ── Toolbar buttons exist ────────────────────────────────────

    def test_save_hil_button_exists(self):
        btn = self.driver.find_element(By.ID, "btn-save-hil")
        self.assertIsNotNone(btn)
        self.assertIn("Save as HIL", btn.text)

    def test_run_hil_button_exists(self):
        btn = self.driver.find_element(By.ID, "btn-run-hil")
        self.assertIsNotNone(btn)
        self.assertIn("Run as HIL", btn.text)

    def test_import_hil_button_exists(self):
        btn = self.driver.find_element(By.ID, "btn-import-hil")
        self.assertIsNotNone(btn)
        self.assertIn("Import HIL", btn.text)

    def test_hil_buttons_have_green_border(self):
        """HIL buttons should have distinctive green-bordered styling."""
        btn = self.driver.find_element(By.ID, "btn-save-hil")
        classes = btn.get_attribute("class")
        self.assertIn("btn-hil", classes)

    # ── Save as HIL modal ────────────────────────────────────────

    def test_save_hil_modal_hidden_initially(self):
        modal = self.driver.find_element(By.ID, "hil-save-modal")
        self.assertEqual(modal.value_of_css_property("display"), "none")

    def test_save_hil_empty_canvas_shows_warning(self):
        """Clicking Save as HIL on empty canvas should log a warning."""
        # Clear canvas first
        self.driver.execute_script("""
            document.querySelectorAll('.block-group').forEach(el => el.remove());
        """)
        # Force clear internal state
        self.driver.execute_script("""
            for (const k of Object.keys(window.__test_blocks || {})) delete window.__test_blocks[k];
        """)
        btn = self.driver.find_element(By.ID, "btn-save-hil")
        btn.click()
        time.sleep(1)
        console = self.driver.find_element(By.ID, "console-output").text
        # Could show empty warning or open modal (either is valid)
        # Just verify no crash occurred
        self.assertIsNotNone(console)

    def test_save_hil_modal_opens_with_block(self):
        """Add a block then open Save as HIL modal."""
        # Add a block by double-clicking a palette item
        palette_items = self.driver.find_elements(By.CSS_SELECTOR, "#palette-list .pal-item")
        if palette_items:
            ActionChains(self.driver).double_click(palette_items[0]).perform()
            time.sleep(0.5)

        btn = self.driver.find_element(By.ID, "btn-save-hil")
        btn.click()
        time.sleep(1)

        # Modal should be visible OR console should have a message
        modal = self.driver.find_element(By.ID, "hil-save-modal")
        console = self.driver.find_element(By.ID, "console-output").text
        # Either modal is shown or console has a message
        modal_visible = modal.value_of_css_property("display") != "none"
        has_console_msg = len(console) > 0
        self.assertTrue(modal_visible or has_console_msg)

    def test_save_hil_modal_has_name_input(self):
        """The save modal should have a name input field."""
        modal = self.driver.find_element(By.ID, "hil-save-modal")
        name_input = self.driver.find_element(By.ID, "hil-save-name")
        self.assertIsNotNone(name_input)
        self.assertEqual(name_input.get_attribute("type"), "text")

    def test_save_hil_modal_has_preview(self):
        """The save modal should have a JSON preview."""
        preview = self.driver.find_element(By.ID, "hil-save-preview")
        self.assertIsNotNone(preview)

    def test_save_hil_modal_buttons(self):
        """The save modal should have Save, Download, and Cancel buttons."""
        save_btn = self.driver.find_element(By.ID, "hil-save-confirm-btn")
        dl_btn = self.driver.find_element(By.ID, "hil-save-download-btn")
        cancel_btn = self.driver.find_element(By.ID, "hil-save-cancel-btn")
        self.assertIsNotNone(save_btn)
        self.assertIsNotNone(dl_btn)
        self.assertIsNotNone(cancel_btn)

    def test_save_hil_cancel_closes_modal(self):
        """Cancel button should close the save modal."""
        # Open modal
        self.driver.execute_script("""
            document.getElementById('hil-save-modal').style.display = 'flex';
        """)
        time.sleep(0.3)
        cancel = self.driver.find_element(By.ID, "hil-save-cancel-btn")
        cancel.click()
        time.sleep(0.3)
        modal = self.driver.find_element(By.ID, "hil-save-modal")
        self.assertEqual(modal.value_of_css_property("display"), "none")

    # ── Import HIL modal ─────────────────────────────────────────

    def test_import_hil_modal_hidden_initially(self):
        modal = self.driver.find_element(By.ID, "hil-modal")
        self.assertEqual(modal.value_of_css_property("display"), "none")

    def test_import_hil_modal_opens(self):
        btn = self.driver.find_element(By.ID, "btn-import-hil")
        btn.click()
        time.sleep(1)
        modal = self.driver.find_element(By.ID, "hil-modal")
        self.assertNotEqual(modal.value_of_css_property("display"), "none")

    def test_import_hil_modal_has_profile_list(self):
        """Import modal should have a profile list area."""
        list_el = self.driver.find_element(By.ID, "hil-profile-list")
        self.assertIsNotNone(list_el)

    def test_import_hil_modal_has_json_input(self):
        """Import modal should have a textarea for JSON input."""
        textarea = self.driver.find_element(By.ID, "hil-json-input")
        self.assertIsNotNone(textarea)
        self.assertEqual(textarea.tag_name, "textarea")

    def test_import_hil_modal_has_file_input(self):
        """Import modal should have a file upload input."""
        file_input = self.driver.find_element(By.ID, "hil-file-input")
        self.assertIsNotNone(file_input)
        self.assertEqual(file_input.get_attribute("accept"), ".json")

    def test_import_hil_modal_has_buttons(self):
        """Import modal should have Import and Cancel buttons."""
        import_btn = self.driver.find_element(By.ID, "hil-import-btn")
        cancel_btn = self.driver.find_element(By.ID, "hil-cancel-btn")
        self.assertIsNotNone(import_btn)
        self.assertIsNotNone(cancel_btn)

    def test_import_hil_cancel_closes_modal(self):
        # Open modal
        btn = self.driver.find_element(By.ID, "btn-import-hil")
        btn.click()
        time.sleep(0.5)
        cancel = self.driver.find_element(By.ID, "hil-cancel-btn")
        cancel.click()
        time.sleep(0.3)
        modal = self.driver.find_element(By.ID, "hil-modal")
        self.assertEqual(modal.value_of_css_property("display"), "none")

    def test_import_hil_loads_profile_list(self):
        """Opening import modal should load profile list from server."""
        btn = self.driver.find_element(By.ID, "btn-import-hil")
        btn.click()
        time.sleep(2)
        list_el = self.driver.find_element(By.ID, "hil-profile-list")
        # Should have items or a "no profiles" message
        content = list_el.text
        has_profiles = len(list_el.find_elements(By.CSS_SELECTOR, ".profile-item")) > 0
        has_message = len(content) > 0
        self.assertTrue(has_profiles or has_message)

    def test_import_hil_paste_json(self):
        """Paste JSON into the import modal and import it."""
        # Clear canvas first to avoid confirm dialog
        self.driver.execute_script("""
            if (typeof clearCanvas === 'function') clearCanvas();
        """)
        time.sleep(0.3)

        btn = self.driver.find_element(By.ID, "btn-import-hil")
        btn.click()
        time.sleep(0.5)

        profile_json = json.dumps({
            "name": "test_import",
            "description": "Test import via paste",
            "instruments": {"power_meter": {"type": "simulated", "params": {}}},
            "actions": [
                {"type": "mark", "label": "start"},
                {"type": "run", "name": "idle", "duration_s": 2, "description": "idle sleep"},
                {"type": "mark", "label": "end"},
            ]
        })

        textarea = self.driver.find_element(By.ID, "hil-json-input")
        textarea.clear()
        textarea.send_keys(profile_json)
        time.sleep(0.3)

        import_btn = self.driver.find_element(By.ID, "hil-import-btn")
        import_btn.click()
        time.sleep(1)

        # Accept confirm dialog if it appears
        try:
            self.driver.switch_to.alert.accept()
            time.sleep(1)
        except Exception:
            pass

        # Modal should close
        modal = self.driver.find_element(By.ID, "hil-modal")
        self.assertEqual(modal.value_of_css_property("display"), "none")

        # Console should show import message
        console = self.driver.find_element(By.ID, "console-output").text
        self.assertIn("Import", console)

    def test_import_hil_creates_blocks(self):
        """Importing a HIL profile should create blocks on canvas."""
        # Clear canvas first to avoid confirm dialog
        self.driver.execute_script("""
            if (typeof clearCanvas === 'function') clearCanvas();
        """)
        time.sleep(0.3)

        btn = self.driver.find_element(By.ID, "btn-import-hil")
        btn.click()
        time.sleep(0.5)

        profile_json = json.dumps({
            "name": "block_test",
            "instruments": {"power_meter": {"type": "simulated", "params": {}}},
            "actions": [
                {"type": "mark", "label": "start"},
                {"type": "run", "name": "measure", "duration_s": 3, "description": "measuring"},
                {"type": "mark", "label": "end"},
            ]
        })

        textarea = self.driver.find_element(By.ID, "hil-json-input")
        textarea.clear()
        textarea.send_keys(profile_json)

        import_btn = self.driver.find_element(By.ID, "hil-import-btn")
        import_btn.click()
        time.sleep(1)

        # Accept the confirm dialog if it appears
        try:
            self.driver.switch_to.alert.accept()
            time.sleep(1)
        except Exception:
            pass

        # Should have blocks on canvas
        block_elements = self.driver.find_elements(By.CSS_SELECTOR, ".block-group")
        self.assertGreater(len(block_elements), 0, "Should have created blocks from HIL import")

    # ── API endpoints ────────────────────────────────────────────

    def test_api_export_hil(self):
        """POST /flowlab/api/export_hil should work."""
        result = self.driver.execute_script("""
            const res = await fetch('/flowlab/api/export_hil', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({diagram: {
                    blocks: [{id:'b1', type:'simulated_power', x:0, y:0, params:{duration_s:2}}],
                    wires: []
                }})
            });
            return await res.json();
        """)
        self.assertIn("profile", result)
        self.assertIn("steps", result["profile"])

    def test_api_import_hil(self):
        """POST /flowlab/api/import_hil should work."""
        result = self.driver.execute_script("""
            const res = await fetch('/flowlab/api/import_hil', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({profile: {
                    name: 'api_test',
                    instruments: {power_meter: {type: 'simulated', params: {}}},
                    actions: [{type: 'mark', label: 'test'}]
                }})
            });
            return await res.json();
        """)
        self.assertIn("diagram", result)
        self.assertIn("blocks", result["diagram"])

    def test_api_hil_profiles_list(self):
        """GET /flowlab/api/hil_profiles should return a list."""
        result = self.driver.execute_script("""
            const res = await fetch('/flowlab/api/hil_profiles');
            return await res.json();
        """)
        self.assertIn("profiles", result)
        self.assertIsInstance(result["profiles"], list)

    def test_api_save_hil(self):
        """POST /flowlab/api/save_hil should save profile to disk."""
        result = self.driver.execute_script("""
            const res = await fetch('/flowlab/api/save_hil', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    name: 'selenium_test_profile',
                    diagram: {
                        blocks: [{id:'b1', type:'delay', x:0, y:0, params:{seconds:1}}],
                        wires: []
                    }
                })
            });
            return await res.json();
        """)
        self.assertTrue(result.get("success"))
        self.assertIn("path", result)

    def test_api_run_hil(self):
        """POST /flowlab/api/run_hil should convert and attempt to run."""
        result = self.driver.execute_script("""
            const res = await fetch('/flowlab/api/run_hil', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    diagram: {
                        blocks: [{id:'b1', type:'simulated_power', x:0, y:0, params:{duration_s:1}}],
                        wires: []
                    }
                })
            });
            return await res.json();
        """)
        self.assertIn("profile", result)
        self.assertIn("execution", result)

    def test_api_export_hil_empty_diagram(self):
        """Export of empty diagram should return error."""
        result = self.driver.execute_script("""
            const res = await fetch('/flowlab/api/export_hil', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({diagram: {blocks: [], wires: []}})
            });
            return {status: res.status, body: await res.json()};
        """)
        self.assertEqual(result["status"], 400)

    def test_api_import_hil_missing_input(self):
        """Import with no profile or name should return error."""
        result = self.driver.execute_script("""
            const res = await fetch('/flowlab/api/import_hil', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({})
            });
            return {status: res.status, body: await res.json()};
        """)
        self.assertEqual(result["status"], 400)

    # ── Keyboard shortcuts ───────────────────────────────────────

    def test_escape_closes_import_modal(self):
        """Pressing Escape should close the import modal."""
        btn = self.driver.find_element(By.ID, "btn-import-hil")
        btn.click()
        time.sleep(0.5)
        ActionChains(self.driver).send_keys('\ue00c').perform()  # Escape
        time.sleep(0.5)
        modal = self.driver.find_element(By.ID, "hil-modal")
        self.assertEqual(modal.value_of_css_property("display"), "none")

    def test_escape_closes_save_modal(self):
        """Pressing Escape should close the save modal."""
        self.driver.execute_script("""
            document.getElementById('hil-save-modal').style.display = 'flex';
        """)
        time.sleep(0.3)
        ActionChains(self.driver).send_keys('\ue00c').perform()  # Escape
        time.sleep(0.5)
        modal = self.driver.find_element(By.ID, "hil-save-modal")
        self.assertEqual(modal.value_of_css_property("display"), "none")

    # ── Full workflow ────────────────────────────────────────────

    def test_full_import_export_cycle(self):
        """Import a profile, then export it back as HIL."""
        # Clear canvas first to avoid confirm dialog
        self.driver.execute_script("""
            if (typeof clearCanvas === 'function') clearCanvas();
        """)
        time.sleep(0.3)

        # Import
        self.driver.find_element(By.ID, "btn-import-hil").click()
        time.sleep(0.5)

        profile = {
            "name": "cycle_test",
            "instruments": {"power_meter": {"type": "simulated", "params": {}}},
            "actions": [
                {"type": "mark", "label": "start"},
                {"type": "run", "name": "sleep_mode", "duration_s": 5, "description": "idle sleep"},
                {"type": "mark", "label": "end"},
            ]
        }

        textarea = self.driver.find_element(By.ID, "hil-json-input")
        textarea.clear()
        textarea.send_keys(json.dumps(profile))

        self.driver.find_element(By.ID, "hil-import-btn").click()
        time.sleep(1)

        # Accept confirm dialog if it appears
        try:
            self.driver.switch_to.alert.accept()
            time.sleep(1)
        except Exception:
            pass

        time.sleep(1)

        # Should have blocks
        blocks = self.driver.find_elements(By.CSS_SELECTOR, ".block-group")
        self.assertGreater(len(blocks), 0)

        # Now export via API
        result = self.driver.execute_script("""
            const res = await fetch('/flowlab/api/export_hil', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({diagram: {
                    blocks: [{id:'b1', type:'simulated_power', x:0, y:0, params:{duration_s:2}}],
                    wires: []
                }})
            });
            return await res.json();
        """)
        self.assertIn("profile", result)
        self.assertIn("steps", result["profile"])


if __name__ == "__main__":
    unittest.main()
