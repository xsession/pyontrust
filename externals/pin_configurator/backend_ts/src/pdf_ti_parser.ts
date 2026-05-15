import { randomUUID } from 'node:crypto';
import { promises as fs } from 'node:fs';
import * as path from 'node:path';
import { buildParsedJobResult, saveParsedJob, type ParsedDatasheetInfoJson, type ParsedPackageInfoJson, type ParsedPackagePinJson, type ParsedPinMuxEntryJson } from './job_registry';
import { extractParsedClockInfo } from './pdf_clock_parser';
import { uploadArtifactDir } from './runtime_paths';

export interface TiPdfSnapshot {
  texts: string[];
  pincm_tables: string[][][];
  package_rows: Record<string, string[][]>;
}

const RE_GPIO_PIN = /^P([A-K])(\d{1,2})$/i;
const RE_TI_PIN = /^P([AB])(\d+)$/i;
const RE_FUNC_SPLIT = /([A-Za-z]+\d*)(?:_(.+))?/;
const VENDOR_PATTERNS: Array<[string, RegExp]> = [
  ['ti', /MSPM0[A-Z]\d{4}|MSP430\w+|TMS320\w+|CC[12][36]\d{2}\w*|AM[23]\d{2}\w*/i],
  ['st', /STM32[A-Z]\d{3}|STM8[SLA]/i],
  ['nxp', /LPC\d{3,4}|MIMXRT\d|MK[LEVW]\d|S32K|MCX[A-Z]\d/i],
  ['microchip', /PIC\d{2}|dsPIC|SAM[DLEVC]\d|AT(?:mega|tiny|SAM)|AVR\d/i],
  ['nordic', /nRF\d{4,5}/i],
  ['infineon', /PSoC\s*[46]|CY8C|XMC[14]\d{3}|TRAVEO/i],
  ['renesas', /R[57]F\w{5,}|RA\d[A-Z]\d|RX\d{3}|RL78/i],
  ['espressif', /ESP32[-]?[A-Z0-9]*/i],
];

function sanitizeFilename(filename: string): string {
  return filename.replace(/[^A-Za-z0-9._-]/g, '_');
}

function detectVendor(texts: string[]): string {
  const sample = texts.slice(0, 6).join('\n').toUpperCase();
  for (const [vendor, pattern] of VENDOR_PATTERNS) {
    if (pattern.test(sample)) return vendor;
  }
  const keywords: Record<string, string> = {
    st: 'STMICROELECTRONICS',
    nxp: 'NXP SEMICONDUCTORS',
    nordic: 'NORDIC SEMICONDUCTOR',
    microchip: 'MICROCHIP TECHNOLOGY',
    infineon: 'INFINEON TECHNOLOGIES',
    renesas: 'RENESAS ELECTRONICS',
    espressif: 'ESPRESSIF SYSTEMS',
    ti: 'TEXAS INSTRUMENTS',
  };
  for (const [vendor, keyword] of Object.entries(keywords)) {
    if (sample.includes(keyword)) return vendor;
  }
  return 'unknown';
}

