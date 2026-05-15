import cors from 'cors';
import express, { type NextFunction, type Request, type Response } from 'express';
import multer from 'multer';
import { existsSync, statSync } from 'node:fs';
import { promises as fs } from 'node:fs';
import * as path from 'node:path';
import { getBoard, invalidateBoardRegistryCache, listBoards } from './board_registry';
import { analyzeClockTree, computeFrequencies, generateClockConfig, getClockTree, getTypedClockTree, listClockTrees } from './clock_registry';
import { downloadMcuDatasheet } from './datasheet_downloader';
import { generateDriver, specFromJson } from './driver_codegen';
import { generateOverlay, type ExternalDeviceConfig, type PeripheralConfig, type PinAssignment } from './dts_generator';
import { parseImport } from './import_parser';
import { generateSensorDriverFromJob, generateSensorRegisterHeader, getParsedJob, getSensorJob, listParsedJobs, listSensorJobs, saveSensorJob } from './job_registry';
import { identifyMcu, identifySensor, listDriverTemplates } from './lookup_registry';
import { generateModuleConfig, listModules } from './module_registry';
import { generateBoardFiles, type ExternalDeviceSpec } from './package_codegen';
import { tryParseGenericPdfNative } from './pdf_generic_parser';
import { parseSensorSnapshot, tryParseSensorPdfNative } from './pdf_sensor_parser';
import { tryParseStm32PdfNative, type Stm32PdfSnapshot } from './pdf_stm32_parser';
import { tryParseTiPdfNative, type TiPdfSnapshot } from './pdf_ti_parser';
import { buildPeripheralInstances, generatePeripheralConfig, listPeripheralTemplates } from './peripheral_registry';
import { callPythonJob, type McuPdfSnapshot, type SensorPdfSnapshot } from './python_jobs';
import { uploadArtifactDir } from './runtime_paths';

const PROJECT_FILE_VERSION = 1;

function pinConfiguratorRoot(): string {
  return path.resolve(__dirname, '..', '..');
}

function uploadsDir(rootDir: string): string {
  return uploadArtifactDir(rootDir, 'incoming');
}

function boardsDir(rootDir: string): string {
  return path.join(rootDir, 'boards');
}

function boardEditorDir(rootDir: string): string {
  return path.join(boardsDir(rootDir), 'editor_json');
}

function frontendDistDir(rootDir: string): string {
  return path.join(rootDir, 'frontend', 'dist');
}

function legacyWebDir(rootDir: string): string {
  return path.join(rootDir, 'web');
}

const frontendMimeTypes = new Map<string, string>([
  ['.js', 'application/javascript'],
  ['.css', 'text/css'],
  ['.html', 'text/html'],
  ['.json', 'application/json'],
  ['.svg', 'image/svg+xml'],
]);

function sendFrontendBundleMissing(res: Response): void {
  res.status(404).type('text/plain').send('Frontend bundle not found. Build the React workspace under frontend/ first.');
}

function sendFrontendAsset(res: Response, distDir: string, assetPath = 'index.html'): void {
  if (!existsSync(distDir)) {
    sendFrontendBundleMissing(res);
    return;
  }

  const distRoot = path.resolve(distDir);
  const requested = path.resolve(path.join(distRoot, assetPath));
  if (requested !== distRoot && !requested.startsWith(`${distRoot}${path.sep}`)) {
    res.sendStatus(404);
    return;
  }

  if (existsSync(requested) && statSync(requested).isFile()) {
    const mimeType = frontendMimeTypes.get(path.extname(requested).toLowerCase());
    if (mimeType) {
      res.type(mimeType);
    }
    res.sendFile(requested);
    return;
  }

  res.type('html').sendFile(path.join(distRoot, 'index.html'));
}

function sanitizeBoardDraftName(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    throw new HttpError(400, 'Missing board draft name');
  }
  const normalized = trimmed
    .replace(/\.json$/i, '')
    .replace(/[^a-zA-Z0-9._-]+/g, '_')
    .replace(/^\.+/, '')
    .replace(/_+/g, '_');
  if (!normalized) {
    throw new HttpError(400, 'Board draft name is invalid');
  }
  return `${normalized}.json`;
}

async function extractMcuPdfSnapshot(rootDir: string, uploadPath: string, filename: string): Promise<McuPdfSnapshot | null> {
  const snapshot = await callPythonJob(rootDir, {
    operation: 'extract-mcu-pdf-snapshot',
    uploadPath,
    filename,
  });
  if (snapshot.status !== 200 || !snapshot.json || typeof snapshot.json !== 'object') {
    return null;
  }
  return snapshot.json as McuPdfSnapshot;
}

async function extractSensorPdfSnapshot(rootDir: string, uploadPath: string, filename: string): Promise<SensorPdfSnapshot | null> {
  const snapshot = await callPythonJob(rootDir, {
    operation: 'extract-sensor-pdf-snapshot',
    uploadPath,
    filename,
  });
  if (snapshot.status !== 200 || !snapshot.json || typeof snapshot.json !== 'object') {
    return null;
  }
  return snapshot.json as SensorPdfSnapshot;
}

