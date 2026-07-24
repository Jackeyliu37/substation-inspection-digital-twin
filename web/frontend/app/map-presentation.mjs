import { worldToMapPixel } from "./map-utils.mjs";

const FOOTPRINT_METERS = Object.freeze({
  power_transformer: [1.8, 1.35],
  breaker: [1.15, 0.8],
  closed_blade_disconnect_switch: [1.4, 0.6],
  current_transformer: [0.8, 0.8],
  potential_transformer: [0.8, 0.8],
  lightning_arrester: [0.55, 0.55],
  glass_disc_insulator: [0.5, 0.5],
  porcelain_pin_insulator: [0.5, 0.5],
  analog_meter: [0.42, 0.42],
});

const LABEL_OFFSETS = Object.freeze([
  [0, -14], [15, -13], [-15, -13], [18, 0], [-18, 0],
  [15, 14], [-15, 14], [0, 17], [28, -20], [-28, -20],
  [30, 0], [-30, 0], [27, 21], [-27, 21], [0, 31],
]);

const finite = (value) => Number.isFinite(Number(value));
const clamp = (value, minimum, maximum) => Math.min(maximum, Math.max(minimum, value));

export function mapPathPoints(points, map) {
  if (!Array.isArray(points)) return [];
  return points
    .map((point) => worldToMapPixel(point, map))
    .filter((point) => point && finite(point.x) && finite(point.y));
}

export function buildAssetMarkers(assets, map) {
  if (!Array.isArray(assets)) return [];
  const resolution = Number(map?.resolution_m);
  if (!finite(resolution) || resolution <= 0) return [];
  const occupiedLabels = [];
  return assets.flatMap((asset, index) => {
    const point = asset?.pose ? worldToMapPixel(asset.pose, map) : null;
    if (!point) return [];
    const [widthM, heightM] = FOOTPRINT_METERS[asset.category] ?? [0.65, 0.65];
    const width = clamp(widthM / resolution, 7, 42);
    const height = clamp(heightM / resolution, 7, 34);
    const offset = LABEL_OFFSETS.find(([dx, dy]) => occupiedLabels.every(
      (label) => Math.hypot(label.x - (point.x + dx), label.y - (point.y + dy)) >= 13,
    )) ?? [0, 14 + (index % 6) * 7];
    const labelX = point.x + offset[0];
    const labelY = point.y + offset[1];
    occupiedLabels.push({ x: labelX, y: labelY });
    return [{
      ...point,
      width,
      height,
      labelX,
      labelY,
      asset,
      index,
    }];
  });
}
