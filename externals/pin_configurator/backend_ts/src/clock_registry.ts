import { promises as fs } from 'node:fs';
import * as path from 'node:path';
import { listParsedJobEntries, type ParsedClockInfoJson, type ParsedJobManifestEntry } from './job_registry';
import { extractParsedClockInfo } from './pdf_clock_parser';
import { callPythonJob, type McuPdfSnapshot } from './python_jobs';

export interface ClockRegistrySnapshot {
  summaries: ClockTreeSummary[];
  byId: Record<string, unknown>;
}

export interface ClockTreeSummary {
  id: string;
  name: string;
  soc: string;
  desc: string;
  max_freq: number;
  node_count: number;
}

export interface ClockTreeNodeProperty {
  key: string;
  type: string;
  default: unknown;
  label?: string;
  help?: string;
  choices?: unknown[];
  dts?: boolean;
  kconfig?: string | null;
}

export interface ClockTreeNode {
  id: string;
  name: string;
  type: string;
  icon?: string;
  desc?: string;
  freq_hz?: number;
  props?: ClockTreeNodeProperty[];
}

export interface ClockTree {
  id: string;
  name: string;
  soc: string;
  nodes: ClockTreeNode[];
  connections?: Array<{ from: string; to: string }>;
  kconfig?: string[];
  desc?: string;
  max_freq?: number;
  engine?: string;
  peripheral_clocks?: Record<string, string>;
}

export interface ClockAnalysisResult {
  frequencies: Record<string, number>;
  warnings: string[];
}

let cachedClockPath = '';
let cachedClockRegistry: ClockRegistrySnapshot | null = null;

function snapshotPath(rootDir: string): string {
  return path.join(rootDir, 'backend_ts', 'src', 'generated', 'clock_trees.json');
}

async function loadClockRegistry(rootDir: string): Promise<ClockRegistrySnapshot> {
  const nextPath = snapshotPath(rootDir);
  if (cachedClockRegistry && cachedClockPath === nextPath) {
    return cachedClockRegistry;
  }

  const text = await fs.readFile(nextPath, 'utf8');
  const parsed = JSON.parse(text) as Partial<ClockRegistrySnapshot>;
  if (!Array.isArray(parsed.summaries) || !parsed.byId || typeof parsed.byId !== 'object') {
    throw new Error(`Invalid clock registry snapshot: ${nextPath}`);
  }

  cachedClockPath = nextPath;
  cachedClockRegistry = {
    summaries: parsed.summaries as ClockTreeSummary[],
    byId: parsed.byId as Record<string, unknown>,
  };
  return cachedClockRegistry;
}

function clockEngine(tree: ClockTree): string {
  return typeof tree.engine === 'string' && tree.engine ? tree.engine : tree.id;
}

function genericSimpleTemplate(soc: string, hint?: ParsedClockInfoJson): ClockTree {
  const maxFreq = hint?.max_freq_hz && hint.max_freq_hz > 0 ? hint.max_freq_hz : 120_000_000;
  const defaultInternal = maxFreq > 64_000_000 ? 16_000_000 : 8_000_000;
  const defaultExternal = maxFreq > 80_000_000 ? 24_000_000 : 8_000_000;
  return {
    id: 'generic_simple',
    engine: 'generic_simple',
    name: `${soc || 'Generic MCU'} Clock Tree`,
    soc,
    desc: hint?.summary || 'Generic MCU clock tree synthesized from parsed PDF text.',
    max_freq: maxFreq,
    nodes: [
      {
        id: 'clk_internal',
        name: 'Internal Oscillator',
        type: 'source',
        freq_hz: defaultInternal,
        props: [
          { key: 'clk-internal-freq', type: 'int', default: defaultInternal, dts: true, kconfig: null },
        ],
      },
      {
        id: 'clk_external',
        name: 'External Oscillator',
        type: 'source',
        freq_hz: 0,
        props: [
          { key: 'clk-external-enable', type: 'bool', default: false, dts: true, kconfig: null },
          { key: 'clk-external-freq', type: 'int', default: defaultExternal, dts: true, kconfig: null },
        ],
      },
      {
        id: 'pll_main',
        name: 'PLL',
        type: 'pll',
        freq_hz: 0,
        props: [
          { key: 'pll-enable', type: 'bool', default: true, dts: true, kconfig: null },
          { key: 'pll-source', type: 'choice', default: 'INTERNAL', dts: true, kconfig: null },
          { key: 'pll-mult', type: 'int', default: Math.max(1, Math.round(maxFreq / defaultInternal)), dts: true, kconfig: null },
          { key: 'pll-div', type: 'int', default: 1, dts: true, kconfig: null },
        ],
      },
      {
        id: 'sysclk_mux',
        name: 'SYSCLK Mux',
        type: 'mux',
        freq_hz: 0,
        props: [
          { key: 'sysclk-source', type: 'choice', default: 'PLL', dts: true, kconfig: null },
        ],
      },
      {
        id: 'sysclk_out',
        name: 'SYSCLK',
        type: 'output',
        freq_hz: 0,
        props: [
          { key: 'sysclk-divider', type: 'int', default: 1, dts: true, kconfig: null },
        ],
      },
      {
        id: 'peripheral_clk',
        name: 'Peripheral Clock',
        type: 'output',
        freq_hz: 0,
        props: [
          { key: 'peripheral-divider', type: 'int', default: 1, dts: true, kconfig: null },
        ],
      },
    ],
    connections: [
      { from: 'clk_internal', to: 'pll_main' },
      { from: 'clk_external', to: 'pll_main' },
      { from: 'clk_internal', to: 'sysclk_mux' },
      { from: 'clk_external', to: 'sysclk_mux' },
      { from: 'pll_main', to: 'sysclk_mux' },
      { from: 'sysclk_mux', to: 'sysclk_out' },
      { from: 'sysclk_out', to: 'peripheral_clk' },
    ],
  };
}

