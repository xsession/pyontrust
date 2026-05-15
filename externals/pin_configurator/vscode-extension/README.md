# Pin Configurator VS Code Extension

This extension hosts the Pin Configurator React workspace in VS Code using the TypeScript backend.

## Features

- stages the React frontend bundle and backend runtime under `runtime/` during packaging
- launches the TypeScript backend automatically when needed
- embeds the packaged `/app` React shell inside a VS Code webview
- exposes restart, stop, and output commands for backend lifecycle control
- falls back to the repo-local `backend_ts` runtime during development

## Packaging

The packaged VSIX includes the compiled extension, the staged React frontend bundle, and the backend runtime assets needed to host `/app` inside the webview.

## Commands

- `Pin Configurator: Open`
- `Pin Configurator: Restart Backend`
- `Pin Configurator: Stop Backend`
- `Pin Configurator: Show Output`

## Development

```bash
npm install
npm run build
npm run package:vsix
```

`npm run build` compiles the extension and stages `runtime/backend_ts` plus `runtime/frontend/dist` for packaging.

The extension starts the staged `backend_ts/dist/server_entry.js` runtime when packaged, or the repo-local backend during development, and then embeds the served `/app` React workspace in a VS Code webview.