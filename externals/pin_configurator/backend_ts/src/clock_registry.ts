import { promises as fs } from 'node:fs';
import * as path from 'node:path';

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
  dts?: boolean;
  kconfig?: string | null;
}

export interface ClockTreeNode {
  id: string;
  name: string;
  type: string;
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

export async function listClockTrees(rootDir: string): Promise<ClockTreeSummary[]> {
  return (await loadClockRegistry(rootDir)).summaries;
}

export async function getClockTree(rootDir: string, treeId: string): Promise<unknown | null> {
  return (await loadClockRegistry(rootDir)).byId[treeId] ?? null;
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

export function computeFrequencies(tree: ClockTree, values: Record<string, unknown>): Record<string, number> {
  if (tree.id === 'mspm0g3507') {
    return computeMspm0(values);
  }
  if (tree.id === 'stm32_generic') {
    return computeStm32(values);
  }
  if (tree.id === 'nrf52') {
    return computeNrf52(values);
  }

  const output: Record<string, number> = {};
  for (const node of tree.nodes) {
    output[node.id] = typeof node.freq_hz === 'number' ? node.freq_hz : 0;
  }
  return output;
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
} {
  const frequencies = computeFrequencies(tree, values);
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
  };
}