import * as path from 'node:path';

export type UploadArtifactKind = 'incoming' | 'downloads' | 'mcu-jobs' | 'sensor-jobs' | 'vendor-matrix' | 'digest-temp';

export function uploadsRootDir(rootDir: string): string {
  return path.join(rootDir, '.uploads');
}

export function uploadArtifactDir(rootDir: string, kind: UploadArtifactKind): string {
  const suffix = {
    incoming: 'incoming',
    downloads: 'downloads',
    'mcu-jobs': 'mcu_jobs',
    'sensor-jobs': 'sensor_jobs',
    'vendor-matrix': 'vendor_matrix',
    'digest-temp': '.digest_tmp',
  }[kind];
  return path.join(uploadsRootDir(rootDir), suffix);
}