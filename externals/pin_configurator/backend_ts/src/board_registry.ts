import { promises as fs } from 'node:fs';
import * as path from 'node:path';

export interface BoardSummary {
  id: string;
  name: string;
  board: string;
  package: string;
  pin_count: number;
}

export interface BoardRegistry {
  summaries: BoardSummary[];
  byId: Record<string, unknown>;
}

let cachedSnapshotPath = '';
let cachedRegistry: BoardRegistry | null = null;

export function invalidateBoardRegistryCache(): void {
  cachedSnapshotPath = '';
  cachedRegistry = null;
}

function snapshotPath(rootDir: string): string {
  return path.join(rootDir, 'backend_ts', 'src', 'generated', 'boards.json');
}

export async function getBoardRegistry(rootDir: string): Promise<BoardRegistry> {
  const nextSnapshotPath = snapshotPath(rootDir);
  if (cachedRegistry && cachedSnapshotPath === nextSnapshotPath) {
    return cachedRegistry;
  }

  const text = await fs.readFile(nextSnapshotPath, 'utf8');
  const parsed = JSON.parse(text) as Partial<BoardRegistry>;

  if (!Array.isArray(parsed.summaries) || !parsed.byId || typeof parsed.byId !== 'object') {
    throw new Error(`Invalid board registry snapshot: ${nextSnapshotPath}`);
  }

  cachedSnapshotPath = nextSnapshotPath;
  cachedRegistry = {
    summaries: parsed.summaries as BoardSummary[],
    byId: parsed.byId as Record<string, unknown>,
  };
  return cachedRegistry;
}

export async function listBoards(rootDir: string): Promise<BoardSummary[]> {
  return (await getBoardRegistry(rootDir)).summaries;
}

export async function getBoard(rootDir: string, boardId: string): Promise<unknown | null> {
  const registry = await getBoardRegistry(rootDir);
  return registry.byId[boardId] ?? null;
}