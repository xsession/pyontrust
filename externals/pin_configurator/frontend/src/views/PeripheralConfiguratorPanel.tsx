import { useEffect, useState } from "react";
import { EmptyState } from "../shared/ui/feedback/EmptyState";
import { DiagnosticBadge } from "../shared/ui/feedback/DiagnosticBadge";
import { InspectorSection } from "../shared/ui/inspectors/InspectorSection";
import type { PeripheralConfiguratorPresenter } from "../domains/peripherals/peripheralConfiguratorPresenter";
import { VirtualizedTreeList, type VirtualizedTreeListSection } from "../shared/ui/virtualized/VirtualizedTreeList";

interface PeripheralConfiguratorPanelProps {
  presenter: PeripheralConfiguratorPresenter;
}

export function PeripheralConfiguratorPanel({ presenter }: PeripheralConfiguratorPanelProps) {
  const [selectedExternalDeviceId, setSelectedExternalDeviceId] = useState("");

  useEffect(() => {
    setSelectedExternalDeviceId((current) => (presenter.externalDevices.some((device) => device.id === current) ? current : presenter.externalDevices[0]?.id ?? ""));
  }, [presenter, presenter.externalDevices]);

  const selectedExternalDevice = presenter.externalDevices.find((device) => device.id === selectedExternalDeviceId) ?? presenter.externalDevices[0] ?? null;
  const groups = new Map<string, (typeof presenter.externalDevices)[number][]>();
  presenter.externalDevices.forEach((device) => {
    const categoryDevices = groups.get(device.category) ?? [];
    categoryDevices.push(device);
    groups.set(device.category, categoryDevices);
  });
  const externalDeviceSections: VirtualizedTreeListSection<(typeof presenter.externalDevices)[number]>[] = [...groups.entries()].map(([category, devices]) => ({
    id: category,
    label: category,
    items: devices,
    meta: `${devices.length} devices`,
    collapsible: true,
  }));

  return (
    <div className="domain-panel domain-panel--split">
      <InspectorSection
        title="Peripheral enablement"
        summary="Drive canonical peripheral and core selections from the React shell instead of legacy globals."
        actions={<DiagnosticBadge label={`${presenter.enabledPeripheralCount} enabled`} tone="info" />}
      >
        {!presenter.peripherals.length ? <EmptyState title="No board peripherals" detail="Select a board with exported peripheral metadata to edit enablement and core routing." compact /> : null}
        {presenter.peripherals.length ? (
          <ul className="domain-list">
            {presenter.peripherals.map((peripheral) => (
              <li key={peripheral.name} className="domain-list__item">
                <div className="domain-list__header">
                  <div>
                    <strong>{peripheral.display}</strong>
                    <span>{`${peripheral.name} • ${peripheral.compatible}`}</span>
                  </div>
                  <label className="domain-toggle">
                    <input
                      type="checkbox"
                      checked={peripheral.enabled}
                      onChange={(event) => presenter.setPeripheralEnabled(peripheral.name, event.target.checked)}
                    />
                    <span>{peripheral.enabled ? "Enabled" : "Disabled"}</span>
                  </label>
                </div>
                <div className="domain-list__controls">
                  <label className="project-flow__field">
                    <span>Core</span>
                    <select value={peripheral.coreId} onChange={(event) => presenter.setPeripheralCore(peripheral.name, event.target.value)}>
                      {peripheral.availableCores.map((coreId) => (
                        <option key={coreId} value={coreId}>{coreId}</option>
                      ))}
                    </select>
                  </label>
                  <span className="domain-list__meta">{peripheral.signals.length ? peripheral.signals.join(", ") : "No signal metadata"}</span>
                </div>
              </li>
            ))}
          </ul>
        ) : null}
      </InspectorSection>

      <InspectorSection
        title="External devices"
        summary="External device selection now lives in canonical project state so sensor additions can be routed without touching legacy globals."
        actions={<DiagnosticBadge label={`${presenter.selectedExternalDeviceCount} selected`} tone="info" />}
      >
        {!presenter.externalDevices.length ? <EmptyState title="No external devices" detail="Board metadata or imported catalog devices will appear here once available." compact /> : null}
        {presenter.externalDevices.length ? (
          <div className="domain-detail-layout">
            <VirtualizedTreeList
              ariaLabel="External devices"
              sections={externalDeviceSections}
              getItemId={(device) => device.id}
              estimatedRowHeight={96}
              overscan={5}
              viewportClassName="domain-list-viewport"
              renderItem={({ item: device }) => (
                <div className={device.id === selectedExternalDeviceId ? "domain-list__item domain-list__item--selected" : "domain-list__item"}>
                  <button type="button" className="domain-list__select" onClick={() => setSelectedExternalDeviceId(device.id)}>
                    <strong>{device.display}</strong>
                    <span>{`${device.category} • ${device.compatible}`}</span>
                  </button>
                </div>
              )}
            />

            <div className="domain-detail-card">
              {!selectedExternalDevice ? <EmptyState title="No device selected" detail="Select an external device to inspect its bus routing and framework metadata." compact /> : null}
              {selectedExternalDevice ? (
                <>
                  <div className="domain-list__header">
                    <div>
                      <strong>{selectedExternalDevice.display}</strong>
                      <span>{`${selectedExternalDevice.category} • ${selectedExternalDevice.compatible}`}</span>
                    </div>
                    <label className="domain-toggle">
                      <input
                        type="checkbox"
                        checked={selectedExternalDevice.selected}
                        onChange={(event) => presenter.setExternalDeviceSelected(selectedExternalDevice.id, event.target.checked)}
                      />
                      <span>{selectedExternalDevice.selected ? "Selected" : "Idle"}</span>
                    </label>
                  </div>
                  <div className="domain-list__controls">
                    <label className="project-flow__field">
                      <span>Bus</span>
                      <select value={selectedExternalDevice.bus} onChange={(event) => presenter.setExternalDeviceBus(selectedExternalDevice.id, event.target.value)}>
                        {selectedExternalDevice.busOptions.map((option) => (
                          <option key={option} value={option}>{option}</option>
                        ))}
                      </select>
                    </label>
                    <span className="domain-list__meta">{selectedExternalDevice.notes || selectedExternalDevice.frameworks.join(", ") || "No notes"}</span>
                  </div>
                  <dl className="shell-key-values shell-key-values--compact">
                    <div><dt>Frameworks</dt><dd>{selectedExternalDevice.frameworks.join(", ") || "None"}</dd></div>
                    <div><dt>Bus options</dt><dd>{selectedExternalDevice.busOptions.join(", ") || "None"}</dd></div>
                  </dl>
                </>
              ) : null}
            </div>
          </div>
        ) : null}
      </InspectorSection>
    </div>
  );
}