# Zephyr Pin Configurator (Pyontrust)

> **A comprehensive web-based configuration tool for Zephyr RTOS embedded projects.**

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## Overview

Pyontrust Pin Configurator is a Flask-powered web application that provides an
interactive GUI for configuring embedded projects. It covers the full
embedded workflow — from parsing MCU datasheets to generating production-ready
Zephyr overlays and Kconfig fragments, plus starter Arduino and bare-metal pin
configuration files.

![Architecture](docs/img/architecture.png)

### Key Features

| Feature | Description |
|---------|-------------|
| **Pin Configurator** | Interactive chip diagram with drag-and-drop pin assignment |
| **Multi-target Export** | Generate Zephyr, Arduino, and bare-metal pin configuration outputs |
| **Package Manager** | Parse MCU datasheet PDFs (18+ vendor families), auto-download by part number |
| **Module Configurator** | Browse & enable 27 Zephyr Kconfig modules (399 options) |
| **Peripheral Configurator** | 11 peripheral templates, 22 instances with DTS generation |
| **Clock Configurator** | Visual clock-tree editor for MSPM0 / STM32 / nRF52 |
| **Overlay Import** | Import existing `.overlay` / `prj.conf` / scan Zephyr projects |
| **Driver Generator** | Scaffold complete Zephyr driver boilerplate from templates |
| **Renode Testbench** | Simulate generated firmware in Renode with RobotFramework |

### Supported MCU Vendors

TI · STMicroelectronics · Nordic Semiconductor · NXP · Microchip · Espressif ·
Infineon · Renesas · Silicon Labs · GigaDevice · WCH · Nuvoton · Bouffalo Lab ·
HPMicro · Puya · Artery · MindMotion · Luat

The built-in board registry now also includes a dual-core RP2040 target for
the Raspberry Pi Pico, exposing CPU-core metadata and export-target metadata to
both the Python and TypeScript backends.

---

## Quick Start

### Prerequisites

