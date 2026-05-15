(() => {
  const BASE_GEOMETRY_FIELDS = [
    { key: "x", label: "X", type: "number", min: 0, step: 1 },
    { key: "y", label: "Y", type: "number", min: 0, step: 1 },
    { key: "w", label: "Width", type: "number", min: 0, step: 1 },
    { key: "h", label: "Height", type: "number", min: 0, step: 1 },
  ];

  const BASE_APPEARANCE_FIELDS = [
    {
      key: "styleMode",
      label: "Appearance Source",
      type: "select",
      full: true,
      options: [
        { value: "local", label: "Local widget colors" },
        { value: "shared", label: "Shared style references" },
      ],
    },
    {
      key: "bg",
      label: "Background",
      type: "color",
      disabledWhen(context) {
        return context.node?.styleMode === "shared";
      },
    },
    {
      key: "color",
      label: "Text Color",
      type: "color",
      disabledWhen(context) {
        return context.node?.styleMode === "shared";
      },
    },
    {
      key: "radius",
      label: "Radius",
      type: "number",
      min: 0,
      step: 1,
      full: true,
      disabledWhen(context) {
        return context.node?.styleMode === "shared";
      },
    },
  ];

  const BASE_ACTION_FIELDS = [
    {
      key: "action",
      label: "Action",
      type: "select",
      full: true,
      options: [
        { value: "none", label: "No action" },
        { value: "goto", label: "Go to screen" },
      ],
    },
    {
      key: "targetScreenId",
      label: "Target Screen",
      type: "select",
      full: true,
      disabledWhen(context) {
        return context.node?.action !== "goto";
      },
      options(context) {
        return [
          { value: "", label: "Select target screen" },
          ...(context.state?.screens || [])
            .filter(screen => screen.id !== (context.parentScreen?.id || context.node?.id))
            .map(screen => ({ value: screen.id, label: screen.name })),
        ];
      },
    },
    {
      key: "transition",
      label: "Transition",
      type: "select",
      disabledWhen(context) {
        return context.node?.action !== "goto";
      },
      options() {
        return Object.entries(window.LVGL_SCREEN_TRANSITIONS || {}).map(([key, value]) => ({
          value: key,
          label: value.label,
        }));
      },
    },
    {
      key: "transitionDuration",
      label: "Duration (ms)",
      type: "number",
      min: 0,
      step: 10,
      disabledWhen(context) {
        return context.node?.action !== "goto";
      },
    },
  ];

  const widgetDefinitions = {
    screen: {
      type: "screen",
      label: "Screen",
      allowsAction: false,
      minWidth: 240,
      minHeight: 180,
      create(context) {
        return {
          ...context.createScreenNode(context.presetKey, context.id, context.name),
          text: context.text,
          entryActionName: "",
          nodes: [],
          styleRefs: [],
          styles: {},
        };
      },
      displayLabel(node) {
        return String(node?.name || "screen");
      },
      propertyFields(context) {
        return [
          { key: "name", label: "Name", type: "text", full: true },
          { key: "text", label: "Text / Caption", type: "text", full: true, disabled: true },
          {
            key: "startupScreen",
            label: "Startup Screen",
            type: "readonly",
            full: true,
            value(_, currentContext) {
              return currentContext.state?.startupScreenId === currentContext.node?.id ? "Yes" : "No";
            },
          },
          {
            key: "entryActionName",
            label: "Entry Hook",
            type: "text",
            full: true,
            placeholder(_, currentContext) {
              return `on_enter_${window.lvglCodeSymbol(currentContext.node?.name, "screen")}`;
            },
          },
          ...BASE_GEOMETRY_FIELDS.map(field => ({ ...field, disabled: true })),
          ...BASE_APPEARANCE_FIELDS,
        ];
      },
    },
    container: {
      type: "container",
      label: "Container",
      allowsAction: true,
      minWidth: 120,
      minHeight: 80,
      defaults: {
        w: 220,
        h: 160,
        bg: "#475569",
        color: "#f8fafc",
        radius: 14,
      },
      codegenCtor: "lv_obj_create(screen)",
    },
    panel: {
      type: "panel",
      label: "Panel",
      allowsAction: true,
      minWidth: 140,
      minHeight: 96,
      defaults: {
        w: 240,
        h: 132,
        bg: "#1e293b",
        color: "#f8fafc",
        radius: 14,
      },
      codegenCtor: "lv_obj_create(screen)",
    },
    label: {
      type: "label",
      label: "Label",
      allowsAction: true,
      minWidth: 96,
      minHeight: 28,
      defaults: {
        w: 180,
        h: 44,
        text: "Hello LVGL",
        bg: "#1e293b",
        color: "#f8fafc",
        radius: 14,
      },
      codegenCtor: "lv_label_create(screen)",
      displayLabel(node) {
        return String(node?.text || node?.name || "Label");
      },
      codegenSetup(lines, variableName, node) {
        lines.push(`    lv_label_set_text(${variableName}, ${JSON.stringify(node.text || node.name)});`);
      },
    },
    button: {
      type: "button",
      label: "Button",
      allowsAction: true,
      minWidth: 88,
      minHeight: 36,
      defaults: {
        text: "Tap",
        bg: "#2563eb",
        color: "#f8fafc",
        radius: 14,
      },
      codegenCtor: "lv_btn_create(screen)",
      displayLabel(node) {
        return String(node?.text || "Button");
      },
      eventType() {
        return "LV_EVENT_CLICKED";
      },
      codegenSetup(lines, variableName, node) {
        const labelVar = `${variableName}_label`;
        lines.push(`    lv_obj_t * ${labelVar} = lv_label_create(${variableName});`);
        lines.push(`    lv_label_set_text(${labelVar}, ${JSON.stringify(node.text || "Button")});`);
        lines.push(`    lv_obj_center(${labelVar});`);
      },
    },
    slider: {
      type: "slider",
      label: "Slider",
      allowsAction: true,
      minWidth: 120,
      minHeight: 24,
      defaults: {
        w: 220,
        h: 32,
        text: "0%  -------  100%",
        bg: "#14532d",
        color: "#f8fafc",
        radius: 14,
      },
      codegenCtor: "lv_slider_create(screen)",
      displayLabel(node) {
        return String(node?.text || "Slider");
      },
      eventType() {
        return "LV_EVENT_VALUE_CHANGED";
      },
      codegenSetup(lines, variableName) {
        lines.push(`    lv_slider_set_value(${variableName}, 40, LV_ANIM_OFF);`);
      },
    },
    bar: {
      type: "bar",
      label: "Bar",
      allowsAction: true,
      minWidth: 120,
      minHeight: 20,
      defaults: {
        w: 220,
        h: 26,
        text: "Progress 72%",
        bg: "#7c2d12",
        color: "#f8fafc",
        radius: 14,
      },
      codegenCtor: "lv_bar_create(screen)",
      displayLabel(node) {
        return String(node?.text || "Bar");
      },
      codegenSetup(lines, variableName) {
        lines.push(`    lv_bar_set_value(${variableName}, 72, LV_ANIM_OFF);`);
      },
    },
    image: {
      type: "image",
      label: "Image",
      allowsAction: true,
      minWidth: 64,
      minHeight: 64,
      defaults: {
        w: 140,
        h: 120,
        text: "img_asset",
        bg: "#5b21b6",
        color: "#f8fafc",
        radius: 14,
      },
      codegenCtor: "lv_obj_create(screen)",
      displayLabel(node) {
        return String(node?.text || "Image");
      },
      codegenSetup(lines, variableName, node) {
        lines.push(`    // TODO: replace ${variableName} with lv_img_create(screen) and set source for ${JSON.stringify(node.text || "img_asset")}.`);
      },
    },
  };

  function getWidgetDefinition(type) {
    return widgetDefinitions[type] || widgetDefinitions.container;
  }

  function listWidgetDefinitions() {
    return Object.values(widgetDefinitions);
  }

  function createNode(type, context) {
    const definition = getWidgetDefinition(type);
    const screen = context.screen;
    const offset = Math.max(0, (screen?.nodes?.length || 0)) * 18;
    const centerX = Math.max(12, Math.round(((screen?.w || 320) - 160) / 2));
    const centerY = Math.max(12, Math.round(((screen?.h || 240) - 72) / 2));
    const base = {
      id: context.allocateNodeId(type),
      type,
      name: `${type}_${(screen?.nodes?.length || 0) + 1}`,
      text: definition.label,
      x: centerX + Math.min(offset, 80),
      y: centerY + Math.min(offset, 120),
      w: 160,
      h: 56,
      bg: "#334155",
      color: "#f8fafc",
      radius: 14,
      action: definition.allowsAction ? "none" : undefined,
      targetScreenId: definition.allowsAction ? "" : undefined,
      transition: definition.allowsAction ? "move_left" : undefined,
      transitionDuration: definition.allowsAction ? 220 : undefined,
      styleRefs: [],
      styles: {},
    };
    const created = typeof definition.create === "function"
      ? definition.create({
          ...context,
          id: base.id,
          name: base.name,
          text: base.text,
        })
      : {};
    return {
      ...base,
      ...(definition.defaults || {}),
      ...created,
    };
  }

  function widgetSupportsAction(type) {
    return !!getWidgetDefinition(type).allowsAction;
  }

  function nodeEventType(node) {
    if (!node) return "";
    if (node.action === "goto") return "LV_EVENT_CLICKED";
    const definition = getWidgetDefinition(node.type);
    if (typeof definition.eventType === "function") {
      return definition.eventType(node) || "";
    }
    return "";
  }

  function nodeLabel(node) {
    const definition = getWidgetDefinition(node?.type);
    if (typeof definition.displayLabel === "function") {
      return definition.displayLabel(node);
    }
    return String(node?.name || definition.label || "Widget");
  }

  function widgetCtor(type) {
    return getWidgetDefinition(type).codegenCtor || "lv_obj_create(screen)";
  }

  function widgetCodegenSetup(lines, variableName, node) {
    const definition = getWidgetDefinition(node?.type);
    if (typeof definition.codegenSetup === "function") {
      definition.codegenSetup(lines, variableName, node);
    }
  }

  function widgetPropertyFields() {
    return [
      { key: "name", label: "Name", type: "text", full: true },
      { key: "text", label: "Text / Caption", type: "text", full: true },
      ...BASE_GEOMETRY_FIELDS,
      ...BASE_APPEARANCE_FIELDS,
      ...BASE_ACTION_FIELDS,
    ];
  }

  function getPropertyFields(node, context = {}) {
    const definition = getWidgetDefinition(node?.type);
    if (typeof definition.propertyFields === "function") {
      return definition.propertyFields({ ...context, node });
    }
    return widgetPropertyFields({ ...context, node });
  }

  function fieldOptions(field, context) {
    if (typeof field.options === "function") {
      return field.options(context) || [];
    }
    return Array.isArray(field.options) ? field.options : [];
  }

  function fieldValue(field, context) {
    if (typeof field.value === "function") {
      return field.value(context.node, context);
    }
    return context.node?.[field.key];
  }

  function fieldPlaceholder(field, context) {
    if (typeof field.placeholder === "function") {
      return field.placeholder(context.node, context) || "";
    }
    return field.placeholder || "";
  }

  function isFieldDisabled(field, context) {
    if (field.disabled) return true;
    if (typeof field.disabledWhen === "function") {
      return !!field.disabledWhen(context);
    }
    return false;
  }

  function isFieldVisible(field, context) {
    if (typeof field.visibleWhen === "function") {
      return !!field.visibleWhen(context);
    }
    return true;
  }

  function normalizeFieldValue(field, rawValue) {
    if (field.type === "number") {
      return Number(rawValue) || 0;
    }
    return rawValue;
  }

  window.LvglRegistry = {
    definitions: widgetDefinitions,
    getWidgetDefinition,
    listWidgetDefinitions,
    createNode,
    widgetSupportsAction,
    nodeEventType,
    nodeLabel,
    widgetCtor,
    widgetCodegenSetup,
    getPropertyFields,
    fieldOptions,
    fieldValue,
    fieldPlaceholder,
    isFieldDisabled,
    isFieldVisible,
    normalizeFieldValue,
  };
})();