export interface LegacyPinAltFunctionState {
  function_id: number;
  name: string;
  pincm: number | string;
  peripheral: string;
  signal: string;
  direction: string;
}

export interface LegacyPinState {
  af?: LegacyPinAltFunctionState;
  props?: Record<string, unknown>;
}

export type LegacyPinStateMap = Record<string, LegacyPinState>;

export interface BoardAltFunctionDefinition {
  function_id: number;
  pincm: number | string;
  name: string;
  peripheral: string;
  signal: string;
  direction: string;
  zephyr_pinmux?: string;
}

export interface BoardPinDefinition {
  number: number;
  name: string;
  alt_functions: BoardAltFunctionDefinition[];
}

export interface BoardDefinitionForPinHydration {
  pins: BoardPinDefinition[];
}

export interface RehydratedPinState {
  af?: BoardAltFunctionDefinition;
  props?: Record<string, unknown>;
}

export type RehydratedPinStateMap = Record<string, RehydratedPinState>;
export type PeripheralEnabledStateMap = Record<string, boolean>;
export type PeripheralCoreStateMap = Record<string, string>;

export interface ExternalDeviceSelectionState {
  selected: boolean;
  bus: string;
}

export type ExternalDeviceSelectionStateMap = Record<string, ExternalDeviceSelectionState>;

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function normalizeText(value: unknown, fallback = ""): string {
  if (typeof value === "string") {
    return value;
  }

  if (typeof value === "number" || typeof value === "boolean" || typeof value === "bigint") {
    return String(value);
  }

  return fallback;
}

function pincmMatches(left: number | string, right: number | string): boolean {
  const leftNumber = Number(left);
  const rightNumber = Number(right);

  if (Number.isFinite(leftNumber) && Number.isFinite(rightNumber)) {
    return leftNumber === rightNumber;
  }

  return String(left) === String(right);
}

export function resolveBoardAltFunction(
  pin: BoardPinDefinition,
  state: LegacyPinAltFunctionState,
): BoardAltFunctionDefinition | null {
  return (
    pin.alt_functions.find(
      (candidate) =>
        pincmMatches(candidate.pincm, state.pincm) && candidate.function_id === state.function_id,
    ) ??
    pin.alt_functions.find(
      (candidate) => candidate.peripheral === state.peripheral && candidate.signal === state.signal,
    ) ??
    null
  );
}

export function rehydratePinStatesForBoard(
  pinStates: LegacyPinStateMap,
  board: BoardDefinitionForPinHydration | null | undefined,
): RehydratedPinStateMap {
  if (!board) {
    return {};
  }

  const next: RehydratedPinStateMap = {};

  Object.entries(pinStates).forEach(([pinNumber, state]) => {
    const boardPin = board.pins.find((candidate) => candidate.number === Number(pinNumber));
    if (!boardPin) {
      return;
    }

    const entry: RehydratedPinState = {};

    if (state.af) {
      const resolvedAltFunction = resolveBoardAltFunction(boardPin, state.af);
      if (resolvedAltFunction) {
        entry.af = resolvedAltFunction;
      }
    }

    if (state.props) {
      entry.props = { ...state.props };
    }

    if (entry.af || entry.props) {
      next[pinNumber] = entry;
    }
  });

  return next;
}

export function normalizePinStates(value: unknown): LegacyPinStateMap {
  const source = asRecord(value);
  const next: LegacyPinStateMap = {};

  Object.entries(source).forEach(([pinNumber, stateValue]) => {
    const state = asRecord(stateValue);
    const afSource = asRecord(state.af);
    const propsSource = asRecord(state.props);
    const normalized: LegacyPinState = {};

    if (Object.keys(afSource).length) {
      const rawPincm = afSource.pincm;
      const numericPincm = Number(rawPincm);

      normalized.af = {
        function_id: Number(afSource.function_id ?? 0),
        name: normalizeText(afSource.name),
        pincm: Number.isFinite(numericPincm) ? numericPincm : normalizeText(rawPincm),
        peripheral: normalizeText(afSource.peripheral),
        signal: normalizeText(afSource.signal),
        direction: normalizeText(afSource.direction, "io"),
      };
    }

    if (Object.keys(propsSource).length) {
      normalized.props = { ...propsSource };
    }

    if (normalized.af || normalized.props) {
      next[pinNumber] = normalized;
    }
  });

  return next;
}

export function normalizePeripheralEnabledStates(value: unknown): PeripheralEnabledStateMap {
  const source = asRecord(value);
  const next: PeripheralEnabledStateMap = {};

  Object.entries(source).forEach(([name, enabled]) => {
    next[name] = Boolean(enabled);
  });

  return next;
}

export function normalizePeripheralCoreStates(value: unknown): PeripheralCoreStateMap {
  const source = asRecord(value);
  const next: PeripheralCoreStateMap = {};

  Object.entries(source).forEach(([name, coreId]) => {
    next[name] = normalizeText(coreId);
  });

  return next;
}

export function normalizeExternalDeviceStates(value: unknown): ExternalDeviceSelectionStateMap {
  const source = asRecord(value);
  const next: ExternalDeviceSelectionStateMap = {};

  Object.entries(source).forEach(([deviceId, stateValue]) => {
    const state = asRecord(stateValue);
    next[deviceId] = {
      selected: Boolean(state.selected),
      bus: normalizeText(state.bus),
    };
  });

  return next;
}