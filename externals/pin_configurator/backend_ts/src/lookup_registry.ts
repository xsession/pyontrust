import { listBoards } from './board_registry';

export interface IdentifiedMcu {
  part_number: string;
  known: boolean;
  existing_board: string | null;
  vendor: string | null;
  vendor_name: string | null;
  family: string | null;
  datasheet_urls: string[];
}

export interface IdentifiedSensor {
  part_number: string;
  known: boolean;
  vendor: string | null;
  vendor_name: string | null;
}

interface VendorPattern {
  pattern: RegExp;
  vendor: string;
  vendorName: string;
  buildUrls: (partNumber: string) => string[];
}

const MCU_VENDOR_PATTERNS: VendorPattern[] = [
  {
    pattern: /^(MSPM0[A-Z]\d{4})/i,
    vendor: 'ti',
    vendorName: 'Texas Instruments',
    buildUrls: (partNumber) => {
      const normalized = partNumber.toUpperCase().toLowerCase();
      return [
        `https://www.ti.com/lit/ds/symlink/${normalized}.pdf`,
        `https://www.ti.com/lit/gpn/${normalized}`,
      ];
    },
  },
  {
    pattern: /^(MSP430\w+)/i,
    vendor: 'ti',
    vendorName: 'Texas Instruments',
    buildUrls: (partNumber) => {
      const normalized = partNumber.toUpperCase().toLowerCase();
      return [
        `https://www.ti.com/lit/ds/symlink/${normalized}.pdf`,
        `https://www.ti.com/lit/gpn/${normalized}`,
      ];
    },
  },
  {
    pattern: /^(CC\d{2,4}[A-Z]\d*)/i,
    vendor: 'ti',
    vendorName: 'Texas Instruments',
    buildUrls: (partNumber) => [`https://www.ti.com/lit/ds/symlink/${partNumber.toUpperCase().toLowerCase()}.pdf`],
  },
  {
    pattern: /^(STM32([A-Z])\d{3}\w*)/i,
    vendor: 'st',
    vendorName: 'STMicroelectronics',
    buildUrls: (partNumber) => {
      const normalized = partNumber.toUpperCase();
      const lower = normalized.toLowerCase();
      const baseMatch = normalized.match(/(STM32[A-Z]\d{3})/i);
      const base = baseMatch ? baseMatch[1].toLowerCase() : lower;
      const urls = [`https://www.st.com/resource/en/datasheet/${lower}.pdf`];
      if (normalized.length > base.length) {
        urls.push(`https://www.st.com/resource/en/datasheet/${base}xx.pdf`);
      }
      if (lower !== base) {
        urls.push(`https://www.st.com/resource/en/datasheet/${base}.pdf`);
      }
      return urls;
    },
  },
  {
    pattern: /^(nRF\d{4,5}\w*)/i,
    vendor: 'nordic',
    vendorName: 'Nordic Semiconductor',
    buildUrls: (partNumber) => {
      const normalized = partNumber.toLowerCase();
      return [
        `https://docs-be.nordicsemi.com/bundle/ps_${normalized}/resource/ref_manual.pdf`,
        `https://infocenter.nordicsemi.com/pdf/${normalized}_ps_v1.0.pdf`,
      ];
    },
  },
  {
    pattern: /^(LPC\d{4}\w*)/i,
    vendor: 'nxp',
    vendorName: 'NXP Semiconductors',
    buildUrls: (partNumber) => [`https://www.nxp.com/docs/en/data-sheet/${partNumber.toUpperCase()}.pdf`],
  },
  {
    pattern: /^(MIMXRT\d{4}\w*)/i,
    vendor: 'nxp',
    vendorName: 'NXP Semiconductors',
    buildUrls: (partNumber) => [`https://www.nxp.com/docs/en/data-sheet/${partNumber.toUpperCase()}.pdf`],
  },
  {
    pattern: /^(MK\w+)/i,
    vendor: 'nxp',
    vendorName: 'NXP Semiconductors',
    buildUrls: (partNumber) => [`https://www.nxp.com/docs/en/data-sheet/${partNumber.toUpperCase()}.pdf`],
  },
  {
    pattern: /^(PIC\d+\w+)/i,
    vendor: 'microchip',
    vendorName: 'Microchip Technology',
    buildUrls: (partNumber) => [`https://ww1.microchip.com/downloads/en/DeviceDoc/${partNumber.toUpperCase()}-datasheet.pdf`],
  },
  {
    pattern: /^(ATSAMD?\d+\w*)/i,
    vendor: 'microchip',
    vendorName: 'Microchip Technology',
    buildUrls: (partNumber) => [`https://ww1.microchip.com/downloads/en/DeviceDoc/${partNumber.toUpperCase()}-datasheet.pdf`],
  },
  {
    pattern: /^(SAMD?\d+\w*)/i,
    vendor: 'microchip',
    vendorName: 'Microchip Technology',
    buildUrls: (partNumber) => [`https://ww1.microchip.com/downloads/en/DeviceDoc/${partNumber.toUpperCase()}-datasheet.pdf`],
  },
  {
    pattern: /^(ESP32\w*)/i,
    vendor: 'espressif',
    vendorName: 'Espressif Systems',
    buildUrls: (partNumber) => [`https://www.espressif.com/sites/default/files/documentation/${partNumber.toLowerCase().replace(/_/g, '-')}_datasheet_en.pdf`],
  },
  {
    pattern: /^(CY8C\w+)/i,
    vendor: 'infineon',
    vendorName: 'Infineon Technologies',
    buildUrls: (partNumber) => [`https://www.infineon.com/dgdl/${partNumber.toUpperCase()}-datasheet.pdf`],
  },
  {
    pattern: /^(PSOC\d\w*)/i,
    vendor: 'infineon',
    vendorName: 'Infineon Technologies',
    buildUrls: (partNumber) => [`https://www.infineon.com/dgdl/${partNumber.toUpperCase()}-datasheet.pdf`],
  },
  {
    pattern: /^(XMC\d{4}\w*)/i,
    vendor: 'infineon',
    vendorName: 'Infineon Technologies',
    buildUrls: (partNumber) => [`https://www.infineon.com/dgdl/${partNumber.toUpperCase()}-datasheet.pdf`],
  },
  {
    pattern: /^(R7FA\w+)/i,
    vendor: 'renesas',
    vendorName: 'Renesas Electronics',
    buildUrls: (partNumber) => [`https://www.renesas.com/document/dst/${partNumber.toUpperCase().toLowerCase()}-group-datasheet`],
  },
  {
    pattern: /^(R5F\w+)/i,
    vendor: 'renesas',
    vendorName: 'Renesas Electronics',
    buildUrls: (partNumber) => [`https://www.renesas.com/document/dst/${partNumber.toUpperCase().toLowerCase()}-group-datasheet`],
  },
  {
    pattern: /^(RA\d[A-Z]\d\w*)/i,
    vendor: 'renesas',
    vendorName: 'Renesas Electronics',
    buildUrls: (partNumber) => [`https://www.renesas.com/document/dst/${partNumber.toUpperCase().toLowerCase()}-group-datasheet`],
  },
];

