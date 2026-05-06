import { spawn } from 'node:child_process';
import * as path from 'node:path';

export interface PythonJobResponse {
  status: number;
  json: unknown;
}

export interface ParsePdfJobRequest {
  operation: 'parse-pdf' | 'parse-sensor-pdf';
  uploadPath: string;
  filename: string;
}

export interface ExtractMcuPdfSnapshotJobRequest {
  operation: 'extract-mcu-pdf-snapshot';
  uploadPath: string;
  filename: string;
}

export interface ExtractSensorPdfSnapshotJobRequest {
  operation: 'extract-sensor-pdf-snapshot';
  uploadPath: string;
  filename: string;
}

export interface GenericPackagePageSnapshot {
  text: string;
  tables: string[][][];
}

export interface McuPdfSnapshot {
  texts: string[];
  vendor?: string;
  pincm_tables?: string[][][];
  package_rows?: Record<string, string[][]>;
  stm32_af_tables?: string[][][];
  stm32_pindef_tables?: string[][][];
  generic_pinmux_tables?: string[][][];
  generic_package_pages?: GenericPackagePageSnapshot[];
}

export interface SensorRegisterPageSnapshot {
  text: string;
  tables: string[][][];
}

export interface SensorPackagePageSnapshot {
  text: string;
  tables: string[][][];
}

export interface SensorPdfSnapshot {
  texts: string[];
  register_pages: SensorRegisterPageSnapshot[];
  detail_pages?: SensorRegisterPageSnapshot[];
  package_pages?: SensorPackagePageSnapshot[];
}

export interface FetchDatasheetJobRequest {
  operation: 'fetch-datasheet-parse';
  partNumber: string;
  uploadPath: string;
  filename: string;
  message: string;
}

export type PythonJobRequest = ParsePdfJobRequest | FetchDatasheetJobRequest | ExtractMcuPdfSnapshotJobRequest | ExtractSensorPdfSnapshotJobRequest;

export async function callPythonJob(rootDir: string, request: PythonJobRequest): Promise<PythonJobResponse> {
  const scriptPath = path.join(rootDir, 'backend_ts', 'job_runtime.py');
  const executable = process.env.PYTHON ?? 'python';

  return await new Promise<PythonJobResponse>((resolve, reject) => {
    const child = spawn(executable, [scriptPath], {
      cwd: rootDir,
      env: process.env,
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (chunk: Buffer) => {
      stdout += chunk.toString('utf8');
    });
    child.stderr.on('data', (chunk: Buffer) => {
      stderr += chunk.toString('utf8');
    });
    child.on('error', reject);
    child.on('exit', (code) => {
      if (code !== 0) {
        reject(new Error(`Python job runtime exited with code ${code}: ${stderr || stdout}`));
        return;
      }

      try {
        resolve(JSON.parse(stdout) as PythonJobResponse);
      } catch (error) {
        reject(new Error(`Could not parse Python job response: ${String(error)}\n${stdout}\n${stderr}`));
      }
    });

    child.stdin.write(JSON.stringify(request));
    child.stdin.end();
  });
}