- Python ≥ 3.10
- [Zephyr SDK](https://docs.zephyrproject.org/latest/develop/getting_started/)
  (for west + toolchain)
- Renode ≥ 1.15 (optional, for simulation)

### Installation

```bash
# Clone and enter the project
cd pyontrust/gui_app/pin_configurator

# Create a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Launch the configurator
python run.py
# → Open http://localhost:5100/app in your browser
```

On Windows you can also use the bundled launcher, which creates the local
virtual environment if needed, installs dependencies, and starts the current
repo build on a predictable port:

```bat
start.bat
REM → Opens http://127.0.0.1:4124

start.bat --port 5100
REM → Override the default port when needed
```

### Using the West Extension (optional)

If you are inside a Zephyr west workspace, you can register the configurator as
a west command:

```bash
# From your west workspace root
west configure          # launch the GUI
west configure --port 5200  # custom port
west configure --headless   # API-only mode (no browser)
```

See [West Extension](#west-extension) below for setup instructions.

### Using the VS Code Extension (TypeScript backend)

The repository also includes a VS Code extension wrapper around the TypeScript backend:

```bash
cd vscode-extension
npm install
npm run build
npm run package:vsix
```

The build step stages the React frontend bundle and backend runtime under `vscode-extension/runtime/`, and the packaged extension hosts the `/app` React workspace directly inside VS Code.

---

## Architecture

```
pin_configurator/
├── server.py               # Flask backend — 22 REST endpoints
├── run.py                  # CLI launcher with argument parsing
├── board_schema.py         # Data classes: Pin, Peripheral, BoardDef
├── dts_generator.py        # DTS overlay & prj.conf generation
├── overlay_parser.py       # Import existing overlay/conf files
├── pdf_parser.py           # Multi-vendor MCU datasheet parser
├── package_generator.py    # Generate board .py from parsed data
├── datasheet_fetcher.py    # Auto-download datasheets by part number
├── module_registry.py      # Zephyr Kconfig module definitions
├── peripheral_registry.py  # Peripheral templates & DTS codegen
├── clock_registry.py       # Clock-tree definitions & frequency calc
├── driver_generator.py     # Zephyr driver boilerplate scaffolding
├── boards/                 # Board definition packages
│   ├── __init__.py         # Board registry
│   └── mspm0g3507_48qfp.py
├── web/                    # Frontend (served as static files)
│   ├── index.html          # Single-page app (dark theme)
│   ├── main.js             # Runtime entry script served by Flask
│   ├── lvgl-model.js       # Generated runtime JS from web/ts/lvgl-model.ts
│   ├── package.json        # Frontend TypeScript build/check scripts
│   ├── tsconfig.json       # Frontend TypeScript compiler settings
│   └── ts/                 # Incremental TypeScript sources for web/*.js
├── testbench/              # Renode simulation testbenches
│   └── CMakeLists.txt      # Build targets: testbench, robotbench
├── scripts/                # Automation & west extensions
│   ├── west/               # Custom west commands
│   │   └── configure.py    # `west configure` command
│   └── release.py          # Release archive + SPDX generation
├── tests/                  # Test suite (pytest)
│   ├── conftest.py         # Fixtures: Flask test client, sample data
│   ├── test_api.py         # API endpoint smoke tests
│   ├── test_pdf_parser.py  # PDF parser unit tests
│   ├── test_overlay.py     # Overlay import/export round-trip
│   └── test_driver_gen.py  # Driver generator output validation
├── Dockerfile              # Reproducible dev environment
├── requirements.txt        # Python dependencies
├── pyproject.toml          # PEP 621 project metadata
└── VERSION                 # Semantic version file
```

### Design Principles (inspired by [Swedish Embedded SDK](https://github.com/swedishembedded/sdk))

1. **West-native integration** — The tool registers as a west extension command,
   fitting naturally into the Zephyr workflow (like SE-SDK's `west simulate`).

2. **Testbench-driven development** — Renode simulation testbenches can be
   generated alongside firmware, with CMake targets for interactive
   (`testbench`) and automated (`robotbench`) testing.

3. **Multi-level testing** — Unit tests (pytest + mocks), integration tests
   (Flask test client), and system tests (RobotFramework + Renode).

4. **SPDX compliance** — All source files carry SPDX license headers. Release
   archives include SPDX BOMs via `west spdx`.

5. **Reproducible environments** — Docker image and `requirements.txt` ensure
   identical builds across machines.

6. **Driver scaffolding** — Like SE-SDK's example driver pattern
   (`DT_DRV_COMPAT`, `DEVICE_DT_INST_DEFINE`), the tool can generate complete
   Zephyr driver boilerplate.

Frontend TypeScript can be checked or rebuilt from `web/package.json` with `npm run check` or `npm run build` inside `web/`. The initial migration compiles `web/ts/*.ts` into `web/generated/` and then syncs the emitted runtime back onto the served `web/*.js` filenames.
The shared frontend contracts now live in `web/ts/lvgl-shared.d.ts`, which feeds the typed sources used for `web/lvgl-model.js` and `web/lvgl-build.js` while `web/ts/lvgl-ui.ts` remains the next incremental TypeScript migration target in the same pipeline.

*** Add File: c:\GIT\addmind\deps\pyontrust\externals\pin_configurator\web\ts\lvgl-build.ts
interface StyleValues {
  bg?: string;
  color?: string;
  radius?: number | string;
  [key: string]: unknown;
}

interface SharedStyle {
  id: string;
  name?: string;
  part?: string;
  state?: string;
  values?: StyleValues;
  symbol?: string;
}

interface LayoutNode {
  id: string;
  type: string;
  name: string;
  text?: string;
  x: number;
  y: number;
  w: number;
  h: number;
  bg?: string;
  color?: string;
  radius?: number;
  styleRefs?: string[];
  action?: string;
  targetScreenId?: string;
  transition?: string;
  transitionDuration?: number;
}

interface ScreenNode extends LayoutNode {
  nodes: LayoutNode[];
  entryActionName?: string;
}

interface LayoutState {
  startupScreenId: string;
  screens: ScreenNode[];
  sharedStyles: SharedStyle[];
}

interface ValidationIssue {
  severity: string;
  scope: string;
  id: string;
  message: string;
}

interface SharedStyleSchema {
  version: number;
}

interface NodeVisual {
  bg: string;
  color: string;
  radius: number;
}

interface TransitionInfo {
  anim: string;
}

interface BuildArtifacts {
  overlay: string;
  prj_conf: string;
  code: string;
  header: string;
  hooksHeader: string;
  hooks: string;
  integration: string;
  validation: string;
  styleSchema: string;
  issues: ValidationIssue[];
}

interface WidgetCallbackMeta {
  callbackName: string;
  hookName: string;
  eventType: string;
  target: ScreenMeta | null;
  transition: TransitionInfo;
  duration: number;
}

interface AccessorMeta {
  getterName: string;
  storageName: string;
}

interface ScreenMeta {
  screen: ScreenNode;
  symbol: string;
  entryHook: string;
}

interface RegistryApi {
  nodeEventType?: (node: LayoutNode) => string;
  widgetCtor?: (type: string) => string;
  widgetCodegenSetup?: (lines: string[], varName: string, node: LayoutNode) => void;
}

interface ModelApi {
  STYLE_SCHEMA?: SharedStyleSchema;
  validateState?: (state: LayoutState) => ValidationIssue[];
  buildValidationReport?: (state: LayoutState, issues: ValidationIssue[]) => string;
  resolveNodeVisual?: (state: LayoutState, node: LayoutNode | ScreenNode) => NodeVisual;
}

interface BuildApi {
  buildArtifacts: (state: LayoutState) => BuildArtifacts;
  buildPrjConf: (state: LayoutState) => string;
  buildHeader: (state: LayoutState) => string;
  buildHooksHeader: (state: LayoutState) => string;
  buildHooksSource: (state: LayoutState) => string;
  buildIntegrationGuide: (state: LayoutState, issues: ValidationIssue[]) => string;
  buildCode: (state: LayoutState) => string;
}

interface Window {
  LvglRegistry?: RegistryApi;
  LvglModel?: ModelApi;
  LvglBuild?: BuildApi;
  lvglCodeSymbol?: (name: string, fallback: string) => string;
  lvglNodeHookName?: (screenSymbol: string, node: LayoutNode) => string;
  lvglTransition?: (transition?: string) => TransitionInfo;
}

(() => {
  function lvglStateMask(style: SharedStyle): string {
    if (!style || style.state === "default") return style?.part || "LV_PART_MAIN";
    const stateMap: Record<string, string> = {
      pressed: "LV_STATE_PRESSED",
      focused: "LV_STATE_FOCUSED",
      checked: "LV_STATE_CHECKED",
      disabled: "LV_STATE_DISABLED",
    };
    return `${style.part || "LV_PART_MAIN"} | ${stateMap[style.state || ""] || "LV_STATE_DEFAULT"}`;
  }

  function buildSharedStyleMeta(state: LayoutState): SharedStyle[] {
    const styleIds = new Set<string>();
    state.screens.forEach((screen) => {
      (screen.styleRefs || []).forEach((styleId) => styleIds.add(styleId));
      (screen.nodes || []).forEach((node) => {
        (node.styleRefs || []).forEach((styleId) => styleIds.add(styleId));
      });
    });
    return (state.sharedStyles || [])
      .filter((style) => styleIds.has(style.id))
      .map((style) => ({
        ...style,
        symbol: window.lvglCodeSymbol?.(style.name || style.id, `style_${style.id}`) || `style_${style.id}`,
      }));
  }

  function emitStyleSetters(lines: string[], styleSymbol: string, values: StyleValues): void {
    if (values.bg) {
      lines.push(`    lv_style_set_bg_color(&${styleSymbol}, lv_color_hex(0x${String(values.bg).replace("#", "")}));`);
    }
    if (values.color) {
      lines.push(`    lv_style_set_text_color(&${styleSymbol}, lv_color_hex(0x${String(values.color).replace("#", "")}));`);
    }
    if (values.radius !== undefined && values.radius !== null && values.radius !== "") {
      lines.push(`    lv_style_set_radius(&${styleSymbol}, ${Number(values.radius) || 0});`);
    }
  }

  function buildPrjConf(state: LayoutState): string {
    const lines = [
      "CONFIG_DISPLAY=y",
      "CONFIG_LVGL=y",
    ];
    if (state.screens.some((screen) => (screen.nodes || []).some((node) => node.type === "image"))) {
      lines.push("CONFIG_LV_Z_MEM_POOL_SIZE=32768");
    }
    return lines.join("\n");
  }

  function buildHeader(state: LayoutState): string {
    const lines = [
      "// Generated by Zephyr Pin Configurator - LVGL Layout Editor",
      "// Generated file: safe to overwrite when layout changes.",
      "#pragma once",
      "",
      "#include <lvgl.h>",
      "",
      "#ifdef __cplusplus",
      "extern \"C\" {",
      "#endif",
      "",
      "// Stable generated IDs",
    ];

    state.screens.forEach((screen) => {
      const symbol = window.lvglCodeSymbol?.(screen.name, "screen") || "screen";
      lines.push(`#define UI_ID_${symbol.toUpperCase()} ${JSON.stringify(screen.name)}`);
      (screen.nodes || []).forEach((node) => {
        const nodeSymbol = window.lvglCodeSymbol?.(node.name, node.type) || node.type;
        lines.push(`#define UI_ID_${symbol.toUpperCase()}_${nodeSymbol.toUpperCase()} ${JSON.stringify(`${screen.name}.${node.name}`)}`);
      });
    });

    lines.push("");
    lines.push("// Screen builders and loaders");
    state.screens.forEach((screen) => {
      const symbol = window.lvglCodeSymbol?.(screen.name, "screen") || "screen";
      lines.push(`lv_obj_t * ui_build_${symbol}(void);`);
      lines.push(`void ui_load_${symbol}(void);`);
    });

    lines.push("");
    lines.push("// Live object accessors for the most recently built UI");
    state.screens.forEach((screen) => {
      const symbol = window.lvglCodeSymbol?.(screen.name, "screen") || "screen";
      lines.push(`lv_obj_t * ui_get_${symbol}(void);`);
      (screen.nodes || []).forEach((node) => {
        const nodeSymbol = window.lvglCodeSymbol?.(node.name, node.type) || node.type;
        lines.push(`lv_obj_t * ui_get_${symbol}_${nodeSymbol}(void);`);
      });
    });

    lines.push("");
    lines.push("void ui_layout_init(void);");
    lines.push("");
    lines.push("#ifdef __cplusplus");
    lines.push("}");
    lines.push("#endif");
    return lines.join("\n");
  }

  function buildHooksHeader(state: LayoutState): string {
    const lines = [
      "// Generated by Zephyr Pin Configurator - LVGL Layout Editor",
      "// Generated file: safe to overwrite when layout changes.",
      "#pragma once",
      "",
      "#include <lvgl.h>",
      "",
      "#ifdef __cplusplus",
      "extern \"C\" {",
      "#endif",
      "",
      "// Optional application hooks (implement in ui_layout_hooks.c or user code)",
    ];

    state.screens.forEach((screen) => {
      const symbol = window.lvglCodeSymbol?.(screen.name, "screen") || "screen";
      (screen.nodes || []).forEach((node) => {
        const eventType = window.LvglRegistry?.nodeEventType?.(node) || "";
        if (!eventType) return;
        lines.push(`void ${window.lvglNodeHookName?.(symbol, node) || `${symbol}_${node.name}_hook`}(lv_event_t * e);`);
      });
    });

    lines.push("");
    lines.push("#ifdef __cplusplus");
    lines.push("}");
    lines.push("#endif");
    return lines.join("\n");
  }

  function buildHooksSource(state: LayoutState): string {
    const lines = [
      "// Generated by Zephyr Pin Configurator - LVGL Layout Editor",
      "// Template file: copy into an application-owned C file before customizing.",
      "// Regeneration may overwrite this template output.",
      "#include \"ui_layout_hooks.h\"",
      "",
    ];
    const hookItems: Array<{ hookName: string; eventType: string }> = [];

    state.screens.forEach((screen) => {
      const screenSymbol = window.lvglCodeSymbol?.(screen.name, "screen") || "screen";
      (screen.nodes || []).forEach((node) => {
        const eventType = window.LvglRegistry?.nodeEventType?.(node) || "";
        if (!eventType) return;
        hookItems.push({
          hookName: window.lvglNodeHookName?.(screenSymbol, node) || `${screenSymbol}_${node.name}_hook`,
          eventType,
        });
      });
    });

    if (!hookItems.length) {
      lines.push("// No widget event hooks are required for the current layout.");
      lines.push("// Keep this file out of the build until the layout emits hook declarations.");
      return lines.join("\n");
    }

    hookItems.forEach((item) => {
      lines.push(`void ${item.hookName}(lv_event_t * e) {`);
      lines.push("    LV_UNUSED(e);");
      lines.push(`    // TODO: handle ${item.eventType.toLowerCase()} here.`);
      lines.push("}");
      lines.push("");
    });

    return lines.join("\n").trim();
  }

  function buildCode(state: LayoutState): string {
    const lines = [
      "// Generated by Zephyr Pin Configurator - LVGL Layout Editor",
      "// Generated file: safe to overwrite when layout changes.",
      "#include \"ui_layout.h\"",
      "#include \"ui_layout_hooks.h\"",
      "",
    ];

    const screenMeta: ScreenMeta[] = state.screens.map((screen) => ({
      screen,
      symbol: window.lvglCodeSymbol?.(screen.name, "screen") || "screen",
      entryHook: screen.entryActionName
        ? window.lvglCodeSymbol?.(screen.entryActionName, `on_enter_${window.lvglCodeSymbol?.(screen.name, "screen") || "screen"}`) || ""
        : "",
    }));
    const metaById = new Map<string, ScreenMeta>(screenMeta.map((item) => [item.screen.id, item]));
    const sharedStyles = buildSharedStyleMeta(state);
    const styleById = new Map<string, SharedStyle>(sharedStyles.map((style) => [style.id, style]));
    const widgetCallbacks: WidgetCallbackMeta[] = [];
    const accessors: AccessorMeta[] = [];

    screenMeta.forEach((item) => {
      accessors.push({ getterName: `ui_get_${item.symbol}`, storageName: `g_ui_${item.symbol}` });
      (item.screen.nodes || []).forEach((node) => {
        const nodeSymbol = window.lvglCodeSymbol?.(node.name, node.type) || node.type;
        accessors.push({
          getterName: `ui_get_${item.symbol}_${nodeSymbol}`,
          storageName: `g_ui_${item.symbol}_${nodeSymbol}`,
        });
      });
    });

    screenMeta.forEach((item) => {
      lines.push(`lv_obj_t * ui_build_${item.symbol}(void);`);
      lines.push(`void ui_load_${item.symbol}(void);`);
    });
    lines.push("");

    accessors.forEach((item) => {
      lines.push(`static lv_obj_t * ${item.storageName};`);
    });
    sharedStyles.forEach((style) => {
      lines.push(`static lv_style_t ${style.symbol};`);
    });
    if (accessors.length) {
      lines.push("");
    }

    if (sharedStyles.length) {
      lines.push("static void ui_init_shared_styles(void);");
    }

    screenMeta.forEach((item) => {
      if (item.entryHook) {
        lines.push(`static void ${item.entryHook}(lv_obj_t * screen);`);
      }
    });

    screenMeta.forEach((item) => {
      (item.screen.nodes || []).forEach((node) => {
        const eventType = window.LvglRegistry?.nodeEventType?.(node) || "";
        if (!eventType) return;
        widgetCallbacks.push({
          callbackName: `on_${item.symbol}_${window.lvglCodeSymbol?.(node.name, node.type) || node.type}_event`,
          hookName: window.lvglNodeHookName?.(item.symbol, node) || `${item.symbol}_${node.name}_hook`,
          eventType,
          target: node.action === "goto" && node.targetScreenId ? metaById.get(node.targetScreenId) || null : null,
          transition: window.lvglTransition?.(node.transition) || { anim: "LV_SCR_LOAD_ANIM_MOVE_LEFT" },
          duration: Math.max(0, Number(node.transitionDuration) || 220),
        });
      });
    });

    const uniqueCallbacks: WidgetCallbackMeta[] = [];
    const seenCallbacks = new Set<string>();
    widgetCallbacks.forEach((item) => {
      if (!item.target || seenCallbacks.has(item.callbackName)) return;
      seenCallbacks.add(item.callbackName);
      uniqueCallbacks.push(item);
    });
    widgetCallbacks.forEach((item) => {
      if (seenCallbacks.has(item.callbackName)) return;
      seenCallbacks.add(item.callbackName);
      uniqueCallbacks.push(item);
    });
    uniqueCallbacks.forEach((item) => {
      lines.push(`static void ${item.callbackName}(lv_event_t * e);`);
    });

    if (lines[lines.length - 1] !== "") {
      lines.push("");
    }

    if (sharedStyles.length) {
      lines.push("static void ui_init_shared_styles(void) {");
      sharedStyles.forEach((style) => {
        lines.push(`    lv_style_init(&${style.symbol});`);
        emitStyleSetters(lines, style.symbol || "style", style.values || {});
      });
      lines.push("}");
      lines.push("");
    }

    screenMeta.forEach((item) => {
      const screen = item.screen;
      const screenVisual = window.LvglModel?.resolveNodeVisual?.(state, screen) || { bg: screen.bg || "#0f172a", color: screen.color || "#f8fafc", radius: screen.radius || 24 };
      lines.push(`lv_obj_t * ui_build_${item.symbol}(void) {`);
      lines.push("    lv_obj_t * screen = lv_obj_create(NULL);");
      lines.push(`    g_ui_${item.symbol} = screen;`);
      lines.push(`    lv_obj_set_size(screen, ${screen.w}, ${screen.h});`);
      lines.push(`    lv_obj_set_style_bg_color(screen, lv_color_hex(0x${screenVisual.bg.replace("#", "")}), LV_PART_MAIN);`);
      lines.push(`    lv_obj_set_style_radius(screen, ${screenVisual.radius}, LV_PART_MAIN);`);
      (screen.styleRefs || []).forEach((styleId) => {
        const style = styleById.get(styleId);
        if (!style || !style.symbol) return;
        lines.push(`    lv_obj_add_style(screen, &${style.symbol}, ${lvglStateMask(style)});`);
      });

      (screen.nodes || []).forEach((node) => {
        const varName = window.lvglCodeSymbol?.(node.name, node.type) || node.type;
        const nodeVisual = window.LvglModel?.resolveNodeVisual?.(state, node) || { bg: node.bg || "#334155", color: node.color || "#f8fafc", radius: node.radius || 14 };
        lines.push("");
        lines.push(`    lv_obj_t * ${varName} = ${window.LvglRegistry?.widgetCtor?.(node.type) || "lv_obj_create(screen)"};`);
        lines.push(`    g_ui_${item.symbol}_${varName} = ${varName};`);
        lines.push(`    lv_obj_set_pos(${varName}, ${node.x}, ${node.y});`);
        lines.push(`    lv_obj_set_size(${varName}, ${node.w}, ${node.h});`);
        lines.push(`    lv_obj_set_style_bg_color(${varName}, lv_color_hex(0x${nodeVisual.bg.replace("#", "")}), LV_PART_MAIN);`);
        lines.push(`    lv_obj_set_style_text_color(${varName}, lv_color_hex(0x${nodeVisual.color.replace("#", "")}), LV_PART_MAIN);`);
        lines.push(`    lv_obj_set_style_radius(${varName}, ${nodeVisual.radius}, LV_PART_MAIN);`);
        (node.styleRefs || []).forEach((styleId) => {
          const style = styleById.get(styleId);
          if (!style || !style.symbol) return;
          lines.push(`    lv_obj_add_style(${varName}, &${style.symbol}, ${lvglStateMask(style)});`);
        });
        window.LvglRegistry?.widgetCodegenSetup?.(lines, varName, node);
        const eventType = window.LvglRegistry?.nodeEventType?.(node) || "";
        if (eventType) {
          const callbackName = `on_${item.symbol}_${window.lvglCodeSymbol?.(node.name, node.type) || node.type}_event`;
          if (node.type !== "button") {
            lines.push(`    lv_obj_add_flag(${varName}, LV_OBJ_FLAG_CLICKABLE);`);
          }
          lines.push(`    lv_obj_add_event_cb(${varName}, ${callbackName}, ${eventType}, NULL);`);
        }
      });

      lines.push("");
      lines.push("    return screen;");
      lines.push("}");
      lines.push("");
    });

    screenMeta.forEach((item) => {
      if (item.entryHook) {
        lines.push(`static void ${item.entryHook}(lv_obj_t * screen) {`);
        lines.push("    LV_UNUSED(screen);");
        lines.push("    // TODO: add screen entry logic here.");
        lines.push("}");
        lines.push("");
      }
    });

    accessors.forEach((item) => {
      lines.push(`lv_obj_t * ${item.getterName}(void) {`);
      lines.push(`    return ${item.storageName};`);
      lines.push("}");
      lines.push("");
    });

    screenMeta.forEach((item) => {
      lines.push(`void ui_load_${item.symbol}(void) {`);
      lines.push(`    lv_obj_t * screen = ui_build_${item.symbol}();`);
      if (item.entryHook) {
        lines.push(`    ${item.entryHook}(screen);`);
      }
      lines.push("    lv_scr_load(screen);");
      lines.push("}");
      lines.push("");
    });

    uniqueCallbacks.forEach((item) => {
      lines.push(`static void ${item.callbackName}(lv_event_t * e) {`);
      lines.push(`    ${item.hookName}(e);`);
      if (item.target) {
        lines.push(`    lv_obj_t * screen = ui_build_${item.target.symbol}();`);
        if (item.target.entryHook) {
          lines.push(`    ${item.target.entryHook}(screen);`);
        }
        lines.push(`    lv_scr_load_anim(screen, ${item.transition.anim}, ${item.duration}, 0, false);`);
      }
      lines.push("}");
      lines.push("");
    });

    const startup = metaById.get(state.startupScreenId) || screenMeta[0];
    if (startup) {
      lines.push("void ui_layout_init(void) {");
      if (sharedStyles.length) {
        lines.push("    ui_init_shared_styles();");
      }
      lines.push(`    ui_load_${startup.symbol}();`);
      lines.push("}");
    }

    return lines.join("\n").trim();
  }

  function buildIntegrationGuide(state: LayoutState, issues: ValidationIssue[]): string {
    const startup = state.screens.find((screen) => screen.id === state.startupScreenId) || state.screens[0] || null;
    const hookCount = state.screens.reduce((count, screen) => {
      return count + (screen.nodes || []).filter((node) => !!(window.LvglRegistry?.nodeEventType?.(node) || "")).length;
    }, 0);
    const screenSummary: string[] = [];
    const accessorSummary: string[] = [];
    const hookSummary: string[] = [];

    state.screens.forEach((screen) => {
      const screenSymbol = window.lvglCodeSymbol?.(screen.name, "screen") || "screen";
      const widgetCount = (screen.nodes || []).length;
      screenSummary.push(`- \`${screen.name}\` (${screen.w}x${screen.h})${screen.id === state.startupScreenId ? " [startup]" : ""} with ${widgetCount} widget${widgetCount === 1 ? "" : "s"}.`);
      screenSummary.push(`  Generated ID: \`UI_ID_${screenSymbol.toUpperCase()}\``);
      screenSummary.push(`  Accessors: \`ui_build_${screenSymbol}()\`, \`ui_load_${screenSymbol}()\`, \`ui_get_${screenSymbol}()\``);

      (screen.nodes || []).forEach((node) => {
        const nodeSymbol = window.lvglCodeSymbol?.(node.name, node.type) || node.type;
        accessorSummary.push(`- \`${screen.name}.${node.name}\`: \`UI_ID_${screenSymbol.toUpperCase()}_${nodeSymbol.toUpperCase()}\`, accessor \`ui_get_${screenSymbol}_${nodeSymbol}()\`.`);
        const eventType = window.LvglRegistry?.nodeEventType?.(node) || "";
        if (eventType) {
          hookSummary.push(`- \`${window.lvglNodeHookName?.(screenSymbol, node) || `${screenSymbol}_${node.name}_hook`}(lv_event_t * e)\` for \`${screen.name}.${node.name}\` on \`${eventType}\`.`);
        }
      });
    });

    const lines = [
      "# LVGL Layout Integration Guide",
      "",
      "## Generated Files",
      "",
      "- `ui_layout.h`: generated public layout API and object accessors. Safe to overwrite.",
      "- `ui_layout.c`: generated screen builders, loaders, and internal event routing. Safe to overwrite.",
      "- `ui_layout_hooks.h`: generated hook declarations for user-owned handlers. Safe to overwrite.",
      hookCount
        ? "- `ui_layout_hooks.template.c`: copy this once into an application-owned `.c` file and rename it before customizing. Regeneration may overwrite the template output."
        : "- `ui_layout_hooks.template.c`: currently only a placeholder because this layout does not emit widget hooks yet.",
      "- `ui_layout_validation.md`: generated validation report for layout consistency and style-schema readiness.",
      "",
      "## Build Integration",
      "",
      "```cmake",
      "target_sources(app PRIVATE",
      "  src/ui/ui_layout.c",
      hookCount ? "  src/ui/ui_layout_hooks_user.c" : "  # no user hook source needed for the current layout",
      ")",
      "```",
      "",
      "## Startup",
      "",
      startup
        ? `The current startup screen is \`${startup.name}\`. Call \`ui_layout_init()\` after LVGL and the display pipeline are initialized.`
        : "Call `ui_layout_init()` after LVGL and the display pipeline are initialized.",
      "",
      "## Shared Style Schema",
      "",
      `- Shared styles configured: ${(state.sharedStyles || []).length}`,
      `- Style schema version: ${window.LvglModel?.STYLE_SCHEMA?.version || 1}`,
      "- Current schema models LVGL parts, states, and property mappings separately from widgets.",
      "- Shared styles attached in generated code are initialized in `ui_init_shared_styles()` and applied with `lv_obj_add_style()`.",
      "",
      "## Validation Summary",
      "",
      issues.length
        ? `- ${issues.filter((issue) => issue.severity === "error").length} error(s), ${issues.filter((issue) => issue.severity === "warning").length} warning(s), ${issues.filter((issue) => issue.severity === "info").length} info item(s).`
        : "- No validation issues detected.",
      "",
      "## Current Layout Inventory",
      "",
      ...screenSummary,
      "",
      "## Generated Widget Accessors",
      "",
      ...(accessorSummary.length ? accessorSummary : ["- No widget accessors are generated because the current layout has no widgets."]),
      "",
      "## Generated Hook Signatures",
      "",
      ...(hookSummary.length ? hookSummary : ["- No generated widget hooks for the current layout."]),
    ];

    return lines.join("\n");
  }

  function buildArtifacts(state: LayoutState): BuildArtifacts {
    const issues = window.LvglModel?.validateState?.(state) || [];
    return {
      overlay: "",
      prj_conf: buildPrjConf(state),
      code: buildCode(state),
      header: buildHeader(state),
      hooksHeader: buildHooksHeader(state),
      hooks: buildHooksSource(state),
      integration: buildIntegrationGuide(state, issues),
      validation: window.LvglModel?.buildValidationReport?.(state, issues) || "",
      styleSchema: JSON.stringify(window.LvglModel?.STYLE_SCHEMA || {}, null, 2),
      issues,
    };
  }

  const LvglBuild: BuildApi = {
    buildArtifacts,
    buildPrjConf,
    buildHeader,
    buildHooksHeader,
    buildHooksSource,
    buildIntegrationGuide,
    buildCode,
  };

  window.LvglBuild = LvglBuild;
})();

---

## API Reference

### Board & Pin Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/boards` | List available board packages |
| `GET`  | `/api/board/<name>` | Get full board definition |
| `POST` | `/api/generate` | Generate Zephyr, Arduino, and bare-metal output files |
| `POST` | `/api/save-project` | Write generated files to disk |

### Package Manager

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/parse-pdf` | Upload & parse MCU datasheet PDF |
| `POST` | `/api/generate-package` | Generate board `.py` from parse results |
| `POST` | `/api/identify-mcu` | Identify MCU vendor from part number |
| `POST` | `/api/fetch-datasheet` | Auto-download & parse datasheet |

### Module Configurator

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/module-defs` | List all Zephyr module definitions |
| `POST` | `/api/generate-module-conf` | Generate prj.conf from module picks |

### Peripheral Configurator

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/peripheral-templates` | List peripheral config templates |
| `GET`  | `/api/peripheral-instances/<board>` | Get instances for a board |
| `POST` | `/api/generate-peripheral` | Generate peripheral DTS config |

### Clock Configurator

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/clock-trees` | List available clock trees |
| `GET`  | `/api/clock-tree/<name>` | Get specific clock tree |
| `POST` | `/api/calculate-clocks` | Compute frequencies from settings |
| `POST` | `/api/generate-clock-config` | Generate clock DTS config |

### Import & Export

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/import-overlay` | Import overlay + conf text |
| `POST` | `/api/scan-project` | Scan Zephyr project directory |

### Driver Generator

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/driver-templates` | List driver scaffolding templates |
| `POST` | `/api/generate-driver` | Generate Zephyr driver boilerplate |

---

## West Extension

Register the configurator as a custom west command by adding to your workspace
`west.yml`:

```yaml
manifest:
  self:
    west-commands: pyontrust/gui_app/pin_configurator/scripts/west/west-commands.yml
```

Then create `scripts/west/west-commands.yml`:

```yaml
west-commands:
  - file: scripts/west/configure.py
    commands:
      - name: configure
        class: Configure
        help: Launch the Pyontrust pin configurator GUI
```

Usage:

```bash
west configure                     # Open GUI in browser
west configure --port 5200         # Custom port
west configure --headless          # API-only, no browser
west configure --board lp_mspm0g3507  # Pre-select board
```

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html

# Run only unit tests (no server required)
pytest tests/ -m "not integration" -v

# Run integration tests (requires running server)
pytest tests/ -m integration -v
```

To validate generated Zephyr artifacts against a real board build, use the
compile-backed test runner script from PowerShell:

```powershell
pwsh -File scripts/run_zephyr_codegen_tests.ps1 `
  -Workspace C:/path/to/existing/west/workspace `
  -Python312Path C:/Python312/python.exe
```

The script:

- bootstraps or reuses the configurator `.venv`
- creates a dedicated Python 3.12 Zephyr test environment under
  `%LOCALAPPDATA%/Pyontrust/pinconfig-zephyr-test-py312`
- installs the minimal Zephyr Python tooling needed by the compile-backed test
- runs `tests/test_zephyr_codegen.py`, including the real `west build` check

For CI, the repository includes a self-contained Zephyr manifest at
`demo/zephyr_ci_workspace/west.yml` that is consumed by the GitHub Actions
workflow.

---

## Simulation / Testbench

The tool can generate Renode testbench files alongside your firmware. Inspired
by the Swedish Embedded SDK testbench architecture:

```bash
# Build firmware
west build -p -b lp_mspm0g3507 .

# Run interactive testbench (Renode GUI)
west build -t testbench

# Run automated tests (RobotFramework + Renode)
west build -t robotbench

# Run board-level simulation
west build -t boardbench
```

---

## Release

```bash
# Generate a release archive with SPDX BOM
python scripts/release.py --board lp_mspm0g3507 --source apps/locator_base

# Output: release/<name>-<board>-<version>.tar.gz
#   Contains: zephyr.elf, .config, spdx/
```

---

## Docker

```bash
# Build the dev image
docker build -t pyontrust:latest .

# Run with USB passthrough (for flashing)
docker run -ti --privileged \
  -v /dev/bus/usb:/dev/bus/usb \
  -p 5100:5100 \
  pyontrust:latest

# Inside container:
python run.py
```

---

## Contributing

1. All source files must include SPDX license headers
2. Run `pytest` before submitting changes
3. Follow PEP 8 style (enforced by flake8)
4. Add tests for new features

---

## License

SPDX-License-Identifier: Apache-2.0

Copyright 2024-2025 Pyontrust Contributors