async function reparseSensorJob(rootDir: string, jobId: string): Promise<{ job_id: string; filename: string; result: unknown }> {
  const job = await getSensorJob(rootDir, jobId);
  if (!job) {
    throw new HttpError(404, 'Job not found');
  }
  if (!job.upload_path) {
    throw new HttpError(400, 'Job has no stored upload path');
  }

  const snapshot = await extractSensorPdfSnapshot(rootDir, job.upload_path, job.filename);
  if (!snapshot) {
    throw new HttpError(500, 'Could not extract sensor PDF snapshot');
  }

  const parsed = parseSensorSnapshot(snapshot);
  if (!parsed) {
    throw new HttpError(400, 'Could not parse sensor metadata from stored PDF');
  }

  await saveSensorJob(rootDir, {
    ...job,
    result: parsed,
  });

  return {
    job_id: job.job_id,
    filename: job.filename,
    result: parsed,
  };
}

function ensureProjectExtension(filePath: string): string {
  return filePath.toLowerCase().endsWith('.zpinproj') ? filePath : `${filePath}.zpinproj`;
}

async function ensureDirectory(dirPath: string): Promise<void> {
  await fs.mkdir(dirPath, { recursive: true });
}

async function saveProjectFile(body: Record<string, unknown>): Promise<{ saved: true; file_path: string }> {
  const rawFilePath = String(body.file_path ?? '').trim();
  if (!rawFilePath) {
    throw new HttpError(400, 'Missing file_path');
  }

  const filePath = ensureProjectExtension(rawFilePath);
  await ensureDirectory(path.dirname(filePath));

  const payload = {
    version: PROJECT_FILE_VERSION,
    board_id: body.board_id ?? '',
    pin_states: body.pin_states ?? {},
    periph_states: body.periph_states ?? {},
    periph_core_states: body.periph_core_states ?? {},
    generated_overlay: body.generated_overlay ?? '',
    generated_conf: body.generated_conf ?? '',
    sensor_jobs: body.sensor_jobs ?? [],
    sensor_selected: body.sensor_selected ?? '',
    mcu_jobs: body.mcu_jobs ?? [],
    mcu_selected: body.mcu_selected ?? '',
  };

  await fs.writeFile(filePath, JSON.stringify(payload, null, 2), 'utf8');
  return { saved: true, file_path: filePath };
}

async function loadProjectFile(body: Record<string, unknown>): Promise<unknown> {
  const filePath = String(body.file_path ?? '').trim();
  if (!filePath) {
    throw new HttpError(400, 'Missing file_path');
  }

  try {
    const text = await fs.readFile(filePath, 'utf8');
    return JSON.parse(text);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      throw new HttpError(404, `File not found: ${filePath}`);
    }
    throw new HttpError(400, `Invalid project file: ${String(error)}`);
  }
}

async function saveGeneratedFiles(body: Record<string, unknown>): Promise<unknown> {
  const projectPath = String(body.project_path ?? '');
  const overlay = String(body.overlay ?? '');
  const prjConf = String(body.prj_conf ?? '');
  const board = String(body.board ?? 'custom_board');

  let stats;
  try {
    stats = await fs.stat(projectPath);
  } catch {
    throw new HttpError(400, `Directory does not exist: ${projectPath}`);
  }
  if (!stats.isDirectory()) {
    throw new HttpError(400, `Directory does not exist: ${projectPath}`);
  }

  const overlayPath = path.join(projectPath, `${board}.overlay`);
  const confPath = path.join(projectPath, 'prj.conf');
  await fs.writeFile(overlayPath, overlay, 'utf8');

  let existing = '';
  try {
    existing = await fs.readFile(confPath, 'utf8');
  } catch {
    existing = '';
  }

  const nextLines = prjConf.split('\n').map((line) => line.trim()).filter((line) => line && !line.startsWith('#'));
  for (const line of nextLines) {
    const key = line.split('=')[0];
    if (!existing.includes(key)) {
      existing += `${existing.endsWith('\n') || existing.length === 0 ? '' : '\n'}${line}`;
    }
  }

  await fs.writeFile(confPath, `${existing.trim()}\n`, 'utf8');
  return {
    saved: true,
    overlay_path: overlayPath,
    conf_path: confPath,
  };
}

