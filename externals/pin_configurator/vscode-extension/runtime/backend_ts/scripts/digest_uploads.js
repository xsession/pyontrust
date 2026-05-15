const path = require('node:path');
const fs = require('node:fs/promises');
const crypto = require('node:crypto');

const { callPythonJob } = require('../dist/python_jobs.js');
const { identifyMcu, identifySensor } = require('../dist/lookup_registry.js');
const { parseSensorSnapshot, tryParseSensorPdfNative } = require('../dist/pdf_sensor_parser.js');
const { tryParseTiPdfNative } = require('../dist/pdf_ti_parser.js');
const { tryParseStm32PdfNative } = require('../dist/pdf_stm32_parser.js');
const { tryParseGenericPdfNative } = require('../dist/pdf_generic_parser.js');

const rootDir = path.resolve(__dirname, '..', '..');
const uploadsDir = path.join(rootDir, '.uploads');
const incomingDir = path.join(uploadsDir, 'incoming');
const tempDir = path.join(uploadsDir, '.digest_tmp');
const reportPath = path.join(rootDir, 'backend_ts', 'validation', 'reports', 'digest_uploads.latest.json');
const parsedJobsPath = path.join(rootDir, 'backend_ts', '.bridge_state', 'parsed_jobs.json');
const sensorJobsPath = path.join(rootDir, 'backend_ts', '.bridge_state', 'sensor_jobs.json');
const digestedUploadsPath = path.join(rootDir, 'backend_ts', '.bridge_state', 'digested_uploads.json');

function looksLikePdf(bytes) {
  return bytes.length >= 5 && Buffer.from(bytes.subarray(0, 5)).toString('ascii') === '%PDF-';
}

function sha256(bytes) {
  return crypto.createHash('sha256').update(bytes).digest('hex');
}

function normalisePath(filePath) {
  return path.resolve(filePath).toLowerCase();
}

function sanitiseFilename(filename) {
  const cleaned = String(filename || '').replace(/[^A-Za-z0-9_.-]/g, '_');
  return cleaned.toLowerCase().endsWith('.pdf') ? cleaned : `${cleaned}.pdf`;
}

function candidateParts(filename) {
  const base = path.basename(filename, path.extname(filename));
  const withoutPrefix = base.replace(/^[a-f0-9]{12,}_/i, '');
  const parts = [base, withoutPrefix, ...withoutPrefix.split(/[^A-Za-z0-9]+/g)];
  return [...new Set(parts.map((part) => part.trim()).filter((part) => part.length >= 4))];
}

async function loadManifest(filePath) {
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

async function collectDigestedPaths() {
  const manifests = await Promise.all([loadManifest(parsedJobsPath), loadManifest(sensorJobsPath)]);
  const digested = new Set();
  for (const manifest of manifests) {
    for (const entry of Object.values(manifest)) {
      if (entry && typeof entry.upload_path === 'string' && entry.upload_path) {
        digested.add(normalisePath(entry.upload_path));
      }
    }
  }
  return digested;
}

async function collectDigestedHashes(digestedPaths) {
  const hashes = new Set();
  for (const normalizedPath of digestedPaths) {
    const originalPath = [...digestedPaths].find((candidate) => candidate === normalizedPath);
    if (!originalPath) {
      continue;
    }
    try {
      const bytes = new Uint8Array(await fs.readFile(originalPath));
      if (looksLikePdf(bytes)) {
        hashes.add(sha256(bytes));
      }
    } catch {
      continue;
    }
  }
  return hashes;
}

async function loadDigestedUploadsState() {
  return await loadManifest(digestedUploadsPath);
}

async function saveDigestedUploadsState(state) {
  await fs.mkdir(path.dirname(digestedUploadsPath), { recursive: true });
  await fs.writeFile(digestedUploadsPath, `${JSON.stringify(state, null, 2)}\n`, 'utf8');
}

async function walkPdfCandidates(dirPath) {
  const entries = await fs.readdir(dirPath, { withFileTypes: true });
  const results = [];
  for (const entry of entries) {
    const fullPath = path.join(dirPath, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === '.digest_tmp') {
        continue;
      }
      results.push(...await walkPdfCandidates(fullPath));
      continue;
    }
    results.push(fullPath);
  }
  return results;
}

