import type { BoardDefinition, BoardExternalDevice, ZephyrCatalogSensorItem } from "../../contracts/api";
import type { ProjectShellController } from "../../project/useProjectShellController";

export interface PeripheralCommandApi {
  setPeripheralEnabled: (peripheral: string, enabled: boolean) => void;
  setPeripheralCore: (peripheral: string, coreId: string) => void;
  setExternalDeviceSelected: (deviceId: string, selected: boolean) => void;
  setExternalDeviceBus: (deviceId: string, bus: string) => void;
  importCatalogSensor: (item: ZephyrCatalogSensorItem) => void;
}

export interface PeripheralRowViewModel {
  name: string;
  display: string;
  compatible: string;
  enabled: boolean;
  coreId: string;
  availableCores: string[];
  signals: string[];
}

export interface ExternalDeviceRowViewModel {
  id: string;
  display: string;
  category: string;
  compatible: string;
  selected: boolean;
  bus: string;
  busOptions: string[];
  frameworks: string[];
  notes: string;
}

export interface PeripheralConfiguratorPresenter extends PeripheralCommandApi {
  peripherals: PeripheralRowViewModel[];
  externalDevices: ExternalDeviceRowViewModel[];
  enabledPeripheralCount: number;
  selectedExternalDeviceCount: number;
}

type PeripheralPresenterInput = Pick<
  ProjectShellController,
  | "activeBoardDefinition"
  | "projectDocument"
  | "setPeripheralEnabled"
  | "setPeripheralCore"
  | "setExternalDeviceSelected"
  | "setExternalDeviceBus"
>;

function normalizeBusFamily(value: string): string {
  const match = value.trim().toLowerCase().match(/^[a-z]+/);
  return match?.[0] ?? "";
}

function synthesizeCatalogDevice(item: ZephyrCatalogSensorItem): BoardExternalDevice {
  const compatible = item.compatible || item.name || item.label;
  const busFamily = item.buses[0] || "i2c";

  return {
    id: `zephyr_${compatible.replace(/[^a-zA-Z0-9]+/g, "_").toLowerCase()}`,
    display: item.label || item.name || compatible,
    category: "sensor",
    bus: `${busFamily}0`,
    compatible,
    address: "",
    required_signals: [],
    frameworks: ["zephyr"],
    notes: item.description || item.binding_paths[0] || compatible,
  };
}

function buildExternalDeviceRows(
  boardDefinition: BoardDefinition | null,
  projectDocument: ProjectShellController["projectDocument"],
): ExternalDeviceRowViewModel[] {
  const boardDevices = new Map((boardDefinition?.external_devices ?? []).map((device) => [device.id, device]));

  Object.keys(projectDocument.external_device_states).forEach((deviceId) => {
    if (boardDevices.has(deviceId)) {
      return;
    }

    const state = projectDocument.external_device_states[deviceId];
    boardDevices.set(deviceId, {
      id: deviceId,
      display: deviceId,
      category: "external",
      bus: state?.bus || "",
      compatible: deviceId,
      address: "",
      required_signals: [],
      frameworks: [],
      notes: "Imported from canonical external device state.",
    });
  });

  const peripherals = boardDefinition?.peripherals ?? [];

  return [...boardDevices.values()]
    .map((device) => {
      const state = projectDocument.external_device_states[device.id];
      const busFamily = normalizeBusFamily(state?.bus || device.bus);
      const busOptions = peripherals
        .filter((peripheral) => normalizeBusFamily(peripheral.name) === busFamily)
        .map((peripheral) => peripheral.name);
      const resolvedBusOptions = [...new Set([state?.bus || "", device.bus, ...busOptions].filter(Boolean))];

      return {
        id: device.id,
        display: device.display,
        category: device.category,
        compatible: device.compatible,
        selected: state?.selected ?? false,
        bus: state?.bus || device.bus,
        busOptions: resolvedBusOptions,
        frameworks: device.frameworks,
        notes: device.notes,
      } satisfies ExternalDeviceRowViewModel;
    })
    .sort((left, right) => left.display.localeCompare(right.display));
}

export function createPeripheralConfiguratorPresenter({
  activeBoardDefinition,
  projectDocument,
  setPeripheralEnabled,
  setPeripheralCore,
  setExternalDeviceSelected,
  setExternalDeviceBus,
}: PeripheralPresenterInput): PeripheralConfiguratorPresenter {
  const peripherals = (activeBoardDefinition?.peripherals ?? [])
    .map((peripheral) => ({
      name: peripheral.name,
      display: peripheral.display,
      compatible: peripheral.compatible,
      enabled: projectDocument.periph_states[peripheral.name] ?? peripheral.enabled,
      coreId: projectDocument.periph_core_states[peripheral.name] ?? peripheral.core_id,
      availableCores: peripheral.available_cores,
      signals: peripheral.signals,
    }))
    .sort((left, right) => left.display.localeCompare(right.display));

  const externalDevices = buildExternalDeviceRows(activeBoardDefinition, projectDocument);

  return {
    peripherals,
    externalDevices,
    enabledPeripheralCount: peripherals.filter((peripheral) => peripheral.enabled).length,
    selectedExternalDeviceCount: externalDevices.filter((device) => device.selected).length,
    setPeripheralEnabled,
    setPeripheralCore,
    setExternalDeviceSelected,
    setExternalDeviceBus,
    importCatalogSensor(item) {
      const device = synthesizeCatalogDevice(item);
      setExternalDeviceSelected(device.id, true);
      setExternalDeviceBus(device.id, device.bus);
    },
  };
}