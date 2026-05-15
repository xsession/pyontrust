# Frontend Packaging Plan

This document is the implemented Phase 13 packaging guide for shipping the React workspace across browser, Flask, and VS Code extension delivery paths without breaking the existing backend and headless workflows.

## Status

- Browser, Flask, west, and VS Code extension delivery now converge on the React shell at `/app`.
- Packaged and repo-local VS Code extension runtime paths are both supported.
- Headless and API-only startup paths remain intact.
- Browser root routing now redirects to `/app`, so the legacy shell is no longer part of the active delivery surface.

## Validation Evidence

1. `npm --prefix vscode-extension run build`
2. `pytest tests/test_frontend_shell.py`
3. `npm --prefix frontend run quality:check`

## Browser And Flask Deployment

1. Build the browser bundle with `npm --prefix frontend run build:browser`.
2. Flask serves the React shell from `/app` and redirects `/` to `/app`.
3. `python run.py --open` now opens `/app` by default, while `--ui-path` can still target a different route when needed.
4. If the React bundle is missing, `/app` returns a clear 404 instead of silently falling back to a legacy shell.

## West Launch Path

1. `west configure` still starts the same Flask server and keeps `--headless` intact for API-only workflows.
2. Browser launch now targets `/app` by default so west-driven workflows land in the React workspace.
3. `--ui-path` remains available for compatibility testing or future route changes.

## VS Code Extension Hosting

1. `npm --prefix vscode-extension run build` compiles the extension and stages a packaged runtime under `vscode-extension/runtime/`.
2. The staged runtime contains the React frontend bundle, the TypeScript backend build, generated backend metadata, and the Python bridge files needed by the packaged backend.
3. When the staged runtime exists, the extension runs that packaged backend and loads `/app` inside the webview.
4. During local development, the extension still falls back to the repo-local backend so source edits remain live and debuggable.
5. Runtime Node dependencies are declared in the extension package so the staged backend can resolve `express`, `cors`, and `multer` after packaging.

## Headless And API-Only Support

1. All `/api/*` routes remain stable and independent from whether `/app` is built.
2. Flask `--open` and west browser launch behavior are only presentation changes; server startup and API behavior stay the same.
3. `west configure --headless` continues to expose the backend without opening a browser.

## Build Optimizations

1. Monaco, Dockview, Radix, and virtualization dependencies stay split into dedicated chunks for production caching and startup control.
2. CSS code splitting remains enabled so heavy editor surfaces do not collapse into one monolithic stylesheet.
3. `assetsInlineLimit: 0` keeps large editor assets external instead of inflating entry chunks.

## Source Map Strategy

1. Browser and Flask production builds emit `hidden` source maps for support and post-deployment debugging without auto-loading them in the browser.
2. Extension-target frontend builds emit normal source maps so local VS Code webview debugging can map back to the React sources.
3. The extension TypeScript compile keeps source maps for local debugging.
4. VSIX packaging excludes `*.map` files so shipped extension bundles stay smaller and do not expose debug artifacts by default.

## Shipping Commands

1. Browser bundle: `npm --prefix frontend run build:browser`
2. Extension staging: `npm --prefix vscode-extension run build`
3. VSIX packaging: `npm --prefix vscode-extension run package:vsix`
4. Full frontend quality gate: `npm --prefix frontend run quality:check`

## Residual Notes

1. The staged extension runtime and `/app` delivery path are now aligned on the same React-only browser surface.
2. The current Windows shell-execution warning in the build wrappers remains non-blocking and does not prevent packaging.