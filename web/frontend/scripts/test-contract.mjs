import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { newCommandId } from "../app/command-id.mjs";
import { decodeOccupancyData, worldToMapPixel } from "../app/map-utils.mjs";
import {
  DEFAULT_VIEWPORT,
  panViewport,
  rotateViewport,
  viewportTransform,
  zoomViewport,
} from "../app/map-viewport.mjs";
import {
  DEFAULT_TWIN_CAMERA,
  orbitTwinCamera,
  panTwinCamera,
  twinCameraPosition,
  zoomTwinCamera,
} from "../app/twin-camera.mjs";
import {
  needsAutonomousMode,
  needsMissionStart,
  needsMissionStop,
  recoverySteps,
} from "../app/command-flow.mjs";
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
for (const command of ["/api/v1/missions/resume", "/api/v1/missions/stop", "/api/v1/robot/mode"]) {
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
for (const readabilityTerm of ["font-size:16px", ".safety-banner", ".operator-guide", ".primary-action"]) {
  if (!css.includes(readabilityTerm)) throw new Error(`missing operator readability style: ${readabilityTerm}`);
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
  "viewportTransform(viewport)",
  "onWheel={handleWheel}",
  "onPointerDown={handlePointerDown}",
  "向左旋转",
  "复位地图",
  "恢复并开始自动巡检",
  "recoverySteps(robot, mission)",
  "waitForSnapshot",
  "waitForCommand",
]) {
  if (!page.includes(implementationTerm)) throw new Error(`missing live console behavior: ${implementationTerm}`);
}
for (const placeholder of ["production model unavailable", "地图数据将由 Gateway", "生产集成待定"]) {
  if (page.includes(placeholder)) throw new Error(`placeholder UI remains: ${placeholder}`);
}
for (const acceptanceFeature of [
  "TwinCameraControls",
  "ScenarioEffect",
  "当前仿真场景",
  "左键拖动旋转",
  "右键或 Shift+拖动平移",
  "ModelShowcase",
  "模型检测效果",
  "/model-showcase/safety-1.jpg",
  "/model-showcase/equipment-1.jpg",
  "/model-showcase/fault-1.jpg",
  "/model-showcase/meter-1.jpg",
]) {
  if (!page.includes(acceptanceFeature)) throw new Error(`missing acceptance feature: ${acceptanceFeature}`);
}
if (page.includes("已按项目决策接受阈值豁免")) {
  throw new Error("threshold waiver wording must not be shown in the product UI");
}
if (page.includes('<text x={point.x + 4}')) {
  throw new Error("full asset labels must not clutter the occupancy map");
}
for (const visualStyle of ["aspect-ratio:", "rotate(-90deg)", ".model-showcase-grid", ".twin-toolbar"]) {
  if (!css.includes(visualStyle)) throw new Error(`missing acceptance visual style: ${visualStyle}`);
}

const decoded = decodeOccupancyData("/wAyZA==", 4, 1);
if (decoded.length !== 4 || decoded[0] !== -1 || decoded[1] !== 0 || decoded[2] !== 50 || decoded[3] !== 100) {
  throw new Error(`occupancy decoding failed: ${Array.from(decoded)}`);
}
const pixel = worldToMapPixel({ x_m: 1, y_m: 2 }, {
  origin: { x_m: -1, y_m: -2 }, resolution_m: 0.5, width_cells: 10, height_cells: 12,
});
if (pixel.x !== 4 || pixel.y !== 3) throw new Error(`world/map transform failed: ${JSON.stringify(pixel)}`);

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
const zoomed = zoomViewport(DEFAULT_VIEWPORT, 20);
if (zoomed.scale !== 6) throw new Error(`map maximum zoom clamp failed: ${zoomed.scale}`);
const zoomedOut = zoomViewport(DEFAULT_VIEWPORT, 0.01);
if (zoomedOut.scale !== 0.75) throw new Error(`map minimum zoom clamp failed: ${zoomedOut.scale}`);
const panned = panViewport(DEFAULT_VIEWPORT, 18, -7);
if (panned.x !== 18 || panned.y !== -7) throw new Error(`map pan failed: ${JSON.stringify(panned)}`);
const rotated = rotateViewport(DEFAULT_VIEWPORT, 15);
if (rotated.rotation !== 15) throw new Error(`map rotation failed: ${rotated.rotation}`);
if (viewportTransform({ scale: 2, x: 18, y: -7, rotation: 15 }) !== "translate(18px, -7px) rotate(15deg) scale(2)") {
  throw new Error("map CSS transform is not deterministic");
}
const twinRotated = orbitTwinCamera(DEFAULT_TWIN_CAMERA, 0.25, -0.1);
if (twinRotated.yaw !== DEFAULT_TWIN_CAMERA.yaw + 0.25 || twinRotated.pitch !== DEFAULT_TWIN_CAMERA.pitch - 0.1) {
  throw new Error(`twin orbit transform failed: ${JSON.stringify(twinRotated)}`);
}
const twinZoomed = zoomTwinCamera(DEFAULT_TWIN_CAMERA, 0.01);
if (twinZoomed.distance !== 5) throw new Error(`twin zoom clamp failed: ${twinZoomed.distance}`);
const twinPanned = panTwinCamera(DEFAULT_TWIN_CAMERA, 1, 0.5);
if (twinPanned.targetY !== 0.5 || twinPanned.targetX === 0) throw new Error(`twin pan failed: ${JSON.stringify(twinPanned)}`);
const twinPosition = twinCameraPosition(DEFAULT_TWIN_CAMERA);
if (![twinPosition.x, twinPosition.y, twinPosition.z].every(Number.isFinite)) {
  throw new Error(`twin camera position is invalid: ${JSON.stringify(twinPosition)}`);
}
const latched = { mode: "estop", emergency_stop: { latched: true } };
const manual = { mode: "manual", emergency_stop: { latched: false } };
const autonomous = { mode: "autonomous", emergency_stop: { latched: false } };
if (!needsMissionStop(latched, { state: "running" })) throw new Error("latched running mission must stop first");
if (!needsMissionStart({ state: "stopped" })) throw new Error("stopped mission must be started");
if (!needsAutonomousMode(manual)) throw new Error("manual robot must enter autonomous mode");
if (JSON.stringify(recoverySteps(latched, { state: "running" })) !== JSON.stringify(["stop", "reset", "start", "autonomous"])) {
  throw new Error("latched recovery flow is unsafe or incomplete");
}
if (JSON.stringify(recoverySteps(manual, { state: "stopped" })) !== JSON.stringify(["start", "autonomous"])) {
  throw new Error("stopped manual recovery flow is incomplete");
}
if (JSON.stringify(recoverySteps(manual, { state: "paused" })) !== JSON.stringify(["resume", "autonomous"])) {
  throw new Error("paused mission recovery flow is incomplete");
}
if (recoverySteps(autonomous, { state: "running" }).length !== 0) throw new Error("healthy autonomous flow must be a no-op");
console.log(`frontend contract: PASS (${requiredViews.length} views, REST/WS boundary locked)`);
