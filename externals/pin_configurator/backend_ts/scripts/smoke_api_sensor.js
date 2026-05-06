const path = require('node:path');
const fs = require('node:fs/promises');

const { createApp } = require('../dist/server.js');

const rootDir = path.resolve(__dirname, '..', '..');
const sensorJobsPath = path.join(rootDir, 'backend_ts', '.bridge_state', 'sensor_jobs.json');

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function readManifest() {
  try {
    const text = await fs.readFile(sensorJobsPath, 'utf8');
    return JSON.parse(text);
  } catch (error) {
    if (error && error.code === 'ENOENT') return {};
    throw error;
  }
}

async function writeManifest(manifest) {
  await fs.mkdir(path.dirname(sensorJobsPath), { recursive: true });
  await fs.writeFile(sensorJobsPath, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
}

async function cleanupJob(jobId) {
  const manifest = await readManifest();
  const entry = manifest[jobId];
  if (entry && entry.upload_path) {
    await fs.rm(entry.upload_path, { force: true });
  }
  if (entry) {
    delete manifest[jobId];
    await writeManifest(manifest);
  }
}

async function main() {
  const app = createApp(rootDir);
  const server = await new Promise((resolve) => {
    const instance = app.listen(0, '127.0.0.1', () => resolve(instance));
  });
  const address = server.address();
  const baseUrl = `http://127.0.0.1:${address.port}`;
  let jobId = '';

  try {
    const pdfPath = path.join(rootDir, '.uploads', 'bmp280.pdf');
    const bytes = await fs.readFile(pdfPath);
    const form = new FormData();
    form.append('pdf', new Blob([bytes], { type: 'application/pdf' }), 'bmp280.pdf');

    const parseResponse = await fetch(`${baseUrl}/api/parse-sensor-pdf`, {
      method: 'POST',
      body: form,
    });
    assert(parseResponse.ok, `parse-sensor-pdf failed with status ${parseResponse.status}`);
    const parsed = await parseResponse.json();
    jobId = String(parsed.job_id || '');
    assert(jobId, 'parse-sensor-pdf did not return job_id');
    assert(parsed.result?.summary?.part_number === 'BMP280', 'unexpected parsed part number');
    assert(parsed.result?.register_map?.register_count === 23, 'unexpected parsed register count');

    const jobsResponse = await fetch(`${baseUrl}/api/sensor-jobs`);
    assert(jobsResponse.ok, `sensor-jobs failed with status ${jobsResponse.status}`);
    const jobs = await jobsResponse.json();
    assert(Array.isArray(jobs) && jobs.some((job) => job.job_id === jobId), 'sensor job not listed after parse');

    const jobResponse = await fetch(`${baseUrl}/api/sensor-job/${jobId}`);
    assert(jobResponse.ok, `sensor-job failed with status ${jobResponse.status}`);
    const job = await jobResponse.json();
    assert(job.result?.summary?.part_number === 'BMP280', 'sensor-job returned wrong part number');

    const headerResponse = await fetch(`${baseUrl}/api/sensor-job/${jobId}/header`);
    assert(headerResponse.ok, `sensor-job header failed with status ${headerResponse.status}`);
    const header = await headerResponse.json();
    assert(String(header.code || '').includes('BMP280_WHO_AM_I_REG'), 'generated header missing WHO_AM_I define');

    console.log('Sensor API smoke test passed.');
  } finally {
    if (jobId) {
      await cleanupJob(jobId);
    }
    await new Promise((resolve, reject) => {
      server.close((error) => (error ? reject(error) : resolve()));
    });
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});