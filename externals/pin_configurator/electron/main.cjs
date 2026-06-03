const { app, BrowserWindow, dialog, shell } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const http = require("http");
const path = require("path");

const APP_ROOT = path.resolve(__dirname, "..");
const BACKEND_HOST = "127.0.0.1";
const BACKEND_PORT = Number.parseInt(process.env.PIN_CONFIGURATOR_PORT || "4124", 10);
const BACKEND_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}/app`;
const BACKEND_WAIT_TIMEOUT_MS = 30_000;
const BACKEND_WAIT_STEP_MS = 500;

let mainWindow = null;
let backendProcess = null;
let quitting = false;

function fileExists(targetPath) {
  try {
    return fs.existsSync(targetPath);
  } catch {
    return false;
  }
}

function resolvePythonCommand() {
  const venvPython = path.join(APP_ROOT, ".venv", "Scripts", "python.exe");
  if (fileExists(venvPython)) {
    return { command: venvPython, args: [] };
  }
  return { command: "python", args: [] };
}

function requestOk(url) {
  return new Promise((resolve) => {
    const request = http.get(url, (response) => {
      response.resume();
      resolve(response.statusCode && response.statusCode >= 200 && response.statusCode < 500);
    });

    request.on("error", () => resolve(false));
    request.setTimeout(2_000, () => {
      request.destroy();
      resolve(false);
    });
  });
}

async function waitForBackend(url, timeoutMs) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (await requestOk(url)) {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, BACKEND_WAIT_STEP_MS));
  }
  return false;
}

function stopBackend() {
  if (!backendProcess || backendProcess.killed) {
    return;
  }

  try {
    backendProcess.kill();
  } catch {
    // Ignore shutdown errors during app exit.
  }
}

function startBackend() {
  if (backendProcess && !backendProcess.killed) {
    return backendProcess;
  }

  const python = resolvePythonCommand();
  const runScript = path.join(APP_ROOT, "run.py");
  const args = [
    ...python.args,
    runScript,
    "--host",
    BACKEND_HOST,
    "--port",
    String(BACKEND_PORT),
    "--ui-path",
    "/app",
  ];

  backendProcess = spawn(python.command, args, {
    cwd: APP_ROOT,
    env: {
      ...process.env,
      PYTHONIOENCODING: "utf-8",
    },
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });

  backendProcess.stdout.on("data", (chunk) => {
    process.stdout.write(`[pin-configurator] ${chunk}`);
  });
  backendProcess.stderr.on("data", (chunk) => {
    process.stderr.write(`[pin-configurator] ${chunk}`);
  });
  backendProcess.on("exit", (code) => {
    if (!quitting && code !== 0 && mainWindow && !mainWindow.isDestroyed()) {
      dialog.showErrorBox(
        "Pin Configurator backend stopped",
        `The Flask backend exited early with code ${code ?? "unknown"}.`,
      );
    }
    backendProcess = null;
  });

  return backendProcess;
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1500,
    height: 980,
    minWidth: 1180,
    minHeight: 760,
    backgroundColor: "#1e1e2e",
    autoHideMenuBar: true,
    title: "Zephyr Pin Configurator",
    titleBarStyle: "hidden",
    titleBarOverlay: {
      color: "#161821",
      symbolColor: "#edf1ff",
      height: 34,
    },
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith(BACKEND_URL) || url.startsWith(`http://${BACKEND_HOST}:${BACKEND_PORT}/`)) {
      return { action: "allow" };
    }
    void shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  void mainWindow.loadURL(BACKEND_URL);
}

async function bootstrap() {
  startBackend();
  const ready = await waitForBackend(BACKEND_URL, BACKEND_WAIT_TIMEOUT_MS);
  if (!ready) {
    dialog.showErrorBox(
      "Pin Configurator backend timeout",
      `The backend did not become ready at ${BACKEND_URL} within ${BACKEND_WAIT_TIMEOUT_MS / 1000} seconds.`,
    );
    app.quit();
    return;
  }
  createMainWindow();
}

const singleInstance = app.requestSingleInstanceLock();
if (!singleInstance) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) {
        mainWindow.restore();
      }
      mainWindow.focus();
    }
  });

  app.whenReady().then(bootstrap);
}

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  quitting = true;
  stopBackend();
});

app.on("activate", () => {
  if (!mainWindow) {
    void bootstrap();
  }
});
