# SPDX-License-Identifier: Apache-2.0
"""Optional browser integration tests for the LVGL editor."""

from contextlib import closing
import json
import socket
import threading
from pathlib import Path

import pytest
from werkzeug.serving import make_server


def _write_temp_zephyr_tree(root: Path) -> Path:
        (root / "boards" / "vendor" / "demo_board").mkdir(parents=True, exist_ok=True)
        (root / "dts" / "bindings" / "sensor").mkdir(parents=True, exist_ok=True)
        (root / "boards" / "vendor" / "demo_board" / "board.yml").write_text(
                """
board:
    name: demo_board
    full_name: Demo Board
    vendor: demo
    socs:
        - name: DEMO_SOC
""".strip(),
                encoding="utf-8",
        )
        (root / "dts" / "bindings" / "sensor" / "demo,temp-i2c.yaml").write_text(
                """
description: Demo temperature sensor
compatible: demo,temp
title: Demo Temp
include: [sensor-device.yaml, i2c-device.yaml]
properties:
    reg:
        type: int
        required: true
        description: I2C address
""".strip(),
                encoding="utf-8",
        )
        return root


def _write_matching_mcu_zephyr_tree(root: Path) -> Path:
        (root / "boards" / "raspberrypi" / "rpi_pico").mkdir(parents=True, exist_ok=True)
        (root / "dts" / "bindings" / "sensor").mkdir(parents=True, exist_ok=True)
        (root / "boards" / "raspberrypi" / "rpi_pico" / "board.yml").write_text(
                """
board:
    name: rpi_pico
    full_name: Raspberry Pi Pico
    vendor: raspberrypi
    socs:
        - name: RP2040
""".strip(),
                encoding="utf-8",
        )
        return root


def _free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return sock.getsockname()[1]


