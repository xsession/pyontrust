interface SceneViewportToolbarProps {
  zoom: number;
  onZoomOut: () => void;
  onZoomIn: () => void;
  onFit: () => void;
  onReset: () => void;
  children?: React.ReactNode;
}

export function SceneViewportToolbar({ zoom, onZoomOut, onZoomIn, onFit, onReset, children }: SceneViewportToolbarProps) {
  return (
    <div className="scene-toolbar" role="toolbar" aria-label="Scene viewport controls">
      <div className="scene-toolbar__group">
        <button type="button" className="shell-button shell-button--ghost" onClick={onZoomOut} aria-label="Zoom out">
          -
        </button>
        <span className="scene-toolbar__zoom">{`${Math.round(zoom * 100)}%`}</span>
        <button type="button" className="shell-button shell-button--ghost" onClick={onZoomIn} aria-label="Zoom in">
          +
        </button>
      </div>
      <div className="scene-toolbar__group">
        <button type="button" className="shell-button shell-button--ghost" onClick={onFit}>
          Fit
        </button>
        <button type="button" className="shell-button shell-button--ghost" onClick={onReset}>
          Reset
        </button>
      </div>
      {children ? <div className="scene-toolbar__meta">{children}</div> : null}
    </div>
  );
}