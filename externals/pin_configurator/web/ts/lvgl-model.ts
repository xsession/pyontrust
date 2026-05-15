type RawLayoutState = Partial<LayoutState> & {
  nodes?: LayoutNode[];
};

(() => {
  const FALLBACK_PRESETS: Record<string, LayoutPreset> = {
    phone: { width: 360, height: 640, label: "Phone 360 x 640" },
    dashboard: { width: 480, height: 272, label: "Dashboard 480 x 272" },
    watch: { width: 240, height: 240, label: "Watch 240 x 240" },
    panel: { width: 800, height: 480, label: "Panel 800 x 480" },
  };
  const STYLE_SCHEMA: StyleSchema = {
    version: 1,
    parts: ["LV_PART_MAIN", "LV_PART_INDICATOR", "LV_PART_KNOB", "LV_PART_ITEMS"],
    states: ["default", "pressed", "focused", "checked", "disabled"],
    properties: [
      { key: "bg", lvgl: "bg_color", type: "color" },
      { key: "color", lvgl: "text_color", type: "color" },
      { key: "radius", lvgl: "radius", type: "number" },
    ],
  };
  const C_RESERVED_IDENTIFIERS = new Set([
    "auto", "break", "case", "char", "const", "continue", "default", "do", "double", "else", "enum", "extern",
    "float", "for", "goto", "if", "inline", "int", "long", "register", "restrict", "return", "short", "signed",
    "sizeof", "static", "struct", "switch", "typedef", "union", "unsigned", "void", "volatile", "while",
    "_alignas", "_alignof", "_atomic", "_bool", "_complex", "_generic", "_imaginary", "_noreturn", "_static_assert",
    "_thread_local", "alignas", "alignof", "bool", "false", "nullptr", "thread_local", "true",
  ]);

  function preset(presetKey: string): LayoutPreset {
    const presets = window.LVGL_LAYOUT_PRESETS || FALLBACK_PRESETS;
    return presets[presetKey] || presets.phone || FALLBACK_PRESETS.phone;
  }

  function createScreenNode(presetKey: string, id = "screen_root", name = "screen_main"): ScreenNode {
    const targetPreset = preset(presetKey);
    return {
      id,
      type: "screen",
      name,
      text: "Main Screen",
      x: 0,
      y: 0,
      w: targetPreset.width,
      h: targetPreset.height,
      bg: "#0f172a",
      color: "#f8fafc",
      radius: 24,
      entryActionName: "",
      styleRefs: [],
      styles: {},
      nodes: [],
    };
  }

  function defaultState(): LayoutState {
    return {
      preset: "phone",
      currentScreenId: "screen_root",
      startupScreenId: "screen_root",
      selectedId: "screen_root",
      selectedIds: ["screen_root"],
      selectedStyleId: "",
      code: "",
      styleSchemaVersion: STYLE_SCHEMA.version,
      sharedStyles: [],
      simulation: {
        running: false,
        activeScreenId: "screen_root",
        log: ["Simulation is idle."],
      },
      screens: [createScreenNode("phone")],
    };
  }

  function normalizeStyleRefs(value: unknown): string[] {
    return Array.isArray(value)
      ? value.map((entry) => String(entry || "").trim()).filter(Boolean)
      : [];
  }

  function normalizeNode(node: Partial<LayoutNode> = {}, isScreen: boolean): LayoutNode {
    const supportsAction = Boolean(window.LvglRegistry?.widgetSupportsAction?.(node?.type));
    return {
      ...(node as LayoutNode),
      id: String(node.id || ""),
      type: String(node.type || "widget"),
      name: String(node.name || ""),
      text: node.text == null ? undefined : String(node.text),
      x: Number(node.x) || 0,
      y: Number(node.y) || 0,
      w: Number(node.w) || 0,
      h: Number(node.h) || 0,
      bg: node.bg == null ? undefined : String(node.bg),
      color: node.color == null ? undefined : String(node.color),
      radius: Number(node.radius) || 0,
      entryActionName: isScreen ? String(node.entryActionName || "") : undefined,
      action: supportsAction ? String(node.action || "none") : undefined,
      targetScreenId: supportsAction ? String(node.targetScreenId || "") : undefined,
      transition: supportsAction ? String(node.transition || "move_left") : undefined,
      transitionDuration: supportsAction ? Math.max(0, Number(node.transitionDuration) || 220) : undefined,
      styleMode: String(node.styleMode || "local"),
      styleRefs: normalizeStyleRefs(node.styleRefs),
      styles: node.styles && typeof node.styles === "object" ? node.styles : {},
    };
  }

  function normalizeState(rawState: RawLayoutState | null | undefined, helpers: LayoutHelpers): LayoutState {
    let state: LayoutState | RawLayoutState = rawState || defaultState();
    const legacyNodes = (state as RawLayoutState).nodes;

    if (Array.isArray(legacyNodes) && legacyNodes.length) {
      const root = normalizeNode(helpers.cloneJson(legacyNodes[0]), true) as ScreenNode;
      const screenId = root.id || "screen_root";
      state = {
        preset: state.preset || "phone",
        currentScreenId: screenId,
        startupScreenId: screenId,
        selectedId: state.selectedId || screenId,
        selectedIds: Array.isArray(state.selectedIds) && state.selectedIds.length ? state.selectedIds : [state.selectedId || screenId],
        selectedStyleId: String(state.selectedStyleId || ""),
        code: state.code || "",
        styleSchemaVersion: STYLE_SCHEMA.version,
        sharedStyles: [],
        simulation: {
          running: false,
          activeScreenId: screenId,
          log: ["Simulation is idle."],
        },
        screens: [{
          ...root,
          nodes: helpers.cloneJson(legacyNodes.slice(1)).map((node: LayoutNode) => normalizeNode(node, false)),
        }],
      };
    } else if (!Array.isArray(state.screens) || !state.screens.length) {
      state = defaultState();
    }

    const normalizedState = state as LayoutState;

    if (!normalizedState.simulation) {
      normalizedState.simulation = {
        running: false,
        activeScreenId: normalizedState.currentScreenId || normalizedState.screens[0].id,
        log: ["Simulation is idle."],
      };
    }
    if (!normalizedState.currentScreenId) {
      normalizedState.currentScreenId = normalizedState.screens[0].id;
    }
    if (!normalizedState.startupScreenId || !normalizedState.screens.some((screen) => screen.id === normalizedState.startupScreenId)) {
      normalizedState.startupScreenId = normalizedState.screens[0].id;
    }
    if (!normalizedState.selectedId) {
      normalizedState.selectedId = normalizedState.currentScreenId;
    }
    normalizedState.selectedIds = Array.isArray(normalizedState.selectedIds)
      ? [...new Set(normalizedState.selectedIds.map((entry) => String(entry || "").trim()).filter(Boolean))]
      : [normalizedState.selectedId];
    if (!normalizedState.selectedIds.length) {
      normalizedState.selectedIds = [normalizedState.selectedId];
    }
    if (!normalizedState.selectedIds.includes(normalizedState.selectedId)) {
      normalizedState.selectedIds = [
        normalizedState.selectedId,
        ...normalizedState.selectedIds.filter((entry) => entry !== normalizedState.selectedId),
      ];
    }
    normalizedState.selectedStyleId = String(normalizedState.selectedStyleId || "");

    normalizedState.styleSchemaVersion = STYLE_SCHEMA.version;
    normalizedState.sharedStyles = Array.isArray(normalizedState.sharedStyles)
      ? normalizedState.sharedStyles
          .map((style) => ({
            id: String(style.id || "").trim(),
            name: String(style.name || style.id || "").trim(),
            part: String(style.part || "LV_PART_MAIN"),
            state: String(style.state || "default"),
            values: style.values && typeof style.values === "object" ? style.values : {},
          }))
          .filter((style) => style.id)
      : [];

    normalizedState.screens = normalizedState.screens.map((screen) => ({
      ...normalizeNode(screen, true),
      type: "screen",
      entryActionName: String(screen.entryActionName || ""),
      styleRefs: normalizeStyleRefs(screen.styleRefs),
      styles: screen.styles && typeof screen.styles === "object" ? screen.styles : {},
      nodes: (screen.nodes || []).map((node) => normalizeNode(node, false)),
    }));

    return normalizedState;
  }

  function codegenSymbol(name: string, fallback = "node"): string {
    if (window.lvglCodeSymbol) {
      return window.lvglCodeSymbol(name, fallback);
    }
    const raw = String(name || fallback)
      .trim()
      .replace(/[^a-zA-Z0-9_]+/g, "_")
      .replace(/^_+/, "");
    const normalized = raw || fallback;
    return /^[A-Za-z_]/.test(normalized) ? normalized : `_${normalized}`;
  }

  function validateState(state: LayoutState): ValidationIssue[] {
    const issues: ValidationIssue[] = [];
    const screens = state.screens || [];
    const screenIds = new Set<string>();
    const screenIdList = new Set<string>();
    const screenNames = new Map<string, string>();
    const sharedStyleIds = new Set<string>();
    const sharedStyleNames = new Map<string, string>();
    const sharedStyleUsage = new Map<string, number>();
    const widgetIds = new Set<string>();
    const screenInboundTargets = new Set<string>();
    const validStyleParts = new Set(STYLE_SCHEMA.parts.map((entry) => String(entry || "").trim().toUpperCase()));
    const validStyleStates = new Set(STYLE_SCHEMA.states.map((entry) => String(entry || "").trim().toLowerCase()));
    const generatedSymbols = new Map<string, { label: string; issueId: string; scope: ValidationIssue["scope"] }>();

    const normalizeStylePart = (value: string): string => {
      const normalized = String(value || "").trim().toUpperCase();
      if (!normalized) {
        return normalized;
      }
      return normalized.startsWith("LV_PART_") ? normalized : `LV_PART_${normalized}`;
    };

    const normalizeStyleState = (value: string): string => String(value || "").trim().toLowerCase();
    const nodeLabel = (node: LayoutNode): string => String(node.name || node.id || node.type || "Widget").trim() || "Widget";
    const screenLabel = (screen: ScreenNode): string => String(screen.name || screen.id || "screen").trim() || "screen";
    const recordGeneratedSymbol = (scope: ValidationIssue["scope"], issueId: string, label: string, symbol: string): void => {
      const normalized = String(symbol || "").trim();
      if (!normalized) {
        return;
      }
      const existing = generatedSymbols.get(normalized);
      if (existing) {
        issues.push({
          severity: "error",
          scope,
          id: issueId,
          message: `${label} collides with ${existing.label} after C symbol normalization (${normalized}).`,
        });
        return;
      }
      generatedSymbols.set(normalized, { label, issueId, scope });
    };
    const validateReservedSymbol = (scope: ValidationIssue["scope"], issueId: string, label: string, symbol: string): void => {
      const normalized = String(symbol || "").trim().toLowerCase();
      if (C_RESERVED_IDENTIFIERS.has(normalized)) {
        issues.push({
          severity: "warning",
          scope,
          id: issueId,
          message: `${label} normalizes to reserved C identifier ${symbol}.`,
        });
      }
    };

    if (!screens.length) {
      issues.push({ severity: "error", scope: "screen", id: "no-screens", message: "The layout has no screens." });
      return issues;
    }

    screens.forEach((screen) => {
      if (screen.id) {
        screenIdList.add(screen.id);
      }
    });

    (state.sharedStyles || []).forEach((style) => {
      if (!style.id) {
        issues.push({ severity: "error", scope: "style", id: "missing-style-id", message: "A shared style is missing its ID." });
      } else if (sharedStyleIds.has(style.id)) {
        issues.push({ severity: "error", scope: "style", id: style.id, message: `Duplicate shared style ID ${style.id}.` });
      } else {
        sharedStyleIds.add(style.id);
        sharedStyleUsage.set(style.id, 0);
      }

      const normalizedStyleName = String(style.name || "").trim().toLowerCase();
      if (!normalizedStyleName) {
        issues.push({ severity: "warning", scope: "style", id: style.id || "style", message: "A shared style has no name." });
      } else if (sharedStyleNames.has(normalizedStyleName)) {
        issues.push({ severity: "warning", scope: "style", id: style.id || normalizedStyleName, message: `Shared style name ${style.name} is duplicated.` });
      } else {
        sharedStyleNames.set(normalizedStyleName, style.id || normalizedStyleName);
      }

      if (!validStyleParts.has(normalizeStylePart(style.part))) {
        issues.push({ severity: "warning", scope: "style", id: style.id || style.name || "style", message: `Shared style ${style.name || style.id || "style"} uses unknown LVGL part ${style.part}.` });
      }
      if (!validStyleStates.has(normalizeStyleState(style.state))) {
        issues.push({ severity: "warning", scope: "style", id: style.id || style.name || "style", message: `Shared style ${style.name || style.id || "style"} uses unknown LVGL state ${style.state}.` });
      }

      const styleSymbol = codegenSymbol(style.name || style.id, `style_${style.id || "shared"}`);
      validateReservedSymbol("style", style.id || style.name || "style", `Shared style ${style.name || style.id || "style"}`, styleSymbol);
    });

    screens.forEach((screen) => {
      const screenSymbol = codegenSymbol(screen.name, "screen");
      if (!screen.id) {
        issues.push({ severity: "error", scope: "screen", id: "missing-screen-id", message: "A screen is missing its ID." });
      } else if (screenIds.has(screen.id)) {
        issues.push({ severity: "error", scope: "screen", id: screen.id, message: `Duplicate screen ID ${screen.id}.` });
      } else {
        screenIds.add(screen.id);
      }

      const normalizedName = String(screen.name || "").trim().toLowerCase();
      if (normalizedName) {
        if (screenNames.has(normalizedName)) {
          issues.push({ severity: "warning", scope: "screen", id: screen.id, message: `Screen name ${screen.name} is duplicated.` });
        } else {
          screenNames.set(normalizedName, screen.id);
        }
      }

      if (!String(screen.name || "").trim()) {
        issues.push({ severity: "warning", scope: "screen", id: screen.id || "screen", message: "A screen has no name." });
      }
      if ((Number(screen.w) || 0) <= 0 || (Number(screen.h) || 0) <= 0) {
        issues.push({ severity: "error", scope: "screen", id: screen.id || screen.name || "screen", message: `Screen ${screenLabel(screen)} has invalid dimensions ${screen.w}x${screen.h}.` });
      }
      validateReservedSymbol("screen", screen.id || screen.name || "screen", `Screen ${screenLabel(screen)}`, screenSymbol);
      recordGeneratedSymbol("screen", screen.id || screen.name || "screen", `screen ${screenLabel(screen)}`, `ui_build_${screenSymbol}`);
      recordGeneratedSymbol("screen", screen.id || screen.name || "screen", `screen loader ${screenLabel(screen)}`, `ui_load_${screenSymbol}`);
      recordGeneratedSymbol("screen", screen.id || screen.name || "screen", `screen accessor ${screenLabel(screen)}`, `ui_get_${screenSymbol}`);
      recordGeneratedSymbol("screen", screen.id || screen.name || "screen", `screen storage ${screenLabel(screen)}`, `g_ui_${screenSymbol}`);

      if (String(screen.entryActionName || "").trim()) {
        const entryHookSymbol = codegenSymbol(screen.entryActionName || "", `on_enter_${screenSymbol}`);
        validateReservedSymbol("screen", screen.id || screen.name || "screen", `Entry hook for ${screenLabel(screen)}`, entryHookSymbol);
        recordGeneratedSymbol("screen", screen.id || screen.name || "screen", `entry hook for ${screenLabel(screen)}`, entryHookSymbol);
      }

      (screen.styleRefs || []).forEach((ref) => {
        if (!sharedStyleIds.has(ref)) {
          issues.push({ severity: "warning", scope: "style", id: screen.id || "screen", message: `Screen ${screenLabel(screen)} references unknown shared style ${ref}.` });
          return;
        }
        sharedStyleUsage.set(ref, (sharedStyleUsage.get(ref) || 0) + 1);
      });

      const widgetNames = new Set<string>();
      (screen.nodes || []).forEach((node) => {
        const widgetSymbol = codegenSymbol(node.name, node.type || "widget");
        if (!node.id) {
          issues.push({ severity: "error", scope: "widget", id: "missing-widget-id", message: `A widget on ${screenLabel(screen)} is missing its ID.` });
        } else if (widgetIds.has(node.id)) {
          issues.push({ severity: "error", scope: "widget", id: node.id, message: `Duplicate widget ID ${node.id}.` });
        } else {
          widgetIds.add(node.id);
        }

        if (!String(node.name || "").trim()) {
          issues.push({ severity: "warning", scope: "widget", id: node.id || screen.id || "widget", message: `A ${node.type || "widget"} on ${screenLabel(screen)} has no name.` });
        }

        const scopedName = String(node.name || "").trim().toLowerCase();
        if (scopedName && widgetNames.has(scopedName)) {
          issues.push({ severity: "warning", scope: "widget", id: node.id, message: `Widget name ${node.name} is duplicated on ${screen.name}.` });
        } else if (scopedName) {
          widgetNames.add(scopedName);
        }

        if ((Number(node.w) || 0) <= 0 || (Number(node.h) || 0) <= 0) {
          issues.push({ severity: "error", scope: "widget", id: node.id || node.name || "widget", message: `${nodeLabel(node)} has invalid dimensions ${node.w}x${node.h}.` });
        }
        if ((Number(node.x) || 0) < 0 || (Number(node.y) || 0) < 0) {
          issues.push({ severity: "warning", scope: "widget", id: node.id || node.name || "widget", message: `${nodeLabel(node)} is positioned outside the top-left bounds of ${screenLabel(screen)}.` });
        }
        if ((Number(node.x) || 0) + (Number(node.w) || 0) > (Number(screen.w) || 0) || (Number(node.y) || 0) + (Number(node.h) || 0) > (Number(screen.h) || 0)) {
          issues.push({ severity: "warning", scope: "widget", id: node.id || node.name || "widget", message: `${nodeLabel(node)} extends beyond the bounds of ${screenLabel(screen)}.` });
        }
        validateReservedSymbol("widget", node.id || node.name || "widget", `Widget ${nodeLabel(node)}`, widgetSymbol);
        recordGeneratedSymbol("widget", node.id || node.name || "widget", `widget accessor ${nodeLabel(node)}`, `ui_get_${screenSymbol}_${widgetSymbol}`);
        recordGeneratedSymbol("widget", node.id || node.name || "widget", `widget storage ${nodeLabel(node)}`, `g_ui_${screenSymbol}_${widgetSymbol}`);

        if (window.LvglRegistry?.widgetSupportsAction?.(node.type) && node.action === "goto" && !node.targetScreenId) {
          issues.push({ severity: "warning", scope: "widget", id: node.id, message: `${nodeLabel(node)} triggers screen navigation but has no target screen.` });
        }
        if (node.targetScreenId && !screenIdList.has(node.targetScreenId)) {
          issues.push({ severity: "warning", scope: "widget", id: node.id, message: `${nodeLabel(node)} references missing target screen ${node.targetScreenId}.` });
        } else if (node.action === "goto" && node.targetScreenId) {
          screenInboundTargets.add(node.targetScreenId);
          if (node.targetScreenId === screen.id) {
            issues.push({ severity: "info", scope: "widget", id: node.id, message: `${nodeLabel(node)} navigates back to its current screen ${screenLabel(screen)}.` });
          }
        }

        if (window.LvglRegistry?.widgetSupportsAction?.(node.type) && node.action === "none" && node.targetScreenId) {
          issues.push({ severity: "info", scope: "widget", id: node.id, message: `${nodeLabel(node)} defines a target screen but its action is disabled.` });
        }
        if ((Number(node.transitionDuration) || 0) < 0) {
          issues.push({ severity: "warning", scope: "widget", id: node.id, message: `${nodeLabel(node)} uses a negative transition duration.` });
        }
        if (window.LvglRegistry?.nodeEventType?.(node)) {
          recordGeneratedSymbol("widget", node.id || node.name || "widget", `widget event hook ${nodeLabel(node)}`, `ui_on_${screenSymbol}_${widgetSymbol}_event`);
        }
        (node.styleRefs || []).forEach((ref) => {
          if (!sharedStyleIds.has(ref)) {
            issues.push({ severity: "warning", scope: "style", id: node.id, message: `${nodeLabel(node)} references unknown shared style ${ref}.` });
            return;
          }
          sharedStyleUsage.set(ref, (sharedStyleUsage.get(ref) || 0) + 1);
        });
        if (node.styleMode === "shared" && !(node.styleRefs || []).length) {
          issues.push({ severity: "warning", scope: "style", id: node.id, message: `${nodeLabel(node)} is set to shared style mode but has no shared style assigned.` });
        } else if (node.styleMode !== "shared" && (node.styleRefs || []).length) {
          issues.push({ severity: "info", scope: "style", id: node.id, message: `${nodeLabel(node)} has shared styles attached but is still using local styling mode.` });
        }
        if (node.type === "image" && (!node.text || node.text === "img_asset")) {
          issues.push({ severity: "info", scope: "widget", id: node.id, message: `${nodeLabel(node)} still uses the placeholder image asset name.` });
        }
      });
    });

    if (!screens.some((screen) => screen.id === state.startupScreenId)) {
      issues.push({ severity: "error", scope: "screen", id: "startup", message: "Startup screen does not exist in the layout." });
    }

    screens.forEach((screen) => {
      if (screen.id !== state.startupScreenId && !screenInboundTargets.has(screen.id)) {
        issues.push({ severity: "info", scope: "screen", id: screen.id, message: `Screen ${screen.name || screen.id} has no inbound navigation path.` });
      }
    });

    (state.sharedStyles || []).forEach((style) => {
      if (style.id && !sharedStyleUsage.get(style.id)) {
        issues.push({ severity: "info", scope: "style", id: style.id, message: `Shared style ${style.name || style.id} is defined but unused.` });
      }
      if (style.id && sharedStyleUsage.get(style.id)) {
        const styleSymbol = codegenSymbol(style.name || style.id, `style_${style.id}`);
        recordGeneratedSymbol("style", style.id, `shared style ${style.name || style.id}`, styleSymbol);
      }
    });

    return issues;
  }

  function buildValidationReport(state: LayoutState, issues: ValidationIssue[]): string {
    const bySeverity = {
      error: issues.filter((issue) => issue.severity === "error"),
      warning: issues.filter((issue) => issue.severity === "warning"),
      info: issues.filter((issue) => issue.severity === "info"),
    };
    const scopeCounts = issues.reduce<Record<string, number>>((acc, issue) => {
      acc[issue.scope] = (acc[issue.scope] || 0) + 1;
      return acc;
    }, {});
    const lines = [
      "# LVGL Layout Validation",
      "",
      `- Screens: ${(state.screens || []).length}`,
      `- Shared styles: ${(state.sharedStyles || []).length}`,
      `- Style schema version: ${STYLE_SCHEMA.version}`,
      `- Issues: ${issues.length}`,
      `- Errors: ${bySeverity.error.length}`,
      `- Warnings: ${bySeverity.warning.length}`,
      `- Info: ${bySeverity.info.length}`,
      "",
      "## Shared Style Schema",
      "",
      `- Parts: ${STYLE_SCHEMA.parts.join(", ")}`,
      `- States: ${STYLE_SCHEMA.states.join(", ")}`,
      `- Properties: ${STYLE_SCHEMA.properties.map((entry) => `${entry.key} -> ${entry.lvgl}`).join(", ")}`,
      "",
      "## Scope Summary",
      "",
      ...(Object.keys(scopeCounts).length
        ? Object.entries(scopeCounts).sort((left, right) => left[0].localeCompare(right[0])).map(([scope, count]) => `- ${scope}: ${count}`)
        : ["- No scoped findings."]),
      "",
      "## Findings",
      "",
    ];

    if (!issues.length) {
      lines.push("- No validation issues detected.");
      return lines.join("\n");
    }

    issues.forEach((issue) => {
      lines.push(`- [${issue.severity}] ${issue.message}`);
    });
    return lines.join("\n");
  }

  function findSharedStyle(state: LayoutState, styleId: string): SharedStyle | null {
    return (state.sharedStyles || []).find((style) => style.id === styleId) || null;
  }

  function resolveAppliedStyles(state: LayoutState, node?: LayoutNode | null): SharedStyle[] {
    return (node?.styleRefs || [])
      .map((styleId) => findSharedStyle(state, styleId))
      .filter((style): style is SharedStyle => style !== null);
  }

  function resolveNodeVisual(state: LayoutState, node?: LayoutNode | null): { bg: string; color: string; radius: number } {
    const base = {
      bg: node?.bg || "#334155",
      color: node?.color || "#f8fafc",
      radius: Number(node?.radius) || 14,
    };
    if (!node || node.styleMode !== "shared") {
      return base;
    }
    const applicable = resolveAppliedStyles(state, node)
      .filter((style) => style.part === "LV_PART_MAIN" && style.state === "default");
    if (!applicable.length) {
      return base;
    }
    const mergedValues = applicable.reduce<Record<string, unknown>>((acc, style) => ({
      ...acc,
      ...(style.values || {}),
    }), {});
    return {
      bg: String(mergedValues.bg || base.bg),
      color: String(mergedValues.color || base.color),
      radius: Number.isFinite(Number(mergedValues.radius)) ? Number(mergedValues.radius) : base.radius,
    };
  }

  const LvglModel: LvglModelApi = {
    STYLE_SCHEMA,
    preset,
    createScreenNode,
    defaultState,
    normalizeState,
    validateState,
    buildValidationReport,
    findSharedStyle,
    resolveAppliedStyles,
    resolveNodeVisual,
  };

  window.LvglModel = LvglModel;
})();
