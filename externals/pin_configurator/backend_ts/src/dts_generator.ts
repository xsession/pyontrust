export interface PinAssignment {
  pin_name: string;
  pincm: number;
  function_id: number;
  af_name: string;
  peripheral: string;
  signal: string;
  direction: string;
  zephyr_pinmux?: string;
  bias_pull_up?: boolean;
  bias_pull_down?: boolean;
  drive_open_drain?: boolean;
  input_enable?: boolean;
}

export interface PeripheralConfig {
  name: string;
  dts_node: string;
  compatible: string;
  enabled?: boolean;
  core_id?: string;
}

export interface ExternalDeviceConfig {
  id: string;
  display: string;
  category?: string;
  bus?: string;
  compatible?: string;
  address?: string;
  required_signals?: string[];
  frameworks?: string[];
  notes?: string;
}

export interface GeneratedOutput {
  overlay: string;
  prj_conf: string;
  targets: Record<string, Record<string, string>>;
}

const KCONFIG_MAP: Record<string, string[]> = {
  'ti,mspm0-uart': ['CONFIG_SERIAL=y', 'CONFIG_UART_CONSOLE=y'],
  'ti,mspm0-spi': ['CONFIG_SPI=y'],
  'ti,mspm0-i2c': ['CONFIG_I2C=y'],
  'ti,mspm0-can': ['CONFIG_CAN=y'],
  'ti,mspm0-gpio': ['CONFIG_GPIO=y'],
  'ti,mspm0-timer': ['CONFIG_COUNTER=y'],
  'ti,mspm0-timer-pwm': ['CONFIG_PWM=y'],
  'ti,mspm0-adc': ['CONFIG_ADC=y'],
  'ti,mspm0-dac': [],
  'ti,mspm0-comp': [],
  'raspberrypi,rp2040-uart': ['CONFIG_SERIAL=y', 'CONFIG_UART_CONSOLE=y'],
  'raspberrypi,rp2040-spi': ['CONFIG_SPI=y'],
  'raspberrypi,rp2040-i2c': ['CONFIG_I2C=y'],
  'raspberrypi,rp2040-pwm': ['CONFIG_PWM=y'],
  'raspberrypi,rp2040-adc': ['CONFIG_ADC=y'],
  'raspberrypi,rp2040-gpio': ['CONFIG_GPIO=y'],
};

const DEVICE_KCONFIG_MAP: Record<string, string[]> = {
  'bosch,bme280': ['CONFIG_SENSOR=y', 'CONFIG_BME280=y'],
  'st,lis2dh': ['CONFIG_SENSOR=y', 'CONFIG_LIS2DH=y'],
  'solomon,ssd1306fb': ['CONFIG_DISPLAY=y', 'CONFIG_SSD1306=y'],
  'sitronix,st7789v': ['CONFIG_DISPLAY=y', 'CONFIG_ST7789V=y'],
};

const DEVICE_CATEGORY_KCONFIG: Record<string, string[]> = {
  sensor: ['CONFIG_SENSOR=y'],
  display: ['CONFIG_DISPLAY=y'],
};

const ARDUINO_DEVICE_SNIPPETS: Record<string, string[]> = {
  'bosch,bme280': [
    '  // Example: Adafruit_BME280 bme280;',
    '  // bme280.begin(0x76);',
  ],
  'solomon,ssd1306fb': [
    '  // Example: Adafruit_SSD1306 display(128, 64, &Wire);',
    '  // display.begin(SSD1306_SWITCHCAPVCC, 0x3C);',
  ],
  'sitronix,st7789v': [
    '  // Example: Adafruit_ST7789 display(TFT_CS, TFT_DC, TFT_RST);',
    '  // display.init(240, 320);',
  ],
};

function functionMacro(functionId: number): string {
  const names: Record<number, string> = {
    0: 'MSPM0_PIN_FUNCTION_ANALOG',
    1: 'MSPM0_PIN_FUNCTION_GPIO',
  };
  return names[functionId] ?? `MSPM0_PIN_FUNCTION_${functionId}`;
}

function pinctrlNodeName(assignment: PinAssignment): string {
  return `${assignment.peripheral}_${assignment.signal}_${assignment.pin_name.toLowerCase()}`;
}

function sanitizeSymbol(value: string): string {
  return value.toUpperCase().replace(/[^A-Z0-9]+/g, '_').replace(/^_+|_+$/g, '') || 'PIN';
}

