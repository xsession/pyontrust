import { randomUUID } from 'node:crypto';
import { promises as fs } from 'node:fs';
import * as path from 'node:path';
import { buildParsedJobResult, saveParsedJob, type ParsedDatasheetInfoJson, type ParsedPackageInfoJson, type ParsedPackagePinJson, type ParsedPinMuxEntryJson } from './job_registry';
import { extractParsedClockInfo } from './pdf_clock_parser';
import type { GenericPackagePageSnapshot, McuPdfSnapshot } from './python_jobs';
import { uploadArtifactDir } from './runtime_paths';

const RE_GPIO_PIN = /^P([A-K])(\d{1,2})$/i;
const RE_BGA_COORD = /^([A-Z])(\d+)$/;
const RE_FUNC_SPLIT = /([A-Za-z]+\d*)(?:_(.+))?/;
const RE_PKG_TYPE = /(LQFP|UFBGA|WLCSP|BGA|TFBGA|TSSOP|UFQFPN|QFN|QFP|TQFP|VFQFPN|HVQFN|MAPBGA|EWLCSP|SO|SOIC|SSOP|CSP|MLF|TFLGA|FBGA)\s*[-]?\s*(\d+)/i;
const STM32_LIKE_VENDORS = new Set(['st', 'gigadevice', 'artery', 'puya', 'mindmotion']);
const VENDOR_PATTERNS: Array<[string, RegExp]> = [
  ['ti', /MSPM0[A-Z]\d|MSP430|TMS320|CC[12][36]\d{2}|AM[23]\d{2}/i],
  ['st', /STM32[A-Z]\d{3}|STM8[SLA]/i],
  ['nxp', /LPC\d{3,4}|MIMXRT\d|MK[LEVW]\d|S32K|MCX[A-Z]\d/i],
  ['microchip', /PIC\d{2}|dsPIC|SAM[DLEVC]\d|AT(?:mega|tiny|SAM)|AVR\d/i],
  ['nordic', /nRF\d{4,5}/i],
  ['infineon', /PSoC\s*[46]|CY8C|XMC[14]\d{3}|TRAVEO/i],
  ['renesas', /R[57]F\w{5,}|RA\d[A-Z]\d|RX\d{3}|RL78/i],
  ['espressif', /ESP32[-]?[A-Z0-9]*/i],
  ['silabs', /EF[MR]32[A-Z]{2}\d|BGM\d|MGM\d/i],
  ['gigadevice', /GD32[A-Z]\d{3}/i],
  ['wch', /CH32[VX]\d{3}|CH5[78]\d/i],
  ['nuvoton', /M\d{3}[A-Z]|NUC\d{3}/i],
  ['bouffalo', /BL[6-8]\d{2}/i],
  ['hpmicro', /HPM\d{4}/i],
  ['puya', /PY32[A-Z]\d/i],
  ['artery', /AT32[A-Z]\d{3}/i],
  ['mindmotion', /MM32[A-Z]/i],
];

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
  if (['NRST', 'RESET', 'RSTN', '/RESET', 'XIN', 'XOUT', 'XIN32', 'XOUT32', 'SWDIO', 'SWCLK', 'SWDCLK', 'SWO', 'JTMS', 'JTCK', 'JTDI', 'JTDO', 'NJTRST', 'BOOT0', 'PDR_ON', 'BYPASS_REG', 'TEST', 'TCK', 'TMS', 'TDI', 'TDO', 'OSC_IN', 'OSC_OUT', 'OSC32_IN', 'OSC32_OUT', 'NC', 'DNC', 'N/C', 'RFU'].includes(upper)) return 'special';
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

function parseGenericPinmuxTables(tables: string[][][] = []): Record<string, ParsedPinMuxEntryJson[]> {
  const result: Record<string, ParsedPinMuxEntryJson[]> = {};

  for (const table of tables) {
    if (!table || table.length < 3) continue;
    const header = table[0].map((cell) => String(cell ?? '').trim());
    const headerUpper = header.map((cell) => cell.toUpperCase());
    let pinCol = -1;
    const functionCols: Array<[number, string]> = [];

    headerUpper.forEach((cell, index) => {
      if (pinCol < 0 && /PIN\s*NAME|GPIO|PORT\s*PIN|PAD\s*NAME|BALL\s*NAME|IO\s*NAME/.test(cell)) {
        pinCol = index;
      } else if (/AF\d+|ALT\s*\d|FUNC|MUX|PERIPH|SIGNAL|ALTERNATE/.test(cell)) {
        functionCols.push([index, cell]);
      }
    });

    if (pinCol < 0 || functionCols.length === 0) continue;

    for (const row of table.slice(1)) {
      if (!row || row.length <= pinCol) continue;
      const rawPin = String(row[pinCol] ?? '').trim().toUpperCase();
      if (!rawPin) continue;
      const pinMatch = /(P[A-K]\d+|GPIO_?\d+|IO\d+)/i.exec(rawPin);
      if (!pinMatch) continue;

      const pinName = pinMatch[1].toUpperCase();
      const [port, gpioNum] = portGpio(pinName);

      for (const [columnIndex, columnName] of functionCols) {
        if (columnIndex >= row.length) continue;
        const cell = String(row[columnIndex] ?? '').trim();
        if (!cell || ['—', '-', '–', 'Reserved'].includes(cell)) continue;
        const afMatch = /AF(\d+)|ALT\s*(\d+)/i.exec(columnName);
        const af = afMatch ? Number(afMatch[1] || afMatch[2]) : -1;

        for (const fn of cell.split(/[,\n/;]/).map((value) => value.trim()).filter((value) => value && !['—', '-', '–'].includes(value))) {
          const [peripheral, signal] = normPeriph(fn);
          result[pinName] ??= [];
          result[pinName].push({
            pin_name: pinName,
            pincm: af,
            function_id: af,
            function_name: fn.toUpperCase().replace(/\./g, '_'),
            peripheral,
            signal,
            direction: guessDir(fn, signal),
          });
        }

        if (port && gpioNum >= 0 && !result[pinName]?.some((entry) => entry.function_name === `GPIO${port}${gpioNum}`)) {
          result[pinName] ??= [];
          result[pinName].push({
            pin_name: pinName,
            pincm: -1,
            function_id: -1,
            function_name: `GPIO${port}${gpioNum}`,
            peripheral: `gpio${port.toLowerCase()}`,
            signal: String(gpioNum),
            direction: 'io',
          });
        }
      }
    }
  }

  return result;
}

