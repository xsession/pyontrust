const path = require('node:path');

const { callPythonJob } = require('../dist/python_jobs.js');
const { parseSensorSnapshot } = require('../dist/pdf_sensor_parser.js');

const rootDir = path.resolve(__dirname, '..', '..');

const EXPECTED = [
  {
    file: 'lm73.pdf',
    part: 'LM73',
    vendor: 'ti',
    protocol: 'i2c',
    addresses: ['0x48', '0x49', '0x4A', '0x4C', '0x4D', '0x4E'],
    whoReg: -1,
    whoVal: -1,
    registerCount: 6,
    firstRegs: ['TEMPERATUREDATA', 'CONFIGURATION', 'T_UPPER_LIMIT', 'T_LOWER_LIMIT', 'CONTROLSTATUS'],
  },
  {
    file: 'dc83cba36045_MPR121.pdf',
    part: 'MPR121',
    vendor: 'nxp',
    protocol: 'i2c',
    addresses: ['0x5A', '0x5B', '0x5C', '0x5D'],
    whoReg: -1,
    whoVal: -1,
    registerCount: 129,
    firstRegs: ['ELE0_ELE7_TOUCH_STATUS', 'ELE8_ELE11_ELEPROX_TOUCH_STATUS', 'ELE0_ELE7_OOR_STATUS', 'ELE8_ELE11_ELEPROX_OOR_STATUS', 'ELE0_ELECTRODE_FILTERED_DATA_LSB'],
  },
  {
    file: 'bmp280.pdf',
    part: 'BMP280',
    vendor: 'bosch',
    protocol: 'i2c+spi',
    addresses: ['0x76', '0x77'],
    whoReg: 208,
    whoVal: 88,
    registerCount: 23,
    firstRegs: ['CALIB_DIG_T1', 'CALIB_DIG_T2', 'CALIB_DIG_T3', 'CALIB_DIG_P1', 'CALIB_DIG_P2'],
    fieldRegisters: [
      { name: 'STATUS', fields: ['MEASURING', 'IM_UPDATE'] },
      { name: 'CTRL_MEAS', fields: ['OSRS_T', 'OSRS_P', 'MODE'] },
      { name: 'CONFIG', fields: ['T_SB', 'FILTER', 'SPI3W_EN'] },
    ],
  },
];

function assertEqual(actual, expected, label) {
  const left = JSON.stringify(actual);
  const right = JSON.stringify(expected);
  if (left !== right) {
    throw new Error(`${label} mismatch\nexpected: ${right}\nactual:   ${left}`);
  }
}

async function parseSample(file) {
  const pdfPath = path.join(rootDir, '.uploads', file);
  const response = await callPythonJob(rootDir, {
    operation: 'extract-sensor-pdf-snapshot',
    uploadPath: pdfPath,
    filename: file,
  });
  if (response.status !== 200) {
    throw new Error(`Snapshot extraction failed for ${file}: ${JSON.stringify(response.json)}`);
  }
  const parsed = parseSensorSnapshot(response.json);
  if (!parsed) {
    throw new Error(`Native parse returned null for ${file}`);
  }
  return parsed;
}

async function main() {
  for (const expected of EXPECTED) {
    const parsed = await parseSample(expected.file);
    assertEqual(parsed.summary?.part_number ?? null, expected.part, `${expected.file} part_number`);
    assertEqual(parsed.summary?.vendor ?? null, expected.vendor, `${expected.file} vendor`);
    assertEqual(parsed.address?.protocol ?? null, expected.protocol, `${expected.file} protocol`);
    assertEqual(parsed.address?.i2c_addresses ?? [], expected.addresses, `${expected.file} i2c_addresses`);
    assertEqual(parsed.summary?.who_am_i_reg ?? null, expected.whoReg, `${expected.file} who_am_i_reg`);
    assertEqual(parsed.summary?.who_am_i_value ?? null, expected.whoVal, `${expected.file} who_am_i_value`);
    assertEqual(parsed.register_map?.registers?.length ?? 0, expected.registerCount, `${expected.file} register_count`);
    assertEqual((parsed.register_map?.registers ?? []).slice(0, 5).map((register) => register.name), expected.firstRegs, `${expected.file} first_regs`);

    if (expected.fieldRegisters) {
      const actualFieldRegisters = (parsed.register_map?.registers ?? [])
        .filter((register) => (register.fields ?? []).length > 0)
        .map((register) => ({
          name: register.name,
          fields: (register.fields ?? []).map((field) => field.name),
        }));
      assertEqual(actualFieldRegisters, expected.fieldRegisters, `${expected.file} field_registers`);
    }
  }

  console.log('Native sensor sample validation passed.');
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});