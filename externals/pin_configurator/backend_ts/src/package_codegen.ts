import { spawn } from 'node:child_process';
import { promises as fs } from 'node:fs';
import * as path from 'node:path';
import type { ParsedDatasheetInfoJson, ParsedPackageInfoJson, ParsedPackagePinJson, ParsedPinMuxEntryJson } from './job_registry';

export interface ExternalDeviceSpec {
  id: string;
  display?: string;
  category?: string;
  bus?: string;
  compatible?: string;
  address?: string;
  required_signals?: string[];
  frameworks?: string[];
  notes?: string;
}

const TI_PERIPH_MAP: Record<string, [string, string, string]> = {
  gpioa: ['ti,mspm0-gpio', '0x400a0000', '&gpioa'],
  gpiob: ['ti,mspm0-gpio', '0x400a2000', '&gpiob'],
  uart0: ['ti,mspm0-uart', '0x40108000', '&uart0'],
  uart1: ['ti,mspm0-uart', '0x40100000', '&uart1'],
  uart2: ['ti,mspm0-uart', '0x40102000', '&uart2'],
  uart3: ['ti,mspm0-uart', '0x40500000', '&uart3'],
  spi0: ['ti,mspm0-spi', '', '&spi0'],
  spi1: ['ti,mspm0-spi', '', '&spi1'],
  i2c0: ['ti,mspm0-i2c', '', '&i2c0'],
  i2c1: ['ti,mspm0-i2c', '', '&i2c1'],
  can0: ['ti,mspm0-can', '', '&can0'],
  tima0: ['ti,mspm0-timer-pwm', '0x40860000', '&tima0'],
  tima1: ['ti,mspm0-timer-pwm', '0x40862000', '&tima1'],
  timg0: ['ti,mspm0-timer', '0x40084000', '&timg0'],
  timg6: ['ti,mspm0-timer', '0x40868000', '&timg6'],
  timg7: ['ti,mspm0-timer', '0x4086a000', '&timg7'],
  timg8: ['ti,mspm0-timer', '0x40090000', '&timg8'],
  timg12: ['ti,mspm0-timer', '0x40870000', '&timg12'],
  adc0: ['ti,mspm0-adc', '', '&adc0'],
  dac0: ['ti,mspm0-dac', '', '&dac0'],
  comp0: ['ti,mspm0-comp', '', '&comp0'],
  comp1: ['ti,mspm0-comp', '', '&comp1'],
};

const PERIPH_DISPLAY: Record<string, string> = {
  gpioa: 'GPIO A', gpiob: 'GPIO B',
  uart0: 'UART 0', uart1: 'UART 1', uart2: 'UART 2', uart3: 'UART 3',
  spi0: 'SPI 0', spi1: 'SPI 1',
  i2c0: 'I2C 0', i2c1: 'I2C 1',
  can0: 'CAN 0',
  tima0: 'Timer A0 (PWM)', tima1: 'Timer A1 (PWM)',
  timg0: 'Timer G0', timg6: 'Timer G6', timg7: 'Timer G7', timg8: 'Timer G8', timg12: 'Timer G12',
  adc0: 'ADC 0', dac0: 'DAC 0', comp0: 'Comp 0', comp1: 'Comp 1',
};

const PERIPH_SIGNALS: Record<string, string[]> = {
  gpioa: [], gpiob: [],
  uart0: ['tx', 'rx'], uart1: ['tx', 'rx'], uart2: ['tx', 'rx'], uart3: ['tx', 'rx'],
  spi0: ['sclk', 'pico', 'poci', 'cs0'], spi1: ['sclk', 'pico', 'poci', 'cs0'],
  i2c0: ['scl', 'sda'], i2c1: ['scl', 'sda'], can0: ['tx', 'rx'],
};

function assignSide(pinCount: number, pinNum: number): 'left' | 'bottom' | 'right' | 'top' {
  const quarter = Math.floor(pinCount / 4);
  if (pinNum <= quarter) return 'left';
  if (pinNum <= 2 * quarter) return 'bottom';
  if (pinNum <= 3 * quarter) return 'right';
  return 'top';
}

function formatAltFunction(entry: ParsedPinMuxEntryJson): string {
  if (entry.function_name.toUpperCase().startsWith('GPIO') && entry.function_id === 1) {
    const port = entry.peripheral.replace('gpio', '').toUpperCase();
    return `_GPIO("${port}", ${entry.signal})`;
  }
  if (entry.direction === 'analog') {
    return `_ANA("${entry.function_name}", "${entry.peripheral}", "${entry.signal}")`;
  }
  return `_AF(${entry.function_id}, "${entry.function_name}", "${entry.peripheral}", "${entry.signal}", "${entry.direction}")`;
}