function parseGenericPackages(pages: GenericPackagePageSnapshot[] = []): ParsedPackageInfoJson[] {
  const raw: Record<string, ParsedPackagePinJson[]> = {};

  for (const page of pages) {
    const pkgMatch = RE_PKG_TYPE.exec(page.text || '');
    const pkgName = pkgMatch ? `${pkgMatch[1].toUpperCase()}${pkgMatch[2]}` : 'PKG';

    for (const table of page.tables ?? []) {
      if (!table || table.length < 2) continue;
      const header = table[0].map((cell) => String(cell ?? '').trim());
      const headerUpper = header.map((cell) => cell.toUpperCase());
      let pinCol = -1;
      let nameCol = -1;

      headerUpper.forEach((cell, index) => {
        if (pinCol < 0 && /PIN\s*(NO|NUM|#)|^#$|BALL/.test(cell)) pinCol = index;
        if (nameCol < 0 && /PIN\s*NAME|SIGNAL|NAME|GPIO|PAD|FUNCTION/.test(cell)) nameCol = index;
      });

      if (pinCol < 0 || nameCol < 0 || pinCol === nameCol) continue;

      for (const row of table.slice(1)) {
        if (!row || row.length <= Math.max(pinCol, nameCol)) continue;
        const pinValue = String(row[pinCol] ?? '').trim();
        const nameValue = String(row[nameCol] ?? '').trim().toUpperCase();
        if (!pinValue || !nameValue) continue;

        let pinNumber = 0;
        const bgaMatch = RE_BGA_COORD.exec(pinValue.toUpperCase());
        if (bgaMatch) pinNumber = (bgaMatch[1].charCodeAt(0) - 64) * 100 + Number(bgaMatch[2]);
        else {
          const digits = pinValue.replace(/[^\d]/g, '');
          if (!digits) continue;
          pinNumber = Number(digits);
        }

        const [port, gpioNum] = portGpio(nameValue);
        raw[pkgName] ??= [];
        raw[pkgName].push({ number: pinNumber, name: nameValue, port, gpio_num: gpioNum, kind: classify(nameValue) });
      }
    }
  }

  return Object.entries(raw).map(([name, pins]) => {
    const unique = [...new Map(pins.sort((left, right) => left.number - right.number).map((pin) => [pin.number, pin])).values()];
    const countMatch = /(\d+)/.exec(name);
    return {
      name,
      pin_count: countMatch ? Number(countMatch[1]) : unique.length,
      pins: unique,
    };
  }).sort((left, right) => left.pin_count - right.pin_count);
}

export function parseGenericSnapshot(snapshot: McuPdfSnapshot): ParsedDatasheetInfoJson | null {
  const vendor = snapshot.vendor || detectVendor(snapshot.texts);
  if (vendor === 'ti' || STM32_LIKE_VENDORS.has(vendor)) return null;

  const pinMux = parseGenericPinmuxTables(snapshot.generic_pinmux_tables);
  const packages = parseGenericPackages(snapshot.generic_package_pages);
  if (Object.keys(pinMux).length === 0 && packages.length === 0) return null;

  const device = extractSummary(snapshot.texts, vendor);

  return {
    device,
    packages,
    pin_mux: pinMux,
    clock: extractParsedClockInfo(snapshot, device),
  };
}

export async function tryParseGenericPdfNative(rootDir: string, uploadPath: string, filename: string, extractSnapshot: (uploadPath: string, filename: string) => Promise<McuPdfSnapshot | null>): Promise<{ job_id: string; filename: string; result: ReturnType<typeof buildParsedJobResult> } | null> {
  const snapshot = await extractSnapshot(uploadPath, filename);
  if (!snapshot) return null;
  const parsed = parseGenericSnapshot(snapshot);
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