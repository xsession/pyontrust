import * as vscode from 'vscode';
import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import { existsSync } from 'node:fs';
import * as net from 'node:net';
import * as path from 'node:path';

interface PinConfiguratorPaths {
  extensionRoot: string;
  repoRoot: string;
  runtimeRoot: string;
  backendTsDir: string;
  backendEntry: string;
  backendNodeModulesDir: string;
  mode: 'packaged' | 'repo';
}

interface BackendSession {
  process: ChildProcessWithoutNullStreams;
  host: string;
  port: number;
  paths: PinConfiguratorPaths;
}

let panel: vscode.WebviewPanel | undefined;
let backendSession: BackendSession | undefined;
let outputChannel: vscode.OutputChannel;
let statusBarItem: vscode.StatusBarItem;

export function activate(context: vscode.ExtensionContext): void {
  outputChannel = vscode.window.createOutputChannel('Pin Configurator');
  statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusBarItem.command = 'pinConfigurator.open';
  context.subscriptions.push(outputChannel, statusBarItem);

  updateStatusBar();
  statusBarItem.show();

  context.subscriptions.push(
    vscode.commands.registerCommand('pinConfigurator.open', async () => {
      await openPinConfigurator(context);
    }),
    vscode.commands.registerCommand('pinConfigurator.restartBackend', async () => {
      const paths = backendSession?.paths ?? resolvePaths(context);
      await restartBackend(paths);
      if (panel) {
        await renderPanel(panel, paths);
      }
    }),
    vscode.commands.registerCommand('pinConfigurator.stopBackend', async () => {
      await stopBackend();
      vscode.window.showInformationMessage('Pin Configurator backend stopped.');
    }),
    vscode.commands.registerCommand('pinConfigurator.showOutput', () => {
      outputChannel.show(true);
    }),
    new vscode.Disposable(() => {
      void stopBackend();
    }),
  );
}

export function deactivate(): Thenable<void> | void {
  return stopBackend();
}

async function openPinConfigurator(context: vscode.ExtensionContext): Promise<void> {
  const paths = resolvePaths(context);
  const activeColumn = vscode.window.activeTextEditor?.viewColumn ?? vscode.ViewColumn.One;

  if (panel) {
    panel.reveal(activeColumn);
    await renderPanel(panel, paths);
    return;
  }

  panel = vscode.window.createWebviewPanel(
    'pinConfigurator.app',
    'Pin Configurator',
    activeColumn,
    {
      enableScripts: true,
      retainContextWhenHidden: true,
    },
  );

  panel.onDidDispose(() => {
    panel = undefined;
  });

  await renderPanel(panel, paths);
}

async function renderPanel(targetPanel: vscode.WebviewPanel, paths: PinConfiguratorPaths): Promise<void> {
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

function resolvePaths(context: vscode.ExtensionContext): PinConfiguratorPaths {
  const extensionRoot = context.extensionPath;
  const packagedRuntimeRoot = path.join(extensionRoot, 'runtime');
  const packagedBackendTsDir = path.join(packagedRuntimeRoot, 'backend_ts');
  const packagedBackendEntry = path.join(packagedBackendTsDir, 'dist', 'server_entry.js');
  if (existsSync(packagedBackendEntry)) {
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

async function ensureBackendRunning(paths: PinConfiguratorPaths): Promise<BackendSession> {
  if (backendSession && backendSession.process.exitCode === null) {
    return backendSession;
  }

  await ensureBackendRuntime(paths);

  const host = String(vscode.workspace.getConfiguration('pinConfigurator').get('host', '127.0.0.1'));
  const preferredPort = Number(vscode.workspace.getConfiguration('pinConfigurator').get('port', 5110));
  const port = await getAvailablePort(preferredPort, host);

  outputChannel.appendLine(`Starting Pin Configurator ${paths.mode} backend on http://${host}:${port}`);
  const child = spawn(process.execPath, [paths.backendEntry, '--host', host, '--port', String(port)], {
    cwd: paths.backendTsDir,
    env: {
      ...process.env,
      NODE_PATH: paths.backendNodeModulesDir,
    },
  });

  child.stdout.on('data', (chunk: Buffer) => {
    outputChannel.append(chunk.toString('utf8'));
  });
  child.stderr.on('data', (chunk: Buffer) => {
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

async function ensureBackendRuntime(paths: PinConfiguratorPaths): Promise<void> {
  if (paths.mode === 'packaged') {
    if (!existsSync(paths.backendEntry)) {
      throw new Error('Packaged Pin Configurator runtime is missing. Rebuild the extension bundle.');
    }
    return;
  }

  if (!existsSync(path.join(paths.backendNodeModulesDir, 'express'))) {
    outputChannel.appendLine('Installing Pin Configurator backend dependencies...');
    await runNpm(['install'], paths.backendTsDir);
  }

  if (!existsSync(paths.backendEntry)) {
    outputChannel.appendLine('Building Pin Configurator TypeScript backend...');
    await runNpm(['run', 'build'], paths.backendTsDir);
  }
}

async function restartBackend(paths: PinConfiguratorPaths): Promise<void> {
  await stopBackend();
  await ensureBackendRunning(paths);
  vscode.window.showInformationMessage('Pin Configurator backend restarted.');
}

async function stopBackend(): Promise<void> {
  if (!backendSession) {
    updateStatusBar();
    return;
  }

  const session = backendSession;
  backendSession = undefined;
  session.process.kill();
  updateStatusBar();
}

async function runNpm(args: string[], cwd: string): Promise<void> {
  const executable = process.platform === 'win32' ? 'npm.cmd' : 'npm';
  await new Promise<void>((resolve, reject) => {
    const child = spawn(executable, args, { cwd, env: process.env });
    child.stdout.on('data', (chunk: Buffer) => outputChannel.append(chunk.toString('utf8')));
    child.stderr.on('data', (chunk: Buffer) => outputChannel.append(chunk.toString('utf8')));
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

async function getAvailablePort(preferredPort: number, host: string): Promise<number> {
  if (!(await isPortOpen(preferredPort, host))) {
    return preferredPort;
  }
  return await getFreePort(host);
}

async function isPortOpen(port: number, host: string): Promise<boolean> {
  return await new Promise<boolean>((resolve) => {
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

async function getFreePort(host: string): Promise<number> {
  return await new Promise<number>((resolve, reject) => {
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

async function waitForPort(port: number, host: string, timeoutMs: number): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (await isPortOpen(port, host)) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error(`Timed out waiting for Pin Configurator backend on ${host}:${port}`);
}

function updateStatusBar(): void {
  if (!statusBarItem) {
    return;
  }
  if (backendSession) {
    statusBarItem.text = `$(plug) Pin Configurator ${backendSession.port}`;
    statusBarItem.tooltip = `Pin Configurator backend running on ${backendSession.host}:${backendSession.port}`;
  } else {
    statusBarItem.text = '$(play) Pin Configurator';
    statusBarItem.tooltip = 'Open Pin Configurator';
  }
}

function getNonce(): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let value = '';
  for (let index = 0; index < 32; index += 1) {
    value += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return value;
}