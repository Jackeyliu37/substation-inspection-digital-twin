export const DEFAULT_TWIN_CAMERA = Object.freeze({
  yaw: 0.71,
  pitch: 0.5,
  distance: 21,
  targetX: 0,
  targetY: 0,
  targetZ: 0,
});

const finite = (value, fallback) => Number.isFinite(Number(value)) ? Number(value) : fallback;
const clamp = (value, minimum, maximum) => Math.min(maximum, Math.max(minimum, value));

export function normalizeTwinCamera(camera) {
  return {
    yaw: finite(camera?.yaw, DEFAULT_TWIN_CAMERA.yaw),
    pitch: clamp(finite(camera?.pitch, DEFAULT_TWIN_CAMERA.pitch), -0.05, 1.35),
    distance: clamp(finite(camera?.distance, DEFAULT_TWIN_CAMERA.distance), 5, 42),
    targetX: clamp(finite(camera?.targetX, DEFAULT_TWIN_CAMERA.targetX), -12, 12),
    targetY: clamp(finite(camera?.targetY, DEFAULT_TWIN_CAMERA.targetY), -2, 8),
    targetZ: clamp(finite(camera?.targetZ, DEFAULT_TWIN_CAMERA.targetZ), -12, 12),
  };
}

export function orbitTwinCamera(camera, yawDelta, pitchDelta) {
  const current = normalizeTwinCamera(camera);
  return normalizeTwinCamera({
    ...current,
    yaw: current.yaw + finite(yawDelta, 0),
    pitch: current.pitch + finite(pitchDelta, 0),
  });
}

export function zoomTwinCamera(camera, factor) {
  const current = normalizeTwinCamera(camera);
  return normalizeTwinCamera({
    ...current,
    distance: current.distance * finite(factor, 1),
  });
}

export function panTwinCamera(camera, horizontal, vertical) {
  const current = normalizeTwinCamera(camera);
  const dx = finite(horizontal, 0);
  const dy = finite(vertical, 0);
  return normalizeTwinCamera({
    ...current,
    targetX: current.targetX + Math.cos(current.yaw) * dx,
    targetZ: current.targetZ - Math.sin(current.yaw) * dx,
    targetY: current.targetY + dy,
  });
}

export function twinCameraPosition(camera) {
  const current = normalizeTwinCamera(camera);
  const horizontal = current.distance * Math.cos(current.pitch);
  return {
    x: current.targetX + horizontal * Math.sin(current.yaw),
    y: current.targetY + current.distance * Math.sin(current.pitch),
    z: current.targetZ + horizontal * Math.cos(current.yaw),
  };
}
