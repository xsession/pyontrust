interface LayoutPreset {
  width: number;
  height: number;
  label: string;
}

interface StyleSchemaProperty {
  key: string;
  lvgl: string;
  type: "color" | "number";
}

interface StyleSchema {
  version: number;
  parts: string[];
  states: string[];
  properties: StyleSchemaProperty[];
}

interface SharedStyle {
  id: string;
  name: string;
  part: string;
  state: string;
  values: Record<string, unknown>;
}

interface SimulationState {
  running: boolean;
  activeScreenId: string;
  log: string[];
}

interface LayoutNode {
  id: string;
  type: string;
  name: string;
  text?: string;
  x: number;
  y: number;
  w: number;
  h: number;
  bg?: string;
  color?: string;
  radius?: number;
  entryActionName?: string;
  action?: string;
  targetScreenId?: string;
  transition?: string;
  transitionDuration?: number;
  styleMode?: string;
  styleRefs?: string[];
  styles?: Record<string, unknown>;
}

interface ScreenNode extends LayoutNode {
  nodes: LayoutNode[];
}

interface LayoutState {
  preset: string;
  currentScreenId: string;
  startupScreenId: string;
  selectedId: string;
  selectedIds: string[];
  selectedStyleId: string;
  code: string;
  styleSchemaVersion: number;
  sharedStyles: SharedStyle[];
  simulation: SimulationState;
  screens: ScreenNode[];
}

interface ValidationIssue {
  severity: "error" | "warning" | "info";
  scope: string;
  id: string;
  message: string;
}

interface LayoutHelpers {
  cloneJson<T>(value: T): T;
}

interface LvglRegistryApi {
  widgetSupportsAction?: (type?: string) => boolean;
  nodeEventType?: (node: LayoutNode) => string;
  widgetCtor?: (type: string) => string;
  widgetCodegenSetup?: (lines: string[], varName: string, node: LayoutNode) => void;
  nodeLabel?: (node?: LayoutNode | null) => string;
}

interface LvglModelApi {
  STYLE_SCHEMA: StyleSchema;
  preset: (presetKey: string) => LayoutPreset;
  createScreenNode: (presetKey: string, id?: string, name?: string) => ScreenNode;
  defaultState: () => LayoutState;
  normalizeState: (rawState: RawLayoutState | null | undefined, helpers: LayoutHelpers) => LayoutState;
  validateState: (state: LayoutState) => ValidationIssue[];
  buildValidationReport: (state: LayoutState, issues: ValidationIssue[]) => string;
  findSharedStyle: (state: LayoutState, styleId: string) => SharedStyle | null;
  resolveAppliedStyles: (state: LayoutState, node?: LayoutNode | null) => SharedStyle[];
  resolveNodeVisual: (state: LayoutState, node?: LayoutNode | null) => {
    bg: string;
    color: string;
    radius: number;
  };
}

interface LvglNodeLookup {
  screen: ScreenNode;
  node: LayoutNode | ScreenNode;
  isScreen: boolean;
}

interface LvglUiApi {
  addLog?: (message: string) => unknown;
  renderSimLog?: () => unknown;
  renderTree?: () => unknown;
  renderStage?: () => unknown;
  renderProps?: () => unknown;
  render?: () => unknown;
  resetLayout?: () => unknown;
  applyPreset?: (presetKey: string) => unknown;
  addWidget?: (type: string) => unknown;
  serializeState?: () => LayoutState;
  restoreState?: (nextState: Partial<LayoutState>, options?: Record<string, unknown>) => unknown;
  init?: () => unknown;
}

interface Window {
  LVGL_LAYOUT_PRESETS?: Record<string, LayoutPreset>;
  LvglRegistry?: LvglRegistryApi;
  LvglModel?: LvglModelApi;
  LvglUi?: LvglUiApi;
  $?: (selector: string) => HTMLElement | null;
  cloneJson: <T>(value: T) => T;
  escapeHtml: (value: unknown) => string;
  lvglEnsureState: () => LayoutState;
  lvglFindNode: (nodeId: string) => LvglNodeLookup | null;
  lvglSelectedNode: () => LayoutNode | ScreenNode | null;
  lvglSyncGeneratedOutputs: (rebuildCode?: boolean) => void;
  lvglClampNode: (node: LayoutNode, screen?: ScreenNode | null) => void;
  lvglAllocateNodeId: (prefix: string) => string;
  lvglCurrentDesignScreen: () => ScreenNode | null;
  lvglDefaultState: () => LayoutState;
  lvglLayoutState: Partial<LayoutState> & { nodes?: LayoutNode[] };
  lvglLayoutNextId: number;
}
