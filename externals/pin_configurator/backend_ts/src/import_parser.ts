export interface ParsedPinAssignment {
  node_label: string;
  pincm: number;
  function_id: number;
  function_macro: string;
  peripheral: string;
  signal: string;
  pin_name: string;
  input_enable: boolean;
  bias_pull_up: boolean;
  bias_pull_down: boolean;
  drive_open_drain: boolean;
}

export interface ParsedPeripheral {
  dts_node: string;
  name: string;
  enabled: boolean;
  pinctrl_refs: string[];
  properties: Record<string, string>;
}

export interface ParsedKconfig {
  key: string;
  value: string;
}

export interface ImportResult {
  board_name: string;
  pins: ParsedPinAssignment[];
  peripherals: ParsedPeripheral[];
  kconfig: Array<{ key: string; value: string }>;
  warnings: string[];
}

const RE_PINMUX = /MSP_PINMUX\s*\(\s*(\d+)\s*,\s*(MSPM0_PIN_FUNCTION_(\d+)|\d+)\s*\)/i;
const RE_PINCM_PF = /<\s*PINCM(\d+)_PF_(\w+)\s*>/i;
const RE_PINCTRL_REFS = /pinctrl-0\s*=\s*<([^>]+)>/;
const RE_STATUS = /status\s*=\s*"(\w+)"/;
const RE_PROP_INT = /(\w[\w-]*)\s*=\s*<(\d+)>/g;
const RE_PROP_STR = /(\w[\w-]*)\s*=\s*"([^"]*)"/g;
const RE_KCONFIG = /^(CONFIG_\w+)\s*=\s*(.+?)\s*$/gm;
const RE_LABEL_PARTS = /^([a-z]+\d*)_([a-z0-9_]+?)_(p[ab]\d+)$/i;
const RE_LABEL_PARTS2 = /^([a-z]+\d*)_(p[ab]\d+)$/i;

function parseLabel(label: string): [string, string, string] {
  const primary = label.match(RE_LABEL_PARTS);
  if (primary) {
    return [primary[1].toLowerCase(), primary[2].toLowerCase(), primary[3].toUpperCase()];
  }
  const secondary = label.match(RE_LABEL_PARTS2);
  if (secondary) {
    return [secondary[1].toLowerCase(), '', secondary[2].toUpperCase()];
  }
  return ['', '', ''];
}

function extractBlocks(text: string, pattern: RegExp): Array<{ name: string; body: string }> {
  const blocks: Array<{ name: string; body: string }> = [];
  pattern.lastIndex = 0;

  while (true) {
    const match = pattern.exec(text);
    if (!match) {
      break;
    }

    const bodyStart = pattern.lastIndex;
    let depth = 1;
    let cursor = bodyStart;

    while (cursor < text.length && depth > 0) {
      const char = text[cursor];
      if (char === '{') {
        depth += 1;
      } else if (char === '}') {
        depth -= 1;
      }
      cursor += 1;
    }

    if (depth !== 0) {
      break;
    }

    blocks.push({
      name: match[1],
      body: text.slice(bodyStart, cursor - 1),
    });

    pattern.lastIndex = cursor;
  }

  return blocks;
}