function renesasRaTemplate(soc: string, hint?: ParsedClockInfoJson): ClockTree {
  const maxFreq = hint?.max_freq_hz && hint.max_freq_hz > 0 ? hint.max_freq_hz : 64_000_000;
  return {
    id: 'renesas_ra',
    engine: 'renesas_ra',
    name: `${soc || 'Renesas RA'} Clock Tree`,
    soc,
    desc: hint?.summary || 'Renesas RA clock tree synthesized from parsed PDF text.',
    max_freq: maxFreq,
    nodes: [
      {
        id: 'hoco',
        name: 'HOCO',
        icon: '🔷',
        desc: 'High-speed on-chip oscillator with selectable 24/32/48/64 MHz output.',
        type: 'source',
        freq_hz: 64_000_000,
        props: [
          { key: 'hoco-enable', label: 'Enable HOCO', help: 'High-speed on-chip oscillator', type: 'bool', default: true, dts: true, kconfig: null },
          { key: 'hoco-freq', label: 'HOCO Frequency', help: 'Select the HOCO operating point', type: 'choice', choices: [24_000_000, 32_000_000, 48_000_000, 64_000_000], default: 64_000_000, dts: true, kconfig: null },
        ],
      },
      {
        id: 'moco',
        name: 'MOCO',
        icon: '🔷',
        desc: 'Middle-speed on-chip oscillator, typically 8 MHz.',
        type: 'source',
        freq_hz: 8_000_000,
        props: [
          { key: 'moco-enable', label: 'Enable MOCO', help: 'Middle-speed on-chip oscillator', type: 'bool', default: true, dts: true, kconfig: null },
        ],
      },
      {
        id: 'loco',
        name: 'LOCO',
        icon: '🔷',
        desc: 'Low-speed on-chip oscillator, typically 32.768 kHz.',
        type: 'source',
        freq_hz: 32_768,
        props: [],
      },
      {
        id: 'mosc',
        name: 'MOSC',
        icon: '💎',
        desc: 'Main clock oscillator using an external crystal or clock input (1 to 20 MHz).',
        type: 'source',
        freq_hz: 0,
        props: [
          { key: 'mosc-enable', label: 'Enable MOSC', help: 'Main external clock oscillator', type: 'bool', default: false, dts: true, kconfig: null },
          { key: 'mosc-freq', label: 'MOSC Frequency', help: 'External main clock frequency in Hz', type: 'int', default: 8_000_000, dts: true, kconfig: null },
        ],
      },
      {
        id: 'sosc',
        name: 'SOSC',
        icon: '💎',
        desc: 'Sub-clock oscillator, typically 32.768 kHz.',
        type: 'source',
        freq_hz: 0,
        props: [
          { key: 'sosc-enable', label: 'Enable SOSC', help: 'Enable the 32.768 kHz sub-clock oscillator', type: 'bool', default: false, dts: true, kconfig: null },
        ],
      },
      {
        id: 'pll',
        name: 'PLL',
        icon: '⚡',
        desc: 'System PLL driven from HOCO or MOSC.',
        type: 'pll',
        freq_hz: 0,
        props: [
          { key: 'pll-enable', label: 'Enable PLL', help: 'Enable the Renesas RA system PLL', type: 'bool', default: true, dts: true, kconfig: null },
          { key: 'pll-source', label: 'PLL Source', help: 'Select the PLL reference source', type: 'choice', choices: ['HOCO', 'MOSC'], default: 'HOCO', dts: true, kconfig: null },
          { key: 'pll-mult', label: 'PLL Multiplier', help: 'PLL multiplication factor', type: 'int', default: 1, dts: true, kconfig: null },
          { key: 'pll-div', label: 'PLL Divider', help: 'PLL input divider', type: 'int', default: 1, dts: true, kconfig: null },
        ],
      },
      {
        id: 'sysclk_mux',
        name: 'System Clock Source',
        icon: '🔀',
        desc: 'Select the root system clock before bus dividers.',
        type: 'mux',
        freq_hz: 0,
        props: [
          { key: 'sysclk-source', label: 'System Clock Source', help: 'Select the RA system clock source', type: 'choice', choices: ['HOCO', 'MOCO', 'LOCO', 'MOSC', 'SOSC', 'PLL'], default: 'PLL', dts: true, kconfig: null },
        ],
      },
      {
        id: 'iclk_out',
        name: 'ICLK',
        icon: '📤',
        desc: 'CPU instruction clock.',
        type: 'output',
        freq_hz: 0,
        props: [
          { key: 'iclk-divider', label: 'ICLK Divider', help: 'Divide the selected system clock for ICLK', type: 'choice', choices: [1, 2, 4, 8, 16, 32, 64], default: 1, dts: true, kconfig: null },
        ],
      },
      {
        id: 'pclkb_out',
        name: 'PCLKB',
        icon: '📤',
        desc: 'Peripheral clock B.',
        type: 'output',
        freq_hz: 0,
        props: [
          { key: 'pclkb-divider', label: 'PCLKB Divider', help: 'Divide the selected system clock for PCLKB', type: 'choice', choices: [1, 2, 4, 8, 16, 32, 64], default: 2, dts: true, kconfig: null },
        ],
      },
      {
        id: 'pclkd_out',
        name: 'PCLKD',
        icon: '📤',
        desc: 'Peripheral clock D.',
        type: 'output',
        freq_hz: 0,
        props: [
          { key: 'pclkd-divider', label: 'PCLKD Divider', help: 'Divide the selected system clock for PCLKD', type: 'choice', choices: [1, 2, 4, 8, 16, 32, 64], default: 1, dts: true, kconfig: null },
        ],
      },
      {
        id: 'fclk_out',
        name: 'FCLK',
        icon: '📤',
        desc: 'Flash interface clock.',
        type: 'output',
        freq_hz: 0,
        props: [
          { key: 'fclk-divider', label: 'FCLK Divider', help: 'Divide the selected system clock for FCLK', type: 'choice', choices: [1, 2, 4, 8, 16, 32, 64], default: 4, dts: true, kconfig: null },
        ],
      },
      {
        id: 'systick_clk',
        name: 'SysTick Clock',
        icon: '📤',
        desc: 'SysTick can be driven from LOCO or ICLK on RA2L1.',
        type: 'output',
        freq_hz: 0,
        props: [
          { key: 'systick-source', label: 'SysTick Source', help: 'Select LOCO or ICLK for SysTick', type: 'choice', choices: ['LOCO', 'ICLK'], default: 'ICLK', dts: true, kconfig: null },
        ],
      },
    ],
    connections: [
      { from: 'hoco', to: 'pll' },
      { from: 'mosc', to: 'pll' },
      { from: 'hoco', to: 'sysclk_mux' },
      { from: 'moco', to: 'sysclk_mux' },
      { from: 'loco', to: 'sysclk_mux' },
      { from: 'mosc', to: 'sysclk_mux' },
      { from: 'sosc', to: 'sysclk_mux' },
      { from: 'pll', to: 'sysclk_mux' },
      { from: 'sysclk_mux', to: 'iclk_out' },
      { from: 'sysclk_mux', to: 'pclkb_out' },
      { from: 'sysclk_mux', to: 'pclkd_out' },
      { from: 'sysclk_mux', to: 'fclk_out' },
      { from: 'loco', to: 'systick_clk' },
      { from: 'iclk_out', to: 'systick_clk' },
    ],
  };
}

