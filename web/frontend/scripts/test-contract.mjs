import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { newCommandId } from "../app/command-id.mjs";
import { decodeOccupancyData, worldToMapPixel } from "../app/map-utils.mjs";
import {
  assetLabel,
  categoryLabel,
  commandErrorLabel,
  missionStateLabel,
  modelLabel,
  riskLabel,
  robotModeLabel,
  scenarioLabel,
} from "../app/ui-labels.mjs";

const root = resolve(new URL("..", import.meta.url).pathname);
const page = await readFile(resolve(root, "app/page.js"), "utf8");
const css = await readFile(resolve(root, "app/globals.css"), "utf8");

const requiredViews = ["驾驶舱", "三维数字孪生", "地图与导航", "风险告警", "感知视频", "仿真场景", "巡检报告", "系统状态"];
for (const view of requiredViews) {
  if (!page.includes(view)) throw new Error(`missing required view: ${view}`);
}
for (const endpoint of ["/api/v1/system/status", "/api/v1/robot/state", "/api/v1/assets", "/api/v1/missions/current", "/api/v1/map", "/api/v1/models", "/api/v1/simulation/scenario", "/api/v1/reports"]) {
  if (!page.includes(endpoint)) throw new Error(`missing REST endpoint: ${endpoint}`);
}
for (const command of ["/api/v1/missions/resume", "/api/v1/missions/stop"]) {
  if (!page.includes(command)) throw new Error(`missing mission command: ${command}`);
}
for (const socket of ["/ws/telemetry", "/ws/events", "/ws/camera"]) {
  if (!page.includes(socket)) throw new Error(`missing websocket endpoint: ${socket}`);
}
for (const cameraContractTerm of ["metadataLength", "jpegLength", "64 + metadataLength + jpegLength", "binaryType = \"arraybuffer\""]) {
  if (!page.includes(cameraContractTerm)) throw new Error(`missing camera framing validation: ${cameraContractTerm}`);
}
if (!page.includes("数据服务不可用") || !page.includes("生产权重已接入")) {
  throw new Error("missing explicit degraded/production model state");
}
for (const labelHelper of ["assetLabel(", "categoryLabel(", "riskLabel(", "missionStateLabel(", "robotModeLabel(", "modelLabel("]) {
  if (!page.includes(labelHelper)) throw new Error(`page does not use Chinese label helper: ${labelHelper}`);
}
for (const engineeringHeading of ["OPERATIONS /", "GAZEBO SCENARIO", "revision ${", "Gateway 不可用"]) {
  if (page.includes(engineeringHeading)) throw new Error(`engineering copy remains visible: ${engineeringHeading}`);
}
if (page.includes("rosbridge") || page.includes("rclpy") || page.includes("/perception/detections")) {
  throw new Error("frontend must not connect to ROS DDS or production perception topic");
}
if (!css.includes("--accent") || !css.includes("grid-template-columns")) {
  throw new Error("missing control-center visual system");
}

const nativeId = "123e4567-e89b-42d3-a456-426614174000";
if (newCommandId({ randomUUID: () => nativeId }) !== nativeId) {
  throw new Error("native randomUUID path is not used when available");
}
const fallbackId = newCommandId({
  getRandomValues(bytes) {
    bytes.fill(0xab);
    return bytes;
  },
});
if (!/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(fallbackId)) {
  throw new Error(`HTTP-safe UUIDv4 fallback is invalid: ${fallbackId}`);
}
if (page.includes("crypto.randomUUID()") || !page.includes("newCommandId(globalThis.crypto)")) {
  throw new Error("commands must use the HTTP-safe UUIDv4 helper");
}
if (!page.includes('reason: "operator web emergency stop"')) {
  throw new Error("emergency stop must include its required audit reason");
}
for (const implementationTerm of [
  "assets?.items",
  "asset.pose",
  "OccupancyMap",
  "RobotModel",
  "mission?.tasks",
  "fire-smoke",
  "gas-high",
  "meter-limit",
  "combined-risk-obstacle",
]) {
  if (!page.includes(implementationTerm)) throw new Error(`missing live console behavior: ${implementationTerm}`);
}
for (const placeholder of ["production model unavailable", "地图数据将由 Gateway", "生产集成待定"]) {
  if (page.includes(placeholder)) throw new Error(`placeholder UI remains: ${placeholder}`);
}

const decoded = decodeOccupancyData("/wAyZA==", 4, 1);
if (decoded.length !== 4 || decoded[0] !== -1 || decoded[1] !== 0 || decoded[2] !== 50 || decoded[3] !== 100) {
  throw new Error(`occupancy decoding failed: ${Array.from(decoded)}`);
}
const pixel = worldToMapPixel({ x_m: 1, y_m: 2 }, {
  origin: { x_m: -1, y_m: -2 }, resolution_m: 0.5, width_cells: 10, height_cells: 12,
});
if (pixel.x !== 4 || pixel.y !== 4) throw new Error(`world/map transform failed: ${JSON.stringify(pixel)}`);

const expectedLabels = [
  [assetLabel("transformer-01"), "主变压器"],
  [assetLabel("meter-pressure-01"), "压力表"],
  [categoryLabel("lightning_arrester"), "避雷器"],
  [categoryLabel("closed_blade_disconnect_switch"), "闭合刀闸隔离开关"],
  [riskLabel("unknown"), "待评估"],
  [riskLabel("emergency"), "紧急"],
  [missionStateLabel("running"), "巡检中"],
  [robotModeLabel("autonomous"), "自动巡检"],
  [scenarioLabel("gas-high"), "气体浓度超限"],
  [modelLabel("yolo11n_equipment"), "电力设备检测模型"],
];
for (const [actual, expected] of expectedLabels) {
  if (actual !== expected) throw new Error(`Chinese UI label mismatch: ${actual} !== ${expected}`);
}
if (categoryLabel("future_device") !== "future_device") throw new Error("unknown category fallback changed");
if (!commandErrorLabel("wait for no active goal and 0.5 seconds of zero velocity").includes("停止当前任务")) {
  throw new Error("motion-safety error is not localized");
}
console.log(`frontend contract: PASS (${requiredViews.length} views, REST/WS boundary locked)`);
