import { promises as fs } from 'node:fs';
import * as path from 'node:path';
import { identifyMcu } from './lookup_registry';

const REQUEST_HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Zephyr-Pin-Configurator/1.0',
  Accept: 'application/pdf,*/*',
};

function safeFileStem(value: string): string {
  return value.replace(/[^\w.-]/g, '_');
}

function looksLikePdf(bytes: Uint8Array, contentType: string | null): boolean {
  if (bytes.length >= 5 && Buffer.from(bytes.subarray(0, 5)).toString('ascii') === '%PDF-') {
    return true;
  }
  return (contentType ?? '').toLowerCase().includes('pdf');
}

export interface DownloadedDatasheet {
  filePath: string;
  filename: string;
  message: string;
}

export async function downloadMcuDatasheet(
  rootDir: string,
  partNumber: string,
  outputDir: string,
  explicitUrl?: string,
): Promise<DownloadedDatasheet> {
  const part = partNumber.trim();
  const url = explicitUrl?.trim();
  let urlsToTry: string[] = [];
  let vendorName: string | null = null;

  if (url) {
    urlsToTry = [url];
  } else {
    const identified = await identifyMcu(rootDir, part);
    if (!identified.known || identified.datasheet_urls.length === 0) {
      throw new Error(`Unknown MCU part number: '${part}'. Cannot determine vendor.`);
    }
    urlsToTry = identified.datasheet_urls;
    vendorName = identified.vendor_name;
  }

  await fs.mkdir(outputDir, { recursive: true });
  const filename = `${safeFileStem(part)}_datasheet.pdf`;
  const destinationPath = path.join(outputDir, filename);

  for (const candidateUrl of urlsToTry) {
    try {
      const response = await fetch(candidateUrl, {
        headers: REQUEST_HEADERS,
        redirect: 'follow',
        signal: AbortSignal.timeout(30_000),
      });
      if (!response.ok) {
        continue;
      }

      const bytes = new Uint8Array(await response.arrayBuffer());
      if (!looksLikePdf(bytes, response.headers.get('content-type'))) {
        continue;
      }

      await fs.writeFile(destinationPath, bytes);
      const sizeKb = bytes.length / 1024;
      const vendorMessage = vendorName ? ` (${vendorName})` : '';
      return {
        filePath: destinationPath,
        filename,
        message: `Downloaded ${sizeKb.toFixed(0)} KB from ${candidateUrl}${vendorMessage}`,
      };
    } catch {
      continue;
    }
  }

  throw new Error(`Could not download datasheet for '${part}'. Tried: ${urlsToTry.join(', ')}`);
}