function genPinCall(pin: ParsedPackagePinJson, muxEntries: ParsedPinMuxEntryJson[], pincm: number, sideVar: string): string {
  const kind = pin.kind ?? 'io';
  if (kind === 'power') return `        _pwr(${pin.number}, "${pin.name}", ${sideVar}),`;
  if (kind === 'ground') return `        _gnd(${pin.number}, "${pin.name}", ${sideVar}),`;
  if (kind === 'special') return `        _spec(${pin.number}, "${pin.name}", ${sideVar}, "${pin.name}"),`;

  const altLines = muxEntries.map((entry) => `            ${formatAltFunction(entry)}`);
  const altsBlock = altLines.length > 0 ? `[
${altLines.join(',\n')},
        ]` : '[]';
  return `        _io(${pin.number}, "${pin.name}", "${pin.port ?? ''}", ${Number(pin.gpio_num ?? -1)}, ${sideVar}, ${pincm}, ${altsBlock}),`;
}

function collectPeripherals(pinMux: Record<string, ParsedPinMuxEntryJson[]>): string[] {
  const seen = new Set<string>();
  for (const entries of Object.values(pinMux)) {
    for (const entry of entries) {
      if (entry.peripheral) {
        seen.add(entry.peripheral);
      }
    }
  }
  const ordered = ['gpioa', 'gpiob', 'uart0', 'uart1', 'uart2', 'uart3', 'spi0', 'spi1', 'i2c0', 'i2c1', 'can0'];
  const timers = [...seen].filter((value) => value.startsWith('tim')).sort((left, right) => left.localeCompare(right, undefined, { numeric: true }));
  const analogs = [...seen].filter((value) => /^(adc|dac|comp)/.test(value)).sort();
  const result: string[] = [];
  for (const id of ordered) {
    if (seen.has(id)) result.push(id);
  }
  for (const id of [...timers, ...analogs, ...[...seen].sort()]) {
    if (!result.includes(id)) result.push(id);
  }
  return result;
}

function genPeripheralLine(periphId: string, pinMux: Record<string, ParsedPinMuxEntryJson[]>): string {
  const [compat, addr, dtsNode] = TI_PERIPH_MAP[periphId] ?? [`ti,mspm0-${periphId.replace(/[0-9]+$/, '')}`, '', `&${periphId}`];
  const display = PERIPH_DISPLAY[periphId] ?? periphId.toUpperCase();
  const signals = PERIPH_SIGNALS[periphId] ?? [...new Set(Object.values(pinMux).flat().filter((entry) => entry.peripheral === periphId && entry.signal).map((entry) => entry.signal))].sort();
  return `        Peripheral("${periphId}", "${display}", "${compat}", [${signals.map((signal) => `"${signal}"`).join(', ')}], "${addr}", "${dtsNode}"),`;
}

function genExternalDeviceLine(device: ExternalDeviceSpec): string {
  const requiredSignals = JSON.stringify((device.required_signals ?? []).map((signal) => String(signal)));
  const frameworks = JSON.stringify((device.frameworks ?? []).map((framework) => String(framework)));
  return `        ExternalDevice(id=${JSON.stringify(String(device.id))}, display=${JSON.stringify(String(device.display ?? device.id))}, category=${JSON.stringify(String(device.category ?? 'device'))}, bus=${JSON.stringify(String(device.bus ?? ''))}, compatible=${JSON.stringify(String(device.compatible ?? ''))}, address=${JSON.stringify(String(device.address ?? ''))}, required_signals=${requiredSignals}, frameworks=${frameworks}, notes=${JSON.stringify(String(device.notes ?? ''))}),`;
}

function formatClock(value: number): string {
  const digits = String(Math.trunc(value || 0));
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, '_');
}

function packageLabel(name: string): string {
  return name.replace(/-/g, '').toLowerCase();
}

function buildBoardKey(socLower: string, pkg: ParsedPackageInfoJson, packageCount: number): string {
  return packageCount > 1 ? `${socLower}_${packageLabel(pkg.name)}` : socLower;
}

