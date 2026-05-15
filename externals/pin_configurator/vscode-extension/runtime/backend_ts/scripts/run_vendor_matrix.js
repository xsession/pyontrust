const path = require('node:path');
const fs = require('node:fs/promises');

const { createApp } = require('../dist/server.js');

const rootDir = path.resolve(__dirname, '..', '..');
const manifestPath = path.join(rootDir, 'backend_ts', 'validation', 'manifests', 'vendor_matrix.json');
const reportPath = path.join(rootDir, 'backend_ts', 'validation', 'reports', 'vendor_matrix.latest.json');
const parsedJobsPath = path.join(rootDir, 'backend_ts', '.bridge_state', 'parsed_jobs.json');
const sensorJobsPath = path.join(rootDir, 'backend_ts', '.bridge_state', 'sensor_jobs.json');
const vendorMatrixUploadsDir = path.join(rootDir, '.uploads', 'vendor_matrix');
const cleanupParsedJobs = process.env.PIN_CONFIG_CLEANUP_VENDOR_JOBS === '1';

function sanitizeSegment(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '') || 'item';
}

function looksLikePdf(bytes, contentType) {
  if (bytes.length >= 5 && Buffer.from(bytes.subarray(0, 5)).toString('ascii') === '%PDF-') {
    return true;
  }
  return String(contentType || '').toLowerCase().includes('pdf');
}

async function readManifestFile(filePath) {
  try {
    const text = await fs.readFile(filePath, 'utf8');
    return JSON.parse(text);
  } catch (error) {
    if (error && error.code === 'ENOENT') return {};
    throw error;
  }
}

async function writeManifestFile(filePath, data) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, `${JSON.stringify(data, null, 2)}\n`, 'utf8');
}

async function cleanupJob(kind, jobId) {
  if (!jobId) return;
  const filePath = kind === 'sensor' ? sensorJobsPath : parsedJobsPath;
  const manifest = await readManifestFile(filePath);
  const entry = manifest[jobId];
  if (entry && entry.upload_path) {
    await fs.rm(entry.upload_path, { force: true });
  }
  if (entry) {
    delete manifest[jobId];
    await writeManifestFile(filePath, manifest);
  }
}

async function tryDownload(urls) {
  for (const url of urls) {
    try {
      const response = await fetch(url, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Pin-Configurator-Validation/1.0',
          Accept: 'application/pdf,*/*',
        },
        redirect: 'follow',
        signal: AbortSignal.timeout(20_000),
      });
      if (!response.ok) {
        continue;
      }
      const bytes = new Uint8Array(await response.arrayBuffer());
      if (!looksLikePdf(bytes, response.headers.get('content-type'))) {
        continue;
      }
      return {
        url,
        bytes,
      };
    } catch {
      continue;
    }
  }
  return null;
}

async function persistReport(report) {
  report.summary.sensor_successes = report.sensors.filter((entry) => entry.success).length;
  report.summary.mcu_successes = report.mcus.filter((entry) => entry.success).length;
  report.summary.distinct_sensor_vendors = new Set(report.sensors.filter((entry) => entry.success).map((entry) => entry.vendor)).size;
  report.summary.distinct_mcu_vendors = new Set(report.mcus.filter((entry) => entry.success).map((entry) => entry.vendor)).size;
  await fs.mkdir(path.dirname(reportPath), { recursive: true });
  await fs.writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8');
}

async function storeDownloadedPdf(kind, entry, downloaded) {
  const safeFileName = `${sanitizeSegment(kind)}_${sanitizeSegment(entry.vendor)}_${sanitizeSegment(entry.label)}.pdf`;
  const storedPath = path.join(vendorMatrixUploadsDir, safeFileName);
  await fs.mkdir(path.dirname(storedPath), { recursive: true });
  await fs.writeFile(storedPath, Buffer.from(downloaded.bytes));
  return storedPath;
}

