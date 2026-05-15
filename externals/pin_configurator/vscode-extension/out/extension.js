"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const node_child_process_1 = require("node:child_process");
const node_fs_1 = require("node:fs");
const net = __importStar(require("node:net"));
const path = __importStar(require("node:path"));
let panel;
let backendSession;
let outputChannel;
let statusBarItem;
function activate(context) {
    outputChannel = vscode.window.createOutputChannel('Pin Configurator');
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    statusBarItem.command = 'pinConfigurator.open';
    context.subscriptions.push(outputChannel, statusBarItem);
    updateStatusBar();
    statusBarItem.show();
    context.subscriptions.push(vscode.commands.registerCommand('pinConfigurator.open', async () => {
        await openPinConfigurator(context);
    }), vscode.commands.registerCommand('pinConfigurator.restartBackend', async () => {
        const paths = backendSession?.paths ?? resolvePaths(context);
        await restartBackend(paths);
        if (panel) {
            await renderPanel(panel, paths);
        }
    }), vscode.commands.registerCommand('pinConfigurator.stopBackend', async () => {
        await stopBackend();
        vscode.window.showInformationMessage('Pin Configurator backend stopped.');
    }), vscode.commands.registerCommand('pinConfigurator.showOutput', () => {
        outputChannel.show(true);
    }), new vscode.Disposable(() => {
        void stopBackend();
    }));
}
function deactivate() {
    return stopBackend();
}
async function openPinConfigurator(context) {
    const paths = resolvePaths(context);
    const activeColumn = vscode.window.activeTextEditor?.viewColumn ?? vscode.ViewColumn.One;
    if (panel) {
        panel.reveal(activeColumn);
        await renderPanel(panel, paths);
        return;
    }
    panel = vscode.window.createWebviewPanel('pinConfigurator.app', 'Pin Configurator', activeColumn, {
        enableScripts: true,
        retainContextWhenHidden: true,
    });
    panel.onDidDispose(() => {
        panel = undefined;
    });
    await renderPanel(panel, paths);
}
async function renderPanel(targetPanel, paths) {
    const backend = await ensureBackendRunning(paths);
    const webview = targetPanel.webview;
    const appUri = await vscode.env.asExternalUri(vscode.Uri.parse(`http://${backend.host}:${backend.port}/app/`));
    const nonce = getNonce();
    targetPanel.webview.html = `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; frame-src ${webview.cspSource} http: https:; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
    <title>Pin Configurator</title>
    <style>
      html, body, iframe {
        width: 100%;
        height: 100%;
        margin: 0;
        padding: 0;
        border: 0;
        overflow: hidden;
        background: #111827;
      }
    </style>
  </head>
  <body>
    <iframe src="${appUri.toString()}" title="Pin Configurator"></iframe>
    <script nonce="${nonce}">
      window.addEventListener('message', () => {});
    </script>
  </body>
</html>`;
}
function resolvePaths(context) {
    const extensionRoot = context.extensionPath;
    const packagedRuntimeRoot = path.join(extensionRoot, 'runtime');
    const packagedBackendTsDir = path.join(packagedRuntimeRoot, 'backend_ts');
    const packagedBackendEntry = path.join(packagedBackendTsDir, 'dist', 'server_entry.js');
    if ((0, node_fs_1.existsSync)(packagedBackendEntry)) {
        return {
            extensionRoot,
            repoRoot: packagedRuntimeRoot,
            runtimeRoot: packagedRuntimeRoot,
            backendTsDir: packagedBackendTsDir,
            backendEntry: packagedBackendEntry,
            backendNodeModulesDir: path.join(extensionRoot, 'node_modules'),
            mode: 'packaged',
        };
    }
    const repoRoot = path.resolve(extensionRoot, '..');
    const backendTsDir = path.join(repoRoot, 'backend_ts');
    const backendEntry = path.join(backendTsDir, 'dist', 'server_entry.js');
    const backendNodeModulesDir = path.join(backendTsDir, 'node_modules');
    return {
        extensionRoot,
        repoRoot,
        runtimeRoot: repoRoot,
        backendTsDir,
        backendEntry,
        backendNodeModulesDir,
        mode: 'repo',
    };
}
async function ensureBackendRunning(paths) {
    if (backendSession && backendSession.process.exitCode === null) {
        return backendSession;
    }
    await ensureBackendRuntime(paths);
    const host = String(vscode.workspace.getConfiguration('pinConfigurator').get('host', '127.0.0.1'));
    const preferredPort = Number(vscode.workspace.getConfiguration('pinConfigurator').get('port', 5110));
    const port = await getAvailablePort(preferredPort, host);
    outputChannel.appendLine(`Starting Pin Configurator ${paths.mode} backend on http://${host}:${port}`);
    const child = (0, node_child_process_1.spawn)(process.execPath, [paths.backendEntry, '--host', host, '--port', String(port)], {
        cwd: paths.backendTsDir,
        env: {
            ...process.env,
            NODE_PATH: paths.backendNodeModulesDir,
        },
    });
    child.stdout.on('data', (chunk) => {
        outputChannel.append(chunk.toString('utf8'));
    });
    child.stderr.on('data', (chunk) => {
        outputChannel.append(chunk.toString('utf8'));
    });
    child.on('exit', (code) => {
        outputChannel.appendLine(`Pin Configurator backend exited with code ${code ?? 'null'}`);
        if (backendSession?.process === child) {
            backendSession = undefined;
            updateStatusBar();
        }
    });
    backendSession = { process: child, host, port, paths };
    updateStatusBar();
    await waitForPort(port, host, 30_000);
    return backendSession;
}
async function ensureBackendRuntime(paths) {
    if (paths.mode === 'packaged') {
        if (!(0, node_fs_1.existsSync)(paths.backendEntry)) {
            throw new Error('Packaged Pin Configurator runtime is missing. Rebuild the extension bundle.');
        }
        return;
    }
    if (!(0, node_fs_1.existsSync)(path.join(paths.backendNodeModulesDir, 'express'))) {
        outputChannel.appendLine('Installing Pin Configurator backend dependencies...');
        await runNpm(['install'], paths.backendTsDir);
    }
    if (!(0, node_fs_1.existsSync)(paths.backendEntry)) {
        outputChannel.appendLine('Building Pin Configurator TypeScript backend...');
        await runNpm(['run', 'build'], paths.backendTsDir);
    }
}
async function restartBackend(paths) {
    await stopBackend();
    await ensureBackendRunning(paths);
    vscode.window.showInformationMessage('Pin Configurator backend restarted.');
}
async function stopBackend() {
    if (!backendSession) {
        updateStatusBar();
        return;
    }
    const session = backendSession;
    backendSession = undefined;
    session.process.kill();
    updateStatusBar();
}
async function runNpm(args, cwd) {
    const executable = process.platform === 'win32' ? 'npm.cmd' : 'npm';
    await new Promise((resolve, reject) => {
        const child = (0, node_child_process_1.spawn)(executable, args, { cwd, env: process.env });
        child.stdout.on('data', (chunk) => outputChannel.append(chunk.toString('utf8')));
        child.stderr.on('data', (chunk) => outputChannel.append(chunk.toString('utf8')));
        child.on('error', reject);
        child.on('exit', (code) => {
            if (code === 0) {
                resolve();
                return;
            }
            reject(new Error(`npm ${args.join(' ')} failed with code ${code ?? 'null'}`));
        });
    });
}
async function getAvailablePort(preferredPort, host) {
    if (!(await isPortOpen(preferredPort, host))) {
        return preferredPort;
    }
    return await getFreePort(host);
}
async function isPortOpen(port, host) {
    return await new Promise((resolve) => {
        const socket = new net.Socket();
        socket.once('connect', () => {
            socket.destroy();
            resolve(true);
        });
        socket.once('error', () => {
            socket.destroy();
            resolve(false);
        });
        socket.connect(port, host);
    });
}
async function getFreePort(host) {
    return await new Promise((resolve, reject) => {
        const server = net.createServer();
        server.on('error', reject);
        server.listen(0, host, () => {
            const address = server.address();
            if (!address || typeof address === 'string') {
                server.close(() => reject(new Error('Could not determine a free port')));
                return;
            }
            const { port } = address;
            server.close((error) => {
                if (error) {
                    reject(error);
                    return;
                }
                resolve(port);
            });
        });
    });
}
async function waitForPort(port, host, timeoutMs) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
        if (await isPortOpen(port, host)) {
            return;
        }
        await new Promise((resolve) => setTimeout(resolve, 200));
    }
    throw new Error(`Timed out waiting for Pin Configurator backend on ${host}:${port}`);
}
function updateStatusBar() {
    if (!statusBarItem) {
        return;
    }
    if (backendSession) {
        statusBarItem.text = `$(plug) Pin Configurator ${backendSession.port}`;
        statusBarItem.tooltip = `Pin Configurator backend running on ${backendSession.host}:${backendSession.port}`;
    }
    else {
        statusBarItem.text = '$(play) Pin Configurator';
        statusBarItem.tooltip = 'Open Pin Configurator';
    }
}
function getNonce() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let value = '';
    for (let index = 0; index < 32; index += 1) {
        value += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return value;
}
//# sourceMappingURL=extension.js.map