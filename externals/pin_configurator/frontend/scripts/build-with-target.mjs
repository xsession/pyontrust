import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, "..");
const target = process.argv[2] || "browser";
const binDir = path.join(rootDir, "node_modules", ".bin");

function executable(name) {
  return process.platform === "win32"
    ? path.join(binDir, `${name}.cmd`)
    : path.join(binDir, name);
}

function run(command, args) {
  const result = spawnSync(command, args, {
    cwd: rootDir,
    stdio: "inherit",
    env: {
      ...process.env,
      PIN_CONFIGURATOR_BUILD_TARGET: target,
    },
    shell: process.platform === "win32",
  });

  if (result.error) {
    throw result.error;
  }

  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

run(executable("tsc"), ["-b"]);
run(executable("vite"), ["build", "--mode", target]);