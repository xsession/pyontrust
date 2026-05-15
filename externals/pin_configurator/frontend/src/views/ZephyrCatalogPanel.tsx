import { DiagnosticBadge } from "../shared/ui/feedback/DiagnosticBadge";
import { EmptyState } from "../shared/ui/feedback/EmptyState";
import { InspectorSection } from "../shared/ui/inspectors/InspectorSection";
import { VirtualizedTreeList, type VirtualizedTreeListSection } from "../shared/ui/virtualized/VirtualizedTreeList";
import type { ZephyrCatalogPresenter } from "../domains/catalog/zephyrCatalogPresenter";

interface ZephyrCatalogPanelProps {
  presenter: ZephyrCatalogPresenter;
}

export function ZephyrCatalogPanel({ presenter }: ZephyrCatalogPanelProps) {
  const selectedItem = presenter.selectedItem;
  const sections: VirtualizedTreeListSection<(typeof presenter.visibleItems)[number]>[] = [];
  const pinnedSelection = !presenter.search.trim() && selectedItem && presenter.visibleItems.some((item) => item.key === selectedItem.key)
    ? [selectedItem]
    : [];
  const visibleWithoutPinned = presenter.visibleItems.filter((item) => !pinnedSelection.some((entry) => entry.key === item.key));

  if (pinnedSelection.length) {
    sections.push({
      id: "pinned-selection",
      label: "Pinned selection",
      items: pinnedSelection,
      meta: selectedItem?.kind === "mcu" ? "MCU" : "Sensor",
    });
  }

  const mcuItems = visibleWithoutPinned.filter((item) => item.kind === "mcu");
  const sensorItems = visibleWithoutPinned.filter((item) => item.kind === "sensor");

  sections.push({ id: "mcus", label: "MCUs", items: mcuItems, meta: `${mcuItems.length} boards`, collapsible: true });
  sections.push({ id: "sensors", label: "Sensors", items: sensorItems, meta: `${sensorItems.length} bindings`, collapsible: true });

  return (
    <div className="domain-panel domain-panel--split">
      <InspectorSection
        title="Zephyr catalog"
        summary="MCU boards and sensor bindings now load through a typed service and presenter instead of the legacy tab runtime."
        actions={<DiagnosticBadge label={presenter.loading ? "Loading" : `${presenter.items.length} items`} tone={presenter.loading ? "warning" : "info"} />}
      >
        <div className="catalog-toolbar">
          <label className="project-flow__field">
            <span>Zephyr root</span>
            <input type="text" value={presenter.root} onChange={(event) => presenter.setRoot(event.target.value)} placeholder="C:/zephyr" />
          </label>
          <button type="button" className="shell-button" onClick={() => presenter.refresh(true)} disabled={presenter.loading}>
            Refresh
          </button>
        </div>
        <div className="catalog-toolbar">
          <label className="project-flow__field">
            <span>Filter</span>
            <select value={presenter.filter} onChange={(event) => presenter.setFilter(event.target.value as typeof presenter.filter)}>
              <option value="all">All</option>
              <option value="mcu">MCUs</option>
              <option value="sensor">Sensors</option>
            </select>
          </label>
          <label className="project-flow__field">
            <span>Search</span>
            <input type="search" value={presenter.search} onChange={(event) => presenter.setSearch(event.target.value)} placeholder="Search name, compatible, bus, or SoC" />
          </label>
        </div>
        <p className="domain-summary-text">{presenter.summaryText}</p>
        {presenter.error ? <EmptyState title="Catalog unavailable" detail={presenter.error} tone="error" compact /> : null}
        {!presenter.error ? (
          <VirtualizedTreeList
            ariaLabel="Zephyr catalog results"
            sections={sections}
            getItemId={(item) => item.key}
            estimatedRowHeight={96}
            overscan={5}
            viewportClassName="domain-list-viewport"
            emptyState={<EmptyState title="No catalog items" detail="Adjust the current filter or search to reveal matching Zephyr boards and sensors." compact />}
            renderItem={({ item }) => (
              <div className={item.key === presenter.selectedKey ? "domain-list__item domain-list__item--selected" : "domain-list__item"}>
                <button type="button" className="domain-list__select" onClick={() => presenter.selectItem(item.key)}>
                  <strong>{item.label || item.name}</strong>
                  <span>{item.kind === "mcu" ? `${item.vendor || "vendor"} • ${item.name}` : `${item.compatible} • ${item.buses.join(", ") || "bus n/a"}`}</span>
                </button>
              </div>
            )}
          />
        ) : null}
      </InspectorSection>

      <InspectorSection
        title={selectedItem ? selectedItem.label || selectedItem.name : "Catalog detail"}
        summary="Selection detail stays docked so catalog-driven actions can feed the migrated domains without jumping back to the legacy tab strip."
      >
        {!selectedItem ? <EmptyState title="No catalog selection" detail="Select an MCU board or sensor binding to inspect its parameters and route it into the active workflow." compact /> : null}
        {selectedItem ? (
          <div className="catalog-detail">
            <div className="catalog-detail__chips">
              {(selectedItem.kind === "mcu" ? selectedItem.socs : selectedItem.buses).map((entry) => (
                <span key={entry} className="catalog-chip">{entry}</span>
              ))}
            </div>
            <div className="catalog-detail__actions">
              <button type="button" className="shell-button" onClick={() => presenter.useInPinConfigurator(selectedItem)}>
                {selectedItem.kind === "mcu" ? "Use In Pin Configurator" : "Add To Pin Configurator"}
              </button>
              {selectedItem.kind === "mcu" ? (
                <button type="button" className="shell-button shell-button--ghost" onClick={() => presenter.useInPackageManager(selectedItem)}>
                  Use In Package Manager
                </button>
              ) : (
                <button type="button" className="shell-button shell-button--ghost" onClick={() => presenter.useInSensorParser(selectedItem)}>
                  Use In Sensor Parser
                </button>
              )}
            </div>
            <dl className="shell-key-values shell-key-values--compact">
              <div>
                <dt>Kind</dt>
                <dd>{selectedItem.kind}</dd>
              </div>
              <div>
                <dt>Vendor</dt>
                <dd>{selectedItem.vendor || "n/a"}</dd>
              </div>
              <div>
                <dt>{selectedItem.kind === "mcu" ? "Board file" : "Compatible"}</dt>
                <dd>{selectedItem.kind === "mcu" ? selectedItem.board_path : selectedItem.compatible}</dd>
              </div>
            </dl>
            {selectedItem.kind === "sensor" ? (
              <div className="catalog-detail__table">
                <table>
                  <tbody>
                    {selectedItem.properties.slice(0, 18).map((property) => (
                      <tr key={property.name}>
                        <th>{property.name}</th>
                        <td>{`${property.type}${property.required ? " • required" : ""}${property.description ? ` • ${property.description}` : ""}`}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
        ) : null}
      </InspectorSection>
    </div>
  );
}