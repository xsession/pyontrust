import type { ReactNode } from "react";
import { penpotShellTokenVars, penpotShellTokens, type PenpotShellTokens } from "./penpotShellTokens";

interface PenpotEditableShellProps {
  tokens?: PenpotShellTokens;
  topBar: ReactNode;
  healthBanner: ReactNode;
  leftRail: ReactNode;
  contentRegion: ReactNode;
  rightInspector: ReactNode;
  bottomStrip: ReactNode;
  statusBar?: ReactNode;
  children?: ReactNode;
}

export function PenpotEditableShell({
  tokens = penpotShellTokens,
  topBar,
  healthBanner,
  leftRail,
  contentRegion,
  rightInspector,
  bottomStrip,
  statusBar,
  children,
}: PenpotEditableShellProps) {
  return (
    <main className="workspace-shell penpot-editable-shell" style={penpotShellTokenVars(tokens)}>
      <header className="shell-layout__top-bar">{topBar}</header>
      {healthBanner}
      <section className="shell-layout__main-grid">
        <div className="shell-layout__left-rail">{leftRail}</div>
        <div className="shell-layout__content-region">{contentRegion}</div>
        <div className="shell-layout__right-inspector">{rightInspector}</div>
      </section>
      <footer className="shell-layout__bottom-strip">{bottomStrip}</footer>
      {statusBar ? <section className="shell-layout__status-bar">{statusBar}</section> : null}
      {children}
    </main>
  );
}