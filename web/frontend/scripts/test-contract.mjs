import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

const root = resolve(new URL("..", import.meta.url).pathname);
const page = await readFile(resolve(root, "app/page.js"), "utf8");
const css = await readFile(resolve(root, "app/globals.css"), "utf8");

const requiredViews = ["驾驶舱", "三维数字孪生", "地图与导航", "风险告警", "感知视频", "仿真场景", "巡检报告", "系统状态"];
for (const view of requiredViews) {
  if (!page.includes(view)) throw new Error(`missing required view: ${view}`);
}
for (const endpoint of ["/api/v1/system/status", "/api/v1/robot/state", "/api/v1/assets", "/api/v1/missions/current"]) {
  if (!page.includes(endpoint)) throw new Error(`missing REST endpoint: ${endpoint}`);
}
for (const socket of ["/ws/telemetry", "/ws/events", "/ws/camera"]) {
  if (!page.includes(socket)) throw new Error(`missing websocket endpoint: ${socket}`);
}
for (const cameraContractTerm of ["metadataLength", "jpegLength", "64 + metadataLength + jpegLength", "binaryType = \"arraybuffer\""]) {
  if (!page.includes(cameraContractTerm)) throw new Error(`missing camera framing validation: ${cameraContractTerm}`);
}
if (!page.includes("Gateway 不可用") || !page.includes("production")) {
  throw new Error("missing explicit degraded/production model state");
}
if (page.includes("rosbridge") || page.includes("rclpy") || page.includes("/perception/detections")) {
  throw new Error("frontend must not connect to ROS DDS or production perception topic");
}
if (!css.includes("--accent") || !css.includes("grid-template-columns")) {
  throw new Error("missing control-center visual system");
}
console.log(`frontend contract: PASS (${requiredViews.length} views, REST/WS boundary locked)`);
