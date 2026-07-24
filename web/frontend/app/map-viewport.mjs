export const DEFAULT_VIEWPORT = Object.freeze({
  scale: 1,
  x: 0,
  y: 0,
  rotation: 0,
});

const finite = (value, fallback) => Number.isFinite(Number(value)) ? Number(value) : fallback;
const clamp = (value, minimum, maximum) => Math.min(maximum, Math.max(minimum, value));

export function zoomViewport(viewport, factor) {
  const current = finite(viewport?.scale, DEFAULT_VIEWPORT.scale);
  const multiplier = finite(factor, 1);
  return { ...DEFAULT_VIEWPORT, ...viewport, scale: clamp(current * multiplier, 0.75, 6) };
}

export function panViewport(viewport, dx, dy) {
  return {
    ...DEFAULT_VIEWPORT,
    ...viewport,
    x: finite(viewport?.x, 0) + finite(dx, 0),
    y: finite(viewport?.y, 0) + finite(dy, 0),
  };
}

export function rotateViewport(viewport, degrees) {
  const value = finite(viewport?.rotation, 0) + finite(degrees, 0);
  const normalized = ((value + 180) % 360 + 360) % 360 - 180;
  return { ...DEFAULT_VIEWPORT, ...viewport, rotation: normalized };
}

export function viewportTransform(viewport) {
  const value = { ...DEFAULT_VIEWPORT, ...viewport };
  return `translate(${finite(value.x, 0)}px, ${finite(value.y, 0)}px) rotate(${finite(value.rotation, 0)}deg) scale(${finite(value.scale, 1)})`;
}
