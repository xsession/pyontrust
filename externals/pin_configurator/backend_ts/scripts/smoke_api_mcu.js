const path = require('node:path');
const fs = require('node:fs/promises');
const { spawn } = require('node:child_process');

const { createApp } = require('../dist/server.js');

const rootDir = path.resolve(__dirname, '..', '..');
const parsedJobsPath = path.join(rootDir, 'backend_ts', '.bridge_state', 'parsed_jobs.json');
const boardsDir = path.join(rootDir, 'boards');

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function readManifest() {
  try {
    const text = await fs.readFile(parsedJobsPath, 'utf8');
    return JSON.parse(text);
  } catch (error) {
    if (error && error.code === 'ENOENT') return {};
    throw error;
  }
}

async function writeManifest(manifest) {
  await fs.mkdir(path.dirname(parsedJobsPath), { recursive: true });
  await fs.writeFile(parsedJobsPath, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
}

async function pruneMissingBoardRegistrations() {
  const initPath = path.join(boardsDir, '__init__.py');
  let text;
  try {
    text = await fs.readFile(initPath, 'utf8');
  } catch {
    return;
  }

  const lines = text.split(/\r?\n/);
  const kept = [];
  const removedBuilders = new Set();

  for (const line of lines) {
    const match = /^from \.([a-z0-9_]+) import (build_[a-z0-9_]+)$/i.exec(line.trim());
    if (!match) {
      kept.push(line);
      continue;
    }

    const modulePath = path.join(boardsDir, `${match[1]}.py`);
    try {
      await fs.access(modulePath);
      kept.push(line);
    } catch {
      removedBuilders.add(match[2]);
    }
  }

  const filtered = kept.filter((line) => {
    const match = /^\s*"[^"]+":\s*(build_[a-z0-9_]+),?\s*$/i.exec(line);
    return !match || !removedBuilders.has(match[1]);
  });

  if (filtered.join('\n') !== text.replace(/\r\n/g, '\n')) {
    await fs.writeFile(initPath, `${filtered.join('\n').replace(/\n+$/,'')}\n`, 'utf8');
  }
}

async function refreshBoardSnapshots() {
  await pruneMissingBoardRegistrations();
  const scriptPath = path.join(rootDir, 'backend_ts', 'scripts', 'export_boards.py');
  const executable = process.env.PYTHON || 'python';
  await new Promise((resolve, reject) => {
    const child = spawn(executable, [scriptPath], {
      cwd: rootDir,
      env: process.env,
      stdio: ['ignore', 'ignore', 'pipe'],
    });
    let stderr = '';
    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString('utf8');
    });
    child.on('error', reject);
    child.on('exit', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`Board export failed with code ${code}: ${stderr}`));
    });
  });
}

async function cleanup(jobId, generatedFiles) {
  const manifest = await readManifest();
  const entry = manifest[jobId];
  if (entry && entry.upload_path) {
    await fs.rm(entry.upload_path, { force: true });
  }
  if (entry) {
    delete manifest[jobId];
    await writeManifest(manifest);
  }

  for (const filePath of generatedFiles) {
    await fs.rm(filePath, { force: true });
  }
  if (generatedFiles.length > 0) {
    await refreshBoardSnapshots();
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
  const generatedFiles = [];

  try {
    const pdfPath = path.join(rootDir, '.uploads', '67c77906b17f_stm32f411re.pdf');
    const bytes = await fs.readFile(pdfPath);
    const form = new FormData();
    form.append('pdf', new Blob([bytes], { type: 'application/pdf' }), 'stm32f411re.pdf');

    const parseResponse = await fetch(`${baseUrl}/api/parse-pdf`, {
      method: 'POST',
      body: form,
    });
    assert(parseResponse.ok, `parse-pdf failed with status ${parseResponse.status}`);
    const parsed = await parseResponse.json();
    jobId = String(parsed.job_id || '');
    assert(jobId, 'parse-pdf did not return job_id');
    assert(parsed.result?.device?.soc === 'STM32F411', 'unexpected parsed MCU soc');
    assert(parsed.result?.pin_mux_count === 82, 'unexpected parsed pin count');

    const jobsResponse = await fetch(`${baseUrl}/api/parse-jobs`);
    assert(jobsResponse.ok, `parse-jobs failed with status ${jobsResponse.status}`);
    const jobs = await jobsResponse.json();
    assert(Array.isArray(jobs) && jobs.some((job) => job.job_id === jobId), 'parsed MCU job not listed after parse');

    const packageResponse = await fetch(`${baseUrl}/api/generate-package`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_id: jobId,
        packages: ['LQFP64'],
        board_name: 'smoke_stm32f411',
        register: false,
      }),
    });
    assert(packageResponse.ok, `generate-package failed with status ${packageResponse.status}`);
    const packageResult = await packageResponse.json();
    assert(packageResult.success === true, 'generate-package did not report success');
    assert(Array.isArray(packageResult.files) && packageResult.files.length === 1, 'generate-package returned unexpected files');
    const generatedPath = String(packageResult.files[0].path || '');
    assert(generatedPath, 'generate-package did not return a file path');
    await fs.access(generatedPath);
    generatedFiles.push(generatedPath);

    console.log('MCU API smoke test passed.');
  } finally {
    await cleanup(jobId, generatedFiles);
    await new Promise((resolve, reject) => {
      server.close((error) => (error ? reject(error) : resolve()));
    });
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});