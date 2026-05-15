import { promises as fs } from 'node:fs';
import * as path from 'node:path';
import { generateDriver, type DriverSpec } from './driver_codegen';

export interface ParsedJobManifestEntry {
  job_id: string;
  filename: string;
  upload_path?: string;
  result?: ParsedJobResult | null;
  full_result?: ParsedDatasheetInfoJson | null;
}

export interface ParsedJobResult {
  device?: {
    soc?: string;
    vendor?: string;
    flash_size_kb?: number;
    sram_size_kb?: number;
    clock_hz?: number;
  };
  packages?: Array<{
    name?: string;
    pin_count?: number;
    pins?: Array<{
      number?: number;
      name?: string;
      port?: string;
      gpio_num?: number;
      kind?: string;
    }>;
  }>;
  pin_mux_count?: number;
  pin_mux_total_funcs?: number;
  pin_mux_sample?: Record<string, Array<{
    function_id?: number;
    function_name?: string;
    peripheral?: string;
    signal?: string;
    direction?: string;
  }>>;
}

export interface ParsedPinMuxEntryJson {
  pin_name: string;
  pincm: number;
  function_id: number;
  function_name: string;
  peripheral: string;
  signal: string;
  direction: string;
}

export interface ParsedPackagePinJson {
  number: number;
  name: string;
  port?: string;
  gpio_num?: number;
  kind?: string;
}

export interface ParsedPackageInfoJson {
  name: string;
  pin_count: number;
  pins: ParsedPackagePinJson[];
}

export interface ParsedDeviceSummaryJson {
  soc: string;
  vendor: string;
  flash_size_kb: number;
  sram_size_kb: number;
  clock_hz: number;
}

export interface ParsedClockInfoJson {
  model?: 'mspm0' | 'stm32_generic' | 'nrf52' | 'renesas_ra' | 'generic_simple';
  max_freq_hz?: number;
  summary?: string;
  features?: string[];
  evidence?: string[];
}

export interface ParsedDatasheetInfoJson {
  device: ParsedDeviceSummaryJson;
  packages: ParsedPackageInfoJson[];
  pin_mux: Record<string, ParsedPinMuxEntryJson[]>;
  clock?: ParsedClockInfoJson;
}

export interface ParsedJobSummary {
  job_id: string;
  filename: string;
  soc: string;
  packages: string[];
  pin_count: number;
}

export interface SensorJobManifestEntry {
  job_id: string;
  filename: string;
  upload_path?: string;
  result?: SensorInfoJson | null;
}

export interface SensorJobSummary {
  job_id: string;
  filename: string;
  part_number: string;
  vendor: string;
  sensor_type: string;
  register_count: number;
  i2c_addresses: string[];
  protocol: string;
  package?: SensorPackageJson;
}

export interface SensorPackagePinJson {
  number: number;
  name: string;
  kind?: string;
}

export interface SensorPackageJson {
  name?: string;
  package_type?: string;
  pin_count?: number;
  width_mm?: number;
  height_mm?: number;
  pitch_mm?: number;
  source?: string;
  pins?: SensorPackagePinJson[];
}

export interface SensorFieldJson {
  name: string;
  bits: string;
  bit_high: number;
  bit_low: number;
  access: string;
  reset_value?: string;
  description?: string;
}

export interface SensorRegisterJson {
  address: string;
  address_int: number;
  name: string;
  c_name: string;
  size: number;
  access: string;
  reset_value?: string;
  description?: string;
  fields?: SensorFieldJson[];
}

export interface SensorInfoJson {
  summary?: {
    part_number?: string;
    vendor?: string;
    vendor_name?: string;
    sensor_type?: string;
    description?: string;
    who_am_i_reg?: number;
    who_am_i_value?: number;
    supply_voltage_min?: number;
    supply_voltage_max?: number;
    temp_range_min?: number;
    temp_range_max?: number;
  };
  address?: {
    protocol?: string;
    i2c_addresses?: string[];
    i2c_address_pin?: string;
    spi_max_freq_hz?: number;
    spi_max_freq_mhz?: number;
    spi_mode?: number;
    spi_word_size?: number;
  };
  register_map?: {
    register_count?: number;
    address_bits?: number;
    auto_increment?: boolean;
    registers?: SensorRegisterJson[];
  };
  package?: SensorPackageJson;
}

