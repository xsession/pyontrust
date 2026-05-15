import { useVirtualizer } from "@tanstack/react-virtual";
import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";

export interface VirtualizedTreeListSection<T> {
  id: string;
  label: string;
  items: T[];
  meta?: string;
  collapsible?: boolean;
  defaultCollapsed?: boolean;
}

interface VirtualizedTreeListItemRenderContext<T> {
  item: T;
  itemId: string;
  depth: number;
  index: number;
  section: VirtualizedTreeListSection<T>;
}

interface VirtualizedTreeListProps<T> {
  ariaLabel: string;
  sections: VirtualizedTreeListSection<T>[];
  getItemId: (item: T) => string;
  renderItem: (context: VirtualizedTreeListItemRenderContext<T>) => ReactNode;
  getItemDepth?: (item: T) => number;
  emptyState?: ReactNode;
  estimatedRowHeight?: number;
  overscan?: number;
  viewportClassName?: string;
  contentClassName?: string;
  rowRole?: string;
  containerRole?: string;
  showSectionHeaders?: boolean;
  dataTestId?: string;
}

type FlatVirtualizedRow<T> =
  | { kind: "section"; key: string; section: VirtualizedTreeListSection<T>; collapsed: boolean }
  | { kind: "item"; key: string; section: VirtualizedTreeListSection<T>; item: T; itemId: string; depth: number; index: number };

function joinClassNames(...values: Array<string | undefined | false>): string {
  return values.filter(Boolean).join(" ");
}

export function VirtualizedTreeList<T>({
  ariaLabel,
  sections,
  getItemId,
  renderItem,
  getItemDepth,
  emptyState,
  estimatedRowHeight = 88,
  overscan = 6,
  viewportClassName,
  contentClassName,
  rowRole = "listitem",
  containerRole = "list",
  showSectionHeaders = true,
  dataTestId,
}: VirtualizedTreeListProps<T>) {
  const parentRef = useRef<HTMLDivElement | null>(null);
  const supportsVirtualization = typeof ResizeObserver !== "undefined";
  const visibleSections = useMemo(() => sections.filter((section) => section.items.length > 0), [sections]);
  const [collapsedBySection, setCollapsedBySection] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setCollapsedBySection((current) => {
      const next: Record<string, boolean> = {};
      visibleSections.forEach((section) => {
        next[section.id] = current[section.id] ?? Boolean(section.defaultCollapsed);
      });
      return next;
    });
  }, [visibleSections]);

  const flatRows = useMemo<FlatVirtualizedRow<T>[]>(() => {
    const rows: FlatVirtualizedRow<T>[] = [];

    visibleSections.forEach((section) => {
      const collapsed = collapsedBySection[section.id] ?? Boolean(section.defaultCollapsed);
      if (showSectionHeaders) {
        rows.push({
          kind: "section",
          key: `section:${section.id}`,
          section,
          collapsed,
        });
      }

      if (collapsed) {
        return;
      }

      section.items.forEach((item, index) => {
        rows.push({
          kind: "item",
          key: `item:${section.id}:${getItemId(item)}`,
          section,
          item,
          itemId: getItemId(item),
          depth: getItemDepth ? getItemDepth(item) : 0,
          index,
        });
      });
    });

    return rows;
  }, [collapsedBySection, getItemDepth, getItemId, showSectionHeaders, visibleSections]);

  const rowVirtualizer = useVirtualizer({
    count: flatRows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => estimatedRowHeight,
    overscan,
  });

  function renderRow(row: FlatVirtualizedRow<T>, style?: CSSProperties) {
    if (row.kind === "section") {
      return (
        <div key={row.key} className="virtualized-tree-list__row virtualized-tree-list__row--section" style={style} role={rowRole}>
          <div className="virtualized-tree-list__section">
            <button
              type="button"
              className="virtualized-tree-list__section-button"
              onClick={() => {
                if (!row.section.collapsible) {
                  return;
                }

                setCollapsedBySection((current) => ({
                  ...current,
                  [row.section.id]: !row.collapsed,
                }));
              }}
              aria-expanded={row.section.collapsible ? !row.collapsed : undefined}
              disabled={!row.section.collapsible}
            >
              <span className="virtualized-tree-list__section-title">{row.section.label}</span>
              <span className="virtualized-tree-list__section-meta">
                {row.section.meta ?? `${row.section.items.length} ${row.section.items.length === 1 ? "item" : "items"}`}
              </span>
            </button>
          </div>
        </div>
      );
    }

    return (
      <div
        key={row.key}
        className="virtualized-tree-list__row virtualized-tree-list__row--item"
        style={{
          ...style,
          "--virtualized-tree-depth": String(row.depth),
        } as CSSProperties}
        role={rowRole}
      >
        <div className="virtualized-tree-list__item">
          {renderItem({ item: row.item, itemId: row.itemId, depth: row.depth, index: row.index, section: row.section })}
        </div>
      </div>
    );
  }

  if (!visibleSections.length) {
    return emptyState ? <>{emptyState}</> : null;
  }

  if (!supportsVirtualization) {
    return (
      <div className={joinClassNames("virtualized-tree-list__viewport virtualized-tree-list__viewport--static", viewportClassName)} role={containerRole} aria-label={ariaLabel} data-testid={dataTestId}>
        <div className={joinClassNames("virtualized-tree-list__content virtualized-tree-list__content--static", contentClassName)}>
          {flatRows.map((row) => renderRow(row))}
        </div>
      </div>
    );
  }

  return (
    <div ref={parentRef} className={joinClassNames("virtualized-tree-list__viewport", viewportClassName)} role={containerRole} aria-label={ariaLabel} data-testid={dataTestId}>
      <div className={joinClassNames("virtualized-tree-list__content", contentClassName)} style={{ height: `${rowVirtualizer.getTotalSize()}px` }}>
        {rowVirtualizer.getVirtualItems().map((virtualItem) => renderRow(flatRows[virtualItem.index], { transform: `translateY(${virtualItem.start}px)` }))}
      </div>
    </div>
  );
}