export function decodeOccupancyData(encoded, width, height) {
  if (typeof encoded !== "string" || !Number.isInteger(width) || !Number.isInteger(height) || width <= 0 || height <= 0) {
    throw new TypeError("invalid occupancy grid metadata");
  }
  const binary = globalThis.atob(encoded);
  if (binary.length !== width * height) throw new RangeError("occupancy grid length mismatch");
  const values = new Int8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    const value = binary.charCodeAt(index);
    values[index] = value > 127 ? value - 256 : value;
  }
  return values;
}

export function occupancyCellColor(value) {
  if (value < 0) return [8, 17, 23];
  if (value >= 65) return [68, 76, 83];
  if (value > 10) return [91, 105, 111];
  return [31, 48, 56];
}

export function worldToMapPixel(point, map) {
  const resolution = Number(map?.resolution_m);
  const width = Number(map?.width_cells);
  const height = Number(map?.height_cells);
  const originX = Number(map?.origin?.x_m);
  const originY = Number(map?.origin?.y_m);
  if (![resolution, width, height, originX, originY, point?.x_m, point?.y_m].every(Number.isFinite) || resolution <= 0) {
    return null;
  }
  return {
    x: (Number(point.x_m) - originX) / resolution,
    y: height - 1 - (Number(point.y_m) - originY) / resolution,
  };
}
