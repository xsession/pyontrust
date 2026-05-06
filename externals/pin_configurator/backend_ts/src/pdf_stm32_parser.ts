import { randomUUID } from 'node:crypto';
import { promises as fs } from 'node:fs';
import * as path from 'node:path';
import { buildParsedJobResult, saveParsedJob, type ParsedDatasheetInfoJson, type ParsedPackageInfoJson, type ParsedPackagePinJson, type ParsedPinMuxEntryJson } from './job_registry';
import { uploadArtifactDir } from './runtime_paths';

export interface Stm32PdfSnapshot {
  texts: string[];
  vendor?: string;
  stm32_af_tables: string[][][];
  stm32_pindef_tables: string[][][];
}

const RE_GPIO_PIN = /^P([A-K])(\d{1,2})$/i;
const RE_BGA_COORD = /^([A-Z])(\d+)$/;
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

const PKG_DECODE: Record<string, string> = {
  LQFP: 'LQFP', PFQL: 'LQFP',
  UFBGA: 'UFBGA', AGBFU: 'UFBGA',
  WLCSP: 'WLCSP', PSCLW: 'WLCSP',
  QFN: 'QFN', NFQ: 'QFN',
  TSSOP: 'TSSOP', POSST: 'TSSOP',
  UFQFPN: 'UFQFPN', NPFQFU: 'UFQFPN',
  TQFP: 'TQFP', PFQT: 'TQFP',
  VFQFPN: 'VFQFPN', NPFQFV: 'VFQFPN',
  HVQFN: 'HVQFN', NFQVH: 'HVQFN',
  BGA: 'BGA', AGB: 'BGA',
};

function sanitizeFilename(filename: string): string {
  return filename.replace(/[^A-Za-z0-9._-]/g, '_');
}

function detectVendor(texts: string[]): string {
  const sample = texts.slice(0, 6).join('\n').toUpperCase();
  for (const [vendor, pattern] of VENDOR_PATTERNS) {
    if (pattern.test(sample)) return vendor;
  }
  return 'unknown';
}

function classify(name: string): string {
  const upper = name.toUpperCase().trim().replace(/\//g, '');
  if (upper.includes('VDD') || upper.includes('VCC') || upper.includes('VREF') || upper.includes('VBAT') || upper.includes('VBUS') || upper.includes('DECOUPLE')) return 'power';
  if (upper.includes('VSS') || upper.includes('GND') || upper.includes('AGND') || upper.includes('EPAD')) return 'ground';
  if (['NRST', 'RESET', 'RSTN', 'NC', 'DNC', 'RFU', 'SWDIO', 'SWCLK', 'BOOT0'].includes(upper)) return 'special';
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
    const candidate = [...scan.matchAll(/(\d+)\s*[-]?\s*MHz/gi)].map((match) => Number(match[1])).find((value) => value >= 16 && value <= 1200);
    if (candidate) device.clock_hz = candidate * 1_000_000;
  }
  return device;
}

function parseAfTables(tables: string[][][]): Record<string, ParsedPinMuxEntryJson[]> {
  const result: Record<string, ParsedPinMuxEntryJson[]> = {};
  for (const table of tables) {
    if (table.length < 3) continue;
    const header = table[0].map((cell) => String(cell ?? '').trim());
    const afMap = header.flatMap((cell, index) => {
      const match = /^AF(\d+)$/i.exec(cell);
      return match ? [[index, Number(match[1])] as [number, number]] : [];
    });
    if (afMap.length === 0) continue;
    for (const row of table.slice(2)) {
      const rawPin = String(row[1] ?? '').trim().toUpperCase();
      if (!rawPin || !RE_GPIO_PIN.test(rawPin)) continue;
      const [port, gpioNum] = portGpio(rawPin);
      for (const [columnIndex, af] of afMap) {
        const cell = String(row[columnIndex] ?? '').trim();
        if (!cell || ['—', '-', '–'].includes(cell)) continue;
        for (const fn of cell.split(/[\/\n]/).map((value) => value.trim()).filter((value) => value && !['—', '-', '–'].includes(value))) {
          const [peripheral, signal] = normPeriph(fn);
          result[rawPin] ??= [];
          result[rawPin].push({ pin_name: rawPin, pincm: af, function_id: af, function_name: fn.toUpperCase().replace(/\./g, '_'), peripheral, signal, direction: guessDir(fn, signal) });
        }
      }
      result[rawPin] ??= [];
      result[rawPin].push({ pin_name: rawPin, pincm: -1, function_id: -1, function_name: `GPIO${port}${gpioNum}`, peripheral: `gpio${port.toLowerCase()}`, signal: String(gpioNum), direction: 'io' });
    }
  }
  return result;
}