async function parsedClockHint(rootDir: string, job: ParsedJobManifestEntry): Promise<ParsedClockInfoJson | null> {
  const stored = job.full_result?.clock;
  if (stored?.model || stored?.summary || stored?.max_freq_hz) {
    return stored;
  }

  if (!job.upload_path || !job.full_result?.device) {
    return null;
  }

  const snapshot = await callPythonJob(rootDir, {
    operation: 'extract-mcu-pdf-snapshot',
    uploadPath: job.upload_path,
    filename: job.filename,
  });
  if (snapshot.status !== 200 || !snapshot.json || typeof snapshot.json !== 'object') {
    return null;
  }

  return extractParsedClockInfo(snapshot.json as McuPdfSnapshot, job.full_result.device) ?? null;
}

function normalizeClockToken(value: string | undefined | null): string {
  return (value || '').toLowerCase().replace(/[^a-z0-9]+/g, '');
}

function zephyrFallbackScore(summary: ClockTreeSummary, device: { soc?: string; vendor?: string }): number {
  const summaryKeys = [summary.id, summary.name, summary.soc].map(normalizeClockToken).filter(Boolean);
  const soc = normalizeClockToken(device.soc);
  const vendor = normalizeClockToken(device.vendor);

  if (soc && summaryKeys.includes(soc)) {
    return 100;
  }
  if (soc && summaryKeys.some((key) => key.includes(soc) || soc.includes(key))) {
    return 80;
  }

  if (soc.includes('mspm0') && summary.id === 'mspm0g3507') {
    return 70;
  }
  if ((soc.includes('stm32') || vendor.includes('stmicro') || vendor === 'st') && summary.id === 'stm32_generic') {
    return 60;
  }
  if ((soc.includes('nrf52') || soc.includes('nrf528') || vendor.includes('nordic')) && summary.id === 'nrf52') {
    return 60;
  }

  return 0;
}

