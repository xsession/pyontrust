// ─────────────────────────────────────────────────────────────────────────────
// Zephyr Pin Configurator — Architecture & Design Document
// ─────────────────────────────────────────────────────────────────────────────

#import "template.typ": *

#show: doc => enterprise-doc(
  title: "Architecture & Design",
  subtitle: "Zephyr Pin Configurator",
  version: "0.1.0",
  date: datetime(year: 2026, month: 3, day: 4),
  doc,
)

= Design Philosophy

The Zephyr Pin Configurator follows these guiding principles:

+ *Minimal dependencies* — Flask + pdfplumber + requests; no frontend
  framework. This keeps the tool lightweight and easy to embed.
+ *Offline-first* — all generation works without internet; datasheet fetching
  is optional.
+ *Vendor-agnostic core* — the `BoardDef` / `Pin` / `Peripheral` schema is
  generic; vendor specifics are isolated in parser pipelines.
+ *Code generation over configuration* — produce valid, copy-pasteable Zephyr
  artifacts rather than abstract representations.
+ *Round-trip fidelity* — any generated overlay can be re-imported via
  `overlay_parser` without data loss.


= System Context

```
┌──────────────────────────────────────────────────────────────┐
│                    Developer Workstation                      │
│                                                              │
│  ┌────────────┐   HTTP    ┌──────────────────┐              │
│  │  Browser    │ ◄──────► │ Pin Configurator  │              │
│  │  (SPA)      │          │ (Flask, port 5100)│              │
│  └────────────┘           └────────┬─────────┘              │
│                                    │                         │
│                           ┌────────┴─────────┐              │
│                           │ File System       │              │
│                           │ • boards/*.py     │              │
│                           │ • .uploads/*.pdf  │              │
│                           │ • *.zpinproj      │              │
│                           └──────────────────┘              │
│                                                              │
│  ┌──────────────────────────────────────────┐               │
│  │ Zephyr Workspace (optional)               │               │
│  │ • west build / west flash                 │               │
│  │ • boards/<board>.overlay                  │               │
│  │ • prj.conf                                │               │
│  └──────────────────────────────────────────┘               │
└──────────────────────────────────────────────────────────────┘
           │
           │ HTTPS (optional)
           ▼
  ┌─────────────────┐
  │ Vendor servers   │  TI, ST, Nordic, NXP, …
  │ (datasheet CDN)  │
  └─────────────────┘
```


= Module Decomposition

== Layer Diagram

```
┌─────────────────────────────────────────────┐
│              Presentation Layer              │
│   web/index.html  ·  web/main.js  ·  CSS    │
└──────────────────┬──────────────────────────┘
                   │  fetch() / JSON
┌──────────────────┴──────────────────────────┐
│              API Layer (server.py)           │
│    26+ Flask routes  ·  request validation   │
│    file upload handling  ·  board cache      │
└──┬───────┬───────┬───────┬──────┬───────┬───┘
   │       │       │       │      │       │
   ▼       ▼       ▼       ▼      ▼       ▼
┌──────┐┌──────┐┌──────┐┌─────┐┌─────┐┌──────┐
│board ││dts   ││over- ││pdf  ││drv  ││sensor│
│schema││gen   ││lay   ││parse││gen  ││parse │
└──────┘└──────┘│parse │└─────┘└─────┘└──────┘
         ┌──────┘└──────┘
         │
   ┌─────┴─────┐  ┌────────────┐  ┌───────────┐
   │clock_reg  │  │module_reg  │  │periph_reg │
   └───────────┘  └────────────┘  └───────────┘
         │
   ┌─────┴──────────┐  ┌──────────────────┐
   │package_generator│  │datasheet_fetcher │
   └────────────────┘  └──────────────────┘
         │
   ┌─────┴─────┐
   │boards/*   │  Board definition registry
   └───────────┘
```

== Module Responsibilities

#table(
  columns: (auto, 1fr, auto),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Module*], [*Single Responsibility*], [*Lines*],
  [`server.py`], [HTTP routing, request validation, response formatting], [~1165],
  [`board_schema.py`], [Domain model — `Pin`, `BoardDef`, `Peripheral`], [~170],
  [`dts_generator.py`], [Forward generation: assignments → DTS + Kconfig], [~200],
  [`overlay_parser.py`], [Reverse generation: DTS text → structured data], [~400],
  [`pdf_parser.py`], [MCU datasheet extraction (18+ vendors)], [~950],
  [`sensor_parser.py`], [Sensor datasheet register map extraction], [~1775],
  [`driver_generator.py`], [Zephyr driver boilerplate scaffolding], [~660],
  [`package_generator.py`], [Board .py file generation from parsed data], [~600],
  [`clock_registry.py`], [Clock tree definitions + frequency compute], [~1190],
  [`module_registry.py`], [Zephyr subsystem Kconfig catalog (27 modules)], [~1100],
  [`peripheral_registry.py`], [Peripheral config templates + DTS gen], [~1250],
  [`zephyr_kconfig_modules.py`], [Extended Kconfig definitions], [~995],
  [`datasheet_fetcher.py`], [Vendor URL construction + download], [~300],
)

*Total backend:* ~10,755 lines of Python.

*Total frontend:* ~5,827 lines (HTML + JS).


= Data Model

== Core Entity Relationships

```
BoardDef 1──* Pin
  │             └──* AltFunction
  │
  └──* Peripheral
        │
        └── matched by compatible → PeripheralTemplate
                                       └──* PropertyGroup
                                              └──* Property
```