function parsePinDefTables(tables: string[][][]): { packages: ParsedPackageInfoJson[]; extraMux: Record<string, ParsedPinMuxEntryJson[]> } {
  const pkgPins: Record<string, ParsedPackagePinJson[]> = {};
  const extraMux: Record<string, ParsedPinMuxEntryJson[]> = {};

  for (const table of tables) {
    if (table.length < 3) continue;
    const header = table[0].map((cell) => String(cell ?? '').trim());
    const sub = table[1].map((cell) => String(cell ?? '').trim());
    let nameCol = -1;
    let altCol = -1;
    for (let index = 0; index < header.length; index += 1) {
      if (header[index] && /Pin\s*name/i.test(header[index])) nameCol = index;
    }
    for (let index = 0; index < sub.length; index += 1) {
      const value = sub[index].toUpperCase();
      if (value.includes('ALTERNATE')) altCol = index;
    }
    if (nameCol < 0 && header.length >= 18) {
      nameCol = 12;
      altCol = 16;
    }
    if (nameCol < 0) continue;

    const pkgCols: Record<string, number> = {};
    for (let index = 0; index < sub.length && index < nameCol; index += 1) {
      const value = sub[index];
      if (!value) continue;
      const normalized = value.toUpperCase().replace(/[_\-\s]/g, '');
      if (normalized.startsWith('SPMS')) continue;
      for (const [key, real] of Object.entries(PKG_DECODE)) {
        if (!normalized.includes(key)) continue;
        const nums = normalized.match(/\d+/g);
        const label = nums && nums.length > 0 ? `${real}${Number(nums[0].split('').reverse().join(''))}` : real;
        if (!(label in pkgCols)) pkgCols[label] = index;
        break;
      }
    }

    for (const row of table.slice(2)) {
      const raw = String(row[nameCol] ?? '').trim();
      if (!raw) continue;
      const clean = raw.replace(/\s+/g, ' ');
      const pinMatch = /(P[A-I]\d+)/i.exec(clean);
      const pinName = pinMatch ? pinMatch[1].toUpperCase() : clean.replace(/\(.*?\)/g, '').split(' ')[0].toUpperCase().replace(/-+$/, '');
      const kind = classify(pinName);
      const [port, gpioNum] = portGpio(pinName);

      for (const [pkg, columnIndex] of Object.entries(pkgCols)) {
        const cell = String(row[columnIndex] ?? '').trim();
        if (!cell || ['-', '–'].includes(cell)) continue;
        let pinNumber = 0;
        const bgaMatch = RE_BGA_COORD.exec(cell.toUpperCase());
        if (bgaMatch) pinNumber = (bgaMatch[1].charCodeAt(0) - 64) * 100 + Number(bgaMatch[2]);
        else {
          const digits = cell.replace(/[^\d]/g, '');
          if (!digits) continue;
          pinNumber = Number(digits);
        }
        if (pinNumber > 0) {
          pkgPins[pkg] ??= [];
          pkgPins[pkg].push({ number: pinNumber, name: pinName, port, gpio_num: gpioNum, kind });
        }
      }

      if (altCol >= 0 && altCol < row.length) {
        const altText = String(row[altCol] ?? '').trim();
        if (altText && !['-', '–', '—'].includes(altText)) {
          for (const fn of altText.split(/[\n,]/).map((value) => value.trim().replace(/\s+/g, '_')).filter((value) => value && !['-', '–', '—'].includes(value))) {
            const [peripheral, signal] = normPeriph(fn);
            extraMux[pinName] ??= [];
            extraMux[pinName].push({ pin_name: pinName, pincm: -1, function_id: -1, function_name: fn.toUpperCase(), peripheral, signal, direction: guessDir(fn, signal) });
          }
        }
      }
    }
  }

  const packages = Object.entries(pkgPins).map(([name, pins]) => {
    const unique = [...new Map(pins.sort((left, right) => left.number - right.number).map((pin) => [pin.number, pin])).values()];
    const countMatch = /(\d+)/.exec(name);
    return { name, pin_count: countMatch ? Number(countMatch[1]) : unique.length, pins: unique };
  }).sort((left, right) => left.pin_count - right.pin_count);
  return { packages, extraMux };
}

export function parseStm32Snapshot(snapshot: Stm32PdfSnapshot): ParsedDatasheetInfoJson | null {
  const vendor = snapshot.vendor || detectVendor(snapshot.texts);
  if (!['st', 'gigadevice', 'artery', 'puya', 'mindmotion'].includes(vendor)) return null;

  const pinMux = parseAfTables(snapshot.stm32_af_tables);
  const { packages, extraMux } = parsePinDefTables(snapshot.stm32_pindef_tables);
  for (const [pinName, entries] of Object.entries(extraMux)) {
    const existing = new Set((pinMux[pinName] ?? []).map((entry) => entry.function_name));
    for (const entry of entries) {
      if (existing.has(entry.function_name)) continue;
      pinMux[pinName] ??= [];
      pinMux[pinName].push(entry);
    }
  }

  if (Object.keys(pinMux).length === 0 && packages.length === 0) return null;
  return {
    device: extractSummary(snapshot.texts, vendor),
    packages,
    pin_mux: pinMux,
  };
}

export async function tryParseStm32PdfNative(rootDir: string, uploadPath: string, filename: string, extractSnapshot: (uploadPath: string, filename: string) => Promise<Stm32PdfSnapshot | null>): Promise<{ job_id: string; filename: string; result: ReturnType<typeof buildParsedJobResult> } | null> {
  const snapshot = await extractSnapshot(uploadPath, filename);
  if (!snapshot) return null;
  const parsed = parseStm32Snapshot(snapshot);
  if (!parsed) return null;

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