const SPDX = '/* SPDX-License-Identifier: Apache-2.0 */';

function parsedJobsPath(rootDir: string): string {
  return path.join(rootDir, 'backend_ts', '.bridge_state', 'parsed_jobs.json');
}

function sensorJobsPath(rootDir: string): string {
  return path.join(rootDir, 'backend_ts', '.bridge_state', 'sensor_jobs.json');
}

async function loadManifest<T>(filePath: string): Promise<Record<string, T>> {
  try {
    const text = (await fs.readFile(filePath, 'utf8')).replace(/^\uFEFF/, '');
    const parsed = JSON.parse(text) as unknown;
    return parsed && typeof parsed === 'object' ? (parsed as Record<string, T>) : {};
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      return {};
    }
    throw error;
  }
}

  async function sensorJobHasArtifact(job: SensorJobManifestEntry): Promise<boolean> {
    const uploadPath = String(job.upload_path ?? '').trim();
    if (!uploadPath) return true;
    try {
      await fs.access(uploadPath);
      return true;
    } catch {
      return false;
    }
  }

export async function listParsedJobs(rootDir: string): Promise<ParsedJobSummary[]> {
  const manifest = await loadManifest<ParsedJobManifestEntry>(parsedJobsPath(rootDir));
  return Object.values(manifest).map((job) => ({
    job_id: job.job_id,
    filename: job.filename,
    soc: job.result?.device?.soc ?? '',
    packages: (job.result?.packages ?? []).map((pkg) => String(pkg.name ?? '')),
    pin_count: Number(job.result?.pin_mux_count ?? 0),
  }));
}

export async function listParsedJobEntries(rootDir: string): Promise<ParsedJobManifestEntry[]> {
  const manifest = await loadManifest<ParsedJobManifestEntry>(parsedJobsPath(rootDir));
  return Object.values(manifest);
}

export async function listSensorJobs(rootDir: string): Promise<SensorJobSummary[]> {
  const manifest = await loadManifest<SensorJobManifestEntry>(sensorJobsPath(rootDir));
    const liveJobs = [] as SensorJobManifestEntry[];
    for (const job of Object.values(manifest)) {
      if (await sensorJobHasArtifact(job)) {
        liveJobs.push(job);
      }
    }

    return liveJobs.map((job) => ({
    job_id: job.job_id,
    filename: job.filename,
    part_number: job.result?.summary?.part_number ?? '',
    vendor: job.result?.summary?.vendor_name ?? '',
    sensor_type: job.result?.summary?.sensor_type ?? '',
    register_count: Number(job.result?.register_map?.register_count ?? job.result?.register_map?.registers?.length ?? 0),
    i2c_addresses: (job.result?.address?.i2c_addresses ?? []).map((address) => String(address)),
    protocol: job.result?.address?.protocol ?? '',
    package: job.result?.package
      ? {
          name: job.result.package.name ?? '',
          package_type: job.result.package.package_type ?? '',
          pin_count: Number(job.result.package.pin_count ?? 0),
          width_mm: Number(job.result.package.width_mm ?? 0),
          height_mm: Number(job.result.package.height_mm ?? 0),
          pitch_mm: Number(job.result.package.pitch_mm ?? 0),
          source: job.result.package.source ?? '',
          pins: (job.result.package.pins ?? []).map((pin) => ({
            number: Number(pin.number ?? 0),
            name: String(pin.name ?? ''),
            kind: String(pin.kind ?? ''),
          })),
        }
      : undefined,
  }));
}

export async function getSensorJob(rootDir: string, jobId: string): Promise<SensorJobManifestEntry | null> {
  const manifest = await loadManifest<SensorJobManifestEntry>(sensorJobsPath(rootDir));
  const job = manifest[jobId] ?? null;
  if (!job) return null;
  return await sensorJobHasArtifact(job) ? job : null;
}

function normalisePrefix(value: string): string {
  const cleaned = value.trim().replace(/[\s-]+/g, '_').replace(/[^A-Za-z0-9_]/g, '_').replace(/_+/g, '_');
  return cleaned ? cleaned.toUpperCase() : 'SENSOR';
}

function formatHex(value: number): string {
  return value.toString(16).toUpperCase().padStart(2, '0');
}

