# Pin Configurator — Documentation

Enterprise-grade technical documentation written in [Typst](https://typst.app/).

## Documents

| File | Purpose |
|------|---------|
| `main.typ` | **Complete reference** — all-in-one 12-chapter document (introduction, architecture, installation, user guide, API reference, module reference, board definitions, testing, deployment, security, configuration, troubleshooting + appendices) |
| `api-reference.typ` | Standalone REST API reference with request/response schemas |
| `architecture.typ` | Architecture & design — system context, module decomposition, data flow, extension points |
| `user-guide.typ` | End-user guide — workflows, UI walkthrough, troubleshooting |
| `developer-guide.typ` | Developer guide — setup, adding features, testing, contributing |
| `template.typ` | Shared Typst template with enterprise page layout, helpers, and callout macros |

## Frontend planning docs

These Markdown documents track the frontend transition and product direction alongside the Typst reference manuals.

| File | Purpose |
|------|---------|
| `frontend_platform_research.md` | External platform review and local baseline research for frontend direction |
| `frontend_product_design_spec.md` | Product-facing target for shell layout, workflow model, inspector behavior, and visual direction |
| `frontend_implementation_checklist.md` | Delivery checklist that turns the design spec into concrete frontend work |
| `frontend_mvp_refactor_plan.md` | Migration plan for the React, TypeScript, and Vite-based shell |
| `frontend_cutover_strategy.md` | React-to-legacy cutover strategy and runtime transition notes |

## Building

### Using Typst CLI

```bash
# Install Typst (https://github.com/typst/typst/releases)
# Build all documents
typst compile docs/main.typ docs/main.pdf
typst compile docs/api-reference.typ docs/api-reference.pdf
typst compile docs/architecture.typ docs/architecture.pdf
typst compile docs/user-guide.typ docs/user-guide.pdf
typst compile docs/developer-guide.typ docs/developer-guide.pdf
```

### Using VS Code

Install the [Typst Preview](https://marketplace.visualstudio.com/items?itemName=mgt19937.typst-preview) extension for live preview.

### Watch mode

```bash
typst watch docs/main.typ docs/main.pdf
```

## Template Usage

The standalone documents (`api-reference.typ`, `architecture.typ`, etc.) import the shared template:

```typst
#import "template.typ": *

#show: doc => enterprise-doc(
  title: "Document Title",
  subtitle: "Zephyr Pin Configurator",
  version: "0.1.0",
  date: datetime(year: 2026, month: 3, day: 4),
  doc,
)
```

### Available helpers

- `#param-table(("name", "in", "type", "required", "desc"), ...)` — API parameter table
- `#note[...]` — Info callout box
- `#warning[...]` — Warning callout box
- `#tip[...]` — Tip callout box
