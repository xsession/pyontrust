import { cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const currentDir = dirname(fileURLToPath(import.meta.url));
const frontendRoot = resolve(currentDir, "..");
const outputRoot = resolve(frontendRoot, "dist", "penpot-surface");

const exportEntries = [
  {
    source: resolve(frontendRoot, "src", "generated", "penpot"),
    target: resolve(outputRoot, "src", "generated", "penpot"),
  },
  {
    source: resolve(frontendRoot, "src", "styles", "index.scss"),
    target: resolve(outputRoot, "src", "styles", "index.scss"),
  },
  {
    source: resolve(frontendRoot, "..", "docs", "frontend_platform_research.md"),
    target: resolve(outputRoot, "docs", "frontend_platform_research.md"),
  },
];

await rm(outputRoot, { recursive: true, force: true });
await mkdir(outputRoot, { recursive: true });

for (const entry of exportEntries) {
  await mkdir(dirname(entry.target), { recursive: true });
  await cp(entry.source, entry.target, { recursive: true });
}

const manifest = {
  exportedAt: new Date().toISOString(),
  root: "dist/penpot-surface",
  entries: exportEntries.map((entry) => ({
    source: entry.source.replace(`${frontendRoot}\\`, ""),
    target: entry.target.replace(`${outputRoot}\\`, ""),
  })),
  notes: [
    "This package contains only designer-owned Penpot shell assets and supporting style/docs context.",
    "Do not copy files back outside src/generated/penpot without engineering review.",
  ],
};

await writeFile(resolve(outputRoot, "manifest.json"), JSON.stringify(manifest, null, 2));

const readme = await readFile(resolve(frontendRoot, "src", "generated", "penpot", "README.md"), "utf8");
await writeFile(resolve(outputRoot, "README.md"), readme);

console.log(`Exported Penpot surface to ${outputRoot}`);