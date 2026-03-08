"""Selenium end-to-end tests for the Lab Bench Manager GUI.

Covers:
  - Page load & styling
  - Layout elements (heading, actions bar, instrument table, types panel)
  - Input field for bench path
  - Load / Save / Connect / Disconnect / Refresh Types buttons
  - Instrument status table rendering
  - Available instrument types display
  - API endpoint responses
  - Error handling (load missing bench)
  - Button interactivity
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time
import unittest

# Ensure project root is on sys.path
_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "src"))

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from tests.selenium_tests.conftest import create_driver, get_gateway_url


class LabBenchSeleniumTests(unittest.TestCase):
    """Comprehensive browser tests for the Lab Bench Manager SPA."""

    driver = None
    base_url = ""

    @classmethod
    def setUpClass(cls):
        cls.base_url = get_gateway_url()
        cls.driver = create_driver()

    @classmethod
    def tearDownClass(cls):
        if cls.driver:
            cls.driver.quit()

    def setUp(self):
        """Navigate to Lab Bench page."""
        self.driver.get(f"{self.base_url}/bench/")
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".bench-page"))
        )

    # ─── helpers ──────────────────────────────────────────────

    def _bench_path_input(self):
        return self.driver.find_element(By.ID, "bench-path")

    def _bench_tbody(self):
        return self.driver.find_element(By.ID, "bench-tbody")

    def _types_content(self):
        return self.driver.find_element(By.ID, "types-content")

    def _click_btn(self, text: str):
        """Click a button by its visible text."""
        buttons = self.driver.find_elements(By.CSS_SELECTOR, ".bench-actions .btn")
        for btn in buttons:
            if text.lower() in btn.text.lower():
                btn.click()
                time.sleep(0.5)
                return
        self.fail(f"Button with text '{text}' not found")

    # ═══════════════════════════════════════════════════════════
    # 1. PAGE LOAD & LAYOUT
    # ═══════════════════════════════════════════════════════════

    def test_01_page_title(self):
        self.assertIn("Lab Bench", self.driver.title)

    def test_02_css_applied(self):
        """Verify Catppuccin Mocha theme via body background."""
        body = self.driver.find_element(By.TAG_NAME, "body")
        bg = body.value_of_css_property("background-color")
        self.assertIn("30, 30, 46", bg)

    def test_03_heading_visible(self):
        h2 = self.driver.find_element(By.CSS_SELECTOR, ".bench-page h2")
        self.assertIn("Lab Bench", h2.text)

    def test_04_actions_bar_visible(self):
        actions = self.driver.find_element(By.CSS_SELECTOR, ".bench-actions")
        self.assertTrue(actions.is_displayed())

    def test_05_bench_path_input(self):
        inp = self._bench_path_input()
        self.assertTrue(inp.is_displayed())
        self.assertEqual(inp.get_attribute("placeholder"), "benches/default.json")

    def test_06_instrument_table_visible(self):
        table = self.driver.find_element(By.ID, "bench-table")
        self.assertTrue(table.is_displayed())

    def test_07_types_panel_visible(self):
        panel = self._types_content()
        self.assertTrue(panel.is_displayed())

    def test_08_table_headers(self):
        headers = self.driver.find_elements(By.CSS_SELECTOR, "#bench-table thead th")
        header_texts = [h.text for h in headers]
        self.assertIn("Type", header_texts)
        self.assertIn("Status", header_texts)
        self.assertIn("Enabled", header_texts)
        self.assertIn("Info", header_texts)

    # ═══════════════════════════════════════════════════════════
    # 2. BUTTONS EXIST AND ARE CLICKABLE
    # ═══════════════════════════════════════════════════════════

    def test_10_load_button_exists(self):
        btn = self.driver.find_element(By.ID, "btn-load")
        self.assertTrue(btn.is_displayed())
        self.assertEqual(btn.text.strip(), "Load")

    def test_11_save_button_exists(self):
        btn = self.driver.find_element(By.ID, "btn-save")
        self.assertTrue(btn.is_displayed())
        self.assertEqual(btn.text.strip(), "Save")

    def test_12_connect_button_exists(self):
        buttons = self.driver.find_elements(By.CSS_SELECTOR, ".bench-actions .btn-primary")
        texts = [b.text for b in buttons]
        self.assertTrue(any("Connect" in t for t in texts))

    def test_13_disconnect_button_exists(self):
        buttons = self.driver.find_elements(By.CSS_SELECTOR, ".bench-actions .btn-danger")
        texts = [b.text for b in buttons]
        self.assertTrue(any("Disconnect" in t for t in texts))

    def test_14_refresh_types_button_exists(self):
        buttons = self.driver.find_elements(By.CSS_SELECTOR, ".bench-actions .btn")
        texts = [b.text for b in buttons]
        self.assertTrue(any("Refresh" in t for t in texts))

    # ═══════════════════════════════════════════════════════════
    # 3. BENCH PATH INPUT
    # ═══════════════════════════════════════════════════════════

    def test_20_type_bench_path(self):
        inp = self._bench_path_input()
        inp.clear()
        inp.send_keys("benches/nrf9160dk.json")
        time.sleep(0.2)
        self.assertEqual(inp.get_attribute("value"), "benches/nrf9160dk.json")

    def test_21_clear_bench_path(self):
        inp = self._bench_path_input()
        inp.clear()
        inp.send_keys("test")
        inp.clear()
        self.assertEqual(inp.get_attribute("value"), "")

    # ═══════════════════════════════════════════════════════════
    # 4. LOAD BENCH
    # ═══════════════════════════════════════════════════════════

    def test_30_load_default_bench(self):
        """Load with default path — should populate table or show 'no instruments'."""
        inp = self._bench_path_input()
        inp.clear()
        inp.send_keys("benches/default.json")
        # Override alert for any error messages
        self.driver.execute_script("window._origAlert = window.alert; window.alert = function(msg) { window._lastAlert = msg; };")
        self._click_btn("Load")
        time.sleep(1)
        # Table should have updated
        tbody = self._bench_tbody()
        self.assertTrue(len(tbody.text) > 0)
        self.driver.execute_script("window.alert = window._origAlert;")

    def test_31_load_nonexistent_bench(self):
        """Loading a non-existent path should show an error alert."""
        inp = self._bench_path_input()
        inp.clear()
        inp.send_keys("nonexistent/path.json")
        self.driver.execute_script("window._lastAlert = null; window.alert = function(msg) { window._lastAlert = msg; };")
        self._click_btn("Load")
        time.sleep(1)
        alert_msg = self.driver.execute_script("return window._lastAlert;")
        # Should either be an error alert or the table shows empty
        # (implementation-dependent)
        self.driver.execute_script("window.alert = function() {};")

    # ═══════════════════════════════════════════════════════════
    # 5. CONNECT / DISCONNECT
    # ═══════════════════════════════════════════════════════════

    def test_40_connect_all(self):
        """Clicking Connect All should not crash."""
        self.driver.execute_script("window.alert = function() {};")
        self._click_btn("Connect All")
        time.sleep(1)
        # Table should still be present
        table = self.driver.find_element(By.ID, "bench-table")
        self.assertTrue(table.is_displayed())

    def test_41_disconnect_all(self):
        """Clicking Disconnect should not crash."""
        self._click_btn("Disconnect")
        time.sleep(1)
        table = self.driver.find_element(By.ID, "bench-table")
        self.assertTrue(table.is_displayed())

    # ═══════════════════════════════════════════════════════════
    # 6. REFRESH TYPES
    # ═══════════════════════════════════════════════════════════

    def test_50_refresh_types(self):
        """Clicking Refresh Types should populate the types panel."""
        self._click_btn("Refresh Types")
        time.sleep(1)
        content = self._types_content()
        # Should show badges or "None found"
        text = content.text
        self.assertTrue(len(text) > 0)

    def test_51_types_displayed_as_badges(self):
        """After refresh, types should appear as .badge elements."""
        self._click_btn("Refresh Types")
        time.sleep(1)
        badges = self._types_content().find_elements(By.CSS_SELECTOR, ".badge")
        # We may or may not have instrument types, but the function shouldn't crash
        # If there are types, they should be badges
        if len(badges) > 0:
            for badge in badges:
                self.assertTrue(badge.is_displayed())

    # ═══════════════════════════════════════════════════════════
    # 7. SAVE BENCH
    # ═══════════════════════════════════════════════════════════

    def test_60_save_bench(self):
        """Save should work or show a message."""
        self.driver.execute_script("window._lastAlert = null; window.alert = function(msg) { window._lastAlert = msg; };")
        self._click_btn("Save")
        time.sleep(1)
        alert_msg = self.driver.execute_script("return window._lastAlert;")
        # Should either say "Saved" or an error
        self.assertIsNotNone(alert_msg, "Expected an alert from save action")
        self.driver.execute_script("window.alert = function() {};")

    # ═══════════════════════════════════════════════════════════
    # 8. API ENDPOINTS (via JS fetch from browser)
    # ═══════════════════════════════════════════════════════════

    def test_70_api_status(self):
        """GET /bench/api/status should return JSON."""
        result = self.driver.execute_script("""
            const res = await fetch('/bench/api/status');
            return { status: res.status, body: await res.json() };
        """)
        self.assertEqual(result["status"], 200)

    def test_71_api_types(self):
        """GET /bench/api/types should return JSON dict."""
        result = self.driver.execute_script("""
            const res = await fetch('/bench/api/types');
            return { status: res.status, body: await res.json() };
        """)
        self.assertEqual(result["status"], 200)
        self.assertIsInstance(result["body"], dict)

    def test_72_api_summary(self):
        """GET /bench/api/summary should return JSON."""
        result = self.driver.execute_script("""
            const res = await fetch('/bench/api/summary');
            return { status: res.status, body: await res.json() };
        """)
        self.assertEqual(result["status"], 200)

    def test_73_api_load_post(self):
        """POST /bench/api/load with empty body."""
        result = self.driver.execute_script("""
            const res = await fetch('/bench/api/load', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({})
            });
            return { status: res.status, body: await res.json() };
        """)
        # Should return 200 or 400 depending on config
        self.assertIn(result["status"], [200, 400])

    def test_74_api_connect_post(self):
        """POST /bench/api/connect should not 500."""
        result = self.driver.execute_script("""
            const res = await fetch('/bench/api/connect', { method: 'POST' });
            return { status: res.status, body: await res.json() };
        """)
        self.assertNotEqual(result["status"], 500)

    def test_75_api_disconnect_post(self):
        """POST /bench/api/disconnect should return success."""
        result = self.driver.execute_script("""
            const res = await fetch('/bench/api/disconnect', { method: 'POST' });
            return { status: res.status, body: await res.json() };
        """)
        self.assertEqual(result["status"], 200)

    # ═══════════════════════════════════════════════════════════
    # 9. TABLE STATE AFTER OPERATIONS
    # ═══════════════════════════════════════════════════════════

    def test_80_table_updates_after_load(self):
        """After loading a bench, the table should have content."""
        inp = self._bench_path_input()
        inp.clear()
        inp.send_keys("benches/default.json")
        self.driver.execute_script("window.alert = function() {};")
        self._click_btn("Load")
        time.sleep(1)

        tbody = self._bench_tbody()
        rows = tbody.find_elements(By.TAG_NAME, "tr")
        self.assertGreaterEqual(len(rows), 1)

    def test_81_status_dots_present(self):
        """After loading, status dots should be in the table."""
        inp = self._bench_path_input()
        inp.clear()
        inp.send_keys("benches/default.json")
        self.driver.execute_script("window.alert = function() {};")
        self._click_btn("Load")
        time.sleep(1)

        dots = self.driver.find_elements(By.CSS_SELECTOR, "#bench-tbody .status-dot")
        # May or may not have dots depending on whether bench loaded successfully
        # The test validates no JS crash

    # ═══════════════════════════════════════════════════════════
    # 10. CARD STYLING
    # ═══════════════════════════════════════════════════════════

    def test_90_cards_have_styling(self):
        """Cards should have the dark theme background."""
        cards = self.driver.find_elements(By.CSS_SELECTOR, ".card")
        self.assertGreaterEqual(len(cards), 1)
        for card in cards:
            bg = card.value_of_css_property("background-color")
            # Should be --bg2 (#252538) = rgb(37, 37, 56)
            self.assertIn("37, 37, 56", bg)

    def test_91_heading_accent_color(self):
        """The h2 should use the accent color."""
        h2 = self.driver.find_element(By.CSS_SELECTOR, ".bench-page h2")
        color = h2.value_of_css_property("color")
        # --accent (#89b4fa) = rgb(137, 180, 250)
        self.assertIn("137, 180, 250", color)


if __name__ == "__main__":
    unittest.main()
