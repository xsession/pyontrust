import { useCallback, useMemo, useRef, useState } from "react";

export interface SceneViewportState {
  zoom: number;
  offsetX: number;
  offsetY: number;
  isDragging: boolean;
  zoomIn: () => void;
  zoomOut: () => void;
  reset: () => void;
  fit: () => void;
  beginPan: (clientX: number, clientY: number) => void;
  movePan: (clientX: number, clientY: number) => void;
  endPan: () => void;
  transform: string;
}

interface UseSceneViewportOptions {
  minZoom?: number;
  maxZoom?: number;
  step?: number;
  fitZoom?: number;
}

export function useSceneViewport(options?: UseSceneViewportOptions): SceneViewportState {
  const minZoom = options?.minZoom ?? 0.6;
  const maxZoom = options?.maxZoom ?? 2.8;
  const step = options?.step ?? 0.2;
  const fitZoom = options?.fitZoom ?? 0.92;
  const [zoom, setZoom] = useState(1);
  const [offsetX, setOffsetX] = useState(0);
  const [offsetY, setOffsetY] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const dragRef = useRef<{ originX: number; originY: number; offsetX: number; offsetY: number } | null>(null);

  const clampZoom = useCallback((value: number) => Math.min(maxZoom, Math.max(minZoom, value)), [maxZoom, minZoom]);

  const zoomIn = useCallback(() => {
    setZoom((current) => clampZoom(current + step));
  }, [clampZoom, step]);

  const zoomOut = useCallback(() => {
    setZoom((current) => clampZoom(current - step));
  }, [clampZoom, step]);

  const reset = useCallback(() => {
    setZoom(1);
    setOffsetX(0);
    setOffsetY(0);
  }, []);

  const fit = useCallback(() => {
    setZoom(clampZoom(fitZoom));
    setOffsetX(0);
    setOffsetY(0);
  }, [clampZoom, fitZoom]);

  const beginPan = useCallback((clientX: number, clientY: number) => {
    dragRef.current = {
      originX: clientX,
      originY: clientY,
      offsetX,
      offsetY,
    };
    setIsDragging(true);
  }, [offsetX, offsetY]);

  const movePan = useCallback((clientX: number, clientY: number) => {
    if (!dragRef.current) {
      return;
    }

    const deltaX = clientX - dragRef.current.originX;
    const deltaY = clientY - dragRef.current.originY;
    setOffsetX(dragRef.current.offsetX + deltaX / zoom);
    setOffsetY(dragRef.current.offsetY + deltaY / zoom);
  }, [zoom]);

  const endPan = useCallback(() => {
    dragRef.current = null;
    setIsDragging(false);
  }, []);

  const transform = useMemo(
    () => `translate(${offsetX} ${offsetY}) scale(${zoom})`,
    [offsetX, offsetY, zoom],
  );

  return {
    zoom,
    offsetX,
    offsetY,
    isDragging,
    zoomIn,
    zoomOut,
    reset,
    fit,
    beginPan,
    movePan,
    endPan,
    transform,
  };
}