export function generateSensorRegisterHeader(info: SensorInfoJson, guardPrefix = ''): string {
  const partNumber = info.summary?.part_number || 'SENSOR';
  const prefix = normalisePrefix(guardPrefix || partNumber);
  const guard = `__${prefix}_REGS_H__`;
  const lines: string[] = [
    SPDX,
    '/**',
    ` * @file ${prefix.toLowerCase()}_regs.h`,
    ` * @brief Register map for ${partNumber}`,
  ];

  if (info.summary?.description) {
    lines.push(` *        ${info.summary.description}`);
  }

  lines.push(' *');
  lines.push(' * Auto-generated by Pyontrust Sensor Parser.');
  lines.push(` * Vendor: ${info.summary?.vendor_name ?? ''}`);
  lines.push(` * Type:   ${info.summary?.sensor_type ?? ''}`);
  lines.push(' */');
  lines.push('');
  lines.push(`#ifndef ${guard}`);
  lines.push(`#define ${guard}`);
  lines.push('');

  const i2cAddresses = info.address?.i2c_addresses ?? [];
  if (i2cAddresses.length > 0) {
    lines.push('/* -- I2C Addresses -------------------------------------- */');
    i2cAddresses.forEach((address, index) => {
      const suffix = i2cAddresses.length > 1 ? `_${index}` : '';
      const formatted = typeof address === 'string' ? address.replace(/^0x/i, '').toUpperCase().padStart(2, '0') : '00';
      lines.push(`#define ${prefix}_I2C_ADDR${suffix}  0x${formatted}u`);
    });
    if (info.address?.i2c_address_pin) {
      lines.push(`/* Address selected by ${info.address.i2c_address_pin} pin */`);
    }
    lines.push('');
  }

  const whoAmIValue = Number(info.summary?.who_am_i_value ?? -1);
  if (whoAmIValue >= 0) {
    lines.push('/* -- Device Identification ------------------------------ */');
    const whoAmIReg = Number(info.summary?.who_am_i_reg ?? -1);
    if (whoAmIReg >= 0) {
      lines.push(`#define ${prefix}_WHO_AM_I_REG   0x${formatHex(whoAmIReg)}u`);
    }
    lines.push(`#define ${prefix}_WHO_AM_I_VAL   0x${formatHex(whoAmIValue)}u`);
    lines.push('');
  }

  const registers = info.register_map?.registers ?? [];
  if (registers.length > 0) {
    lines.push('/* -- Register Addresses --------------------------------- */');
    const maxNameLength = Math.max(...registers.map((register) => `${prefix}_REG_${register.c_name}`.length));
    for (const register of registers) {
      const defineName = `${prefix}_REG_${register.c_name}`;
      const padding = ' '.repeat(maxNameLength - defineName.length + 2);
      let comment = `  /* ${register.access}`;
      const resetValue = register.reset_value ? String(register.reset_value).replace(/^0x/i, '').toUpperCase() : '';
      if (resetValue) {
        comment += `, reset=0x${resetValue}`;
      }
      if (register.description) {
        comment += ` - ${register.description.slice(0, 60)}`;
      }
      comment += ' */';
      lines.push(`#define ${defineName}${padding}0x${formatHex(register.address_int)}u${comment}`);
    }
    lines.push('');
  }

  const registersWithFields = registers.filter((register) => (register.fields ?? []).length > 0);
  if (registersWithFields.length > 0) {
    lines.push('/* -- Bit-Field Definitions ------------------------------ */');
    for (const register of registersWithFields) {
      lines.push('');
      lines.push(`/* ${register.c_name} (0x${formatHex(register.address_int)}) bit fields */`);
      for (const field of register.fields ?? []) {
        const width = field.bit_high - field.bit_low + 1;
        const mask = ((1 << width) - 1) << field.bit_low;
        const fieldName = `${prefix}_${register.c_name}_${field.name}`;
        lines.push(`#define ${fieldName}_SHIFT  ${field.bit_low}u`);
        lines.push(`#define ${fieldName}_MASK   0x${formatHex(mask)}u`);
        if (width === 1) {
          lines.push(`#define ${fieldName}_BIT    (1u << ${field.bit_low})`);
        }
      }
    }
    lines.push('');
  }

  lines.push(`#endif /* ${guard} */`);
  return lines.join('\n');
}