function classify(name: string): string {
  const upper = name.toUpperCase().trim().replace(/\//g, '');
  if (upper.includes('VDD') || upper.includes('VCC') || upper.includes('VREF') || upper.includes('VBAT') || upper.includes('VBUS') || upper.includes('DECOUPLE')) return 'power';
  if (upper.includes('VSS') || upper.includes('GND') || upper.includes('AGND') || upper.includes('EPAD')) return 'ground';
  if (['NRST', 'RESET', 'RSTN', 'NC', 'DNC', 'RFU', 'SWDIO', 'SWCLK'].includes(upper)) return 'special';
  return RE_GPIO_PIN.test(upper) ? 'io' : 'special';
}

function portGpio(name: string): [string, number] {
  const match = RE_GPIO_PIN.exec(name.trim().toUpperCase());
  return match ? [match[1], Number(match[2])] : ['', -1];
}

function normPeriph(functionName: string): [string, string] {
  const value = functionName.trim();
  if (!value) return ['', ''];
  const match = RE_FUNC_SPLIT.exec(value);
  return match ? [match[1].toLowerCase(), (match[2] || '').toLowerCase()] : [value.toLowerCase(), ''];
}

function guessDir(functionName: string, signal: string): string {
  const fn = functionName.toUpperCase();
  const sig = signal.toUpperCase();
  if (/(RX|POCI|CTS|IDX|MISO)/.test(sig) || /(_RX|_POCI|_CTS|_IDX|_MISO)/.test(fn)) return 'in';
  if (/(TX|PICO|RTS|OUT|MOSI)/.test(sig) || /(_TX|_PICO|_RTS|_MOSI|COMP)/.test(fn)) return 'out';
  if (fn.includes('CCP') || fn.includes('PWM') || sig.includes('OC')) return 'out';
  if (/(SCL|SDA|SCK|CLK)/.test(sig)) return 'io';
  if (/(ADC|DAC|COMP|AIN|AOUT)/.test(fn)) return 'analog';
  return 'io';
}

function extractSummary(texts: string[], vendor: string): ParsedDatasheetInfoJson['device'] {
  const scan = texts.slice(0, 12).join('\n');
  const device = { soc: '', vendor, flash_size_kb: 0, sram_size_kb: 0, clock_hz: 0 };
  for (const [, pattern] of VENDOR_PATTERNS) {
    const match = pattern.exec(scan);
    if (match) {
      device.soc = match[0].toUpperCase();
      break;
    }
  }
  for (const pattern of [
    /(?:up\s+to\s+)?(\d+)\s*[-]?\s*(?:MB|Mbyte)\s+(?:of\s+)?(?:Flash|program|code)/i,
    /(?:up\s+to\s+)?(\d+)\s*[-]?\s*(?:KB|Kbyte|KiB)\s+(?:of\s+)?(?:Flash|program|code)/i,
    /Flash\s*(?:Memory|ROM)?[:\s]+(?:up\s+to\s+)?(\d+)\s*[-]?\s*(?:KB|MB)/i,
    /(\d+)\s*[-]?\s*(?:KB|Kbyte)\s+Flash/i,
  ]) {
    const match = pattern.exec(scan);
    if (match) {
      let value = Number(match[1]);
      if (/MB|MBYTE/i.test(match[0])) value *= 1024;
      device.flash_size_kb = value;
      break;
    }
  }
  for (const pattern of [
    /(\d+)\s*[-]?\s*(?:KB|Kbyte|KiB)\s+(?:of\s+)?(?:SRAM|RAM|data\s+memory)/i,
    /(?:SRAM|RAM)[:\s]+(?:up\s+to\s+)?(\d+)\s*[-]?\s*(?:KB|MB)/i,
    /(\d+)\s*[-]?\s*(?:MB|Mbyte)\s+(?:of\s+)?(?:SRAM|RAM)/i,
  ]) {
    const match = pattern.exec(scan);
    if (match) {
      let value = Number(match[1]);
      if (/MB|MBYTE/i.test(match[0]) && value < 32) value *= 1024;
      device.sram_size_kb = value;
      break;
    }
  }
  for (const pattern of [
    /(?:up\s+to\s+)?(\d+)\s*[-]?\s*MHz\s+(?:Arm|CPU|system|core|clock|frequency)/i,
    /(?:CPU|System|Core|Arm)\s*(?:Frequency|Speed|Clock)?[:\s]+(?:up\s+to\s+)?(\d+)\s*MHz/i,
    /(?:frequency|freq|clock)\s+(?:up\s+to\s+)(\d+)\s*MHz/i,
  ]) {
    const match = pattern.exec(scan);
    if (match) {
      device.clock_hz = Number(match[1]) * 1_000_000;
      break;
    }
  }
  if (!device.clock_hz) {
    const matches = [...scan.matchAll(/(\d+)\s*[-]?\s*MHz/gi)];
    const candidate = matches.map((match) => Number(match[1])).find((value) => value >= 16 && value <= 1200);
    if (candidate) device.clock_hz = candidate * 1_000_000;
  }
  return device;
}

function parsePincmTables(tables: string[][][]): Record<string, ParsedPinMuxEntryJson[]> {
  const result: Record<string, ParsedPinMuxEntryJson[]> = {};
  for (const table of tables) {
    if (table.length < 2) continue;
    const header = table[0].map((cell) => String(cell ?? '').trim());
    const headerUpper = header.map((cell) => cell.toUpperCase());
    let nameCol = -1;
    let pincmCol = -1;
    let functionCols: Array<[number, number]> = [];
    headerUpper.forEach((cell, index) => {
      if (nameCol < 0 && /PIN\s*NAME|SIGNAL\s*NAME|NAME/.test(cell)) nameCol = index;
      else if (cell.includes('PINCM')) pincmCol = index;
      else {
        const match = /FUNCTION\s*(\d+)|^F(\d+)$/.exec(cell);
        if (match) functionCols.push([index, Number(match[1] || match[2])]);
      }
    });
    if (nameCol < 0 || pincmCol < 0) continue;
    if (functionCols.length === 0) {
      const start = Math.max(nameCol, pincmCol) + 1;
      functionCols = header.map((_, index) => index).filter((index) => index >= start).map((index) => [index, index - start]);
    }
    for (const row of table.slice(1)) {
      if (row.length <= Math.max(nameCol, pincmCol)) continue;
      const pinName = String(row[nameCol] ?? '').trim().toUpperCase();
      const pincmRaw = String(row[pincmCol] ?? '').trim();
      if (!pinName || !RE_TI_PIN.test(pinName)) continue;
      const pincmDigits = pincmRaw.replace(/[^\d]/g, '');
      if (!pincmDigits) continue;
      const pincm = Number(pincmDigits);
      const [port, gpioNum] = portGpio(pinName);
      const gpioPeripheral = port ? `gpio${port.toLowerCase()}` : 'gpio';
      for (const [columnIndex, functionId] of functionCols) {
        if (columnIndex >= row.length) continue;
        const cell = String(row[columnIndex] ?? '').trim();
        if (!cell || ['—', '-', '–'].includes(cell)) continue;
        for (const fn of cell.split(/[\n,\/]/).map((value) => value.trim()).filter((value) => value && !['—', '-', '–'].includes(value))) {
          if (fn.toUpperCase().startsWith('GPIO')) {
            result[pinName] ??= [];
            result[pinName].push({ pin_name: pinName, pincm, function_id: functionId, function_name: `GPIO${port}${gpioNum}`, peripheral: gpioPeripheral, signal: String(gpioNum), direction: 'io' });
            continue;
          }
          const [peripheral, signal] = normPeriph(fn);
          result[pinName] ??= [];
          result[pinName].push({ pin_name: pinName, pincm, function_id: functionId, function_name: fn.toUpperCase().replace(/\./g, '_'), peripheral, signal, direction: guessDir(fn, signal) });
        }
      }
    }
  }
  return result;
}

function buildPackages(packageRows: Record<string, string[][]>): ParsedPackageInfoJson[] {
  return Object.entries(packageRows).map(([name, rows]) => {
    const countMatch = /(\d+)/.exec(name);
    const pins: ParsedPackagePinJson[] = rows.flatMap((row) => {
      if (row.length < 2) return [];
      const pinName = row[1].replace(/\s+/g, '').toUpperCase();
      const pinNumberDigits = row[0].replace(/[^\d]/g, '');
      if (!pinNumberDigits) return [];
      const [port, gpioNum] = portGpio(pinName);
      return [{ number: Number(pinNumberDigits), name: pinName, port, gpio_num: gpioNum, kind: classify(pinName) }];
    }).sort((left, right) => left.number - right.number);
    return { name, pin_count: countMatch ? Number(countMatch[1]) : pins.length, pins };
  }).sort((left, right) => left.pin_count - right.pin_count);
}

function textFallbackMux(texts: string[]): Record<string, ParsedPinMuxEntryJson[]> {
  const result: Record<string, ParsedPinMuxEntryJson[]> = {};
  const pattern = /(P[AB]\d+)\s+(\d+)\s+(.*)/i;
  let inTable = false;
  for (const text of texts) {
    for (const rawLine of text.split('\n')) {
      const line = rawLine.trim();
      if (/PINCM|Pin\s*Name.*Function/i.test(line)) {
        inTable = true;
        continue;
      }
      if (!inTable) continue;
      if (!line || /^(Table|Note|Copyright|\d+\s+of\s+\d+)/i.test(line)) {
        if (Object.keys(result).length > 0) inTable = false;
        continue;
      }
      const match = pattern.exec(line);
      if (!match) continue;
      const pinName = match[1].toUpperCase();
      const pincm = Number(match[2]);
      const [port, gpioNum] = portGpio(pinName);
      const gpioPeripheral = port ? `gpio${port.toLowerCase()}` : 'gpio';
      match[3].split(/\s{2,}|\t/).map((value, index) => [value.trim(), index] as const).forEach(([fn, functionId]) => {
        if (!fn || ['—', '-', '–', 'N/A'].includes(fn)) return;
        if (fn.toUpperCase().startsWith('GPIO')) {
          result[pinName] ??= [];
          result[pinName].push({ pin_name: pinName, pincm, function_id: functionId, function_name: `GPIO${port}${gpioNum}`, peripheral: gpioPeripheral, signal: String(gpioNum), direction: 'io' });
          return;
        }
        if (['ANALOG', 'ANA'].includes(fn.toUpperCase())) return;
        const [peripheral, signal] = normPeriph(fn);
        result[pinName] ??= [];
        result[pinName].push({ pin_name: pinName, pincm, function_id: functionId, function_name: fn.toUpperCase().replace(/\./g, '_'), peripheral, signal, direction: guessDir(fn, signal) });
      });
    }
  }
  return result;
}

export function parseTiSnapshot(snapshot: TiPdfSnapshot): ParsedDatasheetInfoJson | null {
  const vendor = detectVendor(snapshot.texts);
  if (vendor !== 'ti') return null;
  const pinMux = snapshot.pincm_tables.length > 0 ? parsePincmTables(snapshot.pincm_tables) : textFallbackMux(snapshot.texts);
  const packages = buildPackages(snapshot.package_rows);
  const device = extractSummary(snapshot.texts, 'ti');
  return {
    device,
    packages,
    pin_mux: pinMux,
    clock: extractParsedClockInfo(snapshot, device),
  };
}

export async function tryParseTiPdfNative(rootDir: string, uploadPath: string, filename: string, extractSnapshot: (uploadPath: string, filename: string) => Promise<TiPdfSnapshot | null>): Promise<{ job_id: string; filename: string; result: ReturnType<typeof buildParsedJobResult> } | null> {
  const snapshot = await extractSnapshot(uploadPath, filename);
  if (!snapshot) return null;
  const parsed = parseTiSnapshot(snapshot);
  if (!parsed || (!parsed.packages.length && Object.keys(parsed.pin_mux).length === 0)) return null;

  const jobId = randomUUID().replace(/-/g, '').slice(0, 12);
  const safeName = sanitizeFilename(filename);
  const finalPath = path.join(uploadArtifactDir(rootDir, 'mcu-jobs'), `${jobId}_${safeName}`);
  await fs.mkdir(path.dirname(finalPath), { recursive: true });
  await fs.rename(uploadPath, finalPath);

  const result = buildParsedJobResult(parsed);
  await saveParsedJob(rootDir, {
    job_id: jobId,
    filename: safeName,
    upload_path: finalPath,
    result,
    full_result: parsed,
  });

  return { job_id: jobId, filename: safeName, result };
}