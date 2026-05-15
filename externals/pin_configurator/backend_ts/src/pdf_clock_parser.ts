import type { ParsedClockInfoJson, ParsedDeviceSummaryJson } from './job_registry';
import type { McuPdfSnapshot } from './python_jobs';

const CLOCK_LINE_PATTERN = /(pll|osc|oscillator|clock|sysclk|mclk|lfclk|hfclk|hse|hsi|lse|lsi|msi|sysosc|lfosc|hfxt|lfxt|hfxo|lfxo|lfrc|hoco|moco|loco|mosc|sosc|iclk|pclk|fclk)/i;
const STM32_LIKE_VENDORS = new Set(['st', 'gigadevice', 'artery', 'puya', 'mindmotion']);

function uniquePush(values: string[], value: string): void {
  if (!values.includes(value)) {
    values.push(value);
  }
}

function detectFeatures(text: string): string[] {
  const features: string[] = [];
  const featurePatterns: Array<[string, RegExp]> = [
    ['SYSOSC', /\bSYSOSC\b/i],
    ['LFOSC', /\bLFOSC\b/i],
    ['HFXT', /\bHFXT\b/i],
    ['LFXT', /\bLFXT\b/i],
    ['PLL', /\bPLL\b|phase-locked loop/i],
    ['MCLK', /\bMCLK\b/i],
    ['LFCLK', /\bLFCLK\b/i],
    ['HSE', /\bHSE\b|high-speed external/i],
    ['HSI', /\bHSI\b|high-speed internal/i],
    ['LSE', /\bLSE\b|low-speed external/i],
    ['LSI', /\bLSI\b|low-speed internal/i],
    ['MSI', /\bMSI\b|multi-speed internal/i],
    ['SYSCLK', /\bSYSCLK\b/i],
    ['AHB', /\bAHB\b/i],
    ['APB', /\bAPB\b/i],
    ['HFCLK', /\bHFCLK\b/i],
    ['HFXO', /\bHFXO\b/i],
    ['LFXO', /\bLFXO\b/i],
    ['LFRC', /\bLFRC\b/i],
    ['LFSYNTH', /\bLFSYNTH\b/i],
    ['HOCO', /\bHOCO\b/i],
    ['MOCO', /\bMOCO\b/i],
    ['LOCO', /\bLOCO\b/i],
    ['MOSC', /\bMOSC\b|main\s+clock\s+oscillator/i],
    ['SOSC', /\bSOSC\b|sub-?clock\s+oscillator/i],
    ['ICLK', /\bICLK\b/i],
    ['FCLK', /\bFCLK\b/i],
    ['PCLKA', /\bPCLKA\b/i],
    ['PCLKB', /\bPCLKB\b/i],
    ['PCLKC', /\bPCLKC\b/i],
    ['PCLKD', /\bPCLKD\b/i],
  ];

  for (const [label, pattern] of featurePatterns) {
    if (pattern.test(text)) {
      uniquePush(features, label);
    }
  }

  return features;
}

function detectModel(vendor: string | undefined, features: string[]): NonNullable<ParsedClockInfoJson['model']> {
  const set = new Set(features);
  if (set.has('SYSOSC') || set.has('LFOSC') || set.has('HFXT') || set.has('LFXT')) {
    return 'mspm0';
  }
  if (vendor === 'renesas' && (set.has('HOCO') || set.has('MOCO') || set.has('LOCO') || set.has('MOSC') || set.has('SOSC'))) {
    return 'renesas_ra';
  }
  if (vendor === 'nordic' || set.has('HFCLK') || set.has('HFXO') || set.has('LFXO') || set.has('LFRC') || set.has('LFSYNTH')) {
    return 'nrf52';
  }
  if (STM32_LIKE_VENDORS.has(vendor ?? '') || set.has('HSI') || set.has('HSE') || set.has('LSE') || set.has('LSI') || set.has('AHB') || set.has('APB') || set.has('SYSCLK')) {
    return 'stm32_generic';
  }
  return 'generic_simple';
}

function extractMaxFrequency(text: string, fallbackHz: number): number {
  const candidates = [...text.matchAll(/(?:up\s+to\s+)?(\d{1,4})\s*[-]?\s*MHz/gi)]
    .map((match) => Number(match[1]))
    .filter((value) => Number.isFinite(value) && value >= 1 && value <= 1200);
  const best = candidates.length ? Math.max(...candidates) * 1_000_000 : 0;
  return best || fallbackHz || 0;
}

function buildSummary(device: ParsedDeviceSummaryJson, model: NonNullable<ParsedClockInfoJson['model']>, features: string[], maxFreqHz: number): string {
  const subject = device.soc || 'MCU';
  const freqText = maxFreqHz > 0 ? `up to ${(maxFreqHz / 1_000_000).toFixed(0)} MHz` : 'with parsed clocking features';
  if (model === 'mspm0') {
    return `${subject} clock system parsed from MCU PDF with SYSOSC, external crystals, and PLL support ${freqText}.`;
  }
  if (model === 'stm32_generic') {
    return `${subject} clock system parsed from MCU PDF with internal/external oscillators, PLL, and bus prescalers ${freqText}.`;
  }
  if (model === 'nrf52') {
    return `${subject} clock system parsed from MCU PDF with HFCLK/LFCLK source selection ${freqText}.`;
  }
  if (model === 'renesas_ra') {
    return `${subject} clock system parsed from MCU PDF with HOCO, MOCO, LOCO, MOSC, SOSC, and PLL routing ${freqText}.`;
  }
  const listed = features.slice(0, 4).join(', ');
  return `${subject} clock system parsed from MCU PDF ${freqText}${listed ? `; detected ${listed}` : ''}.`;
}

export function extractParsedClockInfo(snapshot: Pick<McuPdfSnapshot, 'texts' | 'vendor'>, device: ParsedDeviceSummaryJson): ParsedClockInfoJson | undefined {
  const scanPages = (snapshot.texts ?? []).slice(0, 18);
  if (!scanPages.length) {
    return undefined;
  }

  const scan = scanPages.join('\n');
  const features = detectFeatures(scan);
  const evidence = scanPages
    .flatMap((page) => page.split(/\r?\n/))
    .map((line) => line.trim())
    .filter((line) => line.length >= 8 && CLOCK_LINE_PATTERN.test(line))
    .filter((line, index, values) => values.indexOf(line) === index)
    .slice(0, 8);

  if (!features.length && !evidence.length && !device.clock_hz) {
    return undefined;
  }

  const model = detectModel(snapshot.vendor ?? device.vendor, features);
  const maxFreqHz = extractMaxFrequency(scan, device.clock_hz);
  return {
    model,
    max_freq_hz: maxFreqHz,
    features,
    evidence,
    summary: buildSummary(device, model, features, maxFreqHz),
  };
}