export function generateSensorRegisterDefines(info: SensorInfoJson): string {
  const lines: string[] = [];
  for (const register of info.register_map?.registers ?? []) {
    lines.push(`#define REG_${register.c_name}  0x${formatHex(register.address_int)}u`);
  }

  const whoAmIValue = Number(info.summary?.who_am_i_value ?? -1);
  if (whoAmIValue >= 0) {
    lines.push('');
    lines.push(`#define EXPECTED_WHO_AM_I  0x${formatHex(whoAmIValue)}u`);
  }

  return lines.join('\n');
}

export interface SensorDriverOptions {
  name?: string;
  compatible?: string;
  bus?: string;
  has_interrupt?: boolean;
}

export function generateSensorDriverFromJob(info: SensorInfoJson, overrides: SensorDriverOptions = {}): ReturnType<typeof generateDriver> & {
  register_header: string;
  register_defines: string;
} {
  const part = info.summary?.part_number || 'sensor';
  const vendor = info.summary?.vendor || 'vendor';
  const protocol = String(info.address?.protocol ?? '').toLowerCase();
  const bus = overrides.bus || (protocol.includes('i2c') ? 'i2c' : protocol.includes('spi') ? 'spi' : 'i2c');
  const spec: DriverSpec = {
    name: overrides.name || part.toLowerCase().replace(/-/g, '_'),
    driver_type: 'sensor',
    compatible: overrides.compatible || `${vendor},${part.toLowerCase()}`,
    bus,
    description: info.summary?.description || `${part} ${info.summary?.sensor_type ?? 'sensor'} driver`,
    vendor,
    has_interrupt: Boolean(overrides.has_interrupt),
    num_channels: 1,
    registers: (info.register_map?.registers ?? []).map((register) => ({
      name: register.c_name,
      address: register.address_int,
      size: Number(register.size ?? 1),
      rw: register.access || 'rw',
    })),
    author: '',
    year: '',
  };

  return {
    ...generateDriver(spec),
    register_header: generateSensorRegisterHeader(info),
    register_defines: generateSensorRegisterDefines(info),
  };
}

export async function getParsedJob(rootDir: string, jobId: string): Promise<ParsedJobManifestEntry | null> {
  const manifest = await loadManifest<ParsedJobManifestEntry>(parsedJobsPath(rootDir));
  return manifest[jobId] ?? null;
}

export function buildParsedJobResult(info: ParsedDatasheetInfoJson): ParsedJobResult {
  return {
    device: {
      soc: info.device.soc,
      vendor: info.device.vendor,
      flash_size_kb: info.device.flash_size_kb,
      sram_size_kb: info.device.sram_size_kb,
      clock_hz: info.device.clock_hz,
    },
    packages: info.packages.map((pkg) => ({
      name: pkg.name,
      pin_count: pkg.pin_count,
      pins: pkg.pins.map((pin) => ({
        number: pin.number,
        name: pin.name,
        port: pin.port,
        gpio_num: pin.gpio_num,
        kind: pin.kind,
      })),
    })),
    pin_mux_count: Object.keys(info.pin_mux).length,
    pin_mux_total_funcs: Object.values(info.pin_mux).reduce((count, entries) => count + entries.length, 0),
    pin_mux_sample: Object.fromEntries(
      Object.entries(info.pin_mux).slice(0, 5).map(([pinName, entries]) => [
        pinName,
        entries.map((entry) => ({
          function_id: entry.function_id,
          function_name: entry.function_name,
          peripheral: entry.peripheral,
          signal: entry.signal,
          direction: entry.direction,
        })),
      ]),
    ),
  };
}

export async function saveParsedJob(rootDir: string, entry: ParsedJobManifestEntry): Promise<void> {
  const filePath = parsedJobsPath(rootDir);
  const manifest = await loadManifest<ParsedJobManifestEntry>(filePath);
  manifest[entry.job_id] = entry;
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
}

export async function saveSensorJob(rootDir: string, entry: SensorJobManifestEntry): Promise<void> {
  const filePath = sensorJobsPath(rootDir);
  const manifest = await loadManifest<SensorJobManifestEntry>(filePath);
  manifest[entry.job_id] = entry;
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
}