function pickZephyrFallbackTree(base: ClockRegistrySnapshot, device: { soc?: string; vendor?: string }): ClockTree | null {
  let best: ClockTree | null = null;
  let bestScore = 0;

  for (const summary of base.summaries) {
    const score = zephyrFallbackScore(summary, device);
    if (score <= bestScore) {
      continue;
    }
    const tree = asClockTree(base.byId[summary.id]);
    if (!tree) {
      continue;
    }
    best = tree;
    bestScore = score;
  }

  return best;
}

function cloneTree(tree: ClockTree): ClockTree {
  return JSON.parse(JSON.stringify(tree)) as ClockTree;
}

function buildParsedTree(baseTree: ClockTree, job: ParsedJobManifestEntry, hint?: ParsedClockInfoJson | null): ClockTree {
  const device = job.full_result?.device;
  const tree = cloneTree(baseTree);
  tree.id = `parsed_${job.job_id}`;
  tree.name = `${device?.soc || job.filename} Clock Tree (Parsed PDF)`;
  tree.soc = device?.soc || tree.soc;
  tree.desc = hint?.summary || tree.desc;
  tree.max_freq = hint?.max_freq_hz || device?.clock_hz || tree.max_freq;
  tree.engine = clockEngine(baseTree);
  return tree;
}

async function loadCombinedClockRegistry(rootDir: string): Promise<ClockRegistrySnapshot> {
  const base = await loadClockRegistry(rootDir);
  const summaries = [...base.summaries];
  const byId: Record<string, unknown> = { ...base.byId };
  const parsedJobs = await listParsedJobEntries(rootDir);

  for (const job of parsedJobs) {
    const device = job.full_result?.device;
    if (!device) {
      continue;
    }
    const hint = await parsedClockHint(rootDir, job);
    const baseTree = hint?.model === 'generic_simple'
      ? genericSimpleTemplate(device.soc, hint)
      : hint?.model === 'renesas_ra'
        ? renesasRaTemplate(device.soc, hint)
        : hint?.model
          ? asClockTree(base.byId[hint.model])
          : pickZephyrFallbackTree(base, device);
    if (!baseTree) {
      continue;
    }

    const tree = buildParsedTree(baseTree, job, hint);
    byId[tree.id] = tree;
    summaries.push({
      id: tree.id,
      name: tree.name,
      soc: tree.soc,
      desc: tree.desc || '',
      max_freq: tree.max_freq || 0,
      node_count: Array.isArray(tree.nodes) ? tree.nodes.length : 0,
    });
  }

  summaries.sort((left, right) => left.name.localeCompare(right.name));
  return { summaries, byId };
}