export function generateBoardFileSource(
  info: ParsedDatasheetInfoJson,
  pkg: ParsedPackageInfoJson,
  options: { boardName?: string; dtsSocInclude?: string; dtsPinctrlInclude?: string; pinctrlHeader?: string; externalDevices?: ExternalDeviceSpec[] } = {},
): string {
  const soc = info.device.soc.toUpperCase();
  const socLower = soc.toLowerCase();
  const pkgLabel = packageLabel(pkg.name);
  const boardName = options.boardName || `lp_${socLower}`;
  const funcName = `build_${socLower}_${pkgLabel}`;
  const quarter = Math.floor(pkg.pin_count / 4);
  const familyLetter = soc.length > 5 ? soc[5].toLowerCase() : 'g';
  const dtsSocInclude = options.dtsSocInclude ? `"${options.dtsSocInclude}"` : `"<ti/mspm0/${familyLetter}/${socLower}.dtsi>"`;
  const dtsPinctrlInclude = options.dtsPinctrlInclude ? `"${options.dtsPinctrlInclude}"` : '""';
  const pinctrlHeader = options.pinctrlHeader || 'mspm0-pinctrl.h';
  const sideMap = { left: 'L', bottom: 'B', right: 'R', top: 'T' } as const;
  const sideComments = { left: 'LEFT SIDE', bottom: 'BOTTOM SIDE', right: 'RIGHT SIDE', top: 'TOP SIDE' } as const;
  const pkgPinNames = new Set(pkg.pins.map((pin) => pin.name));
  const pkgMux = Object.fromEntries(Object.entries(info.pin_mux).filter(([pinName]) => pkgPinNames.has(pinName)));

  const pinLines: string[] = [];
  let currentSide = '';
  for (const pin of pkg.pins) {
    const side = assignSide(pkg.pin_count, pin.number);
    if (side !== currentSide) {
      const sideIndex = ['left', 'bottom', 'right', 'top'].indexOf(side);
      const start = sideIndex * quarter + 1;
      const end = side === 'top' ? pkg.pin_count : start + quarter - 1;
      pinLines.push('');
      pinLines.push(`        # === ${sideComments[side]} (pins ${start}-${end}) ===`);
      currentSide = side;
    }
    const entries = pkgMux[pin.name] ?? [];
    const pincm = entries[0]?.pincm ?? 0;
    pinLines.push(genPinCall(pin, entries, pincm, sideMap[side]));
  }

  const periphLines = collectPeripherals(pkgMux).map((periphId) => genPeripheralLine(periphId, pkgMux));
  const externalDeviceLines = (options.externalDevices ?? []).map((device) => genExternalDeviceLine(device));
  return `"""
${soc} - ${pkg.pin_count}-pin ${pkg.name.split('-')[0]} board definition for the Zephyr Pin Configurator.

Pin-mux data derived from the ${soc} datasheet (PINCM table) and the
Zephyr \`\`mspm0-pinctrl.h\`\` header: MSP_PINMUX(pincm, function).

*** AUTO-GENERATED by package_generator - do not edit by hand. ***
"""

from board_schema import (
  BoardDef, Pin, AltFunction, Peripheral, ExternalDevice,
    PinKind, PinSide,
)


def _io(number, name, port, gpio, side, pincm, alts, default="Reset"):
    """Shorthand for an I/O pin with alt-functions."""
    return Pin(
        number=number,
        name=name,
        port=port,
        gpio_num=gpio,
        kind=PinKind.IO,
        side=side,
        default_function=default,
        alt_functions=[
            AltFunction(
                function_id=fid,
                pincm=pincm,
                name=n,
                peripheral=per,
                signal=sig,
                direction=d,
            )
            for fid, n, per, sig, d in alts
        ],
    )


def _pwr(number, name, side):
    return Pin(number=number, name=name, kind=PinKind.PWR, side=side)


def _gnd(number, name, side):
    return Pin(number=number, name=name, kind=PinKind.GND, side=side)


def _spec(number, name, side, default=""):
    return Pin(number=number, name=name, kind=PinKind.SPEC, side=side,
               default_function=default or name)


_AF = lambda fid, label, periph, sig, d="io": (fid, label, periph, sig, d)
_GPIO = lambda port, bit: _AF(1, f"GPIO{port}{bit}", f"gpio{port.lower()}", f"{bit}", "io")
_ANA  = lambda label, periph, sig: _AF(0, label, periph, sig, "analog")


def ${funcName}() -> BoardDef:
    """
    Return the full ${soc} ${pkg.name} board definition.

    Pin numbering follows the ${pkg.name} package:
      Left   (top->bottom): pins 1-${quarter}
      Bottom (left->right): pins ${quarter + 1}-${2 * quarter}
      Right  (bottom->top): pins ${2 * quarter + 1}-${3 * quarter}
      Top    (right->left): pins ${3 * quarter + 1}-${pkg.pin_count}
    """
    L, B, R, T = PinSide.LEFT, PinSide.BOTTOM, PinSide.RIGHT, PinSide.TOP

    pins: list[Pin] = [
${pinLines.join('\n')}
    ]

    peripherals = [
${periphLines.join('\n')}
    ]

    external_devices = [
  ${externalDeviceLines.join('\n')}
    ]

    return BoardDef(
        soc="${soc}",
        board="${boardName}",
        vendor="${info.device.vendor}",
        package="${pkg.name}",
        pin_count=${pkg.pin_count},
        pins=pins,
        peripherals=peripherals,
        external_devices=external_devices,
        dts_soc_include=${dtsSocInclude},
        dts_pinctrl_include=${dtsPinctrlInclude},
        pinctrl_header="${pinctrlHeader}",
        flash_size_kb=${info.device.flash_size_kb},
        sram_size_kb=${info.device.sram_size_kb},
        clock_hz=${formatClock(info.device.clock_hz)},
    )
`;
}