async function scanProject(body: Record<string, unknown>): Promise<unknown> {
  const projectPath = String(body.project_path ?? '');
  let stats;
  try {
    stats = await fs.stat(projectPath);
  } catch {
    throw new HttpError(400, `Directory does not exist: ${projectPath}`);
  }
  if (!stats.isDirectory()) {
    throw new HttpError(400, `Directory does not exist: ${projectPath}`);
  }

  const found: Array<Record<string, unknown>> = [];
  const candidates = [projectPath, path.join(projectPath, 'boards')];

  for (const dirPath of candidates) {
    try {
      const entries = await fs.readdir(dirPath, { withFileTypes: true });
      for (const entry of entries.sort((left, right) => left.name.localeCompare(right.name))) {
        if (!entry.isFile()) {
          continue;
        }
        const ext = path.extname(entry.name);
        if (ext !== '.overlay' && ext !== '.conf') {
          continue;
        }
        const fullPath = path.join(dirPath, entry.name);
        const content = await fs.readFile(fullPath, 'utf8');
        const stat = await fs.stat(fullPath);
        found.push({
          path: fullPath,
          relative: path.relative(projectPath, fullPath),
          name: entry.name,
          type: ext.slice(1),
          size: stat.size,
          content,
        });
      }
    } catch {
      // ignore missing boards/ directory
    }
  }

  const prjConfPath = path.join(projectPath, 'prj.conf');
  if (!found.some((entry) => entry.name === 'prj.conf')) {
    try {
      const content = await fs.readFile(prjConfPath, 'utf8');
      const stat = await fs.stat(prjConfPath);
      found.push({
        path: prjConfPath,
        relative: 'prj.conf',
        name: 'prj.conf',
        type: 'conf',
        size: stat.size,
        content,
      });
    } catch {
      // ignore missing file
    }
  }

  return { files: found };
}

async function listGeneratedPackages(rootDir: string): Promise<Array<{ filename: string; module: string; size: number }>> {
  const dirEntries = await fs.readdir(boardsDir(rootDir), { withFileTypes: true });
  const files: Array<{ filename: string; module: string; size: number }> = [];

  for (const entry of dirEntries.sort((left, right) => left.name.localeCompare(right.name))) {
    if (!entry.isFile() || !entry.name.endsWith('.py') || entry.name.startsWith('_')) {
      continue;
    }

    const fullPath = path.join(boardsDir(rootDir), entry.name);
    const stat = await fs.stat(fullPath);
    files.push({
      filename: entry.name,
      module: path.parse(entry.name).name,
      size: stat.size,
    });
  }

  return files;
}

async function listBoardEditorDrafts(rootDir: string): Promise<Array<{ filename: string; size: number; updated_at: number }>> {
  await ensureDirectory(boardEditorDir(rootDir));
  const dirEntries = await fs.readdir(boardEditorDir(rootDir), { withFileTypes: true });
  const drafts: Array<{ filename: string; size: number; updated_at: number }> = [];

  for (const entry of dirEntries) {
    if (!entry.isFile() || !entry.name.toLowerCase().endsWith('.json')) {
      continue;
    }
    const fullPath = path.join(boardEditorDir(rootDir), entry.name);
    const stat = await fs.stat(fullPath);
    drafts.push({
      filename: entry.name,
      size: stat.size,
      updated_at: stat.mtimeMs,
    });
  }

  drafts.sort((left, right) => right.updated_at - left.updated_at || left.filename.localeCompare(right.filename));
  return drafts;
}

async function saveBoardEditorDraft(rootDir: string, body: Record<string, unknown>): Promise<{ saved: true; filename: string; path: string }> {
  const board = body.board;
  if (!board || typeof board !== 'object' || Array.isArray(board)) {
    throw new HttpError(400, 'Missing board object');
  }

  const candidate = board as Record<string, unknown>;
  const boardName = String(body.filename ?? candidate.board ?? candidate.id ?? candidate.soc ?? '').trim();
  const filename = sanitizeBoardDraftName(boardName);
  await ensureDirectory(boardEditorDir(rootDir));
  const fullPath = path.join(boardEditorDir(rootDir), filename);
  await fs.writeFile(fullPath, `${JSON.stringify(board, null, 2)}\n`, 'utf8');

  return {
    saved: true,
    filename,
    path: fullPath,
  };
}

async function loadBoardEditorDraft(rootDir: string, filenameValue: string): Promise<{ filename: string; board: unknown }> {
  const filename = sanitizeBoardDraftName(filenameValue);
  const fullPath = path.join(boardEditorDir(rootDir), filename);
  try {
    const text = await fs.readFile(fullPath, 'utf8');
    return {
      filename,
      board: JSON.parse(text),
    };
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      throw new HttpError(404, `Board draft '${filename}' not found`);
    }
    throw new HttpError(400, `Invalid board draft '${filename}': ${String(error)}`);
  }
}

async function deleteBoardEditorDraft(rootDir: string, filenameValue: string): Promise<{ deleted: true; filename: string }> {
  const filename = sanitizeBoardDraftName(filenameValue);
  const fullPath = path.join(boardEditorDir(rootDir), filename);
  try {
    await fs.unlink(fullPath);
    return { deleted: true, filename };
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      throw new HttpError(404, `Board draft '${filename}' not found`);
    }
    throw new HttpError(500, `Failed to delete board draft '${filename}'`);
  }
}

async function resolveBoardByName(rootDir: string, boardName: string): Promise<unknown | null> {
  const boards = await listBoards(rootDir);
  const summary = boards.find((board) => board.id === boardName || board.board === boardName);
  if (!summary) {
    return null;
  }
  return await getBoard(rootDir, summary.id);
}

