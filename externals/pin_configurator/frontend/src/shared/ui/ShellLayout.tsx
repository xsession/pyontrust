import type { ReactNode } from "react";

interface ShellLayoutProps {
  children: ReactNode;
}

export function ShellFrame({ children }: ShellLayoutProps) {
  return <main className="workspace-shell">{children}</main>;
}

export function ShellTopBar({ children }: ShellLayoutProps) {
  return <header className="shell-layout__top-bar">{children}</header>;
}

export function ShellMainGrid({ children }: ShellLayoutProps) {
  return <section className="shell-layout__main-grid">{children}</section>;
}

export function ShellLeftRail({ children }: ShellLayoutProps) {
  return <div className="shell-layout__left-rail">{children}</div>;
}

export function ShellContentRegion({ children }: ShellLayoutProps) {
  return <div className="shell-layout__content-region">{children}</div>;
}

export function ShellRightInspector({ children }: ShellLayoutProps) {
  return <div className="shell-layout__right-inspector">{children}</div>;
}

export function ShellBottomStrip({ children }: ShellLayoutProps) {
  return <footer className="shell-layout__bottom-strip">{children}</footer>;
}

export function ShellStatusBar({ children }: ShellLayoutProps) {
  return <section className="shell-layout__status-bar">{children}</section>;
}