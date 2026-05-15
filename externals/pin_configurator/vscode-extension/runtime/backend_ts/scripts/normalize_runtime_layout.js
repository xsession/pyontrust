const path = require('node:path');
const fs = require('node:fs/promises');

const rootDir = path.resolve(__dirname, '..', '..');
const uploadsDir = path.join(rootDir, '.uploads');
const bridgeStateDir = path.join(rootDir, 'backend_ts', '.bridge_state');
const parsedJobsPath = path.join(bridgeStateDir, 'parsed_jobs.json');
const sensorJobsPath = path.join(bridgeStateDir, 'sensor_jobs.json');
const digestedUploadsPath = path.join(bridgeStateDir, 'digested_uploads.json');
const reportPath = path.join(rootDir, 'backend_ts', 'validation', 'reports', 'normalize_runtime_layout.latest.json');

function normalizePath(filePath) {
  return path.resolve(filePath).toLowerCase();
}

async function loadJson(filePath) {
  try {
    const text = (await fs.readFile(filePath, 'utf8')).replace(/^\uFEFF/, '');
    const parsed = JSON.parse(text);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (error) {
    if (error && error.code === 'ENOENT') {
      return {};
    }
    throw error;
  }
}

async function writeJson(filePath, value) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

async function moveIfNeeded(sourcePath, targetPath) {
  if (normalizePath(sourcePath) === normalizePath(targetPath)) {
    return false;
  }
  await fs.mkdir(path.dirname(targetPath), { recursive: true });
  await fs.rename(sourcePath, targetPath);
  return true;
}

function classifyTargetSubdir(filePath, preferredKind) {
  if (preferredKind === 'sensor') {
    return path.join(uploadsDir, 'sensor_jobs', path.basename(filePath));
  }
  if (preferredKind === 'mcu') {
    return path.join(uploadsDir, 'mcu_jobs', path.basename(filePath));
  }
  return path.join(uploadsDir, 'incoming', 'legacy', path.basename(filePath));
}

async function normaliseManifest(manifestPath, preferredKind, report) {
  const manifest = await loadJson(manifestPath);
  let changed = false;
  for (const entry of Object.values(manifest)) {
    if (!entry || typeof entry.upload_path !== 'string' || !entry.upload_path) {
      continue;
    }
    const sourcePath = entry.upload_path;
    const normalizedSource = normalizePath(sourcePath);
    if (!normalizedSource.startsWith(normalizePath(uploadsDir))) {
      continue;
    }
    try {
      await fs.access(sourcePath);
    } catch {
      continue;
    }
    const targetPath = classifyTargetSubdir(sourcePath, preferredKind);
    const moved = await moveIfNeeded(sourcePath, targetPath);
    if (moved) {
      report.moves.push({ from: path.relative(rootDir, sourcePath), to: path.relative(rootDir, targetPath), reason: `${preferredKind}_manifest` });
      entry.upload_path = targetPath;
      changed = true;
    }
  }
  if (changed) {
    await writeJson(manifestPath, manifest);
  }
  return manifest;
}

async function normaliseDigestedUploads(report) {
  const digested = await loadJson(digestedUploadsPath);
  const next = {};
  let changed = false;
  for (const [storedPath, entry] of Object.entries(digested)) {
    const sourcePath = storedPath;
    let targetPath = sourcePath;
    try {
      await fs.access(sourcePath);
      const normalizedSource = normalizePath(sourcePath);
      const legacyRoot = normalizePath(uploadsDir + path.sep);
      if (normalizedSource.startsWith(legacyRoot) && path.dirname(normalizedSource) === normalizePath(uploadsDir)) {
        targetPath = classifyTargetSubdir(sourcePath, null);
        const moved = await moveIfNeeded(sourcePath, targetPath);
        if (moved) {
          report.moves.push({ from: path.relative(rootDir, sourcePath), to: path.relative(rootDir, targetPath), reason: 'digested_source' });
          changed = true;
        }
      }
    } catch {
      targetPath = sourcePath;
    }

    const nextKey = normalizePath(targetPath);
    next[nextKey] = {
      ...entry,
      file: path.relative(rootDir, targetPath),
    };
    if (nextKey !== storedPath) {
      changed = true;
    }
  }
  if (changed) {
    await writeJson(digestedUploadsPath, next);
  }
}

async function normaliseLooseRootFiles(report) {
  const entries = await fs.readdir(uploadsDir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.isDirectory()) {
      continue;
    }
    const sourcePath = path.join(uploadsDir, entry.name);
    const targetPath = classifyTargetSubdir(sourcePath, null);
    const moved = await moveIfNeeded(sourcePath, targetPath);
    if (moved) {
      report.moves.push({ from: path.relative(rootDir, sourcePath), to: path.relative(rootDir, targetPath), reason: 'loose_root_artifact' });
    }
  }
}

async function main() {
  const report = {
    generated_at: new Date().toISOString(),
    moves: [],
    summary: {
      moved: 0,
    },
  };

  await fs.mkdir(path.join(uploadsDir, 'incoming'), { recursive: true });
  await fs.mkdir(path.join(uploadsDir, 'mcu_jobs'), { recursive: true });
  await fs.mkdir(path.join(uploadsDir, 'sensor_jobs'), { recursive: true });
  await fs.mkdir(path.join(uploadsDir, 'downloads'), { recursive: true });
  await fs.mkdir(path.join(uploadsDir, 'vendor_matrix'), { recursive: true });

  await normaliseManifest(parsedJobsPath, 'mcu', report);
  await normaliseManifest(sensorJobsPath, 'sensor', report);
  await normaliseDigestedUploads(report);
  await normaliseLooseRootFiles(report);

  report.summary.moved = report.moves.length;
  await writeJson(reportPath, report);
  console.log(JSON.stringify(report.summary, null, 2));
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});