function parsePinctrlBlock(body: string, pins: ParsedPinAssignment[], warnings: string[]): void {
  const nestedBlocks = extractBlocks(body, /(\w+)\s*(?::\s*\w+\s*)?\{/g);
  for (const block of nestedBlocks) {
    const label = block.name;
    const nodeBody = block.body;
    const childBlocks = extractBlocks(nodeBody, /(\w+)\s*(?::\s*\w+\s*)?\{/g);
    if (childBlocks.length > 0) {
      parsePinctrlBlock(nodeBody, pins, warnings);
      continue;
    }

    const pinmux = nodeBody.match(RE_PINMUX);
    const altPinmux = pinmux ? null : nodeBody.match(RE_PINCM_PF);

    let pincm = 0;
    let functionId = 0;
    let functionMacro = '';
    let peripheralOverride = '';
    let signalOverride = '';

    if (pinmux) {
      pincm = Number(pinmux[1]);
      functionMacro = pinmux[2];
      if (pinmux[3] !== undefined) {
        functionId = Number(pinmux[3]);
      } else {
        const parsed = Number(functionMacro);
        if (Number.isFinite(parsed)) {
          functionId = parsed;
          functionMacro = `MSPM0_PIN_FUNCTION_${functionId}`;
        } else {
          warnings.push(`Could not parse function in '${label}': ${functionMacro}`);
        }
      }
    } else if (altPinmux) {
      pincm = Number(altPinmux[1]);
      const pfName = altPinmux[2];
      functionId = -1;
      functionMacro = `PINCM${pincm}_PF_${pfName}`;
      const parts = pfName.split('_', 2);
      peripheralOverride = (parts[0] ?? '').toLowerCase();
      signalOverride = (parts[1] ?? '').toLowerCase();
    } else {
      warnings.push(`pinctrl node '${label}' has no pinmux macro -- skipped`);
      continue;
    }

    let [peripheral, signal, pinName] = parseLabel(label);
    if (altPinmux && !pinmux) {
      if (peripheralOverride) {
        peripheral = peripheralOverride;
      }
      if (signalOverride) {
        signal = signalOverride;
      }
    }

    pins.push({
      node_label: label,
      pincm,
      function_id: functionId,
      function_macro: functionMacro,
      peripheral,
      signal,
      pin_name: pinName,
      input_enable: /\binput-enable\b/.test(nodeBody),
      bias_pull_up: /\bbias-pull-up\b/.test(nodeBody),
      bias_pull_down: /\bbias-pull-down\b/.test(nodeBody),
      drive_open_drain: /\bdrive-open-drain\b/.test(nodeBody),
    });
  }
}

function parsePeripheralBlock(refName: string, body: string, peripherals: ParsedPeripheral[]): void {
  const status = body.match(RE_STATUS);
  const enabled = status ? status[1].toLowerCase() === 'okay' : true;
  const pinctrlRefsMatch = body.match(RE_PINCTRL_REFS);
  const pinctrlRefs = pinctrlRefsMatch
    ? pinctrlRefsMatch[1].split(/\s+/).map((value) => value.trim().replace(/^&/, '')).filter(Boolean)
    : [];

  const properties: Record<string, string> = {};
  for (const match of body.matchAll(RE_PROP_INT)) {
    const key = match[1];
    if (!['status', 'pinctrl-0', 'pinctrl-names'].includes(key)) {
      properties[key] = match[2];
    }
  }
  for (const match of body.matchAll(RE_PROP_STR)) {
    const key = match[1];
    if (!['status', 'pinctrl-names'].includes(key)) {
      properties[key] = match[2];
    }
  }

  peripherals.push({
    dts_node: `&${refName}`,
    name: refName,
    enabled,
    pinctrl_refs: pinctrlRefs,
    properties,
  });
}

function parseOverlay(text: string): { pins: ParsedPinAssignment[]; peripherals: ParsedPeripheral[]; warnings: string[] } {
  const pins: ParsedPinAssignment[] = [];
  const peripherals: ParsedPeripheral[] = [];
  const warnings: string[] = [];

  let clean = text.replace(/\/\*.*?\*\//gs, '');
  clean = clean.replace(/\/\/[^\n]*/g, '');

  for (const block of extractBlocks(clean, /&(\w+)\s*\{/g)) {
    const refName = block.name;
    const body = block.body;
    if (refName === 'pinctrl') {
      parsePinctrlBlock(body, pins, warnings);
    } else {
      parsePeripheralBlock(refName, body, peripherals);
    }
  }

  return { pins, peripherals, warnings };
}

function parseKconfig(text: string): ParsedKconfig[] {
  const results: ParsedKconfig[] = [];
  for (const match of text.matchAll(RE_KCONFIG)) {
    results.push({ key: match[1], value: match[2].trim() });
  }
  return results;
}

function dedupKconfig(entries: ParsedKconfig[]): Array<{ key: string; value: string }> {
  const seen = new Map<string, string>();
  const order: string[] = [];
  for (const entry of entries) {
    if (!seen.has(entry.key)) {
      order.push(entry.key);
    }
    seen.set(entry.key, entry.value);
  }
  return order.map((key) => ({ key, value: seen.get(key) ?? '' }));
}

export function parseImport(overlayText = '', confText = '', boardName = ''): ImportResult {
  let pins: ParsedPinAssignment[] = [];
  let peripherals: ParsedPeripheral[] = [];
  const warnings: string[] = [];

  if (overlayText.trim()) {
    const parsed = parseOverlay(overlayText);
    pins = parsed.pins;
    peripherals = parsed.peripherals;
    warnings.push(...parsed.warnings);
  }

  const kconfig = confText.trim() ? parseKconfig(confText) : [];
  return {
    board_name: boardName,
    pins,
    peripherals,
    kconfig: dedupKconfig(kconfig),
    warnings,
  };
}