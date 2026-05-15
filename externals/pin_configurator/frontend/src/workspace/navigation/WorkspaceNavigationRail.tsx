import { useRef } from "react";
import type { ShellOutputChannelViewModel } from "../../presenters/useShellPresenter";
import { workspaceLayoutPresets, type WorkspaceLayoutPresetId } from "../layout/workspaceShellPreferences";
import { workspaceDockPanelDefinitions } from "../panels/dockPanelDefinitions";

interface WorkspaceNavigationRailProps {
  activeLayoutPresetId: WorkspaceLayoutPresetId;
  activeOutputChannelId: string;
  focusedPanelId: string | null;
  onSelectLayoutPreset: (presetId: WorkspaceLayoutPresetId) => void;
  onFocusPanel: (panelId: string) => void;
  outputChannels: ShellOutputChannelViewModel[];
  onSelectOutputChannel: (channelId: string) => void;
}

const navigationSections = ["Boards", "Artifacts", "Interfaces", "Simulation", "Diagnostics"] as const;

function assignButtonRef(map: Map<string, HTMLButtonElement>, id: string, node: HTMLButtonElement | null) {
  if (node) {
    map.set(id, node);
    return;
  }

  map.delete(id);
}

function getRovingIndex(key: string, currentIndex: number, count: number): number {
  if (count === 0) {
    return -1;
  }

  if (key === "ArrowDown" || key === "ArrowRight") {
    return (currentIndex + 1) % count;
  }

  if (key === "ArrowUp" || key === "ArrowLeft") {
    return (currentIndex - 1 + count) % count;
  }

  if (key === "Home") {
    return 0;
  }

  if (key === "End") {
    return count - 1;
  }

  return currentIndex;
}

function toAriaKeyShortcuts(shortcut: string) {
  return shortcut === "Palette" ? undefined : shortcut.replace(/\+/g, "+");
}

export function WorkspaceNavigationRail({
  activeLayoutPresetId,
  activeOutputChannelId,
  focusedPanelId,
  onSelectLayoutPreset,
  onFocusPanel,
  outputChannels,
  onSelectOutputChannel,
}: WorkspaceNavigationRailProps) {
  const presetRefs = useRef(new Map<string, HTMLButtonElement>());
  const panelRefs = useRef(new Map<string, HTMLButtonElement>());
  const outputRefs = useRef(new Map<string, HTMLButtonElement>());

  return (
    <div className="workspace-navigation-rail">
      <section className="workspace-navigation-rail__section" aria-label="Workspace layout presets">
        <div className="workspace-navigation-rail__header">Workflow presets</div>
        <div className="workspace-navigation-rail__list">
          {workspaceLayoutPresets.map((preset) => (
            <button
              key={preset.id}
              ref={(node) => assignButtonRef(presetRefs.current, preset.id, node)}
              type="button"
              className={`workspace-navigation-rail__button${preset.id === activeLayoutPresetId ? " workspace-navigation-rail__button--active" : ""}`}
              aria-pressed={preset.id === activeLayoutPresetId}
              tabIndex={preset.id === activeLayoutPresetId ? 0 : -1}
              onClick={() => onSelectLayoutPreset(preset.id)}
              onKeyDown={(event) => {
                if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
                  return;
                }

                event.preventDefault();
                const currentIndex = workspaceLayoutPresets.findIndex((entry) => entry.id === preset.id);
                const nextIndex = getRovingIndex(event.key, Math.max(currentIndex, 0), workspaceLayoutPresets.length);
                const nextPreset = workspaceLayoutPresets[nextIndex];
                if (!nextPreset) {
                  return;
                }

                onSelectLayoutPreset(nextPreset.id);
                requestAnimationFrame(() => presetRefs.current.get(nextPreset.id)?.focus());
              }}
            >
              <strong>{preset.label}</strong>
              <span>{preset.description}</span>
            </button>
          ))}
        </div>
      </section>

      {navigationSections.map((section) => {
        const panels = workspaceDockPanelDefinitions.filter((panel) => panel.section === section);
        if (!panels.length) {
          return null;
        }

        return (
          <section key={section} className="workspace-navigation-rail__section" aria-label={`${section} navigation`}>
            <div className="workspace-navigation-rail__header">{section}</div>
            <div className="workspace-navigation-rail__list">
              {panels.map((panel) => (
                <button
                  key={panel.id}
                  ref={(node) => assignButtonRef(panelRefs.current, panel.id, node)}
                  type="button"
                  className={`workspace-navigation-rail__button${panel.id === focusedPanelId ? " workspace-navigation-rail__button--active" : ""}`}
                  aria-pressed={panel.id === focusedPanelId}
                  aria-keyshortcuts={toAriaKeyShortcuts(panel.shortcut)}
                  tabIndex={panel.id === focusedPanelId ? 0 : -1}
                  onClick={() => onFocusPanel(panel.id)}
                  onKeyDown={(event) => {
                    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
                      return;
                    }

                    event.preventDefault();
                    const currentIndex = panels.findIndex((entry) => entry.id === panel.id);
                    const nextIndex = getRovingIndex(event.key, Math.max(currentIndex, 0), panels.length);
                    const nextPanel = panels[nextIndex];
                    if (!nextPanel) {
                      return;
                    }

                    onFocusPanel(nextPanel.id);
                    requestAnimationFrame(() => panelRefs.current.get(nextPanel.id)?.focus());
                  }}
                >
                  <strong>{panel.title}</strong>
                  <span>{panel.shortcut || panel.description}</span>
                </button>
              ))}
            </div>
          </section>
        );
      })}

      <section className="workspace-navigation-rail__section" aria-label="Output channels">
        <div className="workspace-navigation-rail__header">Outputs</div>
        <div className="workspace-navigation-rail__list">
          {outputChannels.map((channel) => (
            <button
              key={channel.id}
              ref={(node) => assignButtonRef(outputRefs.current, channel.id, node)}
              type="button"
              className={`workspace-navigation-rail__button${channel.id === activeOutputChannelId ? " workspace-navigation-rail__button--active" : ""}`}
              aria-pressed={channel.id === activeOutputChannelId}
              tabIndex={channel.id === activeOutputChannelId ? 0 : -1}
              onClick={() => onSelectOutputChannel(channel.id)}
              onKeyDown={(event) => {
                if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
                  return;
                }

                event.preventDefault();
                const currentIndex = outputChannels.findIndex((entry) => entry.id === channel.id);
                const nextIndex = getRovingIndex(event.key, Math.max(currentIndex, 0), outputChannels.length);
                const nextChannel = outputChannels[nextIndex];
                if (!nextChannel) {
                  return;
                }

                onSelectOutputChannel(nextChannel.id);
                requestAnimationFrame(() => outputRefs.current.get(nextChannel.id)?.focus());
              }}
            >
              <strong>{channel.label}</strong>
              <span>{channel.entries[0]?.summary ?? "No shell output yet."}</span>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}