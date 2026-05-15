# SPDX-License-Identifier: Apache-2.0
"""Phase 0 baseline locks for the legacy shell and backend surface.

These tests intentionally assert the current contract before the frontend
platform rewrite starts changing structure.
"""


class TestPhase0ShellBaseline:
    def test_root_shell_contains_primary_tabs(self, client):
        resp = client.get("/")

        assert resp.status_code == 200
        html = resp.get_data(as_text=True)

        for tab_key in [
            "modules",
            "lvgl-layout",
            "protocols",
            "interrupts",
            "peripherals",
            "clock",
            "configurator",
            "board-editor",
            "packages",
            "sensors",
            "zephyr-catalog",
        ]:
            assert f'data-app-tab="{tab_key}"' in html
            assert f'data-app-content="{tab_key}"' in html

    def test_root_shell_contains_primary_regions(self, client):
        resp = client.get("/")

        assert resp.status_code == 200
        html = resp.get_data(as_text=True)

        for marker in [
            'id="boardSelect"',
            'id="chipArea"',
            'id="chipContainer"',
            'id="periphPanel"',
            'id="configPanel"',
            'id="outputBar"',
            'id="outputPre"',
        ]:
            assert marker in html


class TestPhase0RouteBaseline:
    def test_critical_routes_are_registered(self, app):
        routes = {rule.rule for rule in app.url_map.iter_rules()}

        expected = {
            "/",
            "/favicon.ico",
            "/api/boards",
            "/api/board/<name>",
            "/api/generate",
            "/api/save-project",
            "/api/project-file/save",
            "/api/project-file/load",
            "/api/demo-app/export",
            "/api/path-dialog",
            "/api/board-editor/drafts",
            "/api/board-editor/draft/<filename>",
            "/api/board-editor/save",
            "/api/board-editor/delete",
            "/api/zephyr/catalog",
            "/api/lvgl/import",
            "/api/lvgl/export",
            "/api/modules",
            "/api/generate-module-config",
            "/api/peripheral-templates",
            "/api/peripheral-instances/<board_name>",
            "/api/generate-peripheral-config",
            "/api/clock-trees",
            "/api/clock-tree/<tree_id>",
            "/api/clock-frequencies",
            "/api/generate-clock-config",
            "/api/import-config",
            "/api/scan-project",
            "/api/parse-pdf",
            "/api/generate-package",
            "/api/generated-packages",
            "/api/parse-jobs",
            "/api/identify-mcu",
            "/api/fetch-datasheet",
            "/api/driver-templates",
            "/api/generate-driver",
            "/api/parse-sensor-pdf",
            "/api/sensor-jobs",
            "/api/sensor-job/<job_id>",
            "/api/sensor-job/<job_id>/header",
            "/api/sensor-job/<job_id>/driver",
            "/api/identify-sensor",
        }

        missing = expected - routes
        assert not missing, f"Missing critical Phase 0 routes: {sorted(missing)}"