function pinNumericValue(pinName: string, fallback: number): number {
  const match = pinName.match(/(\d+)$/);
  return match ? Number(match[1]) : fallback;
}

function sanitizeNodeName(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9_]+/g, '_').replace(/^_+|_+$/g, '') || 'device';
}

function parseAddress(address: string | undefined): number | null {
  const text = (address ?? '').trim().toLowerCase();
  if (!text) {
    return null;
  }
  const parsed = text.startsWith('0x') ? Number.parseInt(text.slice(2), 16) : Number.parseInt(text, 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function busKind(bus: string | undefined): string {
  const lowered = (bus ?? '').toLowerCase();
  for (const prefix of ['i2c', 'spi', 'uart']) {
    if (lowered.startsWith(prefix)) {
      return prefix;
    }
  }
  return lowered;
}

function generateExternalDeviceZephyr(devices: ExternalDeviceConfig[]): { blocks: string[]; kconfigs: Set<string> } {
  const blocks: string[] = [];
  const kconfigs = new Set<string>();

  for (const device of devices) {
    if (!(device.frameworks ?? []).includes('zephyr') || !device.bus || !device.compatible) {
      continue;
    }

    const nodeId = sanitizeNodeName(device.id);
    const compatTail = sanitizeNodeName(device.compatible.split(',', 2)[1] ?? device.compatible);
    const addressValue = parseAddress(device.address);
    const unitAddr = addressValue !== null ? `@${addressValue.toString(16)}` : '';
    let block = `&${device.bus} {\n`;
    block += `\t${nodeId}: ${compatTail}${unitAddr} {\n`;
    block += `\t\tcompatible = "${device.compatible}";\n`;
    if (addressValue !== null) {
      block += `\t\treg = <0x${addressValue.toString(16)}>;\n`;
    }
    block += `\t\tlabel = "${device.display}";\n`;
    if (device.notes) {
      block += `\t\t/* ${device.notes} */\n`;
    }
    block += '\t\tstatus = "okay";\n';
    block += '\t};\n};\n';
    blocks.push(block);

    for (const line of DEVICE_CATEGORY_KCONFIG[device.category ?? ''] ?? []) {
      kconfigs.add(line);
    }
    for (const line of DEVICE_KCONFIG_MAP[device.compatible] ?? []) {
      kconfigs.add(line);
    }
  }

  return { blocks, kconfigs };
}

function generateExternalDeviceArduino(devices: ExternalDeviceConfig[]): { includes: string[]; setupLines: string[] } {
  const includes: string[] = [];
  const setupLines: string[] = [];
  const startedBuses = new Set<string>();

  for (const device of devices) {
    if (!(device.frameworks ?? []).includes('arduino')) {
      continue;
    }

    const kind = busKind(device.bus);
    if (kind === 'i2c') {
      if (!includes.includes('#include <Wire.h>')) {
        includes.push('#include <Wire.h>');
      }
      if (device.bus && !startedBuses.has(device.bus)) {
        setupLines.push(`  // ${device.bus} for external devices`);
        setupLines.push('  Wire.begin();');
        startedBuses.add(device.bus);
      }
    } else if (kind === 'spi') {
      if (!includes.includes('#include <SPI.h>')) {
        includes.push('#include <SPI.h>');
      }
      if (device.bus && !startedBuses.has(device.bus)) {
        setupLines.push(`  // ${device.bus} for external devices`);
        setupLines.push('  SPI.begin();');
        startedBuses.add(device.bus);
      }
    }

    setupLines.push(`  // Device: ${device.display} on ${device.bus || 'unassigned bus'}${device.address ? ` (${device.address})` : ''}`);
    if (device.notes) {
      setupLines.push(`  // ${device.notes}`);
    }
    setupLines.push(...(ARDUINO_DEVICE_SNIPPETS[device.compatible ?? ''] ?? [`  // Compatible: ${device.compatible ?? ''}`]));
  }

  return { includes, setupLines };
}

function arduinoMode(assignment: PinAssignment): string {
  if (assignment.direction === 'analog') {
    return 'INPUT';
  }
  if (assignment.direction === 'out') {
    return 'OUTPUT';
  }
  if (assignment.bias_pull_up) {
    return 'INPUT_PULLUP';
  }
  return 'INPUT';
}

function baremetalMode(direction: string): string {
  if (direction === 'analog') {
    return 'PIN_MODE_ANALOG';
  }
  if (direction === 'out') {
    return 'PIN_MODE_OUTPUT';
  }
  return 'PIN_MODE_INPUT';
}

function zephyrPinmuxExpr(assignment: PinAssignment): string {
  return assignment.zephyr_pinmux?.trim() || `MSP_PINMUX(${assignment.pincm},${functionMacro(assignment.function_id)})`;
}

function zephyrHeader(assignments: PinAssignment[], boardName: string): string {
  const include = assignments.some((assignment) => assignment.zephyr_pinmux)
    ? '#include <zephyr/dt-bindings/pinctrl/rpi-pico-pinctrl.h>'
    : '#include <zephyr/dt-bindings/pinctrl/mspm0-pinctrl.h>';
  return `/*\n * Auto-generated DTS overlay for ${boardName}\n * Created by Zephyr Pin Configurator\n *\n * SPDX-License-Identifier: Apache-2.0\n */\n\n${include}\n\n`;
}

export function generateOverlay(
  assignments: PinAssignment[],
  peripherals: PeripheralConfig[],
  boardName = 'custom_board',
  targets: string[] = ['zephyr', 'arduino', 'baremetal'],
  externalDevices: ExternalDeviceConfig[] = [],
): GeneratedOutput {
  const periphPins = new Map<string, PinAssignment[]>();
  for (const assignment of assignments) {
    const existing = periphPins.get(assignment.peripheral) ?? [];
    existing.push(assignment);
    periphPins.set(assignment.peripheral, existing);
  }

  const pinctrlNodes: string[] = [];
  for (const assignment of [...assignments].sort((left, right) => left.pincm - right.pincm)) {
    const label = pinctrlNodeName(assignment);
    const props = [`\t\tpinmux = <${zephyrPinmuxExpr(assignment)}>;`];
    if (assignment.input_enable || assignment.direction === 'in' || assignment.direction === 'io') {
      props.push('\t\tinput-enable;');
    }
    if (assignment.bias_pull_up) {
      props.push('\t\tbias-pull-up;');
    }
    if (assignment.bias_pull_down) {
      props.push('\t\tbias-pull-down;');
    }
    if (assignment.drive_open_drain) {
      props.push('\t\tdrive-open-drain;');
    }

    pinctrlNodes.push(`\t${label}: ${label} {\n${props.join('\n')}\n\t};\n`);
  }

  const periphBlocks: string[] = [];
  const enabledPeripherals = new Map(
    peripherals.filter((peripheral) => peripheral.enabled).map((peripheral) => [peripheral.name, peripheral]),
  );

  for (const name of ['gpioa', 'gpiob', 'gpio0']) {
    const peripheral = enabledPeripherals.get(name);
    if (peripheral) {
      const coreComment = peripheral.core_id ? `\t/* assigned-core: ${peripheral.core_id} */\n` : '';
      periphBlocks.push(`${peripheral.dts_node} {\n${coreComment}\tstatus = "okay";\n};\n`);
    }
  }

  for (const [name, peripheral] of [...enabledPeripherals.entries()].sort(([left], [right]) => left.localeCompare(right))) {
    if (name.startsWith('gpio')) {
      continue;
    }

    const pinsForPeripheral = periphPins.get(name) ?? [];
    if (pinsForPeripheral.length === 0 && !['adc0', 'dac0', 'comp0', 'comp1'].includes(name)) {
      continue;
    }

    let block = `${peripheral.dts_node} {\n`;
    if (peripheral.core_id) {
      block += `\t/* assigned-core: ${peripheral.core_id} */\n`;
    }
    block += '\tstatus = "okay";\n';

    if (pinsForPeripheral.length > 0) {
      const labels = [...pinsForPeripheral]
        .sort((left, right) => left.pincm - right.pincm)
        .map((assignment) => `&${pinctrlNodeName(assignment)}`)
        .join(' ');
      block += `\tpinctrl-0 = <${labels}>;\n`;
      block += '\tpinctrl-names = "default";\n';
    }

    if (name.startsWith('uart')) {
      block += '\tcurrent-speed = <115200>;\n';
    }
    if (name.startsWith('i2c')) {
      block += '\tclock-frequency = <I2C_BITRATE_STANDARD>;\n';
    }

    block += '};\n';
    periphBlocks.push(block);
  }

  let overlay = zephyrHeader(assignments, boardName);

  if (pinctrlNodes.length > 0) {
    overlay += '&pinctrl {\n';
    overlay += `${pinctrlNodes.join('\n')}};\n\n`;
  }

  for (const block of periphBlocks) {
    overlay += `${block}\n`;
  }

  const deviceZephyr = generateExternalDeviceZephyr(externalDevices);
  for (const block of deviceZephyr.blocks) {
    overlay += `${block}\n`;
  }

  const kconfigs = new Set<string>(['CONFIG_CLOCK_CONTROL=y']);
  for (const peripheral of peripherals) {
    if (!peripheral.enabled) {
      continue;
    }
    for (const line of KCONFIG_MAP[peripheral.compatible] ?? []) {
      kconfigs.add(line);
    }
  }
  for (const line of deviceZephyr.kconfigs) {
    kconfigs.add(line);
  }

  const prjConf = `# Auto-generated by Zephyr Pin Configurator\n\n${[...kconfigs].sort().join('\n')}\n`;

  const generatedTargets: Record<string, Record<string, string>> = {
    zephyr: {
      [`${boardName}.overlay`]: `${overlay.trimEnd()}\n`,
      'prj.conf': prjConf,
    },
  };

  if (targets.includes('arduino')) {
    const constants: string[] = [];
    const setupLines: string[] = [];
    for (const [index, assignment] of [...assignments].sort((left, right) => left.pincm - right.pincm).entries()) {
      const symbol = `PIN_${sanitizeSymbol(assignment.peripheral)}_${sanitizeSymbol(assignment.signal)}`;
      const pinValue = pinNumericValue(assignment.pin_name, index + 1);
      constants.push(`constexpr uint8_t ${symbol} = ${pinValue};`);
      const coreId = peripherals.find((peripheral) => peripheral.name === assignment.peripheral)?.core_id;
      if (coreId) {
        setupLines.push(`  // ${assignment.peripheral} owned by ${coreId}`);
      }
      setupLines.push(`  pinMode(${symbol}, ${arduinoMode(assignment)});`);
    }
    const deviceArduino = generateExternalDeviceArduino(externalDevices);
    const includeBlock = deviceArduino.includes.length ? `${deviceArduino.includes.join('\n')}\n` : '';
    generatedTargets.arduino = {
      'pin_config.h': `#pragma once\n#include <Arduino.h>\n\n${constants.join('\n')}${constants.length ? '\n' : ''}`,
      [`${boardName}.ino`]: `#include "pin_config.h"\n${includeBlock}\n// Auto-generated Arduino pin map for ${boardName}\nvoid setup() {\n${[...setupLines, ...deviceArduino.setupLines].join('\n') || '  // No assigned pins'}\n}\n\nvoid loop() {\n}\n`,
    };
  }

  if (targets.includes('baremetal')) {
    const entries: string[] = [];
    const comments: string[] = [];
    for (const [index, assignment] of [...assignments].sort((left, right) => left.pincm - right.pincm).entries()) {
      const pinValue = pinNumericValue(assignment.pin_name, index + 1);
      entries.push(`  { "${assignment.pin_name}", ${pinValue}, ${baremetalMode(assignment.direction)} },`);
      const coreId = peripherals.find((peripheral) => peripheral.name === assignment.peripheral)?.core_id;
      if (coreId) {
        comments.push(`  /* ${assignment.peripheral} owned by ${coreId} */`);
      }
      comments.push(`  /* ${assignment.peripheral}.${assignment.signal} -> ${assignment.pin_name} */`);
    }
    generatedTargets.baremetal = {
      'pin_config.h': '#pragma once\n\ntypedef enum {\n  PIN_MODE_INPUT,\n  PIN_MODE_OUTPUT,\n  PIN_MODE_ANALOG,\n} pin_mode_t;\n\ntypedef struct {\n  const char *name;\n  unsigned int pin;\n  pin_mode_t mode;\n} pin_config_entry_t;\n\nvoid pin_config_apply(void);\n',
      'pin_config.c': `#include "pin_config.h"\n\nstatic const pin_config_entry_t board_pin_config[] = {\n${entries.join('\n') || '  { 0, 0, PIN_MODE_INPUT },'}\n};\n\nvoid pin_config_apply(void) {\n${comments.join('\n') || '  /* No assigned pins */'}\n\n  (void)board_pin_config;\n  /* Add MCU-specific register writes for ${boardName} here. */\n}\n`,
    };
  }

  return {
    overlay: `${overlay.trimEnd()}\n`,
    prj_conf: prjConf,
    targets: generatedTargets,
  };
}