async function updateInitFile(boardsDir: string, soc: string, packages: ParsedPackageInfoJson[]): Promise<void> {
  const initPath = path.join(boardsDir, '__init__.py');
  let existing = '';
  try {
    existing = await fs.readFile(initPath, 'utf8');
  } catch {
    existing = '';
  }

  const socLower = soc.toLowerCase();
  const imports: string[] = [];
  const entries: string[] = [];
  for (const pkg of packages) {
    const moduleName = `${socLower}_${packageLabel(pkg.name)}`;
    const funcName = `build_${moduleName}`;
    const boardKey = buildBoardKey(socLower, pkg, packages.length);
    if (!existing.includes(funcName)) {
      imports.push(`from .${moduleName} import ${funcName}`);
      entries.push(`    "${boardKey}": ${funcName},`);
    }
  }

  if (imports.length === 0) return;

  if (existing.includes('BOARDS')) {
    const lines = existing.split('\n');
    const output: string[] = [];
    let inBoards = false;
    for (const line of lines) {
      if (/^BOARDS\s*=\s*\{/.test(line) && !inBoards) {
        output.push(...imports, '', line);
        inBoards = true;
        continue;
      }
      if (inBoards && line.trim() === '}') {
        output.push(...entries, line);
        continue;
      }
      output.push(line);
    }
    await fs.writeFile(initPath, output.join('\n'), 'utf8');
    return;
  }

  const fresh = `${imports.join('\n')}\n\nBOARDS = {\n${entries.join('\n')}\n}\n`;
  await fs.writeFile(initPath, fresh, 'utf8');
}

async function refreshBoardSnapshots(rootDir: string): Promise<void> {
  const scriptPath = path.join(rootDir, 'backend_ts', 'scripts', 'export_boards.py');
  const executable = process.env.PYTHON ?? 'python';
  await new Promise<void>((resolve, reject) => {
    const child = spawn(executable, [scriptPath], { cwd: rootDir, env: process.env, stdio: ['ignore', 'ignore', 'pipe'] });
    let stderr = '';
    child.stderr.on('data', (chunk: Buffer) => {
      stderr += chunk.toString('utf8');
    });
    child.on('error', reject);
    child.on('exit', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`Board export failed with code ${code}: ${stderr}`));
    });
  });
}

export async function generateBoardFiles(
  rootDir: string,
  info: ParsedDatasheetInfoJson,
  options: { packages?: string[]; boardName?: string; dtsSocInclude?: string; dtsPinctrlInclude?: string; pinctrlHeader?: string; externalDevices?: ExternalDeviceSpec[]; register?: boolean } = {},
): Promise<Array<{ filename: string; path: string }>> {
  const boardsDir = path.join(rootDir, 'boards');
  await fs.mkdir(boardsDir, { recursive: true });
  const packageFilter = options.packages && options.packages.length > 0
    ? new Set(options.packages.map((value) => value.toUpperCase().replace(/-/g, '')))
    : null;
  const selectedPackages = packageFilter
    ? info.packages.filter((pkg) => packageFilter.has(pkg.name.toUpperCase().replace(/-/g, '')))
    : info.packages;

  if (selectedPackages.length === 0) {
    throw new Error(`No matching packages. Available: ${info.packages.map((pkg) => pkg.name).join(',')}`);
  }

  const generated: Array<{ filename: string; path: string }> = [];
  for (const pkg of selectedPackages) {
    const filename = `${info.device.soc.toLowerCase()}_${packageLabel(pkg.name)}.py`;
    const filePath = path.join(boardsDir, filename);
    const source = generateBoardFileSource(info, pkg, {
      boardName: options.boardName,
      dtsSocInclude: options.dtsSocInclude,
      dtsPinctrlInclude: options.dtsPinctrlInclude,
      pinctrlHeader: options.pinctrlHeader,
      externalDevices: options.externalDevices,
    });
    await fs.writeFile(filePath, source, 'utf8');
    generated.push({ filename, path: filePath });
  }

  if (options.register !== false) {
    await updateInitFile(boardsDir, info.device.soc, selectedPackages);
  }
  await refreshBoardSnapshots(rootDir);
  return generated;
}