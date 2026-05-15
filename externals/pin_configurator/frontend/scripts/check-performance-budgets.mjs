import { readdir, stat } from "node:fs/promises";
import path from "node:path";

const workspaceRoot = process.cwd();
const distRoot = path.join(workspaceRoot, "dist");
const assetRoot = path.join(distRoot, "assets");

const budgets = {
  html: Number.parseInt(process.env.PINCFG_HTML_BUDGET ?? "5120", 10),
  js: Number.parseInt(process.env.PINCFG_JS_BUDGET ?? "650000", 10),
  css: Number.parseInt(process.env.PINCFG_CSS_BUDGET ?? "150000", 10),
};

function formatBytes(value) {
  return `${(value / 1024).toFixed(1)} KiB`;
}

async function largestAssetSize(directory, extension) {
  const entries = await readdir(directory, { withFileTypes: true });
  const matchingFiles = entries.filter((entry) => entry.isFile() && entry.name.endsWith(extension));

  if (!matchingFiles.length) {
    throw new Error(`No ${extension} assets found in ${directory}. Run the build before checking budgets.`);
  }

  const assets = await Promise.all(
    matchingFiles.map(async (entry) => {
      const filePath = path.join(directory, entry.name);
      const fileStats = await stat(filePath);

      return {
        name: entry.name,
        size: fileStats.size,
      };
    }),
  );

  return assets.sort((left, right) => right.size - left.size)[0];
}

async function main() {
  const htmlStats = await stat(path.join(distRoot, "index.html"));
  const largestJs = await largestAssetSize(assetRoot, ".js");
  const largestCss = await largestAssetSize(assetRoot, ".css");

  const results = [
    { label: "HTML entry", name: "index.html", size: htmlStats.size, budget: budgets.html },
    { label: "Largest JS asset", name: largestJs.name, size: largestJs.size, budget: budgets.js },
    { label: "Largest CSS asset", name: largestCss.name, size: largestCss.size, budget: budgets.css },
  ];

  const failures = results.filter((result) => result.size > result.budget);

  results.forEach((result) => {
    console.log(`${result.label}: ${result.name} = ${formatBytes(result.size)} (budget ${formatBytes(result.budget)})`);
  });

  if (failures.length) {
    const detail = failures
      .map((failure) => `${failure.label} ${failure.name} exceeded budget by ${formatBytes(failure.size - failure.budget)}`)
      .join("; ");
    throw new Error(`Performance budgets failed: ${detail}`);
  }

  console.log("Performance budgets passed.");
}

void main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});