const SENSOR_VENDOR_PATTERNS: Array<{ vendor: string; vendorName: string; pattern: RegExp }> = [
  { vendor: 'bosch', vendorName: 'Bosch Sensortec', pattern: /BM[EAI]\d{3}|BMP\d{3}|BMG\d{3}|BMX\d{3}/i },
  { vendor: 'st', vendorName: 'STMicroelectronics', pattern: /LIS[23][A-Z]{1,3}\d{1,2}|LSM\d[A-Z]{2,3}\d?|LPS\d{2}[A-Z]{2}|HTS\d{3}|STTS\d{3}|IIS\d[A-Z]{2,3}|ISM\d{3}|ASM\d{3}/i },
  { vendor: 'tdk', vendorName: 'TDK InvenSense', pattern: /ICM[-]?\d{5}|MPU[-]?\d{4}|ICP[-]?\d{5}|IAM[-]?\d{5}/i },
  { vendor: 'adi', vendorName: 'Analog Devices', pattern: /ADXL\d{3,4}|ADT\d{4}|ADIS\d{4,5}|MAX\d{5}|LTC\d{4}/i },
  { vendor: 'ti', vendorName: 'Texas Instruments', pattern: /TMP\d{3}|HDC\d{4}|OPT\d{4}|ADS\d{4}|INA\d{3}|LM7[35]\d{0,2}/i },
  { vendor: 'nxp', vendorName: 'NXP Semiconductors', pattern: /FXOS\d{4}|FXAS\d{4,5}|MMA\d{3,4}|MPL\d{4}|LPC\d{4}|MPR\d{3}/i },
  { vendor: 'sensirion', vendorName: 'Sensirion', pattern: /SHT[34]\d|SCD[34]\d|SGP[34]\d|SPS\d{2}|SEN\d{2}/i },
  { vendor: 'honeywell', vendorName: 'Honeywell', pattern: /HMC\d{4}|HSC|SSC|HPM|HIH\d{4}|ABP\d?/i },
  { vendor: 'ams', vendorName: 'ams-OSRAM', pattern: /AS\d{4}|TMD\d{4}|TCS\d{4}|TMF\d{4}|TSL\d{4}/i },
  { vendor: 'infineon', vendorName: 'Infineon Technologies', pattern: /DPS\d{3}|TL[VE]\d{3}[A-Z]|TLE\d{4}/i },
  { vendor: 'renesas', vendorName: 'Renesas', pattern: /FS\d{4}|HS\d{3}|ZMOD\d{4}|ISL\d{5}/i },
  { vendor: 'te', vendorName: 'TE Connectivity / Measurement Specialties', pattern: /MS\d{4}|TSYS\d{2}|HTU\d{2}/i },
  { vendor: 'microchip', vendorName: 'Microchip Technology', pattern: /MCP\d{4}|TC\d{4}|EMC\d{4}/i },
];

