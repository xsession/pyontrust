import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, "..");
const target = process.argv[2] || "browser";
const nodeModulesDir = path.join(rootDir, "node_modules");

function nodeScript(...segments) {
  return path.join(nodeModulesDir, ...segments);
}

function run(command, args) {
  const result = spawnSync(command, args, {
    cwd: rootDir,
    stdio: "inherit",
    env: {
      ...process.env,
      PIN_CONFIGURATOR_BUILD_TARGET: target,
    },
  });

  if (result.error) {
    throw result.error;
  }

  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

run(process.execPath, [nodeScript("typescript", "bin", "tsc"), "-b"]);
run(process.execPath, [nodeScript("vite", "bin", "vite.js"), "build", "--mode", target]);