async function makeWorkingCopy(sourcePath) {
  await fs.mkdir(tempDir, { recursive: true });
  const targetPath = path.join(tempDir, `${crypto.randomUUID()}_${sanitiseFilename(path.basename(sourcePath))}`);
  await fs.copyFile(sourcePath, targetPath);
  return targetPath;
}

async function extractSensorSnapshot(uploadPath, filename) {
  const response = await callPythonJob(rootDir, {
    operation: 'extract-sensor-pdf-snapshot',
    uploadPath,
    filename,
  });
  return response.status === 200 ? response.json : null;
}

async function extractMcuSnapshot(uploadPath, filename) {
  const response = await callPythonJob(rootDir, {
    operation: 'extract-mcu-pdf-snapshot',
    uploadPath,
    filename,
  });
  return response.status === 200 ? response.json : null;
}

async function classifyPdf(filePath, filename) {
  for (const candidate of candidateParts(filename)) {
    if (identifySensor(candidate).known) {
      return { kind: 'sensor', reason: `identifySensor:${candidate}` };
    }
    const mcu = await identifyMcu(rootDir, candidate);
    if (mcu.known) {
      return { kind: 'mcu', reason: `identifyMcu:${candidate}` };
    }
  }

  const snapshot = await extractSensorSnapshot(filePath, filename);
  if (snapshot) {
    const parsed = parseSensorSnapshot(snapshot);
    const registerCount = parsed?.register_map?.registers?.length ?? 0;
    const addressCount = parsed?.address?.i2c_addresses?.length ?? 0;
    if (parsed && (registerCount > 0 || addressCount > 0 || parsed.summary?.part_number)) {
      return { kind: 'sensor', reason: 'sensor_snapshot' };
    }
  }

  return { kind: 'mcu', reason: 'default_mcu' };
}

async function digestSensorPdf(sourcePath, filename) {
  const workingCopy = await makeWorkingCopy(sourcePath);
  try {
    const native = await tryParseSensorPdfNative(rootDir, workingCopy, filename, extractSensorSnapshot);
    if (native) {
      return {
        success: true,
        kind: 'sensor',
        via: 'native',
        job_id: native.job_id,
        parsed_part: native.result?.summary?.part_number || null,
        parsed_vendor: native.result?.summary?.vendor || null,
      };
    }

    const response = await callPythonJob(rootDir, {
      operation: 'parse-sensor-pdf',
      uploadPath: workingCopy,
      filename,
    });
    if (response.status >= 200 && response.status < 300) {
      return {
        success: true,
        kind: 'sensor',
        via: 'python',
        job_id: response.json?.job_id || null,
        parsed_part: response.json?.result?.summary?.part_number || null,
        parsed_vendor: response.json?.result?.summary?.vendor || null,
      };
    }
    return {
      success: false,
      kind: 'sensor',
      via: 'python',
      error: response.json?.error || 'parse_failed',
    };
  } finally {
    await fs.rm(workingCopy, { force: true }).catch(() => undefined);
  }
}

async function digestMcuPdf(sourcePath, filename) {
  const workingCopy = await makeWorkingCopy(sourcePath);
  try {
    const nativeTi = await tryParseTiPdfNative(rootDir, workingCopy, filename, extractMcuSnapshot);
    if (nativeTi) {
      return {
        success: true,
        kind: 'mcu',
        via: 'native-ti',
        job_id: nativeTi.job_id,
        parsed_soc: nativeTi.result?.device?.soc || null,
        parsed_vendor: nativeTi.result?.device?.vendor || null,
      };
    }

    const nativeStm32 = await tryParseStm32PdfNative(rootDir, workingCopy, filename, extractMcuSnapshot);
    if (nativeStm32) {
      return {
        success: true,
        kind: 'mcu',
        via: 'native-stm32',
        job_id: nativeStm32.job_id,
        parsed_soc: nativeStm32.result?.device?.soc || null,
        parsed_vendor: nativeStm32.result?.device?.vendor || null,
      };
    }

    const nativeGeneric = await tryParseGenericPdfNative(rootDir, workingCopy, filename, extractMcuSnapshot);
    if (nativeGeneric) {
      return {
        success: true,
        kind: 'mcu',
        via: 'native-generic',
        job_id: nativeGeneric.job_id,
        parsed_soc: nativeGeneric.result?.device?.soc || null,
        parsed_vendor: nativeGeneric.result?.device?.vendor || null,
      };
    }

    const response = await callPythonJob(rootDir, {
      operation: 'parse-pdf',
      uploadPath: workingCopy,
      filename,
    });
    if (response.status >= 200 && response.status < 300) {
      return {
        success: true,
        kind: 'mcu',
        via: 'python',
        job_id: response.json?.job_id || null,
        parsed_soc: response.json?.result?.device?.soc || null,
        parsed_vendor: response.json?.result?.device?.vendor || null,
      };
    }
    return {
      success: false,
      kind: 'mcu',
      via: 'python',
      error: response.json?.error || 'parse_failed',
    };
  } finally {
    await fs.rm(workingCopy, { force: true }).catch(() => undefined);
  }
}

