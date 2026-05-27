import type { CSSProperties } from "react";

export interface PenpotShellTokens {
  shellPadding: string;
  shellBackground: string;
  topBarGap: string;
  topBarMargin: string;
  mainGridColumns: string;
  mainGridGap: string;
  chromeRadius: string;
  chromeBorder: string;
  chromeBackground: string;
  chromeShadow: string;
  panelRadius: string;
  panelPadding: string;
  panelHeaderGap: string;
  panelHeaderDivider: string;
  healthBannerPadding: string;
  healthBannerRadius: string;
  healthBannerBorder: string;
  healthBannerBackground: string;
}

export const penpotShellTokens: PenpotShellTokens = {
  shellPadding: "0.85rem 1rem 1rem",
  shellBackground:
    "radial-gradient(circle at top right, rgba(137, 180, 250, 0.12), transparent 26%), linear-gradient(180deg, rgba(45, 45, 68, 0.96) 0%, rgba(30, 30, 46, 0.98) 22%, #1e1e2e 100%)",
  topBarGap: "0.65rem",
  topBarMargin: "0.65rem",
  mainGridColumns: "minmax(15rem, 17rem) minmax(0, 1.45fr) minmax(14rem, 16rem)",
  mainGridGap: "0.9rem",
  chromeRadius: "6px",
  chromeBorder: "1px solid var(--border-workspace-chrome)",
  chromeBackground: "var(--surface-workspace-chrome)",
  chromeShadow: "var(--shadow-workspace-chrome)",
  panelRadius: "var(--workspace-panel-radius)",
  panelPadding: "0.75rem 0.85rem",
  panelHeaderGap: "0.55rem",
  panelHeaderDivider: "1px solid rgba(69, 71, 90, 0.92)",
  healthBannerPadding: "0.65rem 0.85rem",
  healthBannerRadius: "8px",
  healthBannerBorder: "1px solid var(--border-workspace-panel)",
  healthBannerBackground: "linear-gradient(180deg, rgba(45, 45, 68, 0.96), rgba(37, 37, 56, 0.98))",
};

export function penpotShellTokenVars(tokens: PenpotShellTokens = penpotShellTokens): CSSProperties {
  return {
    "--penpot-shell-padding": tokens.shellPadding,
    "--penpot-shell-background": tokens.shellBackground,
    "--penpot-top-bar-gap": tokens.topBarGap,
    "--penpot-top-bar-margin": tokens.topBarMargin,
    "--penpot-main-grid-columns": tokens.mainGridColumns,
    "--penpot-main-grid-gap": tokens.mainGridGap,
    "--penpot-chrome-radius": tokens.chromeRadius,
    "--penpot-chrome-border": tokens.chromeBorder,
    "--penpot-chrome-background": tokens.chromeBackground,
    "--penpot-chrome-shadow": tokens.chromeShadow,
    "--penpot-panel-radius": tokens.panelRadius,
    "--penpot-panel-padding": tokens.panelPadding,
    "--penpot-panel-header-gap": tokens.panelHeaderGap,
    "--penpot-panel-header-divider": tokens.panelHeaderDivider,
    "--penpot-health-banner-padding": tokens.healthBannerPadding,
    "--penpot-health-banner-radius": tokens.healthBannerRadius,
    "--penpot-health-banner-border": tokens.healthBannerBorder,
    "--penpot-health-banner-background": tokens.healthBannerBackground,
  } as CSSProperties;
}