export async function listClockTrees(rootDir: string): Promise<ClockTreeSummary[]> {
  return (await loadCombinedClockRegistry(rootDir)).summaries;
}

export async function getClockTree(rootDir: string, treeId: string): Promise<unknown | null> {
  return (await loadCombinedClockRegistry(rootDir)).byId[treeId] ?? null;
}

function asClockTree(value: unknown): ClockTree | null {
  if (!value || typeof value !== 'object') {
    return null;
  }
  const tree = value as Partial<ClockTree>;
  if (!tree.id || !Array.isArray(tree.nodes)) {
    return null;
  }
  return tree as ClockTree;
}

export async function getTypedClockTree(rootDir: string, treeId: string): Promise<ClockTree | null> {
  return asClockTree(await getClockTree(rootDir, treeId));
}

export function analyzeClockTree(tree: ClockTree, values: Record<string, unknown>): ClockAnalysisResult {
  const engine = clockEngine(tree);
  if (engine === 'renesas_ra') {
    return analyzeRenesasRa(values);
  }

  return {
    frequencies: computeFrequencies(tree, values),
    warnings: [],
  };
}

export function computeFrequencies(tree: ClockTree, values: Record<string, unknown>): Record<string, number> {
  const engine = clockEngine(tree);
  if (engine === 'renesas_ra') {
    return analyzeRenesasRa(values).frequencies;
  }
  if (engine === 'mspm0g3507' || engine === 'mspm0') {
    return computeMspm0(values);
  }
  if (engine === 'stm32_generic') {
    return computeStm32(values);
  }
  if (engine === 'nrf52') {
    return computeNrf52(values);
  }
  if (engine === 'generic_simple') {
    return computeGenericSimple(values);
  }

  const output: Record<string, number> = {};
  for (const node of tree.nodes) {
    output[node.id] = typeof node.freq_hz === 'number' ? node.freq_hz : 0;
  }
  return output;
}

function computeGenericSimple(values: Record<string, unknown>): Record<string, number> {
  const output: Record<string, number> = {};
  output.clk_internal = asNumber(values['clk-internal-freq'], 8_000_000);
  output.clk_external = asBool(values['clk-external-enable']) ? asNumber(values['clk-external-freq'], 8_000_000) : 0;

  const pllEnabled = values['pll-enable'] === undefined ? true : asBool(values['pll-enable']);
  if (pllEnabled) {
    const source = asString(values['pll-source'], 'INTERNAL');
    const pllIn = source === 'EXTERNAL' && output.clk_external ? output.clk_external : output.clk_internal;
    const mult = Math.max(1, asNumber(values['pll-mult'], 4) || 1);
    const div = Math.max(1, asNumber(values['pll-div'], 1) || 1);
    output.pll_main = Math.floor((pllIn * mult) / div);
  } else {
    output.pll_main = 0;
  }

  const sysclkSource = asString(values['sysclk-source'], 'PLL');
  if (sysclkSource === 'EXTERNAL' && output.clk_external) {
    output.sysclk_mux = output.clk_external;
  } else if (sysclkSource === 'INTERNAL') {
    output.sysclk_mux = output.clk_internal;
  } else {
    output.sysclk_mux = output.pll_main || output.clk_internal;
  }

  const sysclkDivider = Math.max(1, asNumber(values['sysclk-divider'], 1) || 1);
  output.sysclk_out = Math.floor(output.sysclk_mux / sysclkDivider);
  const peripheralDivider = Math.max(1, asNumber(values['peripheral-divider'], 1) || 1);
  output.peripheral_clk = Math.floor(output.sysclk_out / peripheralDivider);
  return output;
}