function enrichImportedPins(imported: ReturnType<typeof parseImport>, board: unknown): ReturnType<typeof parseImport> {
  if (!board || typeof board !== 'object') {
    return imported;
  }

  const boardPins = (board as { pins?: Array<{ name: string; alt_functions?: Array<Record<string, unknown>> }> }).pins ?? [];
  for (const pin of imported.pins) {
    if (pin.pin_name) {
      continue;
    }

    for (const candidate of boardPins) {
      const match = (candidate.alt_functions ?? []).find((af) => {
        const samePincm = Number(af.pincm ?? -1) === pin.pincm;
        const sameFunction = pin.function_id >= 0 ? Number(af.function_id ?? -1) === pin.function_id : true;
        const samePeripheral = String(af.peripheral ?? '').toLowerCase() === pin.peripheral.toLowerCase();
        const sameSignal = String(af.signal ?? '').toLowerCase() === pin.signal.toLowerCase();
        return samePincm && (sameFunction || (samePeripheral && sameSignal));
      });

      if (match) {
        pin.pin_name = candidate.name;
        break;
      }
    }
  }

  return imported;
}

function parseExternalDevices(value: unknown): ExternalDeviceSpec[] {
  if (!Array.isArray(value)) {
    return [];
  }

  const devices: ExternalDeviceSpec[] = [];
  for (const entry of value) {
    if (!entry || typeof entry !== 'object') {
      continue;
    }

    const device = entry as Record<string, unknown>;
    const id = String(device.id ?? '').trim();
    if (!id) {
      continue;
    }

    devices.push({
      id,
      display: String(device.display ?? id),
      category: String(device.category ?? 'device'),
      bus: String(device.bus ?? ''),
      compatible: String(device.compatible ?? ''),
      address: String(device.address ?? ''),
      required_signals: Array.isArray(device.required_signals) ? device.required_signals.map((signal) => String(signal)) : [],
      frameworks: Array.isArray(device.frameworks) ? device.frameworks.map((framework) => String(framework)) : [],
      notes: String(device.notes ?? ''),
    });
  }

  return devices;
}

class HttpError extends Error {
  readonly statusCode: number;

  constructor(statusCode: number, message: string) {
    super(message);
    this.statusCode = statusCode;
  }
}

function parseGenerateBody(body: Record<string, unknown>): {
  boardName: string;
  assignments: PinAssignment[];
  peripherals: PeripheralConfig[];
  externalDevices: ExternalDeviceConfig[];
  targets: string[];
} {
  const boardName = String(body.board ?? 'custom_board');
  const assignmentsValue = body.assignments;
  const peripheralsValue = body.peripherals;
  const targetsValue = Array.isArray(body.targets) ? body.targets : ['zephyr', 'arduino', 'baremetal'];
  const externalDevicesValue = body.external_devices;

  if (!Array.isArray(assignmentsValue)) {
    throw new HttpError(400, 'Missing assignments array');
  }
  if (!Array.isArray(peripheralsValue)) {
    throw new HttpError(400, 'Missing peripherals array');
  }

  const assignments = assignmentsValue.map((value) => {
    if (!value || typeof value !== 'object') {
      throw new HttpError(400, 'Invalid assignment entry');
    }
    const assignment = value as Record<string, unknown>;
    return {
      pin_name: String(assignment.pin_name ?? ''),
      pincm: Number(assignment.pincm ?? 0),
      function_id: Number(assignment.function_id ?? 0),
      af_name: String(assignment.af_name ?? ''),
      peripheral: String(assignment.peripheral ?? ''),
      signal: String(assignment.signal ?? ''),
      direction: String(assignment.direction ?? 'io'),
      zephyr_pinmux: String(assignment.zephyr_pinmux ?? ''),
      bias_pull_up: Boolean(assignment.bias_pull_up),
      bias_pull_down: Boolean(assignment.bias_pull_down),
      drive_open_drain: Boolean(assignment.drive_open_drain),
      input_enable: Boolean(assignment.input_enable),
    } satisfies PinAssignment;
  });

  const peripherals = peripheralsValue.map((value) => {
    if (!value || typeof value !== 'object') {
      throw new HttpError(400, 'Invalid peripheral entry');
    }
    const peripheral = value as Record<string, unknown>;
    return {
      name: String(peripheral.name ?? ''),
      dts_node: String(peripheral.dts_node ?? ''),
      compatible: String(peripheral.compatible ?? ''),
      enabled: Boolean(peripheral.enabled),
      core_id: String(peripheral.core_id ?? ''),
    } satisfies PeripheralConfig;
  });

  const externalDevices = Array.isArray(externalDevicesValue)
    ? externalDevicesValue.flatMap((value) => {
        if (!value || typeof value !== 'object') {
          return [];
        }
        const device = value as Record<string, unknown>;
        const id = String(device.id ?? '').trim();
        const display = String(device.display ?? id).trim();
        if (!id || !display) {
          return [];
        }
        return [{
          id,
          display,
          category: String(device.category ?? 'device'),
          bus: String(device.bus ?? ''),
          compatible: String(device.compatible ?? ''),
          address: String(device.address ?? ''),
          required_signals: Array.isArray(device.required_signals) ? device.required_signals.map((signal) => String(signal)) : [],
          frameworks: Array.isArray(device.frameworks) ? device.frameworks.map((framework) => String(framework)) : [],
          notes: String(device.notes ?? ''),
        } satisfies ExternalDeviceConfig];
      })
    : [];

  return {
    boardName,
    assignments,
    peripherals,
    externalDevices,
    targets: targetsValue.map((target) => String(target).toLowerCase()),
  };
}