async function main() {
  const report = {
    generated_at: new Date().toISOString(),
    uploads_root: path.relative(rootDir, incomingDir),
    digested: [],
    summary: {
      discovered: 0,
      skipped_existing: 0,
      skipped_non_pdf: 0,
      digested_successes: 0,
      digested_failures: 0,
      sensor_jobs: 0,
      mcu_jobs: 0,
    },
  };

  const digestedPaths = await collectDigestedPaths();
  const digestedHashes = await collectDigestedHashes(digestedPaths);
  const digestedState = await loadDigestedUploadsState();
  const filePaths = await fs.access(incomingDir).then(() => walkPdfCandidates(incomingDir)).catch(() => []);

  for (const filePath of filePaths) {
    const relativePath = path.relative(rootDir, filePath);
    const normalized = normalisePath(filePath);
    const stats = await fs.stat(filePath);
    report.summary.discovered += 1;

    if (digestedPaths.has(normalized)) {
      report.summary.skipped_existing += 1;
      report.digested.push({ file: relativePath, skipped: true, reason: 'already_digested' });
      continue;
    }

    const priorDigest = digestedState[normalized];
    if (priorDigest && priorDigest.size === stats.size && priorDigest.mtime_ms === stats.mtimeMs) {
      report.summary.skipped_existing += 1;
      report.digested.push({ file: relativePath, skipped: true, reason: 'already_digested_source' });
      continue;
    }

    const bytes = new Uint8Array(await fs.readFile(filePath));
    if (!looksLikePdf(bytes)) {
      report.summary.skipped_non_pdf += 1;
      report.digested.push({ file: relativePath, skipped: true, reason: 'not_pdf' });
      continue;
    }

    const fileHash = sha256(bytes);
    if (digestedHashes.has(fileHash)) {
      report.summary.skipped_existing += 1;
      report.digested.push({ file: relativePath, skipped: true, reason: 'already_digested_content' });
      digestedState[normalized] = {
        file: relativePath,
        size: stats.size,
        mtime_ms: stats.mtimeMs,
        content_hash: fileHash,
        kind: 'unknown',
        job_id: null,
      };
      continue;
    }

    const filename = sanitiseFilename(path.basename(filePath));
    const classified = await classifyPdf(filePath, filename);
    const result = classified.kind === 'sensor'
      ? await digestSensorPdf(filePath, filename)
      : await digestMcuPdf(filePath, filename);

    if (result.success) {
      report.summary.digested_successes += 1;
      digestedState[normalized] = {
        file: relativePath,
        size: stats.size,
        mtime_ms: stats.mtimeMs,
        content_hash: fileHash,
        kind: result.kind,
        job_id: result.job_id || null,
      };
      digestedHashes.add(fileHash);
      if (result.kind === 'sensor') {
        report.summary.sensor_jobs += 1;
      } else {
        report.summary.mcu_jobs += 1;
      }
    } else {
      report.summary.digested_failures += 1;
    }

    report.digested.push({
      file: relativePath,
      classified_as: classified.kind,
      classification_reason: classified.reason,
      ...result,
    });
  }

  await saveDigestedUploadsState(digestedState);
  await fs.mkdir(path.dirname(reportPath), { recursive: true });
  await fs.writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8');
  console.log(JSON.stringify(report.summary, null, 2));
  if (report.summary.digested_failures > 0) {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});