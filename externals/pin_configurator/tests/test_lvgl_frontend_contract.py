# SPDX-License-Identifier: Apache-2.0
"""Contract tests for the plain-script LVGL frontend surface."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = ROOT / "web" / "index.html"
MAIN_JS = ROOT / "web" / "main.js"
LVGL_MODEL_JS = ROOT / "web" / "lvgl-model.js"
LVGL_BUILD_JS = ROOT / "web" / "lvgl-build.js"
LVGL_UI_JS = ROOT / "web" / "lvgl-ui.js"
WEB_PACKAGE_JSON = ROOT / "web" / "package.json"
WEB_TSCONFIG = ROOT / "web" / "tsconfig.json"
LVGL_MODEL_TS = ROOT / "web" / "ts" / "lvgl-model.ts"
LVGL_BUILD_TS = ROOT / "web" / "ts" / "lvgl-build.ts"
LVGL_UI_TS = ROOT / "web" / "ts" / "lvgl-ui.ts"
LVGL_SHARED_TYPES = ROOT / "web" / "ts" / "lvgl-shared.d.ts"


def test_index_includes_lvgl_editor_surface(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert 'id="lvglStyleLibrary"' in html
    assert 'id="lvglBtnAddStyle"' in html
    assert 'id="lvglBtnImportGui"' in html
    assert 'id="lvglBtnSaveGui"' in html
    assert 'id="lvglImportModal"' in html
    assert 'id="lvglImportMode"' in html
    assert 'id="lvglSaveModal"' in html
    assert 'id="btnBrowseZephyrCatalogRoot"' in html
    assert 'id="btnBrowseProjectPath"' in html
    assert 'id="btnBrowseProjectFilePath"' in html
    assert 'id="btnBrowseLoadProjectFilePath"' in html
    assert 'id="impBtnBrowseProjectPath"' in html
    assert 'id="lvglBtnBrowseImportSource"' in html
    assert 'id="lvglBtnBrowseSaveFilePath"' in html
    assert 'id="lvglBtnCopy"' in html
    assert 'id="lvglBtnPaste"' in html
    assert 'id="lvglBtnDuplicate"' in html
    assert 'id="lvglBtnUndo"' in html
    assert 'id="lvglBtnRedo"' in html
    assert 'id="lvglBtnSelectTool"' in html
    assert 'id="lvglBtnHandTool"' in html
    assert 'id="lvglBtnSnapToggle"' in html
    assert 'id="lvglBtnZoomIn"' in html
    assert 'id="lvglBtnZoomOut"' in html
    assert 'id="lvglBtnZoomReset"' in html
    assert 'id="lvglZoomLevel"' in html
    assert 'id="lvglQuickStyleBar"' in html
    assert 'id="lvglQuickStyleBg"' in html
    assert 'id="lvglQuickStyleColor"' in html
    assert 'id="lvglQuickStyleRadius"' in html
    assert 'id="lvglStageViewport"' in html
    assert 'id="lvglValidationPanel"' in html
    assert 'id="lvglValidationSummary"' in html
    assert 'id="lvglValidationList"' in html
    assert 'id="lvglValidationSearch"' in html
    assert 'Search findings, symbols, targets...' in html
    assert 'id="lvglValidationSeverityFilter"' in html
    assert 'id="lvglValidationScopeFilter"' in html
    assert 'id="lvglBtnApplyValidationRenames"' in html
    assert 'id="lvglBtnResetValidationFilters"' in html
    assert 'data-app-tab="zephyr-catalog"' in html
    assert 'id="zephyrCatalogRoot"' in html
    assert 'id="zephyrCatalogRefresh"' in html
    assert 'id="zephyrCatalogKind"' in html
    assert 'id="zephyrCatalogSearch"' in html
    assert 'id="zephyrCatalogList"' in html
    assert 'id="zephyrCatalogDetail"' in html
    assert 'src="lvgl-registry.js"' in html
    assert 'src="lvgl-model.js"' in html
    assert 'src="lvgl-build.js"' in html
    assert 'src="lvgl-ui.js"' in html


def test_lvgl_frontend_scripts_expose_new_contract_points():
    main_js = MAIN_JS.read_text(encoding="utf-8")
    model_js = LVGL_MODEL_JS.read_text(encoding="utf-8")
    build_js = LVGL_BUILD_JS.read_text(encoding="utf-8")
    ui_js = LVGL_UI_JS.read_text(encoding="utf-8")

    assert "lvgl:ui_layout_validation.md" in main_js
    assert "lvgl:style_schema.json" in main_js
    assert "selectedStyleId" in model_js
    assert "resolveNodeVisual" in model_js
    assert "ui_init_shared_styles" in build_js
    assert "lv_obj_add_style" in build_js
    assert "window.LvglUi" in ui_js
    assert "data-lvgl-style-ref" in ui_js
    assert "getPropertyFields" in ui_js
    assert 'data-lvgl-custom-preset="true"' in ui_js
    assert 'event.target.value === "__custom__"' in ui_js
    assert "lvglPreviewImport" in main_js
    assert "LVGL_IMPORT_MODES" in main_js
    assert "lvglUpdateImportModeUi" in main_js
    assert "requestPathDialog" in main_js
    assert "bindPathBrowseButton" in main_js
    assert "lvglImportBrowseDialogOptions" in main_js
    assert "lvglSaveLayoutFile" in main_js
    assert "copySelectedWidget" in ui_js
    assert "pasteClipboard" in ui_js
    assert "duplicateSelectedWidget" in ui_js
    assert "setCanvasTool" in ui_js
    assert "selectedIds(" in ui_js
    assert "toggleWidgetSelection" in ui_js
    assert "applyMoveSnap" in ui_js
    assert "adjustZoom" in ui_js
    assert "resetCanvasView" in ui_js
    assert "updateQuickStyleBar" in ui_js
    assert "renderValidation" in ui_js
    assert "lvglValidationList" in ui_js
    assert "lvgl-layout-validation-group" in ui_js
    assert "lvgl-layout-validation-group-title" in ui_js
    assert "lvglValidationSeverityFilter" in ui_js
    assert "lvglValidationScopeFilter" in ui_js
    assert "lvglBtnApplyValidationRenames" in ui_js
    assert "Apply Rename Fixes" in ui_js
    assert "applyVisibleRenameSuggestions" in ui_js
    assert "lvglBtnResetValidationFilters" in ui_js
    assert "No validation findings match the active filters" in ui_js
    assert "Codegen Preview" in ui_js
    assert "lvgl-layout-symbol-preview" in ui_js
    assert "matching-issue" in ui_js
    assert "referenced by current validation findings" in ui_js
    assert "ui_get_" in ui_js
    assert "Rename widget to" in ui_js
    assert "Rename screen to" in ui_js
    assert "Rename hook to" in ui_js
    assert "data-lvgl-validation-rename" in ui_js
    assert "lvglValidationSearch" in ui_js
    assert "data-lvgl-validation-kind" in ui_js
    assert "data-resize-handle" in ui_js
    assert "undo(" in ui_js
    assert "redo(" in ui_js
    assert "zephyrCatalogLoad" in main_js
    assert "zephyrCatalogHandleAction" in main_js
    assert "activateAppTab" in main_js
    assert "zephyrCatalogUseSensorInConfigurator" in main_js
    assert "zephyrCatalogUseSensorInBoardEditor" in main_js


def test_lvgl_static_files_exist():
    assert INDEX_HTML.exists()
    assert MAIN_JS.exists()
    assert LVGL_MODEL_JS.exists()
    assert LVGL_BUILD_JS.exists()
    assert LVGL_UI_JS.exists()


def test_lvgl_frontend_typescript_sources_exist():
    package_json = WEB_PACKAGE_JSON.read_text(encoding="utf-8")
    tsconfig = WEB_TSCONFIG.read_text(encoding="utf-8")
    shared_types = LVGL_SHARED_TYPES.read_text(encoding="utf-8")
    model_ts = LVGL_MODEL_TS.read_text(encoding="utf-8")
    build_ts = LVGL_BUILD_TS.read_text(encoding="utf-8")
    ui_ts = LVGL_UI_TS.read_text(encoding="utf-8")

    assert WEB_PACKAGE_JSON.exists()
    assert WEB_TSCONFIG.exists()
    assert LVGL_SHARED_TYPES.exists()
    assert LVGL_MODEL_TS.exists()
    assert LVGL_BUILD_TS.exists()
    assert LVGL_UI_TS.exists()
    assert '"build"' in package_json
    assert '"check"' in package_json
    assert 'typescript/bin/tsc' in package_json
    assert '"rootDir": "ts"' in tsconfig
    assert '"outDir": "generated"' in tsconfig
    assert '"ts/**/*.d.ts"' in tsconfig
    assert "copyFileSync('generated/lvgl-model.js','lvgl-model.js')" in package_json
    assert "copyFileSync('generated/lvgl-build.js','lvgl-build.js')" in package_json
    assert "copyFileSync('generated/lvgl-ui.js','lvgl-ui.js')" in package_json
    assert 'interface LayoutState' in shared_types
    assert 'interface LvglRegistryApi' in shared_types
    assert 'window.LvglModel = LvglModel;' in model_ts
    assert '@ts-nocheck' not in build_ts
    assert 'interface BuildArtifacts' in build_ts
    assert 'function buildArtifacts(state: LayoutState): BuildArtifacts' in build_ts
    assert 'window.LvglBuild = {' in build_ts
    assert '@ts-nocheck' in ui_ts
    assert 'window.LvglUi' in ui_ts
    assert 'copySelectedWidget' in ui_ts


def test_lvgl_model_validation_report_contract_is_richer():
    model_ts = LVGL_MODEL_TS.read_text(encoding="utf-8")

    assert 'The layout has no screens.' in model_ts
    assert 'Duplicate shared style ID' in model_ts
    assert 'extends beyond the bounds of' in model_ts
    assert 'has no inbound navigation path.' in model_ts
    assert 'normalizes to reserved C identifier' in model_ts
    assert 'collides with' in model_ts
    assert 'ui_build_' in model_ts
    assert 'ui_on_' in model_ts
    assert '## Scope Summary' in model_ts
    assert '`- Errors: ${bySeverity.error.length}`' in model_ts
    assert '`- Warnings: ${bySeverity.warning.length}`' in model_ts
    assert '`- Info: ${bySeverity.info.length}`' in model_ts