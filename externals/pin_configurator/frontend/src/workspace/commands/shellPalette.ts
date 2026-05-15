export interface ShellPaletteItem {
  id: string;
  label: string;
  description: string;
  shortcut: string;
  group: string;
  disabled: boolean;
  keywords: string[];
  run: () => void;
}

export interface ShellPaletteSection {
  id: string;
  label: string;
  items: ShellPaletteItem[];
  meta?: string;
  collapsible?: boolean;
}

import { filterAndRankByFuzzyMatch, normalizeFuzzyText } from "../../shared/search/fuzzySearch";

export function normalizeCommandSearch(value: string) {
  return normalizeFuzzyText(value);
}

export function matchesPaletteItem(item: ShellPaletteItem, query: string) {
  return Boolean(buildVisiblePaletteItems([item], [], query).length);
}

function getPaletteItemSearchableText(item: ShellPaletteItem) {
  return [item.label, item.description, item.group, item.shortcut, ...item.keywords].join(" ");
}

export function isEditableTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) {
    return false;
  }

  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

export function buildCommandPaletteItems(items: Array<{
  id: string;
  label: string;
  description: string;
  shortcut: string;
  group: string;
  disabled: boolean;
  run: () => void;
}>): ShellPaletteItem[] {
  return items.map((item) => ({
    ...item,
    keywords: ["command", item.group.toLowerCase()],
  }));
}

export function buildVisiblePaletteItems(
  paletteItems: ShellPaletteItem[],
  recentPaletteItemIds: string[],
  commandQuery: string,
) {
  const normalizedQuery = normalizeCommandSearch(commandQuery);
  if (!normalizedQuery) {
    return [...paletteItems];
  }

  return filterAndRankByFuzzyMatch(paletteItems, normalizedQuery, getPaletteItemSearchableText);
}

export function buildPaletteSections(
  paletteItems: ShellPaletteItem[],
  recentPaletteItemIds: string[],
  commandQuery: string,
): ShellPaletteSection[] {
  const normalizedQuery = normalizeCommandSearch(commandQuery);
  const sections: ShellPaletteSection[] = [];
  const itemsById = new Map(paletteItems.map((item) => [item.id, item]));
  const recentIds = new Set<string>();

  if (!normalizedQuery) {
    const recentItems = recentPaletteItemIds
      .map((itemId) => itemsById.get(itemId))
      .filter((item): item is ShellPaletteItem => Boolean(item));

    if (recentItems.length) {
      recentItems.forEach((item) => recentIds.add(item.id));
      sections.push({
        id: "recent",
        label: "Recently used",
        items: recentItems,
        meta: `${recentItems.length} shortcuts`,
      });
    }
  }

  const grouped = new Map<string, ShellPaletteItem[]>();
  paletteItems.forEach((item) => {
    if (recentIds.has(item.id)) {
      return;
    }

    const groupItems = grouped.get(item.group) ?? [];
    groupItems.push(item);
    grouped.set(item.group, groupItems);
  });

  grouped.forEach((items, group) => {
    sections.push({
      id: group.toLowerCase().replace(/[^a-z0-9]+/g, "-"),
      label: group,
      items,
      meta: `${items.length} commands`,
      collapsible: true,
    });
  });

  return sections;
}