const DRIVER_TYPES = ['sensor', 'gpio', 'i2c', 'spi', 'uart', 'pwm', 'adc', 'custom'];

function extractFamily(match: string, vendor: string): string {
  const upper = match.toUpperCase();
  if (vendor === 'st') {
    return upper.match(/^(STM32[A-Z]\d)/)?.[1] ?? upper;
  }
  if (vendor === 'ti') {
    return upper.match(/^(MSPM0|MSP430|CC\d{2})/)?.[1] ?? upper;
  }
  if (vendor === 'nordic') {
    return upper.match(/^(NRF\d{2})/)?.[1] ?? upper;
  }
  if (vendor === 'nxp') {
    return upper.match(/^(LPC\d{2}|MIMXRT\d{3}|MK[A-Z]\d)/)?.[1] ?? upper;
  }
  if (vendor === 'espressif') {
    return upper.match(/^(ESP32\w?\d?)/)?.[1] ?? upper;
  }
  if (vendor === 'microchip') {
    return upper.match(/^(ATSAMD?\d+|SAMD?\d+|PIC\d+)/)?.[1] ?? upper;
  }
  if (vendor === 'infineon') {
    return upper.match(/^(CY8C\d|PSOC\d|XMC\d{4})/)?.[1] ?? upper;
  }
  if (vendor === 'renesas') {
    return upper.match(/^(RA\d[A-Z]|R7FA|R5F)/)?.[1] ?? upper;
  }
  return upper;
}

export async function identifyMcu(rootDir: string, partNumber: string): Promise<IdentifiedMcu> {
  const part = partNumber.trim();
  const boards = await listBoards(rootDir);
  const normalizedPart = part.toLowerCase().replace(/[-_]/g, '');
  const existingBoard = boards.find((board) => board.id.toLowerCase().replace(/[-_]/g, '') === normalizedPart)?.id ?? null;

  for (const entry of MCU_VENDOR_PATTERNS) {
    const match = entry.pattern.exec(part);
    if (!match) {
      continue;
    }
    const fullMatch = match[1] ?? part;
    return {
      part_number: part,
      known: true,
      existing_board: existingBoard,
      vendor: entry.vendor,
      vendor_name: entry.vendorName,
      family: extractFamily(fullMatch, entry.vendor),
      datasheet_urls: entry.buildUrls(part),
    };
  }

  return {
    part_number: part,
    known: false,
    existing_board: existingBoard,
    vendor: null,
    vendor_name: null,
    family: null,
    datasheet_urls: [],
  };
}

export function identifySensor(partNumber: string): IdentifiedSensor {
  const part = partNumber.trim();
  for (const entry of SENSOR_VENDOR_PATTERNS) {
    if (entry.pattern.test(part)) {
      return {
        part_number: part,
        known: true,
        vendor: entry.vendor,
        vendor_name: entry.vendorName,
      };
    }
  }

  return {
    part_number: part,
    known: false,
    vendor: null,
    vendor_name: null,
  };
}

export function listDriverTemplates(): Array<{ type: string; description: string }> {
  return DRIVER_TYPES.map((type) => ({
    type,
    description: {
      sensor: 'Sensor API (sample_fetch / channel_get)',
      gpio: 'GPIO controller driver',
      i2c: 'I2C bus device driver',
      spi: 'SPI bus device driver',
      uart: 'UART serial driver',
      pwm: 'PWM output driver',
      adc: 'ADC channel driver',
      custom: 'Bare DEVICE_DT_INST_DEFINE skeleton',
    }[type] ?? type,
  }));
}