== Pin State Machine

```
         ┌───────────┐
         │ Unassigned │ ◄── default
         └─────┬─────┘
               │ user selects AF
               ▼
         ┌───────────┐
         │ Assigned   │ ── selected_af = AF_index
         └─────┬─────┘
               │ user configures properties
               ▼
         ┌───────────┐
         │ Configured │ ── bias, drive, input_enable set
         └─────┬─────┘
               │ generate
               ▼
         ┌───────────┐
         │ In Overlay │ ── appears in generated DTS
         └───────────┘
```


= Request Lifecycle

== `POST /api/generate` — Detailed Flow

```
1. Flask receives JSON body
2. server.py validates required fields (board, assignments, peripherals)
3. Board loaded from _BOARD_CACHE (or built on-demand)
4. Assignments mapped to PinAssignment dataclasses
5. Peripherals mapped to PeripheralConfig dataclasses
6. dts_generator.generate() called:
   a. Group assignments by peripheral
   b. Generate &pinctrl node with pin states
   c. Generate peripheral nodes with status = "okay"
   d. Map DTS compatibles → Kconfig via _KCONFIG_MAP
   e. Return GeneratedOutput(overlay, prj_conf)
7. server.py serializes to JSON response
```

== `POST /api/parse-pdf` — Detailed Flow

```
1. Flask receives multipart upload
2. File saved to .uploads/<uuid>.pdf
3. pdf_parser.parse_datasheet() called:
   a. Extract all text pages via pdfplumber
   b. Detect vendor via _VENDOR_PATTERNS (18 regex patterns)
   c. Route to vendor-specific parser:
      • TI:    _parse_ti()       — PINCM tables
      • STM32: _parse_stm32_like() — AF tables + pin definitions
      • Other: _parse_generic()  — heuristic table extraction
   d. Build DatasheetInfo aggregate
4. Result cached in _PARSED_JOBS[job_id]
5. JSON summary returned
```


= Error Handling Strategy

#table(
  columns: (auto, auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Error Type*], [*HTTP Code*], [*Handling*],
  [Missing field], [400], [`{ "error": "Missing required field: board" }`],
  [Board not found], [404], [`{ "error": "Board 'xyz' not found" }`],
  [File too large], [413], [Flask `MAX_CONTENT_LENGTH` enforcement],
  [PDF parse failure], [500], [Caught exception → error message in response],
  [Invalid JSON], [400], [Werkzeug automatic 400],
  [Internal error], [500], [Flask default handler; debug mode shows traceback],
)


= Caching Strategy

#table(
  columns: (auto, auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Cache*], [*Scope*], [*Invalidation*],
  [`_BOARD_CACHE`], [Module-level dict], [`_reload_boards()` — called after package generation],
  [`_PARSED_JOBS`], [Module-level dict], [Never evicted (bounded by session lifetime)],
  [`_SENSOR_JOBS`], [Module-level dict], [Never evicted],
  [Board `BOARDS` dict], [`boards/__init__.py`], [Module reimport via `_reload_boards()`],
)


= Extension Points

== Adding a New Vendor Parser

+ Add regex pattern to `_VENDOR_PATTERNS` in `pdf_parser.py`.
+ Implement `_parse_<vendor>(pdf, text_pages, verbose) → DatasheetInfo`.
+ Register in `parse_datasheet()` routing logic.

== Adding a New Peripheral Template

+ Add template dict to `PERIPHERAL_TEMPLATES` list in `peripheral_registry.py`.
+ Include `id`, `name`, `icon`, `desc`, `compatible[]`, `signals[]`,
  `kconfig[]`, `groups[]` with `props[]`.
+ Add compatible → Kconfig mapping in `dts_generator._KCONFIG_MAP` if needed.

== Adding a New Clock Tree

+ Define tree dict in `clock_registry.py` with `nodes`, `connections`, `props`.
+ Implement `_compute_<vendor>(values)` function.
+ Register in `get_all_clock_trees()` and `compute_frequencies()` routing.

== Adding a New Driver Type

+ Add type string to `DRIVER_TYPES` list in `driver_generator.py`.
+ Create template string (`_<TYPE>_TEMPLATE`).
+ Implement `generate_<type>_driver(spec) → str`.
+ Register in `generate_driver()` routing.


= Performance Characteristics

#table(
  columns: (auto, auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Operation*], [*Typical Time*], [*Bottleneck*],
  [Board load], [< 5 ms], [Python dict lookup + dataclass construction],
  [Generate overlay], [< 10 ms], [String formatting],
  [Parse MCU PDF], [2 – 30 s], [pdfplumber page extraction (IO-bound)],
  [Parse sensor PDF], [1 – 15 s], [Register table extraction (CPU-bound)],
  [Generate driver], [< 50 ms], [Template string formatting],
  [Clock compute], [< 1 ms], [Arithmetic],
)


= Future Architecture Considerations

#table(
  columns: (auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Improvement*], [*Rationale*],
  [Database (SQLite)], [Persist parse jobs and project history across restarts],
  [WebSocket updates], [Push real-time parse progress to frontend],
  [Plugin system], [Allow third-party vendor parsers as installable packages],
  [REST → gRPC], [Typed API contracts for IDE integrations],
  [WASM PDF parser], [Client-side parsing to reduce server load],
  [Multi-user auth], [OAuth2 / OIDC for team deployments],
)
