import { cpSync, existsSync, mkdirSync, readdirSync, rmSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const extensionDir = path.resolve(__dirname, "..");
const repoRoot = path.resolve(extensionDir, "..");
const runtimeRoot = path.join(extensionDir, "runtime");
const frontendDir = path.join(repoRoot, "frontend");
const backendTsDir = path.join(repoRoot, "backend_ts");

function npmExecutable() {
  return process.platform === "win32" ? "npm.cmd" : "npm";
}

function runNpm(cwd, args) {
  const result = spawnSync(npmExecutable(), args, {
    cwd,
    stdio: "inherit",
    env: process.env,
    shell: process.platform === "win32",
  });

  if (result.error) {
    throw result.error;
  }

  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

function copyDirectory(source, destination) {
  if (!existsSync(source)) {
    throw new Error(`Missing directory: ${source}`);
  }

  cpSync(source, destination, { recursive: true });
}

function copyFile(source, destination) {
  if (!existsSync(source)) {
    throw new Error(`Missing file: ${source}`);
  }

  mkdirSync(path.dirname(destination), { recursive: true });
  cpSync(source, destination);
}

runNpm(frontendDir, ["run", "build:extension"]);
runNpm(backendTsDir, ["run", "build"]);

rmSync(runtimeRoot, { recursive: true, force: true });
mkdirSync(runtimeRoot, { recursive: true });

for (const entry of readdirSync(repoRoot, { withFileTypes: true })) {
  if (!entry.isFile() || !entry.name.endsWith(".py")) {
    continue;
  }

  copyFile(path.join(repoRoot, entry.name), path.join(runtimeRoot, entry.name));
}

copyDirectory(path.join(repoRoot, "boards"), path.join(runtimeRoot, "boards"));
copyDirectory(path.join(frontendDir, "dist"), path.join(runtimeRoot, "frontend", "dist"));
copyDirectory(path.join(backendTsDir, "dist"), path.join(runtimeRoot, "backend_ts", "dist"));
copyDirectory(path.join(backendTsDir, "scripts"), path.join(runtimeRoot, "backend_ts", "scripts"));
copyDirectory(path.join(backendTsDir, "src", "generated"), path.join(runtimeRoot, "backend_ts", "src", "generated"));
copyFile(path.join(backendTsDir, "job_runtime.py"), path.join(runtimeRoot, "backend_ts", "job_runtime.py"));
copyFile(path.join(backendTsDir, "state_runtime.py"), path.join(runtimeRoot, "backend_ts", "state_runtime.py"));