const path = require('node:path');

const { callPythonJob } = require('../dist/python_jobs.js');
const { parseTiSnapshot } = require('../dist/pdf_ti_parser.js');
const { parseStm32Snapshot } = require('../dist/pdf_stm32_parser.js');
const { parseGenericSnapshot } = require('../dist/pdf_generic_parser.js');

const rootDir = path.resolve(__dirname, '..', '..');

function assertEqual(actual, expected, label) {
  const left = JSON.stringify(actual);
  const right = JSON.stringify(expected);
  if (left !== right) {
    throw new Error(`${label} mismatch\nexpected: ${right}\nactual:   ${left}`);
  }
}

async function extractSnapshot(file) {
  const pdfPath = path.join(rootDir, '.uploads', file);
  const response = await callPythonJob(rootDir, {
    operation: 'extract-mcu-pdf-snapshot',
    uploadPath: pdfPath,
    filename: file,
  });
  if (response.status !== 200) {
    throw new Error(`Snapshot extraction failed for ${file}: ${JSON.stringify(response.json)}`);
  }
  return response.json;
}

async function main() {
  const tiSnapshot = {
    texts: ['MSPM0G3507 up to 128 KB Flash and 32 KB SRAM CPU frequency up to 80 MHz'],
    pincm_tables: [[
      ['Pin Name', 'PINCM', 'Function 0', 'Function 1'],
      ['PA0', '0', 'GPIO', 'UART0_RX'],
      ['PA1', '1', 'GPIO', 'UART0_TX'],
    ]],
    package_rows: {
      LQFP64: [
        ['1', 'PA0'],
        ['2', 'PA1'],
      ],
    },
  };
  const tiParsed = parseTiSnapshot(tiSnapshot);
  if (!tiParsed) throw new Error('TI native parse returned null');
  assertEqual(tiParsed.device.soc, 'MSPM0G3507', 'TI soc');
  assertEqual(tiParsed.device.flash_size_kb, 128, 'TI flash_size_kb');
  assertEqual(tiParsed.device.sram_size_kb, 32, 'TI sram_size_kb');
  assertEqual(tiParsed.device.clock_hz, 80_000_000, 'TI clock_hz');
  assertEqual(Object.keys(tiParsed.pin_mux).length, 2, 'TI pin_mux_count');
  assertEqual(tiParsed.packages.map((pkg) => pkg.name), ['LQFP64'], 'TI packages');

  const stm32f411 = parseStm32Snapshot(await extractSnapshot('67c77906b17f_stm32f411re.pdf'));
  if (!stm32f411) throw new Error('STM32F411 native parse returned null');
  assertEqual(stm32f411.device.soc, 'STM32F411', 'STM32F411 soc');
  assertEqual(stm32f411.device.vendor, 'st', 'STM32F411 vendor');
  assertEqual(stm32f411.packages.map((pkg) => pkg.name), ['UFQFPN48', 'WLCSP49', 'LQFP64', 'LQFP100', 'UFBGA100'], 'STM32F411 packages');
  assertEqual(Object.keys(stm32f411.pin_mux).length, 82, 'STM32F411 pin_mux_count');

  const stm32l476 = parseStm32Snapshot(await extractSnapshot('16b53a1485d6_stm32l476rg.pdf'));
  if (!stm32l476) throw new Error('STM32L476 native parse returned null');
  assertEqual(stm32l476.device.soc, 'STM32L476', 'STM32L476 soc');
  assertEqual(stm32l476.device.vendor, 'st', 'STM32L476 vendor');
  assertEqual(stm32l476.packages.slice(0, 5).map((pkg) => pkg.name), ['LQFP64', 'WLCSP72', 'WLCSP81', 'LQFP100', 'UFBGA132'], 'STM32L476 package prefix');
  assertEqual(stm32l476.packages.length, 7, 'STM32L476 package_count');
  assertEqual(Object.keys(stm32l476.pin_mux).length, 114, 'STM32L476 pin_mux_count');

  const genericSnapshot = {
    vendor: 'nxp',
    texts: ['LPC845 up to 64 KB Flash and 16 KB SRAM CPU frequency up to 30 MHz', 'Pin multiplexing and package pin description'],
    generic_pinmux_tables: [[
      ['Pin Name', 'ALT0', 'ALT1'],
      ['PIO0_0', 'GPIO', 'FC0_RXD_SDA_MOSI'],
      ['PIO0_1', 'GPIO', 'FC0_TXD_SCL_MISO'],
      ['PA2', 'GPIO', 'UART0_RX'],
    ]],
    generic_package_pages: [{
      text: 'LQFP-48 pin description',
      tables: [[
        ['Pin No', 'Pin Name'],
        ['1', 'PA2'],
        ['2', 'VDD'],
        ['A3', 'PB1'],
      ]],
    }],
  };
  const genericParsed = parseGenericSnapshot(genericSnapshot);
  if (!genericParsed) throw new Error('Generic native parse returned null');
  assertEqual(genericParsed.device.soc, 'LPC845', 'Generic soc');
  assertEqual(genericParsed.device.vendor, 'nxp', 'Generic vendor');
  assertEqual(Object.keys(genericParsed.pin_mux).length, 2, 'Generic pin_mux_count');
  assertEqual(genericParsed.packages.map((pkg) => pkg.name), ['LQFP48'], 'Generic packages');

  console.log('Native MCU sample validation passed.');
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});