export function createApp(rootDir = pinConfiguratorRoot()): express.Express {
  const app = express();
  const upload = multer({ dest: uploadsDir(rootDir) });
  const webDir = legacyWebDir(rootDir);
  const frontendDir = frontendDistDir(rootDir);

  void ensureDirectory(uploadsDir(rootDir));

  app.use(cors());
  app.use(express.json({ limit: '100mb' }));
  app.use(express.urlencoded({ extended: true, limit: '100mb' }));

  app.get('/api/boards', asyncHandler(async (_req, res) => {
    res.json(await listBoards(rootDir));
  }));

  app.get('/api/board/:name', asyncHandler(async (req, res) => {
    const boardName = Array.isArray(req.params.name) ? req.params.name[0] : req.params.name;
    const board = await getBoard(rootDir, boardName);
    if (board === null) {
      throw new HttpError(404, `Board '${boardName}' not found`);
    }
    res.json(board);
  }));

  app.get('/api/modules', asyncHandler(async (_req, res) => {
    res.json(await listModules(rootDir));
  }));

  app.post('/api/generate-module-config', asyncHandler(async (req, res) => {
    const body = req.body as Record<string, unknown>;
    let modulesMap: Record<string, Record<string, unknown>> = {};

    if (typeof body.module === 'string' && body.values && typeof body.values === 'object') {
      modulesMap = { [body.module]: body.values as Record<string, unknown> };
    } else if (body.modules && typeof body.modules === 'object') {
      modulesMap = body.modules as Record<string, Record<string, unknown>>;
    }

    if (Object.keys(modulesMap).length === 0) {
      throw new HttpError(400, 'No module configuration provided');
    }

    res.json(await generateModuleConfig(rootDir, modulesMap));
  }));

  app.get('/api/clock-trees', asyncHandler(async (_req, res) => {
    res.json(await listClockTrees(rootDir));
  }));

  app.get('/api/clock-tree/:treeId', asyncHandler(async (req, res) => {
    const treeId = Array.isArray(req.params.treeId) ? req.params.treeId[0] : req.params.treeId;
    const tree = await getClockTree(rootDir, treeId);
    if (tree === null) {
      throw new HttpError(404, `Clock tree '${treeId}' not found`);
    }
    res.json(tree);
  }));

  app.post('/api/clock-frequencies', asyncHandler(async (req, res) => {
    const body = req.body as Record<string, unknown>;
    const treeId = String(body.tree ?? '');
    if (!treeId) {
      throw new HttpError(400, "Missing 'tree' field");
    }
    const tree = await getTypedClockTree(rootDir, treeId);
    if (tree === null) {
      throw new HttpError(404, `Clock tree '${treeId}' not found`);
    }
    const values = body.values && typeof body.values === 'object' ? body.values as Record<string, unknown> : {};
    const analysis = analyzeClockTree(tree, values);
    res.json({ frequencies: analysis.frequencies, warnings: analysis.warnings });
  }));

  app.post('/api/generate-clock-config', asyncHandler(async (req, res) => {
    const body = req.body as Record<string, unknown>;
    const treeId = String(body.tree ?? '');
    if (!treeId) {
      throw new HttpError(400, "Missing 'tree' field");
    }
    const tree = await getTypedClockTree(rootDir, treeId);
    if (tree === null) {
      throw new HttpError(404, `Clock tree '${treeId}' not found`);
    }
    const values = body.values && typeof body.values === 'object' ? body.values as Record<string, unknown> : {};
    res.json(generateClockConfig(tree, values));
  }));

  app.get('/api/peripheral-templates', asyncHandler(async (_req, res) => {
    res.json(await listPeripheralTemplates(rootDir));
  }));

  app.get('/api/peripheral-instances/:boardName', asyncHandler(async (req, res) => {
    const boardName = Array.isArray(req.params.boardName) ? req.params.boardName[0] : req.params.boardName;
    try {
      res.json(await buildPeripheralInstances(rootDir, boardName));
    } catch (error) {
      throw new HttpError(404, error instanceof Error ? error.message : `Board '${boardName}' not found`);
    }
  }));

  app.post('/api/generate-peripheral-config', asyncHandler(async (req, res) => {
    const body = req.body as Record<string, unknown>;
    const boardName = String(body.board ?? '');
    const instances = body.instances;
    if (!boardName) {
      throw new HttpError(400, "Missing 'board' field");
    }
    if (!instances || typeof instances !== 'object' || Object.keys(instances).length === 0) {
      throw new HttpError(400, 'No peripheral instances provided');
    }
    try {
      res.json(await generatePeripheralConfig(rootDir, boardName, instances as Record<string, Record<string, unknown>>));
    } catch (error) {
      throw new HttpError(404, error instanceof Error ? error.message : `Board '${boardName}' not found`);
    }
  }));

  app.post('/api/identify-mcu', asyncHandler(async (req, res) => {
    const body = req.body as Record<string, unknown>;
    const partNumber = String(body.part_number ?? '').trim();
    if (!partNumber) {
      throw new HttpError(400, 'No part_number provided');
    }
    res.json(await identifyMcu(rootDir, partNumber));
  }));

  app.get('/api/driver-templates', asyncHandler(async (_req, res) => {
    res.json(listDriverTemplates());
  }));

  app.post('/api/generate-driver', asyncHandler(async (req, res) => {
    const body = req.body as Record<string, unknown> | undefined;
    if (!body || Object.keys(body).length === 0) {
      throw new HttpError(400, 'JSON body required');
    }

    const spec = specFromJson(body);
    res.json(generateDriver(spec));
  }));

  app.post('/api/identify-sensor', asyncHandler(async (req, res) => {
    const body = req.body as Record<string, unknown>;
    const partNumber = String(body.part_number ?? '').trim();
    if (!partNumber) {
      throw new HttpError(400, 'No part_number provided');
    }
    res.json(identifySensor(partNumber));
  }));

  app.post('/api/parse-pdf', upload.any(), asyncHandler(async (req, res) => {
    const files = (req.files ?? []) as Express.Multer.File[];
    const pdfFile = files.find((file) => file.fieldname === 'pdf');
    if (!pdfFile) {
      throw new HttpError(400, "No 'pdf' file in request");
    }

    const nativeResult = await tryParseTiPdfNative(rootDir, pdfFile.path, pdfFile.originalname, async (uploadPath, filename) => await extractMcuPdfSnapshot(rootDir, uploadPath, filename) as TiPdfSnapshot | null);

    if (nativeResult) {
      for (const file of files) {
        void fs.unlink(file.path).catch(() => undefined);
      }
      res.json(nativeResult);
      return;
    }

    const nativeStm32Result = await tryParseStm32PdfNative(rootDir, pdfFile.path, pdfFile.originalname, async (uploadPath, filename) => await extractMcuPdfSnapshot(rootDir, uploadPath, filename) as Stm32PdfSnapshot | null);

    if (nativeStm32Result) {
      for (const file of files) {
        void fs.unlink(file.path).catch(() => undefined);
      }
      res.json(nativeStm32Result);
      return;
    }

    const nativeGenericResult = await tryParseGenericPdfNative(rootDir, pdfFile.path, pdfFile.originalname, async (uploadPath, filename) => await extractMcuPdfSnapshot(rootDir, uploadPath, filename));

    if (nativeGenericResult) {
      for (const file of files) {
        void fs.unlink(file.path).catch(() => undefined);
      }
      res.json(nativeGenericResult);
      return;
    }

    const response = await callPythonJob(rootDir, {
      operation: 'parse-pdf',
      uploadPath: pdfFile.path,
      filename: pdfFile.originalname,
    });

    for (const file of files) {
      void fs.unlink(file.path).catch(() => undefined);
    }

    res.status(response.status).json(response.json);
  }));

  app.post('/api/fetch-datasheet', asyncHandler(async (req, res) => {
    const body = req.body as Record<string, unknown>;
    const partNumber = String(body.part_number ?? '').trim();
    if (!partNumber) {
      throw new HttpError(400, 'No part_number provided');
    }

    let downloaded;
    try {
      downloaded = await downloadMcuDatasheet(
        rootDir,
        partNumber,
        uploadArtifactDir(rootDir, 'downloads'),
        String(body.url ?? '').trim() || undefined,
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const isUnknownPart = message.startsWith('Unknown MCU part number:');
      const isDownloadFailure = message.startsWith('Could not download datasheet for');
      throw new HttpError(isUnknownPart || isDownloadFailure ? 404 : 500, message);
    }

    const nativeResult = await tryParseTiPdfNative(rootDir, downloaded.filePath, downloaded.filename, async (uploadPath, filename) => await extractMcuPdfSnapshot(rootDir, uploadPath, filename) as TiPdfSnapshot | null);
    if (nativeResult) {
      res.json({
        ...nativeResult,
        message: downloaded.message,
        part_number: partNumber,
      });
      return;
    }

    const nativeStm32Result = await tryParseStm32PdfNative(rootDir, downloaded.filePath, downloaded.filename, async (uploadPath, filename) => await extractMcuPdfSnapshot(rootDir, uploadPath, filename) as Stm32PdfSnapshot | null);
    if (nativeStm32Result) {
      res.json({
        ...nativeStm32Result,
        message: downloaded.message,
        part_number: partNumber,
      });
      return;
    }

    const nativeGenericResult = await tryParseGenericPdfNative(rootDir, downloaded.filePath, downloaded.filename, async (uploadPath, filename) => await extractMcuPdfSnapshot(rootDir, uploadPath, filename));
    if (nativeGenericResult) {
      res.json({
        ...nativeGenericResult,
        message: downloaded.message,
        part_number: partNumber,
      });
      return;
    }

    const response = await callPythonJob(rootDir, {
      operation: 'fetch-datasheet-parse',
      partNumber,
      uploadPath: downloaded.filePath,
      filename: downloaded.filename,
      message: downloaded.message,
    });
    res.status(response.status).json(response.json);
  }));

  app.post('/api/generate-package', asyncHandler(async (req, res) => {
    const body = req.body as Record<string, unknown>;
    const jobId = String(body.job_id ?? '').trim();
    const job = await getParsedJob(rootDir, jobId);
    if (!job || !job.full_result) {
      throw new HttpError(404, `Job '${jobId}' not found. Parse a PDF first.`);
    }

    const packages = Array.isArray(body.packages) ? body.packages.map((value) => String(value)) : undefined;
    const externalDevices = parseExternalDevices(body.external_devices);
    try {
      const files = await generateBoardFiles(rootDir, job.full_result, {
        packages,
        boardName: typeof body.board_name === 'string' ? body.board_name : undefined,
        dtsSocInclude: typeof body.dts_soc_include === 'string' ? body.dts_soc_include : undefined,
        dtsPinctrlInclude: typeof body.dts_pinctrl_include === 'string' ? body.dts_pinctrl_include : undefined,
        pinctrlHeader: typeof body.pinctrl_header === 'string' ? body.pinctrl_header : undefined,
        externalDevices,
        register: body.register === undefined ? true : Boolean(body.register),
      });
      invalidateBoardRegistryCache();
      res.json({ success: true, files });
    } catch (error) {
      throw new HttpError(400, error instanceof Error ? error.message : String(error));
    }
  }));

  app.post('/api/parse-sensor-pdf', upload.any(), asyncHandler(async (req, res) => {
    const files = (req.files ?? []) as Express.Multer.File[];
    const pdfFile = files.find((file) => file.fieldname === 'pdf');
    if (!pdfFile) {
      throw new HttpError(400, "No 'pdf' file in request");
    }

    const nativeResult = await tryParseSensorPdfNative(rootDir, pdfFile.path, pdfFile.originalname, async (uploadPath, filename) => await extractSensorPdfSnapshot(rootDir, uploadPath, filename));
    if (nativeResult) {
      for (const file of files) {
        void fs.unlink(file.path).catch(() => undefined);
      }
      res.json(nativeResult);
      return;
    }

    const response = await callPythonJob(rootDir, {
      operation: 'parse-sensor-pdf',
      uploadPath: pdfFile.path,
      filename: pdfFile.originalname,
    });

    for (const file of files) {
      void fs.unlink(file.path).catch(() => undefined);
    }

    res.status(response.status).json(response.json);
  }));

  app.get('/api/parse-jobs', asyncHandler(async (_req, res) => {
    res.json(await listParsedJobs(rootDir));
  }));

  app.get('/api/sensor-jobs', asyncHandler(async (_req, res) => {
    res.json(await listSensorJobs(rootDir));
  }));

  app.get('/api/sensor-job/:jobId', asyncHandler(async (req, res) => {
    const jobId = Array.isArray(req.params.jobId) ? req.params.jobId[0] : req.params.jobId;
    const job = await getSensorJob(rootDir, jobId);
    if (!job || !job.result) {
      throw new HttpError(404, 'Job not found');
    }

    res.json({
      job_id: job.job_id,
      filename: job.filename,
      result: job.result,
    });
  }));

  app.post('/api/sensor-jobs/reparse', asyncHandler(async (req, res) => {
    const body = (req.body as Record<string, unknown> | undefined) ?? {};
    const requestedJobIds = Array.isArray(body.job_ids)
      ? body.job_ids.map((value) => String(value)).filter(Boolean)
      : [];

    const jobIds = requestedJobIds.length
      ? requestedJobIds
      : (await listSensorJobs(rootDir)).map((job) => job.job_id);

    const results = [] as Array<{ job_id: string; filename: string; result?: unknown; error?: string }>;
    for (const jobId of jobIds) {
      try {
        results.push(await reparseSensorJob(rootDir, jobId));
      } catch (error) {
        results.push({
          job_id: jobId,
          filename: '',
          error: error instanceof Error ? error.message : String(error),
        });
      }
    }

    res.json({
      updated: results.filter((entry) => !entry.error).length,
      failed: results.filter((entry) => entry.error).length,
      jobs: results,
    });
  }));

  app.get('/api/sensor-job/:jobId/header', asyncHandler(async (req, res) => {
    const jobId = Array.isArray(req.params.jobId) ? req.params.jobId[0] : req.params.jobId;
    const job = await getSensorJob(rootDir, jobId);
    if (!job || !job.result) {
      throw new HttpError(404, 'Job not found');
    }

    const prefix = String(req.query.prefix ?? '').trim();
    const partNumber = job.result.summary?.part_number || 'sensor';
    res.json({
      job_id: job.job_id,
      filename: `${partNumber.toLowerCase()}_regs.h`,
      code: generateSensorRegisterHeader(job.result, prefix),
    });
  }));

  app.post('/api/sensor-job/:jobId/driver', asyncHandler(async (req, res) => {
    const jobId = Array.isArray(req.params.jobId) ? req.params.jobId[0] : req.params.jobId;
    const job = await getSensorJob(rootDir, jobId);
    if (!job || !job.result) {
      throw new HttpError(404, 'Job not found');
    }

    const body = (req.body as Record<string, unknown> | undefined) ?? {};
    res.json(generateSensorDriverFromJob(job.result, {
      name: typeof body.name === 'string' ? body.name : undefined,
      compatible: typeof body.compatible === 'string' ? body.compatible : undefined,
      bus: typeof body.bus === 'string' ? body.bus : undefined,
      has_interrupt: Boolean(body.has_interrupt),
    }));
  }));

  app.post('/api/save-project', asyncHandler(async (req, res) => {
    res.json(await saveGeneratedFiles(req.body as Record<string, unknown>));
  }));

  app.post('/api/project-file/save', asyncHandler(async (req, res) => {
    res.json(await saveProjectFile(req.body as Record<string, unknown>));
  }));

  app.post('/api/project-file/load', asyncHandler(async (req, res) => {
    res.json(await loadProjectFile(req.body as Record<string, unknown>));
  }));

  app.post('/api/scan-project', asyncHandler(async (req, res) => {
    res.json(await scanProject(req.body as Record<string, unknown>));
  }));

  app.get('/api/generated-packages', asyncHandler(async (_req, res) => {
    res.json(await listGeneratedPackages(rootDir));
  }));

  app.get('/api/board-editor/drafts', asyncHandler(async (_req, res) => {
    res.json({ drafts: await listBoardEditorDrafts(rootDir) });
  }));

  app.get('/api/board-editor/draft/:filename', asyncHandler(async (req, res) => {
    const filename = Array.isArray(req.params.filename) ? req.params.filename[0] : req.params.filename;
    res.json(await loadBoardEditorDraft(rootDir, filename));
  }));

  app.post('/api/board-editor/save', asyncHandler(async (req, res) => {
    res.json(await saveBoardEditorDraft(rootDir, req.body as Record<string, unknown>));
  }));

  app.post('/api/board-editor/delete', asyncHandler(async (req, res) => {
    const body = req.body as Record<string, unknown>;
    res.json(await deleteBoardEditorDraft(rootDir, String(body.filename ?? '')));
  }));

  app.post('/api/import-config', upload.any(), asyncHandler(async (req, res) => {
    let overlayText = '';
    let confText = '';
    let boardName = '';

    if (req.is('application/json')) {
      const body = req.body as Record<string, unknown>;
      overlayText = String(body.overlay ?? '');
      confText = String(body.conf ?? '');
      boardName = String(body.board_name ?? '');
    } else {
      const files = (req.files ?? []) as Express.Multer.File[];
      const overlayFile = files.find((file) => file.fieldname === 'overlay');
      const confFile = files.find((file) => file.fieldname === 'conf');

      if (overlayFile) {
        overlayText = await fs.readFile(overlayFile.path, 'utf8');
        boardName = path.basename(overlayFile.originalname ?? '', '.overlay');
      }
      if (confFile) {
        confText = await fs.readFile(confFile.path, 'utf8');
      }

      for (const file of files) {
        void fs.unlink(file.path).catch(() => undefined);
      }

      const formBoardName = (req.body as Record<string, unknown>).board_name;
      if (formBoardName !== undefined) {
        boardName = String(formBoardName || boardName);
      }
    }

    if (!overlayText && !confText) {
      throw new HttpError(400, 'No overlay or conf content provided');
    }

    const imported = parseImport(overlayText, confText, boardName);
    const board = boardName ? await resolveBoardByName(rootDir, boardName) : null;
    res.json(enrichImportedPins(imported, board));
  }));

  app.post('/api/generate', asyncHandler(async (req, res) => {
    const { boardName, assignments, peripherals, externalDevices, targets } = parseGenerateBody(req.body as Record<string, unknown>);
    res.json(generateOverlay(assignments, peripherals, boardName, targets, externalDevices));
  }));

  app.use('/api', (_req, res) => {
    res.status(404).json({ error: 'Not found' });
  });

  app.get('/app', (_req, res) => {
    sendFrontendAsset(res, frontendDir);
  });
  app.get('/app/*', (req, res) => {
    const wildcardParams = req.params as unknown as { '0'?: string | string[] };
    const assetPath = Array.isArray(wildcardParams['0']) ? wildcardParams['0'][0] : wildcardParams['0'];
    sendFrontendAsset(res, frontendDir, assetPath);
  });

  app.get('/', (_req, res) => {
    res.redirect('/app');
  });
  app.get('*', (_req, res) => {
    res.redirect('/app');
  });

  app.use((error: unknown, _req: Request, res: Response, _next: NextFunction) => {
    const statusCode = error instanceof HttpError ? error.statusCode : 500;
    const message = error instanceof Error ? error.message : 'Unexpected error';
    res.status(statusCode).json({ error: message });
  });

  return app;
}

function asyncHandler(handler: (req: Request, res: Response, next: NextFunction) => Promise<void>): express.RequestHandler {
  return (req, res, next) => {
    void handler(req, res, next).catch(next);
  };
}