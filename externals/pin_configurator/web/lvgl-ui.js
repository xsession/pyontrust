"use strict";
// @ts-nocheck
(() => {
    const HISTORY_LIMIT = 80;
    const PASTE_OFFSET = 16;
    const historyState = {
        undoStack: [],
        redoStack: [],
        isApplying: false,
    };
    let dragStartSnapshot = null;
    let widgetClipboard = null;
    let treeFilter = "";
    let styleFilter = "";
    let validationSeverityFilter = "all";
    let validationScopeFilter = "all";
    let validationSearchFilter = "";
    let suppressClickUntil = 0;
    const MIN_ZOOM = 0.4;
    const MAX_ZOOM = 2.5;
    const ZOOM_STEP = 0.1;
    const canvasView = {
        zoom: 1,
        panX: 0,
        panY: 0,
        tool: "select",
        snap: true,
        guides: [],
    };
    function escapeNodeLabel(node) {
        return window.escapeHtml(window.LvglRegistry?.nodeLabel(node) || node?.name || "widget");
    }
    function serializeStateForHistory() {
        return window.cloneJson(window.lvglEnsureState());
    }
    function snapshotsEqual(left, right) {
        return JSON.stringify(left) === JSON.stringify(right);
    }
    function isLvglTabActive() {
        return !!document.querySelector('.tab-content[data-app-content="lvgl-layout"].active');
    }
    function updateHistoryButtons() {
        const undoBtn = window.$("#lvglBtnUndo");
        const redoBtn = window.$("#lvglBtnRedo");
        const copyBtn = window.$("#lvglBtnCopy");
        const pasteBtn = window.$("#lvglBtnPaste");
        const duplicateBtn = window.$("#lvglBtnDuplicate");
        const selectedNodes = selectedWidgetNodes();
        if (undoBtn)
            undoBtn.disabled = historyState.undoStack.length === 0;
        if (redoBtn)
            redoBtn.disabled = historyState.redoStack.length === 0;
        if (copyBtn)
            copyBtn.disabled = selectedNodes.length !== 1;
        if (duplicateBtn)
            duplicateBtn.disabled = selectedNodes.length !== 1;
        if (pasteBtn)
            pasteBtn.disabled = !widgetClipboard;
    }
    function selectedIds(state = window.lvglEnsureState()) {
        const ids = Array.isArray(state.selectedIds) ? state.selectedIds.filter(Boolean) : [];
        return ids.length ? ids : (state.selectedId ? [state.selectedId] : []);
    }
    function syncSelectionState(state, nextIds, primaryId = "") {
        const normalized = [...new Set((nextIds || []).map(entry => String(entry || "").trim()).filter(Boolean))];
        const fallback = primaryId || normalized[0] || state.currentScreenId || state.screens?.[0]?.id || "screen_root";
        state.selectedId = fallback;
        state.selectedIds = normalized.length
            ? [fallback, ...normalized.filter(entry => entry !== fallback)]
            : [fallback];
    }
    function selectedNodeEntries(state = window.lvglEnsureState()) {
        return selectedIds(state)
            .map(id => window.lvglFindNode(id))
            .filter((entry) => !!entry);
    }
    function selectedWidgetNodes(state = window.lvglEnsureState()) {
        return selectedNodeEntries(state)
            .filter(entry => !entry.isScreen)
            .map(entry => entry.node);
    }
    function nodeIsSelected(state, nodeId) {
        return selectedIds(state).includes(nodeId);
    }
    function setSingleSelection(state, nodeId) {
        const found = window.lvglFindNode(nodeId);
        if (found?.isScreen) {
            state.currentScreenId = nodeId;
        }
        syncSelectionState(state, [nodeId], nodeId);
    }
    function toggleWidgetSelection(state, nodeId) {
        const found = window.lvglFindNode(nodeId);
        if (!found || found.isScreen) {
            setSingleSelection(state, nodeId);
            return;
        }
        const current = selectedIds(state).filter(id => {
            const entry = window.lvglFindNode(id);
            return entry && !entry.isScreen && entry.screen.id === found.screen.id;
        });
        const exists = current.includes(nodeId);
        const next = exists ? current.filter(id => id !== nodeId) : [...current, nodeId];
        syncSelectionState(state, next.length ? next : [nodeId], nodeId);
    }
    function recordHistorySnapshot(snapshot) {
        if (!snapshot || historyState.isApplying)
            return;
        historyState.undoStack.push(window.cloneJson(snapshot));
        if (historyState.undoStack.length > HISTORY_LIMIT) {
            historyState.undoStack.shift();
        }
        historyState.redoStack = [];
        updateHistoryButtons();
    }
    function resetHistory() {
        historyState.undoStack = [];
        historyState.redoStack = [];
        updateHistoryButtons();
    }
    function applyMutation(mutator, options = {}) {
        const before = serializeStateForHistory();
        mutator(window.lvglEnsureState());
        const after = serializeStateForHistory();
        if (snapshotsEqual(before, after))
            return;
        if (options.history !== false) {
            recordHistorySnapshot(before);
        }
        if (options.logMessage) {
            addLog(options.logMessage);
        }
        window.lvglSyncGeneratedOutputs(options.rebuildCode !== false);
        render();
    }
    function restoreStateInternal(nextState, options = {}) {
        historyState.isApplying = true;
        try {
            if (!nextState || !Array.isArray(nextState.nodes) || !nextState.nodes.length) {
                window.lvglLayoutState = window.cloneJson(nextState || window.lvglDefaultState());
            }
            else {
                window.lvglLayoutState = window.cloneJson(nextState);
            }
            window.lvglEnsureState();
            if (options.logMessage) {
                addLog(options.logMessage);
            }
            const ids = [];
            window.lvglLayoutState.screens.forEach((screen) => {
                ids.push(screen.id);
                (screen.nodes || []).forEach((node) => ids.push(node.id));
            });
            window.lvglLayoutNextId = Math.max(1, ...ids.map(id => {
                const match = String(id || "").match(/_(\d+)$/);
                return match ? Number(match[1]) + 1 : 1;
            }));
            window.lvglSyncGeneratedOutputs(!window.lvglLayoutState.code || options.rebuildCode !== false);
            render();
            if (!options.preserveHistory) {
                resetHistory();
            }
            else {
                updateHistoryButtons();
            }
        }
        finally {
            historyState.isApplying = false;
        }
    }
    function undo() {
        if (!historyState.undoStack.length)
            return;
        const current = serializeStateForHistory();
        const previous = historyState.undoStack.pop();
        historyState.redoStack.push(current);
        restoreStateInternal(previous, { preserveHistory: true });
    }
    function redo() {
        if (!historyState.redoStack.length)
            return;
        const current = serializeStateForHistory();
        const next = historyState.redoStack.pop();
        historyState.undoStack.push(current);
        restoreStateInternal(next, { preserveHistory: true });
    }
    function handleKeyboardShortcuts(event) {
        if (!isLvglTabActive())
            return;
        const target = event.target;
        if (target instanceof HTMLElement && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) {
            return;
        }
        if ((event.ctrlKey || event.metaKey) && !event.shiftKey && event.key.toLowerCase() === "z") {
            event.preventDefault();
            undo();
            return;
        }
        if ((event.ctrlKey || event.metaKey) && !event.shiftKey && event.key.toLowerCase() === "c") {
            event.preventDefault();
            copySelectedWidget();
            return;
        }
        if ((event.ctrlKey || event.metaKey) && !event.shiftKey && event.key.toLowerCase() === "v") {
            event.preventDefault();
            pasteClipboard();
            return;
        }
        if ((event.ctrlKey || event.metaKey) && !event.shiftKey && event.key.toLowerCase() === "d") {
            event.preventDefault();
            duplicateSelectedWidget();
            return;
        }
        if ((event.ctrlKey || event.metaKey) && (event.key.toLowerCase() === "y" || (event.shiftKey && event.key.toLowerCase() === "z"))) {
            event.preventDefault();
            redo();
            return;
        }
        if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.key)) {
            const moveNodes = selectedWidgetNodes();
            if (!moveNodes.length)
                return;
            const distance = event.shiftKey ? 10 : 1;
            applyMutation(() => {
                moveNodes.forEach(target => {
                    const found = window.lvglFindNode(target.id);
                    if (!found?.node || found.isScreen)
                        return;
                    if (event.key === "ArrowUp")
                        found.node.y -= distance;
                    if (event.key === "ArrowDown")
                        found.node.y += distance;
                    if (event.key === "ArrowLeft")
                        found.node.x -= distance;
                    if (event.key === "ArrowRight")
                        found.node.x += distance;
                    window.lvglClampNode(found.node, found.screen);
                });
            }, { rebuildCode: true, logMessage: `Nudged ${moveNodes.length > 1 ? `${moveNodes.length} widgets` : moveNodes[0].name}` });
            event.preventDefault();
        }
    }
    function clipboardSourceNode() {
        const node = window.lvglSelectedNode();
        if (!node || node.type === "screen")
            return null;
        return node;
    }
    function normalizeNameBase(name, type) {
        const raw = String(name || type || "widget").trim();
        return raw.replace(/_\d+$/, "") || type || "widget";
    }
    function uniqueWidgetName(state, type, preferredName) {
        const names = new Set((state.screens || []).flatMap(screen => [
            screen.name,
            ...((screen.nodes || []).map(node => node.name)),
        ]).filter(Boolean));
        const base = normalizeNameBase(preferredName, type);
        if (!names.has(base))
            return base;
        let index = 1;
        while (names.has(`${base}_${index}`)) {
            index += 1;
        }
        return `${base}_${index}`;
    }
    function createWidgetClone(state, sourceNode, screen, options = {}) {
        if (!sourceNode || sourceNode.type === "screen")
            return null;
        const clone = window.cloneJson(sourceNode);
        clone.id = window.lvglAllocateNodeId(clone.type || "widget");
        clone.name = uniqueWidgetName(state, clone.type, options.name || clone.name || clone.type);
        clone.x = Number(clone.x) || 0;
        clone.y = Number(clone.y) || 0;
        const offset = Number(options.offset ?? PASTE_OFFSET) || 0;
        clone.x += offset;
        clone.y += offset;
        clone.styleRefs = Array.isArray(clone.styleRefs) ? [...clone.styleRefs] : [];
        window.lvglClampNode(clone, screen);
        return clone;
    }
    function copySelectedWidget() {
        const node = clipboardSourceNode();
        if (!node)
            return false;
        widgetClipboard = window.cloneJson(node);
        updateHistoryButtons();
        addLog(`Copied ${node.name}`);
        renderSimLog();
        return true;
    }
    function pasteClipboard() {
        if (!widgetClipboard)
            return false;
        let pastedName = "widget";
        applyMutation((state) => {
            const screen = window.lvglCurrentDesignScreen();
            if (!screen)
                return;
            const clone = createWidgetClone(state, widgetClipboard, screen);
            if (!clone)
                return;
            screen.nodes.push(clone);
            syncSelectionState(state, [clone.id], clone.id);
            pastedName = clone.name;
        }, { rebuildCode: true, logMessage: `Pasted ${pastedName}` });
        return true;
    }
    function duplicateSelectedWidget() {
        const node = clipboardSourceNode();
        if (!node)
            return false;
        let duplicateName = node.name;
        applyMutation((state) => {
            const found = window.lvglFindNode(node.id);
            const screen = state.screens.find(entry => entry.id === found?.screen?.id) || window.lvglCurrentDesignScreen();
            if (!screen)
                return;
            const currentNode = (screen.nodes || []).find(entry => entry.id === node.id);
            const clone = createWidgetClone(state, currentNode, screen);
            if (!clone)
                return;
            screen.nodes.push(clone);
            syncSelectionState(state, [clone.id], clone.id);
            duplicateName = clone.name;
            widgetClipboard = window.cloneJson(clone);
        }, { rebuildCode: true, logMessage: `Duplicated ${duplicateName}` });
        return true;
    }
    function nextStyleId(state) {
        const numericIds = (state.sharedStyles || []).map(style => {
            const match = String(style.id || "").match(/style_(\d+)$/);
            return match ? Number(match[1]) : 0;
        });
        return `style_${Math.max(0, ...numericIds) + 1}`;
    }
    function selectedStyle(state) {
        return window.LvglModel?.findSharedStyle(state, state.selectedStyleId) || null;
    }
    function ensureSelectedStyle(state) {
        if (state.selectedStyleId && selectedStyle(state))
            return selectedStyle(state);
        state.selectedStyleId = state.sharedStyles?.[0]?.id || "";
        return selectedStyle(state);
    }
    function addLog(message) {
        const state = window.lvglEnsureState();
        const log = Array.isArray(state.simulation.log) ? state.simulation.log : [];
        log.unshift(message);
        state.simulation.log = log.slice(0, 8);
    }
    function renderSimLog() {
        const logEl = window.$("#lvglSimLog");
        if (!logEl)
            return;
        const state = window.lvglEnsureState();
        const entries = Array.isArray(state.simulation.log) && state.simulation.log.length
            ? state.simulation.log
            : ["Simulation is idle."];
        logEl.innerHTML = entries.map(entry => `<div class="lvgl-layout-simlog-entry">${window.escapeHtml(entry)}</div>`).join("");
    }
    function renderValidation() {
        const summaryEl = window.$("#lvglValidationSummary");
        const listEl = window.$("#lvglValidationList");
        const searchFilterEl = window.$("#lvglValidationSearch");
        const severityFilterEl = window.$("#lvglValidationSeverityFilter");
        const scopeFilterEl = window.$("#lvglValidationScopeFilter");
        const applyRenamesBtn = window.$("#lvglBtnApplyValidationRenames");
        const resetFiltersBtn = window.$("#lvglBtnResetValidationFilters");
        if (!summaryEl || !listEl || !searchFilterEl || !severityFilterEl || !scopeFilterEl || !applyRenamesBtn || !resetFiltersBtn)
            return;
        const state = window.lvglEnsureState();
        const issues = window.LvglModel?.validateState(state) || [];
        const severityCounts = issues.reduce((acc, issue) => {
            acc[issue.severity] = (acc[issue.severity] || 0) + 1;
            return acc;
        }, { error: 0, warning: 0, info: 0 });
        searchFilterEl.value = validationSearchFilter;
        const styleIds = new Set((state.sharedStyles || []).map(style => style.id));
        const scopeLabel = (scope) => ({ screen: "Screen", widget: "Widget", style: "Style" }[scope] || "Layout");
        const targetForIssue = (issue) => {
            if (issue.scope === "style" && styleIds.has(issue.id)) {
                const style = (state.sharedStyles || []).find(entry => entry.id === issue.id);
                return {
                    kind: "style",
                    id: issue.id,
                    label: style?.name ? `Focus shared style ${style.name}` : `Focus shared style ${issue.id}`,
                };
            }
            const found = issue.id ? window.lvglFindNode(issue.id) : null;
            if (found) {
                return {
                    kind: found.isScreen ? "screen" : "node",
                    id: found.node.id,
                    label: found.isScreen
                        ? `Focus screen ${found.node.name || found.node.id}`
                        : `Focus ${found.node.name || found.node.id} on ${found.screen.name || found.screen.id}`,
                };
            }
            return null;
        };
        const validationGroupForIssue = (issue) => {
            const target = targetForIssue(issue);
            if (target) {
                return {
                    key: `${target.kind}:${target.id}`,
                    title: target.label,
                    meta: `${scopeLabel(issue.scope)} target`,
                };
            }
            if (issue.id) {
                return {
                    key: `${issue.scope}:${issue.id}`,
                    title: `${scopeLabel(issue.scope)} ${issue.id}`,
                    meta: "Unresolved target",
                };
            }
            return {
                key: `${issue.scope}:unscoped:${issue.message}`,
                title: `${scopeLabel(issue.scope)} findings`,
                meta: "General layout issue",
            };
        };
        const filteredIssues = issues.filter((issue) => {
            const severityMatch = validationSeverityFilter === "all" || issue.severity === validationSeverityFilter;
            const scopeMatch = validationScopeFilter === "all" || issue.scope === validationScopeFilter;
            const target = targetForIssue(issue);
            const searchHaystack = [
                issue.message,
                issue.severity,
                issue.scope,
                scopeLabel(issue.scope),
                target?.label || "",
            ].join(" ").toLowerCase();
            const searchMatch = !validationSearchFilter || searchHaystack.includes(validationSearchFilter);
            return severityMatch && scopeMatch && searchMatch;
        });
        severityFilterEl.value = validationSeverityFilter;
        scopeFilterEl.value = validationScopeFilter;
        resetFiltersBtn.disabled = validationSeverityFilter === "all" && validationScopeFilter === "all" && !validationSearchFilter;
        const renameSuggestions = filteredIssues.reduce((acc, issue) => {
            const found = issue.id ? window.lvglFindNode(issue.id) : null;
            const style = issue.scope === "style" && styleIds.has(issue.id)
                ? (state.sharedStyles || []).find((entry) => entry.id === issue.id)
                : null;
            const suggestion = renameSuggestionForIssue(state, issue, found, style);
            if (!suggestion)
                return acc;
            const key = `${issue.scope}:${issue.id || "layout"}:${suggestion.label}`;
            if (!acc.some((entry) => entry.key === key)) {
                acc.push({ key, issue, label: suggestion.label });
            }
            return acc;
        }, []);
        applyRenamesBtn.disabled = !renameSuggestions.length;
        applyRenamesBtn.textContent = renameSuggestions.length
            ? `Apply ${renameSuggestions.length} rename fix${renameSuggestions.length === 1 ? "" : "es"}`
            : "Apply Rename Fixes";
        const summaryBadges = [
            `<span class="lvgl-layout-validation-badge${issues.length ? "" : " sev-info"}">${filteredIssues.length} of ${issues.length} findings</span>`,
            `<span class="lvgl-layout-validation-badge sev-error">${severityCounts.error} errors</span>`,
            `<span class="lvgl-layout-validation-badge sev-warning">${severityCounts.warning} warnings</span>`,
            `<span class="lvgl-layout-validation-badge sev-info">${severityCounts.info} info</span>`,
        ];
        summaryEl.innerHTML = summaryBadges.join("");
        if (!issues.length) {
            listEl.innerHTML = '<div class="lvgl-layout-empty compact">No validation findings. The current layout looks structurally consistent for generation.</div>';
            return;
        }
        if (!filteredIssues.length) {
            listEl.innerHTML = '<div class="lvgl-layout-empty compact">No validation findings match the active filters. Clear filters to see all findings again.</div>';
            return;
        }
        const groupedIssues = filteredIssues.reduce((groups, issue) => {
            const group = validationGroupForIssue(issue);
            const existing = groups.find((entry) => entry.key === group.key);
            if (existing) {
                existing.items.push(issue);
            }
            else {
                groups.push({ ...group, items: [issue] });
            }
            return groups;
        }, []);
        let issueCounter = 0;
        listEl.innerHTML = groupedIssues.map((group) => {
            const severities = group.items.reduce((acc, issue) => {
                acc[issue.severity] = (acc[issue.severity] || 0) + 1;
                return acc;
            }, {});
            const severityLabel = Object.entries(severities)
                .map(([severity, count]) => `${count} ${severity}`)
                .join(" • ");
            const itemsMarkup = group.items.map((issue) => {
                const severity = issue.severity || "info";
                const found = issue.id ? window.lvglFindNode(issue.id) : null;
                const style = issue.scope === "style" && styleIds.has(issue.id)
                    ? (state.sharedStyles || []).find((entry) => entry.id === issue.id)
                    : null;
                const target = targetForIssue(issue);
                const renameAction = renameSuggestionForIssue(state, issue, found, style);
                const currentIndex = issueCounter;
                issueCounter += 1;
                return `
          <div class="lvgl-layout-validation-item sev-${severity}${target ? " actionable" : ""}">
            <div class="lvgl-layout-validation-meta">
              <span>${severity}</span>
              <span>${scopeLabel(issue.scope)}</span>
              <span>#${currentIndex + 1}</span>
            </div>
            <div class="lvgl-layout-validation-message">${window.escapeHtml(issue.message)}</div>
            ${(target || renameAction) ? `
              <div class="lvgl-layout-validation-actions">
                ${target ? `<button type="button" class="lvgl-layout-validation-action-btn" data-lvgl-validation-kind="${target.kind}" data-lvgl-validation-id="${window.escapeHtml(target.id)}">${window.escapeHtml(target.label)}</button>` : ""}
                ${renameAction ? `<button type="button" class="lvgl-layout-validation-action-btn rename" data-lvgl-validation-rename="${currentIndex}">${window.escapeHtml(renameAction.label)}</button>` : ""}
              </div>
            ` : ""}
          </div>
        `;
            }).join("");
            return `
        <div class="lvgl-layout-validation-group">
          <div class="lvgl-layout-validation-group-head">
            <div class="lvgl-layout-validation-group-title">${window.escapeHtml(group.title)}</div>
            <div class="lvgl-layout-validation-group-meta">${window.escapeHtml(group.meta)} • ${window.escapeHtml(severityLabel || `${group.items.length} findings`)}</div>
          </div>
          <div class="lvgl-layout-validation-group-items">
            ${itemsMarkup}
          </div>
        </div>
      `;
        }).join("");
        listEl.querySelectorAll("[data-lvgl-validation-kind][data-lvgl-validation-id]").forEach(item => {
            item.addEventListener("click", () => {
                const kind = item.dataset.lvglValidationKind;
                const targetId = item.dataset.lvglValidationId;
                const nextState = window.lvglEnsureState();
                if (!targetId)
                    return;
                if (kind === "style") {
                    nextState.selectedStyleId = targetId;
                    renderProps();
                    return;
                }
                const found = window.lvglFindNode(targetId);
                if (!found)
                    return;
                nextState.currentScreenId = found.screen.id;
                syncSelectionState(nextState, [found.node.id], found.node.id);
                render();
            });
        });
        listEl.querySelectorAll("[data-lvgl-validation-rename]").forEach(item => {
            item.addEventListener("click", (event) => {
                event.stopPropagation();
                const issueIndex = Number(item.dataset.lvglValidationRename);
                const issue = filteredIssues[issueIndex];
                if (!issue)
                    return;
                applyMutation((draftState) => {
                    const draftFound = issue.id ? window.lvglFindNode(issue.id) : null;
                    const draftStyle = issue.scope === "style" && styleIds.has(issue.id)
                        ? (draftState.sharedStyles || []).find((entry) => entry.id === issue.id)
                        : null;
                    const suggestion = renameSuggestionForIssue(draftState, issue, draftFound, draftStyle);
                    suggestion?.apply?.();
                }, { rebuildCode: true, logMessage: `Applied rename suggestion for finding #${issueIndex + 1}` });
            });
        });
    }
    function applyVisibleRenameSuggestions() {
        const state = window.lvglEnsureState();
        const styleIds = new Set((state.sharedStyles || []).map(style => style.id));
        const visibleIssues = (window.LvglModel?.validateState(state) || []).filter((issue) => {
            const severityMatch = validationSeverityFilter === "all" || issue.severity === validationSeverityFilter;
            const scopeMatch = validationScopeFilter === "all" || issue.scope === validationScopeFilter;
            const target = issue.id
                ? (issue.scope === "style" && styleIds.has(issue.id)
                    ? { label: ((state.sharedStyles || []).find((entry) => entry.id === issue.id)?.name || issue.id) }
                    : (() => {
                        const found = window.lvglFindNode(issue.id);
                        return found ? { label: found.isScreen ? (found.node.name || found.node.id) : `${found.node.name || found.node.id} ${found.screen.name || found.screen.id}` } : null;
                    })())
                : null;
            const searchHaystack = [
                issue.message,
                issue.severity,
                issue.scope,
                target?.label || "",
            ].join(" ").toLowerCase();
            const searchMatch = !validationSearchFilter || searchHaystack.includes(validationSearchFilter);
            return severityMatch && scopeMatch && searchMatch;
        });
        const suggestions = visibleIssues.reduce((acc, issue) => {
            const found = issue.id ? window.lvglFindNode(issue.id) : null;
            const style = issue.scope === "style" && styleIds.has(issue.id)
                ? (state.sharedStyles || []).find((entry) => entry.id === issue.id)
                : null;
            const suggestion = renameSuggestionForIssue(state, issue, found, style);
            if (!suggestion)
                return acc;
            const key = `${issue.scope}:${issue.id || "layout"}:${suggestion.label}`;
            if (!acc.some((entry) => entry.key === key)) {
                acc.push({ key, issue });
            }
            return acc;
        }, []);
        if (!suggestions.length)
            return;
        applyMutation((draftState) => {
            suggestions.forEach(({ issue }) => {
                const draftStyleIds = new Set((draftState.sharedStyles || []).map((style) => style.id));
                const draftFound = issue.id ? window.lvglFindNode(issue.id) : null;
                const draftStyle = issue.scope === "style" && draftStyleIds.has(issue.id)
                    ? (draftState.sharedStyles || []).find((entry) => entry.id === issue.id)
                    : null;
                const suggestion = renameSuggestionForIssue(draftState, issue, draftFound, draftStyle);
                suggestion?.apply?.();
            });
        }, {
            rebuildCode: true,
            logMessage: `Applied ${suggestions.length} validation rename fix${suggestions.length === 1 ? "" : "es"}`,
        });
    }
    function resolveSearchInput(id, totalCount, currentFilter) {
        const input = window.$(id);
        if (!input)
            return currentFilter;
        const visible = totalCount > 5;
        input.hidden = !visible;
        if (!visible) {
            if (input.value)
                input.value = "";
            return "";
        }
        const normalized = String(currentFilter || "").trim().toLowerCase();
        if (input.value.trim().toLowerCase() !== normalized) {
            input.value = normalized;
        }
        return normalized;
    }
    function clampZoom(value) {
        return Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, Number(value) || 1));
    }
    function updateCanvasChrome() {
        const viewport = window.$("#lvglStageViewport");
        const wrap = window.$(".lvgl-layout-canvas-wrap");
        const zoomLabel = window.$("#lvglZoomLevel");
        const selectBtn = window.$("#lvglBtnSelectTool");
        const handBtn = window.$("#lvglBtnHandTool");
        const snapBtn = window.$("#lvglBtnSnapToggle");
        if (viewport) {
            viewport.style.transform = `translate(${canvasView.panX}px, ${canvasView.panY}px) scale(${canvasView.zoom})`;
        }
        if (wrap) {
            wrap.classList.toggle("hand-tool", canvasView.tool === "hand");
            wrap.classList.toggle("panning", window.lvglLayoutDrag?.mode === "pan");
        }
        if (zoomLabel) {
            zoomLabel.textContent = `${Math.round(canvasView.zoom * 100)}%`;
        }
        if (selectBtn) {
            selectBtn.classList.toggle("active", canvasView.tool === "select");
        }
        if (handBtn) {
            handBtn.classList.toggle("active", canvasView.tool === "hand");
        }
        if (snapBtn) {
            snapBtn.classList.toggle("active", canvasView.snap);
            snapBtn.textContent = canvasView.snap ? "Snap On" : "Snap Off";
        }
    }
    function stagePointFromEvent(event, stageEl) {
        const rect = stageEl.getBoundingClientRect();
        return {
            x: (event.clientX - rect.left) / canvasView.zoom,
            y: (event.clientY - rect.top) / canvasView.zoom,
        };
    }
    function resizeNodeWithHandle(node, screen, dragState, event) {
        const deltaX = (event.clientX - dragState.startClientX) / canvasView.zoom;
        const deltaY = (event.clientY - dragState.startClientY) / canvasView.zoom;
        let nextX = dragState.startX;
        let nextY = dragState.startY;
        let nextW = dragState.startW;
        let nextH = dragState.startH;
        const handle = dragState.handle || "se";
        if (handle.includes("e")) {
            nextW = dragState.startW + deltaX;
        }
        if (handle.includes("s")) {
            nextH = dragState.startH + deltaY;
        }
        if (handle.includes("w")) {
            nextW = dragState.startW - deltaX;
            nextX = dragState.startX + deltaX;
        }
        if (handle.includes("n")) {
            nextH = dragState.startH - deltaY;
            nextY = dragState.startY + deltaY;
        }
        nextW = Math.max(36, Math.round(nextW));
        nextH = Math.max(24, Math.round(nextH));
        nextX = Math.round(nextX);
        nextY = Math.round(nextY);
        if (nextX < 0) {
            nextW += nextX;
            nextX = 0;
        }
        if (nextY < 0) {
            nextH += nextY;
            nextY = 0;
        }
        nextW = Math.max(36, Math.min(screen.w - nextX, nextW));
        nextH = Math.max(24, Math.min(screen.h - nextY, nextH));
        node.x = nextX;
        node.y = nextY;
        node.w = nextW;
        node.h = nextH;
        window.lvglClampNode(node, screen);
    }
    function updateQuickStyleBar() {
        const state = window.lvglEnsureState();
        const node = window.lvglSelectedNode();
        const selectedLocalNodes = selectedWidgetNodes(state).filter(entry => entry.styleMode !== "shared");
        const bgInput = window.$("#lvglQuickStyleBg");
        const colorInput = window.$("#lvglQuickStyleColor");
        const radiusInput = window.$("#lvglQuickStyleRadius");
        const hint = window.$("#lvglQuickStyleHint");
        if (!bgInput || !colorInput || !radiusInput || !hint)
            return;
        const editable = (!!node && node.styleMode !== "shared") || selectedLocalNodes.length > 1;
        const visual = node ? (window.LvglModel?.resolveNodeVisual(state, node) || node) : null;
        bgInput.disabled = !editable;
        colorInput.disabled = !editable;
        radiusInput.disabled = !editable;
        bgInput.value = visual?.bg || "#334155";
        colorInput.value = visual?.color || "#f8fafc";
        radiusInput.value = Number(node?.radius ?? visual?.radius ?? 14) || 0;
        if (!node) {
            hint.textContent = "Select a locally styled widget to edit fill, text, and radius directly from the canvas toolbar.";
            return;
        }
        if (selectedLocalNodes.length > 1) {
            hint.textContent = `Editing ${selectedLocalNodes.length} selected widgets together. Drag any selected widget to move the group or resize from the primary selection.`;
            return;
        }
        if (node.styleMode === "shared") {
            hint.textContent = `${node.name} is driven by shared styles. Edit it from the Shared Style Editor for reusable styling.`;
            return;
        }
        hint.textContent = `Editing ${node.name} directly. Drag handles to resize or use the hand tool to pan the canvas.`;
    }
    function buildSnapCandidates(screen, primaryNode) {
        const vertical = [0, screen.w / 2, screen.w];
        const horizontal = [0, screen.h / 2, screen.h];
        (screen.nodes || []).forEach(node => {
            if (node.id === primaryNode.id)
                return;
            vertical.push(node.x, node.x + node.w / 2, node.x + node.w);
            horizontal.push(node.y, node.y + node.h / 2, node.y + node.h);
        });
        return { vertical, horizontal };
    }
    function nearestSnap(value, candidates, threshold = 6) {
        let best = null;
        candidates.forEach(candidate => {
            const distance = Math.abs(value - candidate);
            if (distance <= threshold && (!best || distance < best.distance)) {
                best = { value: candidate, distance };
            }
        });
        return best;
    }
    function applyMoveSnap(primaryNode, proposed, screen) {
        if (!canvasView.snap) {
            canvasView.guides = [];
            return proposed;
        }
        const grid = 16;
        const candidates = buildSnapCandidates(screen, primaryNode);
        let nextX = Math.round(proposed.x / grid) * grid;
        let nextY = Math.round(proposed.y / grid) * grid;
        const guides = [];
        const leftSnap = nearestSnap(nextX, candidates.vertical);
        const centerSnap = nearestSnap(nextX + primaryNode.w / 2, candidates.vertical);
        const topSnap = nearestSnap(nextY, candidates.horizontal);
        const middleSnap = nearestSnap(nextY + primaryNode.h / 2, candidates.horizontal);
        if (leftSnap) {
            nextX = leftSnap.value;
            guides.push({ axis: "v", pos: leftSnap.value });
        }
        else if (centerSnap) {
            nextX = centerSnap.value - primaryNode.w / 2;
            guides.push({ axis: "v", pos: centerSnap.value });
        }
        if (topSnap) {
            nextY = topSnap.value;
            guides.push({ axis: "h", pos: topSnap.value });
        }
        else if (middleSnap) {
            nextY = middleSnap.value - primaryNode.h / 2;
            guides.push({ axis: "h", pos: middleSnap.value });
        }
        canvasView.guides = guides;
        return { x: nextX, y: nextY };
    }
    function renderStyleLibrary() {
        const library = window.$("#lvglStyleLibrary");
        if (!library)
            return;
        const state = window.lvglEnsureState();
        const styles = state.sharedStyles || [];
        styleFilter = resolveSearchInput("#lvglStyleSearch", styles.length, styleFilter);
        if (!styles.length) {
            library.innerHTML = '<div class="lvgl-layout-empty compact">No shared styles yet.</div>';
            return;
        }
        const filtered = styles.filter((style) => {
            if (!styleFilter)
                return true;
            const haystack = `${style.name} ${style.part} ${style.state}`.toLowerCase();
            return haystack.includes(styleFilter);
        });
        if (!filtered.length) {
            library.innerHTML = '<div class="lvgl-layout-empty compact">No shared styles match the current search.</div>';
            return;
        }
        library.innerHTML = filtered.map(style => `
      <button class="lvgl-layout-style-item${style.id === state.selectedStyleId ? " active" : ""}" data-lvgl-style="${style.id}">
        <span class="lvgl-layout-style-name">${window.escapeHtml(style.name)}</span>
        <span class="lvgl-layout-style-meta">${window.escapeHtml(style.part)} / ${window.escapeHtml(style.state)}</span>
      </button>
    `).join("");
        library.querySelectorAll("[data-lvgl-style]").forEach(item => {
            item.addEventListener("click", () => {
                state.selectedStyleId = item.dataset.lvglStyle;
                renderProps();
                renderStyleLibrary();
            });
        });
    }
    function renderTree() {
        const state = window.lvglEnsureState();
        const tree = window.$("#lvglTree");
        if (!tree)
            return;
        const itemCount = (state.screens || []).reduce((total, screen) => total + 1 + (screen.nodes || []).length, 0);
        treeFilter = resolveSearchInput("#lvglTreeSearch", itemCount, treeFilter);
        tree.innerHTML = state.screens.map(screen => {
            const screenMatch = !treeFilter || `${screen.name} ${screen.id}`.toLowerCase().includes(treeFilter);
            const childNodes = screen.nodes || [];
            const filteredChildren = childNodes.filter((node) => {
                if (!treeFilter)
                    return true;
                return `${node.name} ${node.type} ${node.id}`.toLowerCase().includes(treeFilter);
            });
            if (treeFilter && !screenMatch && !filteredChildren.length) {
                return "";
            }
            const visibleChildren = screenMatch ? childNodes : filteredChildren;
            const header = `
        <div class="lvgl-layout-tree-item${nodeIsSelected(state, screen.id) ? " active" : ""}" data-lvgl-tree-node="${screen.id}">
          <span class="lvgl-layout-tree-label">${window.escapeHtml(screen.name)}${screen.id === state.startupScreenId ? ' <span class="lvgl-layout-tree-badge">startup</span>' : ''}</span>
          <span class="lvgl-layout-tree-meta">screen</span>
        </div>`;
            const children = visibleChildren.map(node => `
        <div class="lvgl-layout-tree-item child${nodeIsSelected(state, node.id) ? " active" : ""}" data-lvgl-tree-node="${node.id}">
          <span>${window.escapeHtml(node.name)}</span>
          <span class="lvgl-layout-tree-meta">${window.escapeHtml(node.type)}</span>
        </div>
      `).join("");
            return header + children;
        }).join("");
        if (!tree.innerHTML.trim()) {
            tree.innerHTML = '<div class="lvgl-layout-empty compact">No layout items match the current search.</div>';
            return;
        }
        tree.querySelectorAll("[data-lvgl-tree-node]").forEach(item => {
            item.addEventListener("click", (event) => {
                const nextId = item.dataset.lvglTreeNode;
                if (event.ctrlKey || event.metaKey || event.shiftKey) {
                    toggleWidgetSelection(state, nextId);
                }
                else {
                    setSingleSelection(state, nextId);
                }
                render();
            });
        });
    }
    function renderStage() {
        const state = window.lvglEnsureState();
        const stage = window.$("#lvglStage");
        const presetSelect = window.$("#lvglPresetSelect");
        const stageMeta = window.$("#lvglStageMeta");
        const selectionMeta = window.$("#lvglSelectionMeta");
        const simBtn = window.$("#lvglBtnSimulate");
        if (!stage)
            return;
        updateCanvasChrome();
        const screen = window.lvglCurrentScreen();
        const screenVisual = window.LvglModel?.resolveNodeVisual(state, screen) || screen;
        stage.style.width = `${screen.w}px`;
        stage.style.height = `${screen.h}px`;
        stage.style.background = screenVisual.bg;
        stage.style.color = screenVisual.color;
        stage.style.borderRadius = `${screenVisual.radius}px`;
        const currentPreset = window.lvglPreset(state.preset);
        const matchesPreset = currentPreset && currentPreset.width === screen.w && currentPreset.height === screen.h;
        if (presetSelect) {
            let customOption = presetSelect.querySelector('option[data-lvgl-custom-preset="true"]');
            if (matchesPreset) {
                if (customOption)
                    customOption.remove();
                presetSelect.value = state.preset;
            }
            else {
                if (!customOption) {
                    customOption = document.createElement("option");
                    customOption.value = "__custom__";
                    customOption.dataset.lvglCustomPreset = "true";
                    presetSelect.appendChild(customOption);
                }
                customOption.textContent = `Custom ${screen.w} x ${screen.h}`;
                presetSelect.value = "__custom__";
            }
        }
        if (stageMeta) {
            const stageLabel = matchesPreset ? currentPreset.label : `${screen.w} x ${screen.h}`;
            const displayLabel = state.importMeta?.display?.label ? ` • ${window.escapeHtml(state.importMeta.display.label)}` : "";
            stageMeta.innerHTML = `${window.escapeHtml(screen.name)} • ${window.escapeHtml(stageLabel)}${displayLabel}${screen.id === state.startupScreenId ? ' <span class="lvgl-layout-stage-badge">startup</span>' : ''}${state.simulation.running ? ' • simulation' : ''}`;
        }
        if (simBtn) {
            simBtn.textContent = state.simulation.running ? "Stop Simulation" : "Start Simulation";
        }
        stage.innerHTML = (screen.nodes || []).map(node => {
            const visual = window.LvglModel?.resolveNodeVisual(state, node) || node;
            const styleBadges = (node.styleRefs || []).map(styleId => window.LvglModel?.findSharedStyle(state, styleId)).filter(Boolean);
            return `
        <div class="lvgl-layout-node t-${node.type}${node.id === state.selectedId ? " selected" : ""}${nodeIsSelected(state, node.id) && node.id !== state.selectedId ? " multi-selected" : ""}${node.styleMode === "shared" ? " style-driven" : ""}"
             data-lvgl-node="${node.id}"
             style="left:${node.x}px;top:${node.y}px;width:${node.w}px;height:${node.h}px;background:${visual.bg};color:${visual.color};border-radius:${visual.radius}px;">
          <div class="lvgl-layout-node-label">${escapeNodeLabel(node)}</div>
          ${styleBadges.length ? `<div class="lvgl-layout-node-style-badges">${styleBadges.map(style => `<span class="lvgl-layout-node-style-badge">${window.escapeHtml(style.name)}</span>`).join("")}</div>` : ""}
          ${node.id === state.selectedId && !state.simulation.running && canvasView.tool === "select" ? `
            <div class="lvgl-layout-resize-handle h-nw" data-resize-handle="nw"></div>
            <div class="lvgl-layout-resize-handle h-ne" data-resize-handle="ne"></div>
            <div class="lvgl-layout-resize-handle h-sw" data-resize-handle="sw"></div>
            <div class="lvgl-layout-resize-handle h-se" data-resize-handle="se"></div>
          ` : ""}
        </div>
      `;
        }).join("") + canvasView.guides.map(guide => guide.axis === "v"
            ? `<div class="lvgl-layout-guide v" style="left:${guide.pos}px;"></div>`
            : `<div class="lvgl-layout-guide h" style="top:${guide.pos}px;"></div>`).join("");
        stage.querySelectorAll("[data-lvgl-node]").forEach(nodeEl => {
            nodeEl.addEventListener("click", (event) => {
                if (Date.now() < suppressClickUntil) {
                    event.stopPropagation();
                    event.preventDefault();
                    return;
                }
                if (canvasView.tool === "hand")
                    return;
                event.stopPropagation();
                const found = window.lvglFindNode(nodeEl.dataset.lvglNode);
                if (!found)
                    return;
                if (!state.simulation.running && (event.ctrlKey || event.metaKey || event.shiftKey)) {
                    toggleWidgetSelection(state, found.node.id);
                }
                else {
                    setSingleSelection(state, found.node.id);
                }
                if (!state.simulation.running) {
                    state.currentScreenId = found.screen.id;
                }
                if (state.simulation.running && window.lvglWidgetSupportsAction(found.node.type)) {
                    if (found.node.action === "goto" && found.node.targetScreenId) {
                        const transition = window.lvglTransition(found.node.transition);
                        window.lvglActivateSimulationScreen(found.node.targetScreenId, `Pressed ${found.node.name} (${transition.label}, ${found.node.transitionDuration}ms)`);
                    }
                    else {
                        addLog(`Pressed ${found.node.name}`);
                    }
                }
                render();
            });
            nodeEl.addEventListener("mousedown", (event) => {
                if (state.simulation.running || canvasView.tool === "hand")
                    return;
                const found = window.lvglFindNode(nodeEl.dataset.lvglNode);
                if (!found || found.isScreen)
                    return;
                const point = stagePointFromEvent(event, stage);
                dragStartSnapshot = serializeStateForHistory();
                if (!nodeIsSelected(state, found.node.id)) {
                    setSingleSelection(state, found.node.id);
                }
                const moveIds = selectedIds(state).filter(id => {
                    const entry = window.lvglFindNode(id);
                    return entry && !entry.isScreen && entry.screen.id === found.screen.id;
                });
                window.lvglLayoutDrag = {
                    mode: "move",
                    id: found.node.id,
                    screenId: found.screen.id,
                    startPointerX: point.x,
                    startPointerY: point.y,
                    origins: moveIds.map(id => {
                        const entry = window.lvglFindNode(id);
                        return { id, x: entry.node.x, y: entry.node.y, w: entry.node.w, h: entry.node.h };
                    }),
                };
                nodeEl.classList.add("dragging");
                event.preventDefault();
            });
            nodeEl.querySelectorAll("[data-resize-handle]").forEach(handleEl => {
                handleEl.addEventListener("click", (event) => {
                    event.stopPropagation();
                    event.preventDefault();
                });
                handleEl.addEventListener("mousedown", (event) => {
                    if (state.simulation.running)
                        return;
                    event.stopPropagation();
                    const found = window.lvglFindNode(nodeEl.dataset.lvglNode);
                    if (!found || found.isScreen)
                        return;
                    dragStartSnapshot = serializeStateForHistory();
                    if (!nodeIsSelected(state, found.node.id)) {
                        setSingleSelection(state, found.node.id);
                    }
                    const resizeIds = selectedIds(state).filter(id => {
                        const entry = window.lvglFindNode(id);
                        return entry && !entry.isScreen && entry.screen.id === found.screen.id;
                    });
                    window.lvglLayoutDrag = {
                        mode: "resize",
                        handle: handleEl.dataset.resizeHandle,
                        id: found.node.id,
                        screenId: found.screen.id,
                        startClientX: event.clientX,
                        startClientY: event.clientY,
                        origins: resizeIds.map(id => {
                            const entry = window.lvglFindNode(id);
                            return { id, x: entry.node.x, y: entry.node.y, w: entry.node.w, h: entry.node.h };
                        }),
                    };
                    nodeEl.classList.add("resizing");
                    event.preventDefault();
                });
            });
        });
        stage.onclick = () => {
            if (Date.now() < suppressClickUntil)
                return;
            if (canvasView.tool === "hand")
                return;
            setSingleSelection(state, screen.id);
            render();
        };
        const selected = window.lvglSelectedNode();
        const selectedWidgets = selectedWidgetNodes(state);
        if (selectionMeta) {
            selectionMeta.textContent = selectedWidgets.length > 1
                ? `${selectedWidgets.length} widgets selected • primary ${selected?.name || "widget"}`
                : (selected
                    ? `${selected.name} • ${selected.type} • ${selected.w} x ${selected.h}`
                    : "No widget selected");
        }
        updateQuickStyleBar();
    }
    function styleCheckboxes(state, node) {
        if (!(state.sharedStyles || []).length) {
            return '<div class="lvgl-layout-empty compact">Create a shared style to assign it here.</div>';
        }
        return state.sharedStyles.map(style => `
      <label class="lvgl-layout-style-check">
        <input type="checkbox" data-lvgl-style-ref="${style.id}" ${node.styleRefs?.includes(style.id) ? "checked" : ""}>
        <span>${window.escapeHtml(style.name)} <span class="lvgl-layout-style-check-meta">${window.escapeHtml(style.part)} / ${window.escapeHtml(style.state)}</span></span>
      </label>
    `).join("");
    }
    function codeSymbol(name, fallback = "node") {
        return window.lvglCodeSymbol ? window.lvglCodeSymbol(name, fallback) : fallback;
    }
    function normalizedNameSeed(name, fallback = "item") {
        const raw = String(name || fallback).trim().replace(/[_\-]+/g, " ").replace(/\s+/g, " ");
        return raw || fallback;
    }
    function uniqueNameBySymbol(preferredName, fallback, existingSymbols) {
        const base = normalizedNameSeed(preferredName, fallback);
        if (!existingSymbols.has(codeSymbol(base, fallback))) {
            return base;
        }
        let index = 2;
        while (existingSymbols.has(codeSymbol(`${base} ${index}`, fallback))) {
            index += 1;
        }
        return `${base} ${index}`;
    }
    function renameSuggestionForIssue(state, issue, found, style) {
        const message = String(issue?.message || "");
        if (!message.includes("reserved C identifier") && !message.includes("collides with")) {
            return null;
        }
        if (style) {
            const existingSymbols = new Set((state.sharedStyles || [])
                .filter((entry) => entry.id !== style.id)
                .map((entry) => codeSymbol(entry.name || entry.id, `style_${entry.id || "shared"}`)));
            const suggestedName = uniqueNameBySymbol(message.includes("reserved C identifier") ? `${style.name || style.id} ui` : `${style.name || style.id}`, `style_${style.id || "shared"}`, existingSymbols);
            return {
                label: `Rename style to ${suggestedName}`,
                apply: () => {
                    const targetStyle = (state.sharedStyles || []).find((entry) => entry.id === style.id);
                    if (!targetStyle)
                        return;
                    targetStyle.name = suggestedName;
                    state.selectedStyleId = targetStyle.id;
                },
            };
        }
        if (!found)
            return null;
        if (found.isScreen) {
            if (message.startsWith("Entry hook for ")) {
                const screenSymbol = codeSymbol(found.node.name, "screen");
                const existingSymbols = new Set((state.screens || [])
                    .filter((screen) => screen.id !== found.node.id && String(screen.entryActionName || "").trim())
                    .map((screen) => codeSymbol(screen.entryActionName || "", `on_enter_${codeSymbol(screen.name, "screen")}`)));
                const currentHook = String(found.node.entryActionName || "").trim() || `on_enter_${screenSymbol}`;
                const suggestedName = uniqueNameBySymbol(message.includes("reserved C identifier") ? `${currentHook} ui` : currentHook, `on_enter_${screenSymbol}`, existingSymbols);
                return {
                    label: `Rename hook to ${suggestedName}`,
                    apply: () => {
                        const screen = (state.screens || []).find((entry) => entry.id === found.node.id);
                        if (!screen)
                            return;
                        screen.entryActionName = suggestedName;
                        state.currentScreenId = screen.id;
                        syncSelectionState(state, [screen.id], screen.id);
                    },
                };
            }
            const existingSymbols = new Set((state.screens || [])
                .filter((screen) => screen.id !== found.node.id)
                .map((screen) => codeSymbol(screen.name, "screen")));
            const suggestedName = uniqueNameBySymbol(message.includes("reserved C identifier") ? `${found.node.name} ui` : found.node.name, "screen", existingSymbols);
            return {
                label: `Rename screen to ${suggestedName}`,
                apply: () => {
                    const screen = (state.screens || []).find((entry) => entry.id === found.node.id);
                    if (!screen)
                        return;
                    screen.name = suggestedName;
                    state.currentScreenId = screen.id;
                    syncSelectionState(state, [screen.id], screen.id);
                },
            };
        }
        const existingSymbols = new Set(((found.screen?.nodes) || [])
            .filter((node) => node.id !== found.node.id)
            .map((node) => codeSymbol(node.name, node.type || "widget")));
        const suggestedName = uniqueNameBySymbol(message.includes("reserved C identifier") ? `${found.node.name} ui` : found.node.name, found.node.type || "widget", existingSymbols);
        return {
            label: `Rename widget to ${suggestedName}`,
            apply: () => {
                const current = window.lvglFindNode(found.node.id)?.node;
                if (!current || current.type === "screen")
                    return;
                current.name = suggestedName;
                state.currentScreenId = found.screen.id;
                syncSelectionState(state, [current.id], current.id);
            },
        };
    }
    function extractReferencedSymbols(issues) {
        const symbols = new Set();
        (issues || []).forEach((issue) => {
            const message = String(issue?.message || "");
            const normalizedMatch = message.match(/\(([A-Za-z_][A-Za-z0-9_]*)\)\.?$/);
            if (normalizedMatch?.[1]) {
                symbols.add(normalizedMatch[1]);
            }
            const reservedMatch = message.match(/reserved C identifier\s+([A-Za-z_][A-Za-z0-9_]*)\.?$/i);
            if (reservedMatch?.[1]) {
                symbols.add(reservedMatch[1]);
            }
        });
        return symbols;
    }
    function symbolPreviewMarkup(title, description, entries, highlightedSymbols = new Set()) {
        if (!entries.length)
            return "";
        const highlightedCount = entries.filter((entry) => highlightedSymbols.has(entry.value)).length;
        return `
      <section class="lvgl-layout-section">
        <div class="lvgl-layout-section-title">${window.escapeHtml(title)}</div>
        <div class="lvgl-layout-symbol-preview">
          <div class="lvgl-layout-symbol-preview-copy">
            <p>${window.escapeHtml(description)}</p>
            ${highlightedCount ? `<div class="lvgl-layout-symbol-preview-issue-note">${highlightedCount} generated identifier${highlightedCount === 1 ? " is" : "s are"} referenced by current validation findings.</div>` : ""}
          </div>
          <div class="lvgl-layout-symbol-preview-grid">
            ${entries.map((entry) => `
              <div class="lvgl-layout-symbol-preview-item${highlightedSymbols.has(entry.value) ? " matching-issue" : ""}">
                <label>${window.escapeHtml(entry.label)}</label>
                <code>${window.escapeHtml(entry.value)}</code>
              </div>
            `).join("")}
          </div>
        </div>
      </section>
    `;
    }
    function nodeSymbolPreviewMarkup(node, parentScreen, highlightedSymbols = new Set()) {
        if (!node)
            return "";
        if (node.type === "screen") {
            const screenSymbol = codeSymbol(node.name, "screen");
            const entries = [
                { label: "Screen Symbol", value: screenSymbol },
                { label: "Build Function", value: `ui_build_${screenSymbol}` },
                { label: "Load Function", value: `ui_load_${screenSymbol}` },
                { label: "Accessor", value: `ui_get_${screenSymbol}` },
                { label: "Storage", value: `g_ui_${screenSymbol}` },
            ];
            if (String(node.entryActionName || "").trim()) {
                entries.push({ label: "Entry Hook", value: codeSymbol(node.entryActionName || "", `on_enter_${screenSymbol}`) });
            }
            return symbolPreviewMarkup("Codegen Preview", "These are the identifiers the generator will emit for the selected screen.", entries, highlightedSymbols);
        }
        const screen = parentScreen || window.lvglCurrentDesignScreen();
        const screenSymbol = codeSymbol(screen?.name, "screen");
        const nodeSymbol = codeSymbol(node.name, node.type || "widget");
        const entries = [
            { label: "Widget Symbol", value: nodeSymbol },
            { label: "Accessor", value: `ui_get_${screenSymbol}_${nodeSymbol}` },
            { label: "Storage", value: `g_ui_${screenSymbol}_${nodeSymbol}` },
        ];
        if (window.LvglRegistry?.nodeEventType?.(node)) {
            entries.push({ label: "Event Hook", value: `ui_on_${screenSymbol}_${nodeSymbol}_event` });
        }
        return symbolPreviewMarkup("Codegen Preview", "These are the identifiers the generator will emit for the selected widget in its current screen scope.", entries, highlightedSymbols);
    }
    function styleSymbolPreviewMarkup(style, highlightedSymbols = new Set()) {
        if (!style)
            return "";
        const styleSymbol = codeSymbol(style.name || style.id, `style_${style.id || "shared"}`);
        return symbolPreviewMarkup("Codegen Preview", "This is the normalized symbol the LVGL generator will use for the selected shared style.", [
            { label: "Style Symbol", value: styleSymbol },
            { label: "Part / State", value: `${style.part || "LV_PART_MAIN"} / ${style.state || "default"}` },
        ], highlightedSymbols);
    }
    function styleEditorMarkup(style, highlightedSymbols = new Set()) {
        if (!style) {
            return '<div class="lvgl-layout-empty compact">Select or create a shared style to edit it.</div>';
        }
        return `
      <div class="lvgl-layout-form">
        <div class="lvgl-layout-field full">
          <label>Style Name</label>
          <input data-lvgl-style-prop="name" value="${window.escapeHtml(style.name)}">
        </div>
        <div class="lvgl-layout-field">
          <label>Part</label>
          <select data-lvgl-style-prop="part">
            ${(window.LvglModel?.STYLE_SCHEMA?.parts || []).map(part => `<option value="${part}" ${style.part === part ? "selected" : ""}>${window.escapeHtml(part)}</option>`).join("")}
          </select>
        </div>
        <div class="lvgl-layout-field">
          <label>State</label>
          <select data-lvgl-style-prop="state">
            ${(window.LvglModel?.STYLE_SCHEMA?.states || []).map(styleState => `<option value="${styleState}" ${style.state === styleState ? "selected" : ""}>${window.escapeHtml(styleState)}</option>`).join("")}
          </select>
        </div>
        <div class="lvgl-layout-field">
          <label>Background</label>
          <input type="color" data-lvgl-style-value="bg" value="${window.escapeHtml(style.values?.bg || "#334155")}">
        </div>
        <div class="lvgl-layout-field">
          <label>Text Color</label>
          <input type="color" data-lvgl-style-value="color" value="${window.escapeHtml(style.values?.color || "#f8fafc")}">
        </div>
        <div class="lvgl-layout-field full">
          <label>Radius</label>
          <input type="number" data-lvgl-style-value="radius" value="${style.values?.radius ?? 14}">
        </div>
        <div class="lvgl-layout-field full">
          <button class="btn" id="lvglBtnDeleteStyle">Delete Shared Style</button>
        </div>
      </div>
      ${styleSymbolPreviewMarkup(style, highlightedSymbols)}
    `;
    }
    function renderField(field, context) {
        if (!window.LvglRegistry?.isFieldVisible(field, context))
            return "";
        const disabled = window.LvglRegistry?.isFieldDisabled(field, context) ? "disabled" : "";
        const fullClass = field.full ? " full" : "";
        const label = window.escapeHtml(field.label || field.key || "Field");
        const value = window.LvglRegistry?.fieldValue(field, context);
        const placeholder = window.escapeHtml(window.LvglRegistry?.fieldPlaceholder(field, context) || "");
        const safeValue = window.escapeHtml(value ?? "");
        const minAttr = field.min !== undefined ? ` min="${field.min}"` : "";
        const stepAttr = field.step !== undefined ? ` step="${field.step}"` : "";
        if (field.type === "readonly") {
            return `
        <div class="lvgl-layout-field${fullClass}">
          <label>${label}</label>
          <input value="${safeValue}" disabled>
        </div>
      `;
        }
        if (field.type === "select") {
            const options = (window.LvglRegistry?.fieldOptions(field, context) || []).map(option => {
                const optionValue = window.escapeHtml(option.value ?? "");
                const optionLabel = window.escapeHtml(option.label ?? option.value ?? "");
                const selected = String(option.value ?? "") === String(value ?? "") ? "selected" : "";
                return `<option value="${optionValue}" ${selected}>${optionLabel}</option>`;
            }).join("");
            return `
        <div class="lvgl-layout-field${fullClass}">
          <label>${label}</label>
          <select data-lvgl-prop="${field.key}" ${disabled}>${options}</select>
        </div>
      `;
        }
        if (field.type === "textarea") {
            return `
        <div class="lvgl-layout-field${fullClass}">
          <label>${label}</label>
          <textarea data-lvgl-prop="${field.key}" placeholder="${placeholder}" ${disabled}>${safeValue}</textarea>
        </div>
      `;
        }
        return `
      <div class="lvgl-layout-field${fullClass}">
        <label>${label}</label>
        <input type="${field.type || "text"}" data-lvgl-prop="${field.key}" value="${safeValue}" placeholder="${placeholder}"${minAttr}${stepAttr} ${disabled}>
      </div>
    `;
    }
        function displayProfileSectionMarkup(state) {
                const meta = state?.importMeta;
                const display = meta?.display;
                if (!display) {
                        return "";
                }
                const resolution = Number(display.width) > 0 && Number(display.height) > 0
                        ? `${display.width} x ${display.height}`
                        : "Inherited from current layout";
                const buses = Array.isArray(display.buses) && display.buses.length ? display.buses.join(", ") : "bus n/a";
                const bindings = Array.isArray(display.bindingPaths) && display.bindingPaths.length ? display.bindingPaths.join("\n") : "n/a";
                const propertySummary = Array.isArray(display.properties) && display.properties.length
                        ? display.properties.slice(0, 10).map((prop) => {
                                const tokens = [prop.name, prop.type];
                                if (prop.required)
                                        tokens.push("required");
                                if (prop.default !== undefined && prop.default !== null && prop.default !== "")
                                        tokens.push(`default=${prop.default}`);
                                return tokens.join(" - ");
                        }).join("\n")
                        : "No binding properties captured.";
                return `
            <section class="lvgl-layout-section">
                <div class="lvgl-layout-section-title">Display Profile</div>
                <div class="lvgl-layout-form">
                    <div class="lvgl-layout-field">
                        <label>Label</label>
                        <input value="${window.escapeHtml(display.label || "Display")}" disabled>
                    </div>
                    <div class="lvgl-layout-field">
                        <label>Resolution</label>
                        <input value="${window.escapeHtml(resolution)}" disabled>
                    </div>
                    <div class="lvgl-layout-field full">
                        <label>Compatible</label>
                        <input value="${window.escapeHtml(display.compatible || "n/a")}" disabled>
                    </div>
                    <div class="lvgl-layout-field">
                        <label>Bus</label>
                        <input value="${window.escapeHtml(buses)}" disabled>
                    </div>
                    <div class="lvgl-layout-field">
                        <label>Source</label>
                        <input value="${window.escapeHtml(meta.source || meta.kind || "catalog")}" disabled>
                    </div>
                    <div class="lvgl-layout-field full">
                        <label>Binding Paths</label>
                        <textarea disabled>${window.escapeHtml(bindings)}</textarea>
                    </div>
                    <div class="lvgl-layout-field full">
                        <label>Binding Properties</label>
                        <textarea disabled>${window.escapeHtml(propertySummary)}</textarea>
                    </div>
                </div>
            </section>`;
        }
    function renderNodeActions(node, state) {
        if (!node)
            return "";
        const isScreen = node.type === "screen";
        return [
            !isScreen ? '<div class="lvgl-layout-field full"><button class="btn" id="lvglBtnDeleteNode">Delete Widget</button></div>' : "",
            isScreen && node.id !== state.startupScreenId ? '<div class="lvgl-layout-field full"><button class="btn" id="lvglBtnSetStartupScreen">Use As Startup Screen</button></div>' : "",
            isScreen && state.screens.length > 1 ? '<div class="lvgl-layout-field full"><button class="btn" id="lvglBtnDeleteScreen">Delete Screen</button></div>' : "",
        ].filter(Boolean).join("");
    }
    function lvglGeneratedPreviewFiles(state) {
        return [
            { id: "prj_conf", label: "prj.conf", path: "lvgl/prj.conf", group: "LVGL Layout", content: generatedFragments.lvgl?.prj_conf || "" },
            { id: "overlay", label: ".overlay", path: "lvgl/lvgl.overlay", group: "LVGL Layout", content: generatedFragments.lvgl?.overlay || "" },
            { id: "code", label: "ui_layout.c", path: "lvgl/ui_layout.c", group: "LVGL Layout", content: state.code || generatedFragments.lvgl?.code || "" },
            { id: "header", label: "ui_layout.h", path: "lvgl/ui_layout.h", group: "LVGL Layout", content: generatedFragments.lvgl?.header || "" },
            { id: "hooks_header", label: "ui_layout_hooks.h", path: "lvgl/ui_layout_hooks.h", group: "LVGL Layout", content: generatedFragments.lvgl?.hooksHeader || "" },
            { id: "hooks", label: "ui_layout_hooks.template.c", path: "lvgl/ui_layout_hooks.template.c", group: "LVGL Layout", content: generatedFragments.lvgl?.hooks || "" },
            { id: "integration", label: "integration.md", path: "lvgl/integration.md", group: "LVGL Layout", content: generatedFragments.lvgl?.integration || "" },
            { id: "validation", label: "validation.md", path: "lvgl/validation.md", group: "LVGL Layout", content: generatedFragments.lvgl?.validation || "" },
            { id: "style_schema", label: "style_schema.json", path: "lvgl/style_schema.json", group: "LVGL Layout", content: generatedFragments.lvgl?.styleSchema || "" },
        ];
    }
    function bindPropertyInputs(panel, node, found, state, fields) {
        panel.querySelectorAll("[data-lvgl-prop]").forEach(input => {
            const eventName = input.tagName === "SELECT" ? "change" : "input";
            input.addEventListener(eventName, () => {
                if (!node)
                    return;
                const key = input.dataset.lvglProp;
                const field = fields.find(entry => entry.key === key);
                applyMutation(() => {
                    const currentNode = window.lvglFindNode(node.id)?.node;
                    if (!currentNode)
                        return;
                    currentNode[key] = window.LvglRegistry?.normalizeFieldValue(field || { type: input.type }, input.value);
                    if (key === "action" && currentNode.action !== "goto") {
                        currentNode.targetScreenId = "";
                        currentNode.transition = "move_left";
                        currentNode.transitionDuration = 220;
                    }
                    if (currentNode.type === "screen" && ["w", "h"].includes(key)) {
                        (currentNode.nodes || []).forEach(entry => window.lvglClampNode(entry, currentNode));
                    }
                    if (currentNode.type !== "screen") {
                        window.lvglClampNode(currentNode, found?.screen);
                    }
                }, { rebuildCode: true });
            });
        });
    }
    function bindStyleInputs(panel, node) {
        panel.querySelectorAll("[data-lvgl-style-ref]").forEach(input => {
            input.addEventListener("change", () => {
                if (!node)
                    return;
                const styleId = input.dataset.lvglStyleRef;
                applyMutation(() => {
                    const currentNode = window.lvglFindNode(node.id)?.node;
                    if (!currentNode)
                        return;
                    const refs = new Set(currentNode.styleRefs || []);
                    if (input.checked)
                        refs.add(styleId);
                    else
                        refs.delete(styleId);
                    currentNode.styleRefs = [...refs];
                }, { rebuildCode: true });
            });
        });
        panel.querySelectorAll("[data-lvgl-style-prop]").forEach(input => {
            const eventName = input.tagName === "SELECT" ? "change" : "input";
            input.addEventListener(eventName, () => {
                applyMutation(state => {
                    const style = ensureSelectedStyle(state);
                    if (!style)
                        return;
                    style[input.dataset.lvglStyleProp] = input.value;
                }, { rebuildCode: true });
            });
        });
        panel.querySelectorAll("[data-lvgl-style-value]").forEach(input => {
            input.addEventListener("input", () => {
                applyMutation(state => {
                    const style = ensureSelectedStyle(state);
                    if (!style)
                        return;
                    const key = input.dataset.lvglStyleValue;
                    style.values = style.values || {};
                    style.values[key] = key === "radius" ? Number(input.value) || 0 : input.value;
                }, { rebuildCode: true });
            });
        });
    }
    function bindActionButtons(panel, node, found) {
        const deleteBtn = panel.querySelector("#lvglBtnDeleteNode");
        if (deleteBtn) {
            deleteBtn.addEventListener("click", () => {
                const parentScreen = found?.screen;
                if (!parentScreen || !node)
                    return;
                const removalIds = new Set(selectedWidgetNodes().map(entry => entry.id));
                if (!removalIds.size) {
                    removalIds.add(node.id);
                }
                applyMutation(state => {
                    const currentParent = state.screens.find(screen => screen.id === parentScreen.id);
                    if (!currentParent)
                        return;
                    currentParent.nodes = (currentParent.nodes || []).filter(entry => !removalIds.has(entry.id));
                    syncSelectionState(state, [currentParent.id], currentParent.id);
                }, { rebuildCode: true, logMessage: `Removed ${removalIds.size > 1 ? `${removalIds.size} widgets` : `widget ${node.name}`}` });
            });
        }
        const startupBtn = panel.querySelector("#lvglBtnSetStartupScreen");
        if (startupBtn) {
            startupBtn.addEventListener("click", () => {
                applyMutation(state => {
                    state.startupScreenId = node.id;
                    state.currentScreenId = node.id;
                    syncSelectionState(state, [node.id], node.id);
                }, { rebuildCode: true, logMessage: `Set ${node.name} as startup screen` });
            });
        }
        const deleteScreenBtn = panel.querySelector("#lvglBtnDeleteScreen");
        if (deleteScreenBtn) {
            deleteScreenBtn.addEventListener("click", () => {
                applyMutation(state => {
                    state.screens = state.screens.filter(screen => screen.id !== node.id);
                    state.currentScreenId = state.screens[0]?.id || "screen_root";
                    if (state.startupScreenId === node.id) {
                        state.startupScreenId = state.currentScreenId;
                    }
                    syncSelectionState(state, [state.currentScreenId], state.currentScreenId);
                    state.simulation.activeScreenId = state.currentScreenId;
                }, { rebuildCode: true, logMessage: `Removed screen ${node.name}` });
            });
        }
        const deleteStyleBtn = panel.querySelector("#lvglBtnDeleteStyle");
        if (deleteStyleBtn) {
            deleteStyleBtn.addEventListener("click", () => {
                applyMutation(state => {
                    const style = ensureSelectedStyle(state);
                    if (!style)
                        return;
                    state.sharedStyles = state.sharedStyles.filter(entry => entry.id !== style.id);
                    state.screens.forEach(screen => {
                        screen.styleRefs = (screen.styleRefs || []).filter(ref => ref !== style.id);
                        (screen.nodes || []).forEach(nodeEntry => {
                            nodeEntry.styleRefs = (nodeEntry.styleRefs || []).filter(ref => ref !== style.id);
                        });
                    });
                    state.selectedStyleId = state.sharedStyles[0]?.id || "";
                }, { rebuildCode: true, logMessage: "Removed shared style" });
            });
        }
    }
    function renderProps() {
        const panel = window.$("#lvglPropsPanel");
        if (!panel)
            return;
        const state = window.lvglEnsureState();
        const node = window.lvglSelectedNode();
        const currentStyle = ensureSelectedStyle(state);
        const displayProfileMarkup = displayProfileSectionMarkup(state);
        const highlightedSymbols = extractReferencedSymbols(window.LvglModel?.validateState(state) || []);
        window.renderCodeReviewPanel?.("lvglGeneratedReview", lvglGeneratedPreviewFiles(state), {
            emptyMessage: 'Press "Generate LVGL Code" to export the current layout as starter C code.',
            preferredSelection: state.code ? "code" : "prj_conf",
        });
        if (!node && !currentStyle && !displayProfileMarkup) {
            panel.className = "lvgl-layout-empty";
            panel.textContent = "Select a widget from the canvas or tree to edit its properties.";
            return;
        }
        const found = node ? window.lvglFindNode(node.id) : null;
        const fieldContext = { state, node, parentScreen: found?.screen };
        const fields = node ? (window.LvglRegistry?.getPropertyFields(node, fieldContext) || []) : [];
        panel.className = "";
        panel.innerHTML = `
            ${displayProfileMarkup}
      ${node ? `
      <section class="lvgl-layout-section">
        <div class="lvgl-layout-section-title">Widget Properties</div>
        <div class="lvgl-layout-form">
          ${fields.map(field => renderField(field, fieldContext)).join("")}
          <div class="lvgl-layout-field full">
            <label>Shared Styles</label>
            <div class="lvgl-layout-style-checks">${styleCheckboxes(state, node)}</div>
          </div>
          ${renderNodeActions(node, state)}
        </div>
      </section>
      ${nodeSymbolPreviewMarkup(node, found?.screen, highlightedSymbols)}` : ""}
      <section class="lvgl-layout-section">
        <div class="lvgl-layout-section-title">Shared Style Editor</div>
        ${styleEditorMarkup(currentStyle, highlightedSymbols)}
      </section>
    `;
        if (node) {
            bindPropertyInputs(panel, node, found, state, fields);
        }
        bindStyleInputs(panel, node);
        bindActionButtons(panel, node, found);
    }
    function render() {
        window.lvglEnsureState();
        renderTree();
        renderStyleLibrary();
        renderStage();
        renderProps();
        renderSimLog();
        renderValidation();
        updateQuickStyleBar();
        updateHistoryButtons();
    }
    function setCanvasTool(tool) {
        canvasView.tool = tool === "hand" ? "hand" : "select";
        updateCanvasChrome();
        renderStage();
    }
    function adjustZoom(delta) {
        canvasView.zoom = clampZoom(canvasView.zoom + delta);
        updateCanvasChrome();
    }
    function resetCanvasView() {
        canvasView.zoom = 1;
        canvasView.panX = 0;
        canvasView.panY = 0;
        updateCanvasChrome();
    }
    function resetLayout() {
        applyMutation(state => {
            const next = window.lvglDefaultState();
            Object.keys(state).forEach(key => delete state[key]);
            Object.assign(state, next);
        }, { rebuildCode: true, logMessage: "Reset layout" });
    }
    function applyPreset(presetKey) {
        applyMutation(state => {
            state.preset = presetKey;
            const preset = window.lvglPreset(presetKey);
            state.screens = state.screens.map(screen => {
                const next = { ...screen, w: preset.width, h: preset.height };
                next.nodes = (screen.nodes || []).map(node => {
                    const cloned = { ...node };
                    window.lvglClampNode(cloned, next);
                    return cloned;
                });
                return next;
            });
        }, { rebuildCode: true, logMessage: `Applied ${window.lvglPreset(presetKey).label}` });
    }
    function addSharedStyle() {
        applyMutation(state => {
            const styleId = nextStyleId(state);
            const style = {
                id: styleId,
                name: `style_${(state.sharedStyles || []).length + 1}`,
                part: "LV_PART_MAIN",
                state: "default",
                values: {
                    bg: "#1d4ed8",
                    color: "#f8fafc",
                    radius: 12,
                },
            };
            state.sharedStyles.push(style);
            state.selectedStyleId = style.id;
        }, { rebuildCode: true, logMessage: "Added shared style" });
    }
    function addWidget(type) {
        applyMutation(state => {
            if (type === "screen") {
                const screenId = window.lvglAllocateNodeId("screen");
                const screenName = `screen_${state.screens.length + 1}`;
                state.screens.push({
                    ...window.lvglScreenNodeForPreset(state.preset, screenId, screenName),
                    text: `Screen ${state.screens.length + 1}`,
                    nodes: [],
                    styleRefs: [],
                    styleMode: "local",
                });
                state.currentScreenId = screenId;
                syncSelectionState(state, [screenId], screenId);
                addLog(`Created ${screenName}`);
                return;
            }
            const node = window.lvglCreateNode(type);
            const screen = window.lvglCurrentDesignScreen();
            screen.nodes.push(node);
            syncSelectionState(state, [node.id], node.id);
            addLog(`Added ${node.name} to ${screen.name}`);
        }, { rebuildCode: true });
    }
    function serializeState() {
        return serializeStateForHistory();
    }
    function restoreState(nextState) {
        const options = arguments[1] || {};
        restoreStateInternal(nextState, { preserveHistory: false, ...options });
    }
    function init() {
        const stage = window.$("#lvglStage");
        const canvasWrap = window.$(".lvgl-layout-canvas-wrap");
        if (!stage)
            return;
        window.$("#lvglPalette")?.querySelectorAll("[data-lvgl-add]").forEach(btn => {
            btn.addEventListener("click", () => addWidget(btn.dataset.lvglAdd));
        });
        window.$("#lvglPresetSelect")?.addEventListener("change", (event) => {
            if (event.target.value === "__custom__")
                return;
            applyPreset(event.target.value);
        });
        window.$("#lvglBtnAddScreen")?.addEventListener("click", () => addWidget("screen"));
        window.$("#lvglBtnAddStyle")?.addEventListener("click", addSharedStyle);
        window.$("#lvglTreeSearch")?.addEventListener("input", (event) => {
            treeFilter = event.target.value.trim().toLowerCase();
            renderTree();
        });
        window.$("#lvglStyleSearch")?.addEventListener("input", (event) => {
            styleFilter = event.target.value.trim().toLowerCase();
            renderStyleLibrary();
        });
        window.$("#lvglValidationSeverityFilter")?.addEventListener("change", (event) => {
            validationSeverityFilter = event.target.value || "all";
            renderValidation();
        });
        window.$("#lvglValidationScopeFilter")?.addEventListener("change", (event) => {
            validationScopeFilter = event.target.value || "all";
            renderValidation();
        });
        window.$("#lvglValidationSearch")?.addEventListener("input", (event) => {
            validationSearchFilter = event.target.value.trim().toLowerCase();
            renderValidation();
        });
        window.$("#lvglBtnApplyValidationRenames")?.addEventListener("click", applyVisibleRenameSuggestions);
        window.$("#lvglBtnResetValidationFilters")?.addEventListener("click", () => {
            validationSeverityFilter = "all";
            validationScopeFilter = "all";
            validationSearchFilter = "";
            renderValidation();
        });
        window.$("#lvglBtnCopy")?.addEventListener("click", copySelectedWidget);
        window.$("#lvglBtnPaste")?.addEventListener("click", pasteClipboard);
        window.$("#lvglBtnDuplicate")?.addEventListener("click", duplicateSelectedWidget);
        window.$("#lvglBtnUndo")?.addEventListener("click", undo);
        window.$("#lvglBtnRedo")?.addEventListener("click", redo);
        window.$("#lvglBtnSelectTool")?.addEventListener("click", () => setCanvasTool("select"));
        window.$("#lvglBtnHandTool")?.addEventListener("click", () => setCanvasTool("hand"));
        window.$("#lvglBtnZoomIn")?.addEventListener("click", () => adjustZoom(ZOOM_STEP));
        window.$("#lvglBtnZoomOut")?.addEventListener("click", () => adjustZoom(-ZOOM_STEP));
        window.$("#lvglBtnZoomReset")?.addEventListener("click", resetCanvasView);
        window.$("#lvglBtnSnapToggle")?.addEventListener("click", () => {
            canvasView.snap = !canvasView.snap;
            if (!canvasView.snap) {
                canvasView.guides = [];
            }
            updateCanvasChrome();
            renderStage();
        });
        window.$("#lvglQuickStyleBg")?.addEventListener("input", (event) => {
            const targets = selectedWidgetNodes().filter(entry => entry.styleMode !== "shared");
            if (!targets.length) {
                const selected = window.lvglSelectedNode();
                if (!selected || selected.styleMode === "shared")
                    return;
                targets.push(selected);
            }
            applyMutation(() => {
                targets.forEach(target => {
                    const current = window.lvglFindNode(target.id)?.node;
                    if (!current || current.styleMode === "shared")
                        return;
                    current.bg = event.target.value;
                });
            }, { rebuildCode: true });
        });
        window.$("#lvglQuickStyleColor")?.addEventListener("input", (event) => {
            const targets = selectedWidgetNodes().filter(entry => entry.styleMode !== "shared");
            if (!targets.length) {
                const selected = window.lvglSelectedNode();
                if (!selected || selected.styleMode === "shared")
                    return;
                targets.push(selected);
            }
            applyMutation(() => {
                targets.forEach(target => {
                    const current = window.lvglFindNode(target.id)?.node;
                    if (!current || current.styleMode === "shared")
                        return;
                    current.color = event.target.value;
                });
            }, { rebuildCode: true });
        });
        window.$("#lvglQuickStyleRadius")?.addEventListener("input", (event) => {
            const targets = selectedWidgetNodes().filter(entry => entry.styleMode !== "shared");
            if (!targets.length) {
                const selected = window.lvglSelectedNode();
                if (!selected || selected.styleMode === "shared")
                    return;
                targets.push(selected);
            }
            applyMutation(() => {
                targets.forEach(target => {
                    const current = window.lvglFindNode(target.id)?.node;
                    if (!current || current.styleMode === "shared")
                        return;
                    current.radius = Math.max(0, Number(event.target.value) || 0);
                });
            }, { rebuildCode: true });
        });
        window.$("#lvglBtnSimulate")?.addEventListener("click", () => {
            applyMutation(state => {
                state.simulation.running = !state.simulation.running;
                if (state.simulation.running) {
                    window.lvglActivateSimulationScreen(state.startupScreenId || state.currentScreenId, "Simulation started");
                }
                else {
                    addLog("Simulation stopped.");
                }
            }, { rebuildCode: false });
        });
        window.$("#lvglBtnReset")?.addEventListener("click", resetLayout);
        window.$("#lvglBtnGenerate")?.addEventListener("click", () => {
            window.lvglSyncGeneratedOutputs(true);
            renderProps();
            window.toast("Generated LVGL starter code");
        });
        window.addEventListener("mousemove", (event) => {
            if (!window.lvglLayoutDrag)
                return;
            if (window.lvglLayoutDrag.mode === "pan") {
                canvasView.panX = window.lvglLayoutDrag.startPanX + (event.clientX - window.lvglLayoutDrag.startClientX);
                canvasView.panY = window.lvglLayoutDrag.startPanY + (event.clientY - window.lvglLayoutDrag.startClientY);
                updateCanvasChrome();
                return;
            }
            const screen = window.lvglFindScreen(window.lvglLayoutDrag.screenId);
            const node = screen?.nodes?.find(entry => entry.id === window.lvglLayoutDrag.id);
            const stageEl = window.$("#lvglStage");
            if (!node || !screen || !stageEl)
                return;
            if (window.lvglLayoutDrag.mode === "resize") {
                const deltaX = (event.clientX - window.lvglLayoutDrag.startClientX) / canvasView.zoom;
                const deltaY = (event.clientY - window.lvglLayoutDrag.startClientY) / canvasView.zoom;
                const primaryOrigin = window.lvglLayoutDrag.origins.find(entry => entry.id === node.id) || { x: node.x, y: node.y, w: node.w, h: node.h };
                let snappedPrimary = null;
                window.lvglLayoutDrag.origins.forEach(origin => {
                    const currentNode = screen.nodes.find(entry => entry.id === origin.id);
                    if (!currentNode)
                        return;
                    const metrics = { x: origin.x, y: origin.y, w: origin.w, h: origin.h };
                    const handle = window.lvglLayoutDrag.handle || "se";
                    if (handle.includes("e"))
                        metrics.w = origin.w + deltaX;
                    if (handle.includes("s"))
                        metrics.h = origin.h + deltaY;
                    if (handle.includes("w")) {
                        metrics.w = origin.w - deltaX;
                        metrics.x = origin.x + deltaX;
                    }
                    if (handle.includes("n")) {
                        metrics.h = origin.h - deltaY;
                        metrics.y = origin.y + deltaY;
                    }
                    let nextMetrics = {
                        x: Math.round(metrics.x),
                        y: Math.round(metrics.y),
                        w: Math.max(36, Math.round(metrics.w)),
                        h: Math.max(24, Math.round(metrics.h)),
                    };
                    if (origin.id === node.id && canvasView.snap) {
                        const grid = 16;
                        nextMetrics = {
                            x: Math.round(nextMetrics.x / grid) * grid,
                            y: Math.round(nextMetrics.y / grid) * grid,
                            w: Math.round(nextMetrics.w / grid) * grid,
                            h: Math.round(nextMetrics.h / grid) * grid,
                        };
                        canvasView.guides = [
                            { axis: "v", pos: nextMetrics.x + nextMetrics.w },
                            { axis: "h", pos: nextMetrics.y + nextMetrics.h },
                        ];
                        snappedPrimary = nextMetrics;
                    }
                    currentNode.x = nextMetrics.x;
                    currentNode.y = nextMetrics.y;
                    currentNode.w = nextMetrics.w;
                    currentNode.h = nextMetrics.h;
                    window.lvglClampNode(currentNode, screen);
                });
                if (!snappedPrimary && !canvasView.snap) {
                    canvasView.guides = [];
                }
            }
            else {
                const point = stagePointFromEvent(event, stageEl);
                const primaryOrigin = window.lvglLayoutDrag.origins.find(entry => entry.id === node.id) || { x: node.x, y: node.y };
                const snapped = applyMoveSnap(node, {
                    x: primaryOrigin.x + (point.x - window.lvglLayoutDrag.startPointerX),
                    y: primaryOrigin.y + (point.y - window.lvglLayoutDrag.startPointerY),
                }, screen);
                const appliedDelta = {
                    x: snapped.x - primaryOrigin.x,
                    y: snapped.y - primaryOrigin.y,
                };
                window.lvglLayoutDrag.origins.forEach(origin => {
                    const currentNode = screen.nodes.find(entry => entry.id === origin.id);
                    if (!currentNode)
                        return;
                    currentNode.x = Math.round(origin.x + appliedDelta.x);
                    currentNode.y = Math.round(origin.y + appliedDelta.y);
                    window.lvglClampNode(currentNode, screen);
                });
            }
            render();
        });
        window.addEventListener("mouseup", () => {
            if (window.lvglLayoutDrag) {
                suppressClickUntil = Date.now() + 180;
            }
            if (window.lvglLayoutDrag && window.lvglLayoutDrag.mode !== "pan") {
                const current = serializeStateForHistory();
                if (dragStartSnapshot && !snapshotsEqual(dragStartSnapshot, current)) {
                    recordHistorySnapshot(dragStartSnapshot);
                }
                window.lvglSyncGeneratedOutputs(true);
            }
            window.lvglLayoutDrag = null;
            dragStartSnapshot = null;
            canvasView.guides = [];
            updateCanvasChrome();
            updateHistoryButtons();
        });
        canvasWrap?.addEventListener("mousedown", (event) => {
            if (event.target.closest("[data-lvgl-node]"))
                return;
            if (canvasView.tool !== "hand")
                return;
            window.lvglLayoutDrag = {
                mode: "pan",
                startClientX: event.clientX,
                startClientY: event.clientY,
                startPanX: canvasView.panX,
                startPanY: canvasView.panY,
            };
            updateCanvasChrome();
            event.preventDefault();
        });
        document.addEventListener("keydown", handleKeyboardShortcuts);
        window.lvglEnsureState();
        resetHistory();
        window.lvglSyncGeneratedOutputs(true);
        render();
    }
    window.LvglUi = {
        addLog,
        renderSimLog,
        renderTree,
        renderStage,
        renderProps,
        render,
        resetLayout,
        applyPreset,
        addWidget,
        serializeState,
        restoreState,
        init,
        addSharedStyle,
        copySelectedWidget,
        pasteClipboard,
        duplicateSelectedWidget,
        undo,
        redo,
    };
})();