function analyzeRenesasRa(values: Record<string, unknown>): ClockAnalysisResult {
  const warnings: string[] = [];
  const output: Record<string, number> = {};
  const capRa = (value: number, label: string): number => {
    const limited = Math.max(0, Math.min(64_000_000, Math.floor(value)));
    if (limited !== Math.floor(value)) {
      warnings.push(`${label} was limited to 64 MHz.`);
    }
    return limited;
  };

  output.hoco = asBool(values['hoco-enable']) ? asNumber(values['hoco-freq'], 64_000_000) : 0;
  output.moco = values['moco-enable'] === undefined || asBool(values['moco-enable']) ? 8_000_000 : 0;
  output.loco = 32_768;

  const moscEnabled = asBool(values['mosc-enable']);
  const requestedMosc = asNumber(values['mosc-freq'], 8_000_000);
  if (moscEnabled) {
    const clampedMosc = Math.min(20_000_000, Math.max(1_000_000, requestedMosc));
    if (clampedMosc !== requestedMosc) {
      warnings.push(`MOSC frequency was clamped into the documented 1-20 MHz range.`);
    }
    output.mosc = clampedMosc;
  } else {
    output.mosc = 0;
  }

  output.sosc = asBool(values['sosc-enable']) ? 32_768 : 0;

  const pllEnabled = values['pll-enable'] === undefined ? true : asBool(values['pll-enable']);
  if (pllEnabled) {
    const pllSource = asString(values['pll-source'], 'HOCO');
    const pllUsesMosc = pllSource === 'MOSC';
    if (pllUsesMosc && !output.mosc) {
      warnings.push('PLL source requested MOSC, but MOSC is disabled. Falling back to HOCO.');
    }
    const pllInput = pllUsesMosc && output.mosc ? output.mosc : output.hoco;
    const pllMult = Math.max(1, asNumber(values['pll-mult'], 1) || 1);
    const pllDiv = Math.max(1, asNumber(values['pll-div'], 1) || 1);
    output.pll = capRa((pllInput * pllMult) / pllDiv, 'PLL output');
  } else {
    output.pll = 0;
  }

  const sysclkSource = asString(values['sysclk-source'], 'PLL');
  const sysclkMap: Record<string, number> = {
    HOCO: output.hoco,
    MOCO: output.moco,
    LOCO: output.loco,
    MOSC: output.mosc,
    SOSC: output.sosc,
    PLL: output.pll,
  };
  if (!sysclkMap[sysclkSource]) {
    warnings.push(`System clock source '${sysclkSource}' is unavailable with the current oscillator settings. Falling back to HOCO.`);
  }
  output.sysclk_mux = capRa(sysclkMap[sysclkSource] || output.hoco || output.moco || output.loco, 'System clock');

  const iclkDiv = Math.max(1, asNumber(values['iclk-divider'], 1) || 1);
  const pclkbDiv = Math.max(1, asNumber(values['pclkb-divider'], 2) || 1);
  const pclkdDiv = Math.max(1, asNumber(values['pclkd-divider'], 1) || 1);
  const fclkDiv = Math.max(1, asNumber(values['fclk-divider'], 4) || 1);
  output.iclk_out = capRa(output.sysclk_mux / iclkDiv, 'ICLK');
  output.pclkb_out = capRa(output.sysclk_mux / pclkbDiv, 'PCLKB');
  output.pclkd_out = capRa(output.sysclk_mux / pclkdDiv, 'PCLKD');
  output.fclk_out = capRa(output.sysclk_mux / fclkDiv, 'FCLK');

  const systickSource = asString(values['systick-source'], 'ICLK');
  output.systick_clk = systickSource === 'LOCO' ? output.loco : output.iclk_out;

  return { frequencies: output, warnings };
}

function computeRenesasRa(values: Record<string, unknown>): Record<string, number> {
  return analyzeRenesasRa(values).frequencies;
}