@pytest.mark.integration
def test_lvgl_undo_redo_flow_in_browser(app):
    playwright = pytest.importorskip("playwright.sync_api", reason="Install playwright to run browser integration tests")

    port = _free_port()
    server = make_server("127.0.0.1", port, app)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        with playwright.sync_playwright() as instance:
            try:
                browser = instance.chromium.launch()
            except Exception as exc:  # pragma: no cover - environment dependent
                pytest.skip(f"Playwright browser launch unavailable: {exc}")

            try:
                page = browser.new_page()
                page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
                page.locator('[data-app-tab="lvgl-layout"]').click(force=True)
                page.locator("#lvglBtnAddStyle").evaluate("button => button.click()")

                assert page.locator("#lvglStyleLibrary [data-lvgl-style]").count() == 1
                assert page.locator("#lvglBtnUndo").is_disabled() is False
                assert page.locator("#lvglBtnRedo").is_disabled() is True

                page.locator("#lvglBtnUndo").evaluate("button => button.click()")
                assert page.locator("#lvglStyleLibrary [data-lvgl-style]").count() == 0
                assert page.locator("#lvglBtnRedo").is_disabled() is False

                page.locator("#lvglBtnRedo").evaluate("button => button.click()")
                assert page.locator("#lvglStyleLibrary [data-lvgl-style]").count() == 1
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.integration
def test_lvgl_copy_duplicate_and_paste_in_browser(app):
    playwright = pytest.importorskip("playwright.sync_api", reason="Install playwright to run browser integration tests")

    port = _free_port()
    server = make_server("127.0.0.1", port, app)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        with playwright.sync_playwright() as instance:
            try:
                browser = instance.chromium.launch()
            except Exception as exc:  # pragma: no cover - environment dependent
                pytest.skip(f"Playwright browser launch unavailable: {exc}")

            try:
                page = browser.new_page()
                page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
                page.locator('[data-app-tab="lvgl-layout"]').click(force=True)
                page.locator('[data-lvgl-add="button"]').click()

                assert page.locator("#lvglStage [data-lvgl-node]").count() == 1
                assert page.locator("#lvglBtnCopy").is_disabled() is False
                assert page.locator("#lvglBtnDuplicate").is_disabled() is False

                page.locator("#lvglBtnCopy").evaluate("button => button.click()")
                assert page.locator("#lvglBtnPaste").is_disabled() is False

                page.locator("#lvglBtnPaste").evaluate("button => button.click()")
                assert page.locator("#lvglStage [data-lvgl-node]").count() == 2

                page.locator("#lvglBtnDuplicate").evaluate("button => button.click()")
                assert page.locator("#lvglStage [data-lvgl-node]").count() == 3

                page.locator("#lvglBtnUndo").evaluate("button => button.click()")
                assert page.locator("#lvglStage [data-lvgl-node]").count() == 2

                page.locator("#lvglBtnUndo").evaluate("button => button.click()")
                assert page.locator("#lvglStage [data-lvgl-node]").count() == 1

                page.locator("#lvglBtnRedo").evaluate("button => button.click()")
                assert page.locator("#lvglStage [data-lvgl-node]").count() == 2
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.integration
def test_lvgl_import_edit_and_save_in_browser(app, tmp_path):
    playwright = pytest.importorskip("playwright.sync_api", reason="Install playwright to run browser integration tests")

    port = _free_port()
    server = make_server("127.0.0.1", port, app)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    save_path = tmp_path / "imported_layout"
    imported = {
        "version": 1,
        "kind": "lvgl-layout",
        "lvgl_layout": {
            "preset": "dashboard",
            "startupScreenId": "screen_root",
            "currentScreenId": "screen_root",
            "selectedId": "screen_root",
            "sharedStyles": [],
            "screens": [
                {
                    "id": "screen_root",
                    "type": "screen",
                    "name": "screen_main",
                    "w": 480,
                    "h": 272,
                    "nodes": [
                        {
                            "id": "label_1",
                            "type": "label",
                            "name": "status_label",
                            "text": "Imported GUI",
                            "x": 24,
                            "y": 18,
                            "w": 160,
                            "h": 36,
                        }
                    ],
                }
            ],
        },
    }

    try:
        with playwright.sync_playwright() as instance:
            try:
                browser = instance.chromium.launch()
            except Exception as exc:  # pragma: no cover - environment dependent
                pytest.skip(f"Playwright browser launch unavailable: {exc}")

            try:
                page = browser.new_page()
                page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
                page.locator("#appTabSelect").select_option("lvgl-layout")

                page.locator("#lvglBtnImportGui").evaluate("button => button.click()")
                page.locator("#lvglImportJson").evaluate(
                    "(el, value) => { el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); }",
                    json.dumps(imported, indent=2),
                )
                page.locator("#lvglBtnPreviewJson").evaluate("button => button.click()")
                assert page.locator("#lvglBtnApplyImport").is_disabled() is False

                page.locator("#lvglBtnApplyImport").evaluate("button => button.click()")
                assert page.locator("#lvglStage [data-lvgl-node]").count() == 1
                assert "Imported GUI" in page.locator("#lvglCodePre").text_content()

                page.locator('[data-lvgl-add="button"]').evaluate("button => button.click()")
                assert page.locator("#lvglStage [data-lvgl-node]").count() == 2

                page.locator("#lvglBtnSaveGui").evaluate("button => button.click()")
                page.locator("#lvglSaveFilePath").evaluate(
                    "(el, value) => { el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); }",
                    str(save_path),
                )
                page.locator("#lvglBtnConfirmSaveGui").evaluate("button => button.click()")

                saved_path = save_path.with_suffix(".lvgl.json")
                assert saved_path.exists()
                saved = json.loads(saved_path.read_text(encoding="utf-8"))
                assert saved["kind"] == "lvgl-layout"
                assert saved["lvgl_layout"]["screens"][0]["nodes"][0]["text"] == "Imported GUI"
                assert any(node["type"] == "button" for node in saved["lvgl_layout"]["screens"][0]["nodes"])
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.integration
def test_lvgl_import_external_pages_schema_in_browser(app):
    playwright = pytest.importorskip("playwright.sync_api", reason="Install playwright to run browser integration tests")

    port = _free_port()
    server = make_server("127.0.0.1", port, app)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    external = {
        "project": "External GUI",
        "width": 480,
        "height": 272,
        "startupPage": "home",
        "styles": [
            {"name": "primaryCard", "background": "#1e293b", "color": "#f8fafc", "radius": 18}
        ],
        "pages": [
            {
                "id": "home",
                "name": "Home",
                "widgets": [
                    {"type": "Text", "name": "headline", "text": "External Headline", "x": 18, "y": 12, "width": 180, "height": 30},
                    {"type": "Button", "name": "openSettings", "text": "Settings", "x": 24, "y": 72, "width": 160, "height": 52, "style": "primaryCard", "targetPage": "settings"},
                ],
            },
            {"id": "settings", "name": "Settings", "widgets": []},
        ],
    }

    try:
        with playwright.sync_playwright() as instance:
            try:
                browser = instance.chromium.launch()
            except Exception as exc:  # pragma: no cover - environment dependent
                pytest.skip(f"Playwright browser launch unavailable: {exc}")

            try:
                page = browser.new_page()
                page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
                page.locator('[data-app-tab="lvgl-layout"]').click(force=True)
                page.locator("#lvglBtnImportGui").evaluate("button => button.click()")
                page.locator("#lvglImportJson").evaluate(
                    "(el, value) => { el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); }",
                    json.dumps(external, indent=2),
                )
                page.locator("#lvglBtnPreviewJson").evaluate("button => button.click()")
                page.locator("#lvglBtnApplyImport").evaluate("button => button.click()")

                assert page.locator("#lvglStage [data-lvgl-node]").count() == 2
                assert page.locator("#lvglStyleLibrary [data-lvgl-style]").count() == 1
                assert "External Headline" in page.locator("#lvglCodePre").text_content()
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.integration
def test_lvgl_import_display_pdf_in_browser(app, tmp_path, monkeypatch):
    playwright = pytest.importorskip("playwright.sync_api", reason="Install playwright to run browser integration tests")

    import server as server_module

    monkeypatch.setattr(
        server_module,
        "_extract_display_pdf_text",
        lambda pdf_bytes: "ILI9341 is a TFT liquid crystal display controller with resolution of 240RGBx320 dots and 262K color.",
    )

    pdf_path = tmp_path / "ili9341.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% mock display pdf\n")

    port = _free_port()
    server = make_server("127.0.0.1", port, app)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        with playwright.sync_playwright() as instance:
            try:
                browser = instance.chromium.launch()
            except Exception as exc:  # pragma: no cover - environment dependent
                pytest.skip(f"Playwright browser launch unavailable: {exc}")

            try:
                page = browser.new_page()
                page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
                page.locator("#appTabSelect").select_option("lvgl-layout")

                page.locator("#lvglBtnImportGui").evaluate("button => button.click()")
                page.locator("#lvglImportMode").select_option("display-pdf")
                page.locator("#lvglImportSource").evaluate(
                    "(el, value) => { el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); }",
                    str(pdf_path),
                )
                page.locator("#lvglBtnPreviewSource").evaluate("button => button.click()")

                expect = playwright.expect
                display_field = page.locator("#lvglImportPreview .lvgl-layout-field").filter(has_text="Display").locator("input")
                source_field = page.locator("#lvglImportPreview .lvgl-layout-field").filter(has_text="Source").locator("input")
                expect(display_field).to_have_value("240 x 320")
                expect(source_field).to_have_value(str(pdf_path))
                assert page.locator("#lvglBtnApplyImport").is_disabled() is False

                page.locator("#lvglBtnApplyImport").evaluate("button => button.click()")
                expect(page.locator("#lvglImportModal")).not_to_have_class(".*show.*")
                expect(page.locator("#lvglSelectionMeta")).to_contain_text("240 x 320")
                expect(page.locator("#lvglCodePre")).to_contain_text("lv_obj_set_size(screen, 240, 320)")
                expect(page.locator("#lvglPresetSelect")).to_have_value("__custom__")
                expect(page.locator("#lvglPresetSelect option:checked")).to_contain_text("Custom 240 x 320")
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.integration
def test_lvgl_drawio_style_resize_and_hand_tool_in_browser(app):
    playwright = pytest.importorskip("playwright.sync_api", reason="Install playwright to run browser integration tests")

    port = _free_port()
    server = make_server("127.0.0.1", port, app)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        with playwright.sync_playwright() as instance:
            try:
                browser = instance.chromium.launch()
            except Exception as exc:  # pragma: no cover - environment dependent
                pytest.skip(f"Playwright browser launch unavailable: {exc}")

            try:
                page = browser.new_page(viewport={"width": 1600, "height": 1000})
                page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
                page.locator("#appTabSelect").select_option("lvgl-layout")

                page.locator('[data-lvgl-add="button"]').click()
                page.locator('#lvglStage [data-lvgl-node="button_1"]').click()

                page.locator("#lvglQuickStyleBg").evaluate(
                    "(el, value) => { el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); }",
                    "#ff0000",
                )
                page.locator("#lvglQuickStyleRadius").evaluate(
                    "(el, value) => { el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); }",
                    "22",
                )

                page.evaluate("""
                    () => {
                        const handle = document.querySelector('#lvglStage [data-lvgl-node="button_1"] [data-resize-handle="se"]');
                        if (!handle) {
                            throw new Error('Resize handle not found');
                        }
                        const rect = handle.getBoundingClientRect();
                        const startX = rect.left + rect.width / 2;
                        const startY = rect.top + rect.height / 2;
                        handle.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, clientX: startX, clientY: startY }));
                        window.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: startX + 36, clientY: startY + 28 }));
                        window.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, clientX: startX + 36, clientY: startY + 28 }));
                    }
                """)

                selected = page.evaluate("""
                    () => {
                        const node = window.lvglSelectedNode();
                        return { bg: node.bg, radius: node.radius, w: node.w, h: node.h };
                    }
                """)
                assert selected["bg"] == "#ff0000"
                assert selected["radius"] == 22
                assert selected["w"] > 160
                assert selected["h"] > 56

                page.locator("#lvglBtnHandTool").click()
                page.evaluate("""
                    () => {
                        const wrap = document.querySelector('.lvgl-layout-canvas-wrap');
                        if (!wrap) {
                            throw new Error('Canvas wrap not found');
                        }
                        const rect = wrap.getBoundingClientRect();
                        const startX = rect.left + rect.width / 2;
                        const startY = rect.top + rect.height / 2;
                        wrap.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, clientX: startX, clientY: startY }));
                        window.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: startX + 60, clientY: startY + 40 }));
                        window.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, clientX: startX + 60, clientY: startY + 40 }));
                    }
                """)

                viewport_transform = page.locator("#lvglStageViewport").evaluate("el => el.style.transform")
                assert "translate(" in viewport_transform
                assert "scale(1)" in viewport_transform
                assert viewport_transform != "translate(0px, 0px) scale(1)"
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.integration
def test_lvgl_multi_select_and_snap_in_browser(app):
    playwright = pytest.importorskip("playwright.sync_api", reason="Install playwright to run browser integration tests")

    port = _free_port()
    server = make_server("127.0.0.1", port, app)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        with playwright.sync_playwright() as instance:
            try:
                browser = instance.chromium.launch()
            except Exception as exc:  # pragma: no cover - environment dependent
                pytest.skip(f"Playwright browser launch unavailable: {exc}")

            try:
                page = browser.new_page(viewport={"width": 1600, "height": 1000})
                page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
                page.locator("#appTabSelect").select_option("lvgl-layout")

                page.locator('[data-lvgl-add="button"]').click()
                page.locator('[data-lvgl-add="label"]').click()

                page.evaluate("""
                    () => {
                        const button = document.querySelector('#lvglStage [data-lvgl-node="button_1"]');
                        const label = document.querySelector('#lvglStage [data-lvgl-node="label_2"]');
                        if (!button || !label) throw new Error('Expected widgets not found');
                        button.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                        label.dispatchEvent(new MouseEvent('click', { bubbles: true, ctrlKey: true }));
                    }
                """)

                selection = page.evaluate("() => ({ ids: window.lvglEnsureState().selectedIds || [], meta: document.getElementById('lvglSelectionMeta')?.textContent || '' })")
                assert len(selection["ids"]) == 2
                assert "2 widgets selected" in selection["meta"]

                page.keyboard.press("Shift+ArrowRight")
                moved = page.evaluate("""
                    () => {
                        const state = window.lvglEnsureState();
                        const button = state.screens[0].nodes.find(node => node.id === 'button_1');
                        const label = state.screens[0].nodes.find(node => node.id === 'label_2');
                        return { buttonX: button.x, labelX: label.x };
                    }
                """)
                assert moved["buttonX"] > 100
                assert moved["labelX"] > 100

                page.evaluate("""
                    () => {
                        const button = document.querySelector('#lvglStage [data-lvgl-node="button_1"]');
                        if (!button) throw new Error('Button not found');
                        button.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                        const rect = button.getBoundingClientRect();
                        const startX = rect.left + rect.width / 2;
                        const startY = rect.top + rect.height / 2;
                        button.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, clientX: startX, clientY: startY }));
                        window.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: startX + 13, clientY: startY + 11 }));
                        window.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, clientX: startX + 13, clientY: startY + 11 }));
                    }
                """)

                snapped = page.evaluate("""
                    () => {
                        const state = window.lvglEnsureState();
                        const button = state.screens[0].nodes.find(node => node.id === 'button_1');
                        return { x: button.x, y: button.y, snapText: document.getElementById('lvglBtnSnapToggle')?.textContent || '' };
                    }
                """)
                assert snapped["x"] % 16 == 0
                assert snapped["y"] != 284
                assert "Snap On" in snapped["snapText"]
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.integration
def test_lvgl_import_zephyr_project_in_browser(app, tmp_path):
    playwright = pytest.importorskip("playwright.sync_api", reason="Install playwright to run browser integration tests")

    project_dir = tmp_path / "demo_app"
    project_dir.mkdir()
    (project_dir / "prj.conf").write_text(
        "CONFIG_LV_HOR_RES_MAX=800\nCONFIG_LV_VER_RES_MAX=480\n",
        encoding="utf-8",
    )
    (project_dir / "demo_board.overlay").write_text(
        '&display0 { compatible = "sitronix,st7701s"; width = <800>; height = <480>; };\n',
        encoding="utf-8",
    )

    port = _free_port()
    server = make_server("127.0.0.1", port, app)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        with playwright.sync_playwright() as instance:
            try:
                browser = instance.chromium.launch()
            except Exception as exc:  # pragma: no cover - environment dependent
                pytest.skip(f"Playwright browser launch unavailable: {exc}")

            try:
                page = browser.new_page()
                page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
                page.locator("#appTabSelect").select_option("lvgl-layout")

                page.locator("#lvglBtnImportGui").evaluate("button => button.click()")
                page.locator("#lvglImportMode").select_option("zephyr")
                page.locator("#lvglImportSource").evaluate(
                    "(el, value) => { el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); }",
                    str(project_dir),
                )
                page.locator("#lvglBtnPreviewSource").evaluate("button => button.click()")

                expect = playwright.expect
                display_field = page.locator("#lvglImportPreview .lvgl-layout-field").filter(has_text="Display").locator("input")
                source_field = page.locator("#lvglImportPreview .lvgl-layout-field").filter(has_text="Source").locator("input")
                expect(display_field).to_have_value("800 x 480")
                expect(source_field).to_have_value(f"Zephyr project {project_dir}")
                assert page.locator("#lvglBtnApplyImport").is_disabled() is False

                page.locator("#lvglBtnApplyImport").evaluate("button => button.click()")
                expect(page.locator("#lvglImportModal")).not_to_have_class(".*show.*")
                expect(page.locator("#lvglSelectionMeta")).to_contain_text("800 x 480")
                expect(page.locator("#lvglCodePre")).to_contain_text("lv_obj_set_size(screen, 800, 480)")
                expect(page.locator("#lvglPresetSelect")).to_have_value("panel")
                expect(page.locator("#lvglPresetSelect option:checked")).to_contain_text("Panel 800 x 480")
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.integration
def test_lvgl_rejects_mcu_datasheet_pdf_in_browser(app):
    playwright = pytest.importorskip("playwright.sync_api", reason="Install playwright to run browser integration tests")

    pdf_path = Path(__file__).resolve().parent.parent / ".uploads" / "stm32f427_datasheet.pdf"

    port = _free_port()
    server = make_server("127.0.0.1", port, app)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        with playwright.sync_playwright() as instance:
            try:
                browser = instance.chromium.launch()
            except Exception as exc:  # pragma: no cover - environment dependent
                pytest.skip(f"Playwright browser launch unavailable: {exc}")

            try:
                page = browser.new_page()
                page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
                page.locator("#appTabSelect").select_option("lvgl-layout")

                page.locator("#lvglBtnImportGui").evaluate("button => button.click()")
                page.locator("#lvglImportMode").select_option("display-pdf")
                page.locator("#lvglImportSource").evaluate(
                    "(el, value) => { el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); }",
                    str(pdf_path),
                )
                page.locator("#lvglBtnPreviewSource").evaluate("button => button.click()")

                expect = playwright.expect
                expect(page.locator("#lvglBtnApplyImport")).to_be_disabled()
                expect(page.locator("#lvglImportPreview")).to_contain_text(
                    "Load a display datasheet PDF to infer the panel resolution and seed the LVGL canvas."
                )
                expect(page.locator("body")).to_contain_text("Could not infer display resolution from the PDF")
                expect(page.locator("#lvglImportModal")).to_be_visible()
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.integration
def test_zephyr_catalog_sensor_action_in_browser(app, tmp_path):
    playwright = pytest.importorskip("playwright.sync_api", reason="Install playwright to run browser integration tests")

    port = _free_port()
    server = make_server("127.0.0.1", port, app)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    zephyr_root = _write_temp_zephyr_tree(tmp_path / "zephyr")

    try:
        with playwright.sync_playwright() as instance:
            try:
                browser = instance.chromium.launch()
            except Exception as exc:  # pragma: no cover - environment dependent
                pytest.skip(f"Playwright browser launch unavailable: {exc}")

            try:
                page = browser.new_page()
                page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
                page.evaluate(
                    "root => localStorage.setItem('zpincfg_zephyr_catalog_root', root)",
                    str(zephyr_root),
                )
                page.locator('[data-app-tab="zephyr-catalog"]').click(force=True)

                page.locator("#zephyrCatalogList .zcatalog-item").first.wait_for()
                assert "1 MCU boards" in page.locator("#zephyrCatalogSummary").text_content()

                page.locator('#zephyrCatalogKind').select_option('sensor')
                page.locator("#zephyrCatalogList .zcatalog-item").first.click()
                page.locator('[data-zcatalog-action="use-sensor-parser"]').click()

                page.locator('[data-app-content="sensors"].active').wait_for()
                assert page.locator("#snsPartInput").input_value() == "TEMP"
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.integration
def test_zephyr_catalog_mcu_action_loads_matching_board(app, tmp_path):
    playwright = pytest.importorskip("playwright.sync_api", reason="Install playwright to run browser integration tests")

    port = _free_port()
    server = make_server("127.0.0.1", port, app)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    zephyr_root = _write_matching_mcu_zephyr_tree(tmp_path / "zephyr")

    try:
        with playwright.sync_playwright() as instance:
            try:
                browser = instance.chromium.launch()
            except Exception as exc:  # pragma: no cover - environment dependent
                pytest.skip(f"Playwright browser launch unavailable: {exc}")

            try:
                page = browser.new_page()
                page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
                page.evaluate(
                    "root => localStorage.setItem('zpincfg_zephyr_catalog_root', root)",
                    str(zephyr_root),
                )
                page.locator('[data-app-tab="zephyr-catalog"]').click(force=True)

                page.locator('#zephyrCatalogKind').select_option('mcu')
                page.locator("#zephyrCatalogList .zcatalog-item").first.wait_for()
                page.locator("#zephyrCatalogList .zcatalog-item").first.click()
                page.locator('[data-zcatalog-action="use-mcu-configurator"]').click()

                page.locator('[data-app-content="configurator"].active').wait_for()
                page.wait_for_function(
                    "() => document.querySelector('#boardSelect')?.value === 'rpi_pico'"
                )
                assert page.locator("#boardSelect").input_value() == "rpi_pico"
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()