async function runEntry(baseUrl, kind, entry) {
  const downloaded = await tryDownload(entry.urls);
  if (!downloaded) {
    return {
      vendor: entry.vendor,
      label: entry.label,
      kind,
      success: false,
      error: 'download_failed',
      urls: entry.urls,
    };
  }

  const storedPath = await storeDownloadedPdf(kind, entry, downloaded);

  const endpoint = kind === 'sensor' ? '/api/parse-sensor-pdf' : '/api/parse-pdf';
  const form = new FormData();
  form.append('pdf', new Blob([downloaded.bytes], { type: 'application/pdf' }), entry.filename);

  let response;
  let payload = null;
  let jobId = '';
  try {
    response = await fetch(`${baseUrl}${endpoint}`, {
      method: 'POST',
      body: form,
      signal: AbortSignal.timeout(240_000),
    });

    try {
      payload = await response.json();
    } catch {
      payload = null;
    }

    jobId = String(payload?.job_id || '');

    if (!response.ok) {
      return {
        vendor: entry.vendor,
        label: entry.label,
        kind,
        success: false,
        url: downloaded.url,
        status: response.status,
        stored_path: path.relative(rootDir, storedPath),
        error: payload?.error || 'parse_failed',
      };
    }

    if (kind === 'sensor') {
      return {
        vendor: entry.vendor,
        label: entry.label,
        kind,
        success: true,
        url: downloaded.url,
        status: response.status,
        stored_path: path.relative(rootDir, storedPath),
        job_id: jobId,
        parsed_part: payload?.result?.summary?.part_number || null,
        parsed_vendor: payload?.result?.summary?.vendor || null,
        protocol: payload?.result?.address?.protocol || null,
        register_count: payload?.result?.register_map?.register_count || 0,
      };
    }

    return {
      vendor: entry.vendor,
      label: entry.label,
      kind,
      success: true,
      url: downloaded.url,
      status: response.status,
      stored_path: path.relative(rootDir, storedPath),
      job_id: jobId,
      parsed_soc: payload?.result?.device?.soc || null,
      parsed_vendor: payload?.result?.device?.vendor || null,
      package_count: Array.isArray(payload?.result?.packages) ? payload.result.packages.length : 0,
      pin_mux_count: payload?.result?.pin_mux_count || 0,
    };
  } catch (error) {
    return {
      vendor: entry.vendor,
      label: entry.label,
      kind,
      success: false,
      url: downloaded.url,
      stored_path: path.relative(rootDir, storedPath),
      error: error instanceof Error ? error.message : String(error),
    };
  } finally {
    if (cleanupParsedJobs) {
      try {
        await cleanupJob(kind, jobId);
      } catch {
        // Cleanup should not abort the remaining matrix entries.
      }
    }
  }
}

async function main() {
  const manifest = JSON.parse(await fs.readFile(manifestPath, 'utf8'));
  const app = createApp(rootDir);
  const server = await new Promise((resolve) => {
    const instance = app.listen(0, '127.0.0.1', () => resolve(instance));
  });
  const address = server.address();
  const baseUrl = `http://127.0.0.1:${address.port}`;

  try {
    const report = {
      generated_at: new Date().toISOString(),
      sensors: [],
      mcus: [],
      summary: {
        sensor_successes: 0,
        mcu_successes: 0,
        distinct_sensor_vendors: 0,
        distinct_mcu_vendors: 0,
      },
    };

    for (const entry of manifest.sensors) {
      report.sensors.push(await runEntry(baseUrl, 'sensor', entry));
      await persistReport(report);
    }
    for (const entry of manifest.mcus) {
      report.mcus.push(await runEntry(baseUrl, 'mcu', entry));
      await persistReport(report);
    }

    await persistReport(report);

    console.log(JSON.stringify(report.summary, null, 2));

    if (report.summary.distinct_sensor_vendors < 10 || report.summary.distinct_mcu_vendors < 10) {
      throw new Error(`Vendor matrix incomplete. Sensors=${report.summary.distinct_sensor_vendors}/10 MCUs=${report.summary.distinct_mcu_vendors}/10`);
    }
  } finally {
    await new Promise((resolve, reject) => {
      server.close((error) => (error ? reject(error) : resolve()));
    });
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});