function asNumber(value: unknown, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function asBool(value: unknown): boolean {
  return Boolean(value);
}

function asString(value: unknown, fallback: string): string {
  return typeof value === 'string' ? value : fallback;
}

function computeMspm0(values: Record<string, unknown>): Record<string, number> {
  const output: Record<string, number> = {};
  output.sysosc = asNumber(values['sysosc-freq'], 32_000_000);
  output.lfosc = 32_768;
  output.hfxt = asBool(values['hfxt-enable']) ? asNumber(values['hfxt-freq'], 48_000_000) : 0;
  output.lfxt = asBool(values['lfxt-enable']) ? 32_768 : 0;

  const pllEnabled = asBool(values['syspll-enable']);
  if (pllEnabled) {
    const pllSource = asString(values['syspll-input'], 'SYSOSC');
    const pllIn = pllSource === 'HFXT' && output.hfxt ? output.hfxt : output.sysosc;
    const pdiv = asNumber(values['syspll-pdiv'], 1) || 1;
    const qdiv = asNumber(values['syspll-qdiv'], 5) || 5;
    const vco = Math.floor(pllIn / pdiv) * qdiv;
    const clk0Div = asNumber(values['syspll-clk0-div'], 2) || 2;
    const clk2xDiv = asNumber(values['syspll-clk2x-div'], 1) || 1;
    output.syspll = vco;
    output._syspll_clk0 = Math.floor(vco / clk0Div);
    output._syspll_clk2x = Math.floor((vco * 2) / clk2xDiv);
  } else {
    output.syspll = 0;
    output._syspll_clk0 = 0;
    output._syspll_clk2x = 0;
  }

  const mclkSource = asString(values['mclk-source'], 'SYSOSC');
  let mclkRaw = output.sysosc;
  if (mclkSource === 'HFXT' && output.hfxt) {
    mclkRaw = output.hfxt;
  } else if (mclkSource === 'SYSPLL_CLK0' && pllEnabled) {
    mclkRaw = output._syspll_clk0;
  } else if (mclkSource === 'SYSPLL_CLK2X' && pllEnabled) {
    mclkRaw = output._syspll_clk2x;
  }
  output.mclk_mux = mclkRaw;

  const mclkDiv = asNumber(values['mclk-divider'], 1) || 1;
  output.mclk_div = Math.floor(mclkRaw / mclkDiv);
  output.mclk_out = output.mclk_div;

  const ulpDiv = asNumber(values['ulpclk-divider'], 1) || 1;
  output.ulpclk_div = Math.floor(mclkRaw / ulpDiv);
  output.ulpclk_out = output.ulpclk_div;

  const lfclkSource = asString(values['lfclk-source'], 'LFOSC');
  output.lfclk_mux = lfclkSource === 'LFXT' && output.lfxt ? output.lfxt : 32_768;
  output.lfclk_out = output.lfclk_mux;

  const canclkSource = asString(values['canclk-source'], 'MCLK');
  let canBase = output.mclk_out;
  if (canclkSource === 'SYSPLL_CLK0' && pllEnabled) {
    canBase = output._syspll_clk0;
  } else if (canclkSource === 'HFXT' && output.hfxt) {
    canBase = output.hfxt;
  }
  const canDiv = asNumber(values['canclk-divider'], 1) || 1;
  output.canclk_div = Math.floor(canBase / canDiv);
  output.canclk_out = output.canclk_div;

  return output;
}

function computeStm32(values: Record<string, unknown>): Record<string, number> {
  const output: Record<string, number> = {};
  output.hsi = asNumber(values['hsi-freq'], 16_000_000);
  output.hse = asBool(values['hse-enable']) ? asNumber(values['hse-freq'], 8_000_000) : 0;
  output.lsi = 32_000;
  output.lse = asBool(values['lse-enable']) ? 32_768 : 0;

  const pllEnabled = values['pll-enable'] === undefined ? true : asBool(values['pll-enable']);
  if (pllEnabled) {
    const pllSource = asString(values['pll-source'], 'HSI');
    const pllIn = pllSource === 'HSE' && output.hse ? output.hse : output.hsi;
    const m = Math.max(1, asNumber(values['pll-m'], 1) || 1);
    const n = Math.max(1, asNumber(values['pll-n'], 20) || 20);
    const p = Math.max(2, asNumber(values['pll-p'], 2) || 2);
    const vco = Math.floor(pllIn / m) * n;
    output.pll_main = Math.floor(vco / p);
  } else {
    output.pll_main = 0;
  }

  const sysclkSource = asString(values['sysclk-source'], 'PLL');
  let sysclk = output.hsi;
  if (sysclkSource === 'HSE' && output.hse) {
    sysclk = output.hse;
  } else if (sysclkSource === 'PLL' && pllEnabled) {
    sysclk = output.pll_main;
  }
  output.sysclk_mux = sysclk;

  const ahb = Math.max(1, asNumber(values['ahb-prescaler'], 1) || 1);
  const apb1 = Math.max(1, asNumber(values['apb1-prescaler'], 1) || 1);
  const apb2 = Math.max(1, asNumber(values['apb2-prescaler'], 1) || 1);
  output.ahb_div = Math.floor(sysclk / ahb);
  output.hclk = output.ahb_div;
  output.apb1_div = Math.floor(output.ahb_div / apb1);
  output.pclk1 = output.apb1_div;
  output.apb2_div = Math.floor(output.ahb_div / apb2);
  output.pclk2 = output.apb2_div;
  return output;
}

function computeNrf52(values: Record<string, unknown>): Record<string, number> {
  const output: Record<string, number> = {};
  output.hfint = 64_000_000;
  output.hfxo = values['hfxo-enable'] === undefined || asBool(values['hfxo-enable']) ? 64_000_000 : 0;
  output.lfrc = 32_768;
  output.lfxo = asBool(values['lfxo-enable']) ? 32_768 : 0;

  const hfclkSource = asString(values['hfclk-source'], 'HFXO');
  output.hfclk_mux = hfclkSource === 'HFXO' && output.hfxo ? output.hfxo : output.hfint;
  output.hfclk_out = output.hfclk_mux;

  const lfclkSource = asString(values['lfclk-source'], 'LFRC');
  if (lfclkSource === 'LFXO' && output.lfxo) {
    output.lfclk_mux = output.lfxo;
  } else if (lfclkSource === 'LFSYNTH') {
    output.lfclk_mux = 32_768;
  } else {
    output.lfclk_mux = output.lfrc;
  }
  output.lfclk_out = output.lfclk_mux;
  return output;
}

export function generateClockConfig(tree: ClockTree, values: Record<string, unknown>): {
  overlay: string;
  prj_conf: string;
  frequencies: Record<string, number>;
  warnings: string[];
} {
  const analysis = analyzeClockTree(tree, values);
  const frequencies = analysis.frequencies;
  const overlayLines = [
    '/*',
    ' * Clock system configuration',
    ` * SoC: ${tree.soc}`,
    ' * Generated by Zephyr Clock System Configurator',
    ' */',
    '',
  ];

  for (const node of tree.nodes) {
    const dtsProps: string[] = [];
    for (const prop of node.props ?? []) {
      if (!prop.dts) {
        continue;
      }
      const value = values[prop.key] ?? prop.default;
      if (value === prop.default) {
        continue;
      }
      if (prop.type === 'bool') {
        if (value) {
          dtsProps.push(`\t${prop.key};`);
        }
      } else if (prop.type === 'int') {
        dtsProps.push(`\t${prop.key} = <${value}>;`);
      } else if (prop.type === 'choice') {
        if (typeof value === 'number') {
          dtsProps.push(`\t${prop.key} = <${Math.trunc(value)}>;`);
        } else {
          dtsProps.push(`\t${prop.key} = "${String(value)}";`);
        }
      } else {
        dtsProps.push(`\t${prop.key} = "${String(value)}";`);
      }
    }

    if (dtsProps.length > 0) {
      overlayLines.push(`/* ${node.name} (${node.type}) */`);
      overlayLines.push('&clocks {');
      overlayLines.push(...dtsProps);
      overlayLines.push('};');
      overlayLines.push('');
    }
  }

  overlayLines.push('/*');
  overlayLines.push(' * Computed frequencies:');
  for (const node of tree.nodes) {
    const hz = frequencies[node.id] ?? 0;
    if (hz <= 0) {
      continue;
    }
    let label = `${hz} Hz`;
    if (hz >= 1_000_000) {
      label = `${(hz / 1_000_000).toFixed(2)} MHz`;
    } else if (hz >= 1_000) {
      label = `${(hz / 1_000).toFixed(2)} kHz`;
    }
    overlayLines.push(` *   ${node.name.padEnd(20, ' ')} = ${label}`);
  }
  overlayLines.push(' */');

  const kconfigLines = [
    '# --- Clock system configuration ---------------------------------',
    `# SoC: ${tree.soc}`,
    '# Generated by Zephyr Clock System Configurator',
    '',
    ...(tree.kconfig ?? []),
  ];

  for (const node of tree.nodes) {
    for (const prop of node.props ?? []) {
      if (!prop.kconfig) {
        continue;
      }
      const value = values[prop.key] ?? prop.default;
      if (prop.type === 'bool') {
        kconfigLines.push(`${prop.kconfig}=${value ? 'y' : 'n'}`);
      } else if (prop.type === 'int') {
        kconfigLines.push(`${prop.kconfig}=${value}`);
      } else {
        kconfigLines.push(`${prop.kconfig}="${String(value)}"`);
      }
    }
  }

  const publicFrequencies = Object.fromEntries(
    Object.entries(frequencies).filter(([key]) => !key.startsWith('_')),
  );
  return {
    overlay: overlayLines.join('\n'),
    prj_conf: kconfigLines.join('\n'),
    frequencies: publicFrequencies,
    warnings: analysis.warnings,
  };
}