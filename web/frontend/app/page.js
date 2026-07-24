"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { newCommandId } from "./command-id.mjs";
import { decodeOccupancyData, worldToMapPixel } from "./map-utils.mjs";
import {
  DEFAULT_VIEWPORT,
  panViewport,
  rotateViewport,
  viewportTransform,
  zoomViewport,
} from "./map-viewport.mjs";
import { recoverySteps } from "./command-flow.mjs";
import {
  DEFAULT_TWIN_CAMERA,
  normalizeTwinCamera,
  orbitTwinCamera,
  panTwinCamera,
  twinCameraPosition,
  zoomTwinCamera,
} from "./twin-camera.mjs";
import {
  assetLabel,
  categoryLabel,
  commandErrorLabel,
  eventLabel,
  missionStateLabel,
  modelLabel,
  riskLabel,
  robotModeLabel,
  scenarioLabel,
} from "./ui-labels.mjs";

const VIEWS = [
  ["dashboard", "驾驶舱", "总览"],
  ["twin", "三维数字孪生", "孪生"],
  ["map", "地图与导航", "地图"],
  ["risk", "风险告警", "风险"],
  ["perception", "感知视频", "感知"],
  ["scenario", "仿真场景", "场景"],
  ["reports", "巡检报告", "报告"],
  ["system", "系统状态", "系统"],
];

const MODEL_SHOWCASES = [
  {
    model: "yolo11n_safety",
    name: "人员与安全风险检测",
    purpose: "识别人员、安全帽、未佩戴安全帽、火焰和烟雾",
    images: ["/model-showcase/safety-1.jpg", "/model-showcase/safety-2.jpg", "/model-showcase/safety-3.jpg"],
  },
  {
    model: "yolo11n_equipment",
    name: "电力设备检测",
    purpose: "识别变压器、断路器、隔离开关、绝缘子等设备",
    images: ["/model-showcase/equipment-1.jpg", "/model-showcase/equipment-2.jpg", "/model-showcase/equipment-3.jpg"],
  },
  {
    model: "yolo11n_fault",
    name: "设备缺陷分类",
    purpose: "区分正常、锈蚀、部件破损和鸟巢异物",
    images: ["/model-showcase/fault-1.jpg", "/model-showcase/fault-2.jpg", "/model-showcase/fault-3.jpg"],
  },
  {
    model: "meter_locator",
    name: "仪表定位检测",
    purpose: "定位模拟仪表区域，为后续读数解析提供裁剪目标",
    images: ["/model-showcase/meter-1.jpg", "/model-showcase/meter-2.jpg", "/model-showcase/meter-3.jpg"],
  },
];

const SNAPSHOT_ENDPOINTS = [
  "/api/v1/system/status",
  "/api/v1/robot/state",
  "/api/v1/assets",
  "/api/v1/missions/current",
  "/api/v1/map",
  "/api/v1/models",
  "/api/v1/simulation/scenario",
  "/api/v1/reports",
];
const REQUIRED_ENDPOINTS = SNAPSHOT_ENDPOINTS.slice(0, 4);
const apiData = (value) => value?.data ?? value ?? null;
const now = () => new Date().toLocaleTimeString("zh-CN", { hour12: false });
const delay = (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

async function fetchSnapshot(endpoint) {
  const response = await fetch(endpoint, { headers: { accept: "application/json" }, cache: "no-store" });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload?.detail || payload?.code || `HTTP ${response.status}`);
  return apiData(payload);
}

async function waitForSnapshot(endpoint, predicate, timeoutMilliseconds = 8000) {
  const deadline = Date.now() + timeoutMilliseconds;
  let snapshot = null;
  while (Date.now() < deadline) {
    snapshot = await fetchSnapshot(endpoint);
    if (predicate(snapshot)) return snapshot;
    await delay(200);
  }
  throw new Error("等待机器人状态更新超时");
}

async function waitForCommand(commandId, timeoutMilliseconds = 8000) {
  const deadline = Date.now() + timeoutMilliseconds;
  let command = null;
  while (Date.now() < deadline) {
    command = await fetchSnapshot(`/api/v1/commands/${commandId}`);
    if (command?.status === "succeeded") return command;
    if (command?.status && command.status !== "accepted") {
      throw new Error(command.error?.message || command.error?.code || "命令执行失败");
    }
    await delay(200);
  }
  throw new Error("等待命令执行结果超时");
}

async function submitCommand(endpoint, body, { waitForTerminal = true } = {}) {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json", "Idempotency-Key": newCommandId(globalThis.crypto) },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload?.detail || payload?.title || payload?.code || `HTTP ${response.status}`);
  if (waitForTerminal && payload.command_id) return waitForCommand(payload.command_id);
  return payload;
}

function socketUrl(path) {
  if (typeof window === "undefined") return path;
  return `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}${path}`;
}

function StatusPill({ connection }) {
  const label = connection === "live" ? "实时连接" : connection === "recovering" ? "正在恢复" : "数据服务不可用";
  return <span className={`status-pill ${connection}`}>{label}</span>;
}

function Metric({ label, value, detail, tone = "neutral" }) {
  return <section className={`metric ${tone}`}><span>{label}</span><strong>{value ?? "--"}</strong><small>{detail ?? "等待实时数据"}</small></section>;
}

function EmptyState({ title, children }) {
  return <div className="empty-state"><strong>{title}</strong><span>{children}</span></div>;
}

export default function HomePage() {
  const [view, setView] = useState("dashboard");
  const [connection, setConnection] = useState("recovering");
  const [snapshots, setSnapshots] = useState({});
  const [events, setEvents] = useState([]);
  const [cameraUrl, setCameraUrl] = useState(null);
  const [cameraMeta, setCameraMeta] = useState(null);
  const [cameraFps, setCameraFps] = useState(0);
  const [trail, setTrail] = useState([]);
  const [commandNote, setCommandNote] = useState("尚未提交命令");
  const [loading, setLoading] = useState(false);
  const cameraObjectUrl = useRef(null);
  const cameraTimes = useRef([]);
  const lastMessageAt = useRef(0);

  const refresh = useCallback(async (showProgress = false) => {
    if (showProgress) setCommandNote("正在刷新实时快照…");
    try {
      const settled = await Promise.allSettled(SNAPSHOT_ENDPOINTS.map(async (endpoint) => {
        const response = await fetch(endpoint, { headers: { accept: "application/json" }, cache: "no-store" });
        if (!response.ok) throw new Error(`${endpoint}: ${response.status}`);
        return [endpoint, apiData(await response.json())];
      }));
      const fulfilled = settled.flatMap((result) => result.status === "fulfilled" ? [result.value] : []);
      setSnapshots((current) => ({ ...current, ...Object.fromEntries(fulfilled) }));
      const available = new Set(fulfilled.map(([endpoint]) => endpoint));
      if (!REQUIRED_ENDPOINTS.every((endpoint) => available.has(endpoint))) throw new Error("required snapshot unavailable");
      setConnection("live");
      lastMessageAt.current = Date.now();
      if (showProgress) setCommandNote("实时快照已刷新");
    } catch {
      setConnection("offline");
      if (showProgress) setCommandNote("刷新失败：实时数据暂时不可用");
    }
  }, []);

  const sendCommand = useCallback(async (endpoint, body = {}) => {
    setLoading(true);
    setCommandNote("命令提交中…");
    try {
      const payload = await submitCommand(endpoint, body);
      setCommandNote(`命令执行成功 ${payload.command_id ?? ""}`.trim());
      await refresh(false);
    } catch (error) {
      setCommandNote(`命令未提交：${commandErrorLabel(error.message)}`);
    } finally {
      setLoading(false);
    }
  }, [refresh]);

  useEffect(() => {
    refresh(false);
    const receive = (message) => {
      lastMessageAt.current = Date.now();
      if (message?.type === "system.health") setSnapshots((current) => ({ ...current, "/api/v1/system/status": message.payload }));
      if (message?.type === "robot.state") setSnapshots((current) => ({ ...current, "/api/v1/robot/state": message.payload }));
      if (message?.type === "mission.state") setSnapshots((current) => ({ ...current, "/api/v1/missions/current": message.payload }));
      if (message?.type === "risk.assets") setSnapshots((current) => ({ ...current, "/api/v1/assets": message.payload }));
      if (message?.type && !["heartbeat", "stream.open"].includes(message.type)) {
        setEvents((current) => [{ type: message.type, timestamp: message.timestamp, payload: message.payload }, ...current].slice(0, 50));
      }
      setConnection("live");
    };
    const openSocket = (path) => {
      const socket = new WebSocket(socketUrl(path), "substation.v1");
      if (path === "/ws/camera") socket.binaryType = "arraybuffer";
      socket.onmessage = (event) => {
        if (typeof event.data === "string") {
          try { receive(JSON.parse(event.data)); } catch { /* ignore a malformed volatile message */ }
          return;
        }
        if (path !== "/ws/camera") return;
        const frame = new Uint8Array(event.data);
        if (frame.byteLength < 64 || String.fromCharCode(...frame.slice(0, 4)) !== "SSCF" || frame[4] !== 1) return;
        const header = new DataView(frame.buffer, frame.byteOffset, frame.byteLength);
        const headerLength = header.getUint16(6, false);
        const metadataLength = header.getUint32(24, false);
        const jpegLength = header.getUint32(28, false);
        if (headerLength !== 64 || metadataLength < 1 || metadataLength > 16384 || jpegLength < 1 || jpegLength > 2097152 || frame.byteLength !== 64 + metadataLength + jpegLength) return;
        let metadata;
        try { metadata = JSON.parse(new TextDecoder().decode(frame.slice(64, 64 + metadataLength))); } catch { return; }
        const jpeg = frame.slice(64 + metadataLength);
        if (jpeg[0] !== 0xff || jpeg[1] !== 0xd8 || jpeg.at(-2) !== 0xff || jpeg.at(-1) !== 0xd9) return;
        const objectUrl = URL.createObjectURL(new Blob([jpeg], { type: "image/jpeg" }));
        if (cameraObjectUrl.current) URL.revokeObjectURL(cameraObjectUrl.current);
        cameraObjectUrl.current = objectUrl;
        setCameraUrl(objectUrl);
        setCameraMeta(metadata);
        const time = performance.now();
        cameraTimes.current = [...cameraTimes.current.filter((item) => time - item < 2000), time];
        if (cameraTimes.current.length > 1) setCameraFps((cameraTimes.current.length - 1) * 1000 / (time - cameraTimes.current[0]));
        lastMessageAt.current = Date.now();
        setConnection("live");
      };
      socket.onerror = () => setConnection((state) => state === "offline" ? state : "recovering");
      socket.onclose = () => setConnection((state) => state === "offline" ? state : "recovering");
      return socket;
    };
    const sockets = [openSocket("/ws/telemetry"), openSocket("/ws/events"), openSocket("/ws/camera")];
    const poller = window.setInterval(() => refresh(false), 2000);
    const watchdog = window.setInterval(() => {
      if (lastMessageAt.current && Date.now() - lastMessageAt.current > 6000) setConnection("offline");
    }, 1000);
    return () => {
      sockets.forEach((socket) => socket.close());
      window.clearInterval(poller);
      window.clearInterval(watchdog);
      if (cameraObjectUrl.current) URL.revokeObjectURL(cameraObjectUrl.current);
    };
  }, [refresh]);

  const system = snapshots["/api/v1/system/status"];
  const robot = snapshots["/api/v1/robot/state"];
  const assets = snapshots["/api/v1/assets"];
  const mission = snapshots["/api/v1/missions/current"];
  const map = snapshots["/api/v1/map"];
  const models = snapshots["/api/v1/models"];
  const scenario = snapshots["/api/v1/simulation/scenario"];
  const reports = snapshots["/api/v1/reports"];
  const assetItems = Array.isArray(assets?.items) ? assets.items : [];
  const modelItems = Array.isArray(models?.items) ? models.items : [];
  const routeGoals = Array.isArray(mission?.tasks) ? mission.tasks.map((task) => task.goal).filter(Boolean) : [];
  const alertItems = events.filter((event) => event.payload?.alert_id).map((event) => event.payload);
  const controlsDisabled = connection !== "live" || loading;

  useEffect(() => {
    const pose = robot?.pose;
    if (!pose || !Number.isFinite(pose.x_m) || !Number.isFinite(pose.y_m)) return;
    setTrail((current) => {
      const last = current.at(-1);
      if (last && Math.hypot(last.x_m - pose.x_m, last.y_m - pose.y_m) < 0.03) return current;
      return [...current, { x_m: pose.x_m, y_m: pose.y_m }].slice(-160);
    });
  }, [robot?.pose?.x_m, robot?.pose?.y_m]);

  const recoverAutonomousInspection = useCallback(async () => {
    setLoading(true);
    setCommandNote("正在检查机器人安全状态…");
    try {
      let currentRobot = await fetchSnapshot("/api/v1/robot/state");
      let currentMission = await fetchSnapshot("/api/v1/missions/current");
      let steps = recoverySteps(robot, mission);
      steps = recoverySteps(currentRobot, currentMission);
      if (!steps.length) {
        setCommandNote("自动巡检已经在运行");
        return;
      }
      for (const step of steps) {
        if (step === "stop") {
          setCommandNote("正在停止旧任务并等待机器人静止…");
          await submitCommand("/api/v1/missions/stop", {
            mission_id: currentMission.mission_id,
            reason: "operator guided autonomous recovery stop",
          });
          currentMission = await waitForSnapshot("/api/v1/missions/current", (value) => value?.state === "stopped");
          await delay(700);
        }
        if (step === "reset") {
          setCommandNote("正在解除紧急停止…");
          let reset = false;
          for (let attempt = 0; attempt < 4 && !reset; attempt += 1) {
            currentRobot = await fetchSnapshot("/api/v1/robot/state");
            try {
              await submitCommand("/api/v1/robot/emergency-stop/reset", {
                observed_latch_revision: String(currentRobot.emergency_stop.latch_revision),
                confirm: true,
                reason: "operator guided autonomous recovery reset",
              });
              reset = true;
            } catch (error) {
              if (!String(error.message).includes("MOTION_SAFETY_BARRIER_PENDING") && !String(error.message).includes("zero velocity")) throw error;
              await delay(750);
            }
          }
          if (!reset) throw new Error("MOTION_SAFETY_BARRIER_PENDING");
          currentRobot = await waitForSnapshot("/api/v1/robot/state", (value) => value?.emergency_stop?.latched === false);
        }
        if (step === "start") {
          setCommandNote("正在建立新的巡检任务…");
          await submitCommand("/api/v1/missions/start", {
            route_id: "default-route",
            reason: "operator guided autonomous inspection start",
          }, { waitForTerminal: false });
          currentMission = await waitForSnapshot("/api/v1/missions/current", (value) => value?.state === "running" && Boolean(value?.mission_id));
        }
        if (step === "resume") {
          setCommandNote("正在继续巡检任务…");
          await submitCommand("/api/v1/missions/resume", {
            mission_id: currentMission.mission_id,
            reason: "operator guided autonomous inspection resume",
          });
          currentMission = await waitForSnapshot("/api/v1/missions/current", (value) => value?.state === "running");
        }
        if (step === "autonomous") {
          setCommandNote("正在切换为自动巡检模式…");
          let autonomous = false;
          for (let attempt = 0; attempt < 4 && !autonomous; attempt += 1) {
            currentMission = await fetchSnapshot("/api/v1/missions/current");
            currentRobot = await fetchSnapshot("/api/v1/robot/state");
            try {
              await submitCommand("/api/v1/robot/mode", {
                mission_id: currentMission.mission_id,
                target_mode: "autonomous",
                observed_state_revision: String(currentMission.state_revision),
                observed_latch_revision: String(currentRobot.emergency_stop.latch_revision),
                reason: "operator guided autonomous mode",
              });
              autonomous = true;
            } catch (error) {
              if (!String(error.message).includes("MOTION_SAFETY_BARRIER_PENDING") && !String(error.message).includes("zero velocity")) throw error;
              await delay(750);
            }
          }
          if (!autonomous) throw new Error("MOTION_SAFETY_BARRIER_PENDING");
          await waitForSnapshot("/api/v1/robot/state", (value) => value?.mode === "autonomous");
        }
      }
      await refresh(false);
      setCommandNote("自动巡检已启动，请在地图或三维数字孪生中观察机器人移动");
    } catch (error) {
      setCommandNote(`自动巡检启动失败：${commandErrorLabel(error.message)}`);
    } finally {
      setLoading(false);
    }
  }, [mission, refresh, robot]);

  const renderView = useMemo(() => ({
    dashboard: <Dashboard robot={robot} mission={mission} assets={assetItems} alerts={alertItems} events={events} onCommand={sendCommand} onRecover={recoverAutonomousInspection} disabled={controlsDisabled} />,
    twin: <TwinView assets={assetItems} robot={robot} routeGoals={routeGoals} trail={trail} scenario={scenario} />,
    map: <MapView robot={robot} map={map} assets={assetItems} mission={mission} />,
    risk: <RiskView assets={assetItems} alerts={alertItems} />,
    perception: <PerceptionView cameraUrl={cameraUrl} cameraMeta={cameraMeta} cameraFps={cameraFps} models={modelItems} />,
    scenario: <ScenarioView scenario={scenario} system={system} onCommand={sendCommand} disabled={controlsDisabled} />,
    reports: <ReportsView connection={connection} reports={reports} />,
    system: <SystemView system={system} models={modelItems} events={events} onRefresh={() => refresh(true)} />,
  }), [alertItems, assetItems, cameraFps, cameraMeta, cameraUrl, connection, controlsDisabled, events, map, mission, modelItems, recoverAutonomousInspection, refresh, robot, routeGoals, scenario, sendCommand, system, trail]);

  return <main className="control-center">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">S</span><div><strong>变电站巡检</strong><small>控制中心</small></div></div>
      <nav aria-label="主导航">{VIEWS.map(([id, label, short]) => <button key={id} className={view === id ? "nav-item active" : "nav-item"} onClick={() => setView(id)}><span>{short.slice(0, 1)}</span>{label}</button>)}</nav>
      <div className="sidebar-foot"><span>生产运行入口</span><small>仿真环境 · 机器人系统 · 数据服务</small></div>
    </aside>
    <section className="workbench">
      <header className="topbar"><div><span className="eyebrow">智能巡检 / {VIEWS.find(([id]) => id === view)?.[1]}</span><h1>{VIEWS.find(([id]) => id === view)?.[1]}</h1></div><div className="top-actions"><span className="clock">{now()}</span><StatusPill connection={connection} /><button className="icon-button" title="刷新实时数据" onClick={() => refresh(true)}>刷新</button><button className="emergency" onClick={() => sendCommand("/api/v1/robot/emergency-stop", { reason: "operator web emergency stop" })} disabled={loading}>紧急停止</button></div></header>
      {connection === "offline" && <div className="connection-banner"><strong>数据服务不可用</strong><span>实时数据已中断，控制操作暂时禁用。</span></div>}
      {robot?.emergency_stop?.latched && <div className="safety-banner"><strong>机器人已紧急停止</strong><span>请点击“恢复并开始自动巡检”。系统会先停止旧任务、等待机器人静止，再安全解除锁定。</span></div>}
      <div className="command-note" aria-live="polite">{commandNote}</div>
      <div className="view-content">{renderView[view]}</div>
    </section>
  </main>;
}

function Dashboard({ robot, mission, assets, alerts, events, onCommand, onRecover, disabled }) {
  const highRisk = assets.filter((asset) => ["alert", "emergency"].includes(asset.risk?.level)).length;
  const missionBody = { mission_id: mission?.mission_id ?? "", reason: "operator web mission control" };
  const autonomousRunning = robot?.mode === "autonomous" && mission?.state === "running" && !robot?.emergency_stop?.latched;
  return <><div className="metric-grid"><Metric label="机器人模式" value={robotModeLabel(robot?.mode)} detail={robot?.current_task_id ? `任务 ${robot.current_task_id.slice(0, 8)}` : "机器人在线"} /><Metric label="电量" value={robot?.battery_percent != null ? `${robot.battery_percent.toFixed(0)}%` : "--"} detail={robot?.stale ? "位姿已过期" : "实时仿真电量"} /><Metric label="高风险资产" value={highRisk} detail={`${assets.length} 个孪生资产`} tone="warning" /><Metric label="风险事件" value={alerts.length} detail="当前运行事件流" tone="danger" /></div><div className="dashboard-grid"><section className="panel mission-panel"><PanelTitle title="巡检任务" action={mission?.route_id ? "默认巡检路线" : "等待路线"} /><div className="progress"><i style={{ width: `${Math.round((mission?.progress_0_1 ?? 0) * 100)}%` }} /></div><div className="mission-stats"><strong>{missionStateLabel(mission?.state ?? "idle")}</strong><span>{Math.round((mission?.progress_0_1 ?? 0) * 100)}% 完成</span></div><div className="operator-guide"><strong>人工验收</strong><span>点击主按钮后，机器人会解除安全锁定并沿十个设备目标自动巡检。请在地图或三维数字孪生中观察位置和轨迹变化。</span></div><div className="button-row"><button className="primary-action" onClick={onRecover} disabled={disabled || autonomousRunning}>{autonomousRunning ? "自动巡检运行中" : "恢复并开始自动巡检"}</button><button className="secondary" onClick={() => onCommand("/api/v1/missions/pause", missionBody)} disabled={disabled || mission?.state !== "running"}>暂停</button><button className="secondary" onClick={() => onCommand("/api/v1/missions/resume", missionBody)} disabled={disabled || mission?.state !== "paused"}>继续</button><button className="secondary" onClick={() => onCommand("/api/v1/missions/stop", missionBody)} disabled={disabled || !["ready", "running", "paused", "stopping"].includes(mission?.state)}>停止</button></div></section><section className="panel"><PanelTitle title="资产状态" action={`${assets.length} 个设备`} />{assets.length ? <AssetRows assets={assets.slice(0, 5)} /> : <EmptyState title="等待资产数据">数字孪生状态尚未到达。</EmptyState>}</section><section className="panel event-panel"><PanelTitle title="事件流" action="最近 50 条" />{events.length ? events.slice(0, 7).map((event, index) => <div className="event" key={`${event.type}-${index}`}><span className="event-dot" /><div><strong>{event.payload?.asset_id ? assetLabel(event.payload.asset_id) : eventLabel(event.type)}</strong><small>{event.timestamp ?? "实时事件"}</small></div></div>) : <EmptyState title="运行平稳">尚无新的风险或命令事件。</EmptyState>}</section></div></>;
}

function TwinView({ assets, robot, routeGoals, trail, scenario }) {
  const controlsRef = useRef(null);
  const activeScenario = scenario?.active ? scenarioLabel(scenario.scenario_id) : "无异常场景";
  return <section className="panel twin-panel"><PanelTitle title="三维数字孪生" action={`${assets.length} 个设备 · 机器人${robot?.stale ? "位姿过期" : "在线"}`} /><div className="twin-stage"><Canvas camera={{ position: [12, 10, 14], fov: 48 }} dpr={[1, 1.5]}><color attach="background" args={["#071016"]} /><ambientLight intensity={1.35} /><directionalLight position={[6, 12, 4]} intensity={3.2} /><TwinCameraControls controlsRef={controlsRef} /><YardModel />{assets.map((asset) => <AssetModel key={asset.asset_id} asset={asset} />)}{routeGoals.map((goal, index) => <RouteMarker key={`${goal.x_m}-${goal.y_m}-${index}`} goal={goal} index={index} />)}{trail.filter((_, index) => index % 4 === 0).map((point, index) => <mesh key={`${point.x_m}-${point.y_m}-${index}`} position={[point.x_m, 0.08, -point.y_m]}><sphereGeometry args={[0.055, 8, 8]} /><meshStandardMaterial color="#5ad7bd" emissive="#174e43" /></mesh>)}{robot?.pose && <RobotModel robot={robot} />}<ScenarioEffect scenario={scenario} /></Canvas><div className="twin-toolbar"><button onClick={() => controlsRef.current?.orbit(-0.28, 0)}>向左旋转</button><button onClick={() => controlsRef.current?.orbit(0.28, 0)}>向右旋转</button><button onClick={() => controlsRef.current?.zoom(0.82)}>放大</button><button onClick={() => controlsRef.current?.zoom(1.22)}>缩小</button><button onClick={() => controlsRef.current?.reset()}>复位视角</button></div><div className={`twin-scenario ${scenario?.active ? "active" : ""}`}><strong>当前仿真场景</strong><span>{activeScenario}</span></div><div className="twin-legend"><strong>三维操作</strong><span>左键拖动旋转</span><span>右键或 Shift+拖动平移</span><span>滚轮缩放 · 双击复位</span></div></div><div className="twin-summary">{assets.map((asset) => <span key={asset.asset_id}><b>{assetLabel(asset.asset_id)}</b>{asset.pose ? `${asset.pose.x_m.toFixed(1)}, ${asset.pose.y_m.toFixed(1)}` : "--"}</span>)}</div></section>;
}

function TwinCameraControls({ controlsRef }) {
  const { camera, gl } = useThree();
  const stateRef = useRef({ ...DEFAULT_TWIN_CAMERA });
  const dragRef = useRef(null);
  useEffect(() => {
    const element = gl.domElement;
    const apply = (next) => {
      stateRef.current = normalizeTwinCamera(next);
      const position = twinCameraPosition(stateRef.current);
      camera.position.set(position.x, position.y, position.z);
      camera.lookAt(stateRef.current.targetX, stateRef.current.targetY, stateRef.current.targetZ);
      camera.updateProjectionMatrix();
    };
    const api = {
      orbit: (yaw, pitch) => apply(orbitTwinCamera(stateRef.current, yaw, pitch)),
      pan: (x, y) => apply(panTwinCamera(stateRef.current, x, y)),
      zoom: (factor) => apply(zoomTwinCamera(stateRef.current, factor)),
      reset: () => apply(DEFAULT_TWIN_CAMERA),
    };
    controlsRef.current = api;
    const pointerDown = (event) => {
      element.setPointerCapture(event.pointerId);
      dragRef.current = {
        pointerId: event.pointerId,
        x: event.clientX,
        y: event.clientY,
        mode: event.button === 2 || event.shiftKey ? "pan" : "orbit",
      };
    };
    const pointerMove = (event) => {
      const drag = dragRef.current;
      if (!drag || drag.pointerId !== event.pointerId) return;
      const dx = event.clientX - drag.x;
      const dy = event.clientY - drag.y;
      if (drag.mode === "pan") api.pan(-dx * 0.012, dy * 0.012);
      else api.orbit(-dx * 0.006, -dy * 0.006);
      dragRef.current = { ...drag, x: event.clientX, y: event.clientY };
    };
    const pointerUp = (event) => {
      if (dragRef.current?.pointerId === event.pointerId) dragRef.current = null;
      if (element.hasPointerCapture(event.pointerId)) element.releasePointerCapture(event.pointerId);
    };
    const wheel = (event) => {
      event.preventDefault();
      api.zoom(Math.exp(event.deltaY * 0.001));
    };
    const contextMenu = (event) => event.preventDefault();
    const reset = () => api.reset();
    element.addEventListener("pointerdown", pointerDown);
    element.addEventListener("pointermove", pointerMove);
    element.addEventListener("pointerup", pointerUp);
    element.addEventListener("pointercancel", pointerUp);
    element.addEventListener("wheel", wheel, { passive: false });
    element.addEventListener("contextmenu", contextMenu);
    element.addEventListener("dblclick", reset);
    apply(DEFAULT_TWIN_CAMERA);
    return () => {
      controlsRef.current = null;
      element.removeEventListener("pointerdown", pointerDown);
      element.removeEventListener("pointermove", pointerMove);
      element.removeEventListener("pointerup", pointerUp);
      element.removeEventListener("pointercancel", pointerUp);
      element.removeEventListener("wheel", wheel);
      element.removeEventListener("contextmenu", contextMenu);
      element.removeEventListener("dblclick", reset);
    };
  }, [camera, controlsRef, gl]);
  return null;
}

function ScenarioEffect({ scenario }) {
  if (!scenario?.active) return null;
  const id = scenario.scenario_id;
  if (id === "ppe") return <group position={[0.4, 0, -0.4]}><mesh position={[0, .8, 0]}><capsuleGeometry args={[.18, .9, 6, 12]} /><meshStandardMaterial color="#f0a650" /></mesh><mesh position={[0, 1.55, 0]}><sphereGeometry args={[.22, 16, 12]} /><meshStandardMaterial color="#d9a075" /></mesh><pointLight position={[0, 1.4, 0]} color="#ffb04d" intensity={3} distance={3} /></group>;
  if (id === "gas-high") return <group position={[5, 1.1, -3]}>{[[0, 0, 0], [.6, .25, .15], [-.55, .35, -.2], [.2, .75, -.25]].map((position, index) => <mesh key={index} position={position}><sphereGeometry args={[.75 - index * .07, 16, 12]} /><meshStandardMaterial color="#9be46f" emissive="#315e28" transparent opacity={.26} /></mesh>)}</group>;
  if (id === "meter-limit") return <group position={[4, 1.2, -3]}><mesh><torusGeometry args={[.42, .08, 12, 32]} /><meshStandardMaterial color="#ffbc4d" emissive="#9c5e00" /></mesh><pointLight color="#ff9e32" intensity={5} distance={3} /></group>;
  const fire = id === "fire-smoke" || id === "temperature-high" || id === "combined-risk-obstacle";
  return <group>{fire && <group position={[4.5, .45, -3]}><mesh><coneGeometry args={[.35, 1.2, 14]} /><meshStandardMaterial color="#ff6b32" emissive="#a32d0a" /></mesh><pointLight position={[0, .8, 0]} color="#ff5c2d" intensity={6} distance={4} />{[[0, 1.1, 0], [.3, 1.6, -.1], [-.25, 2.05, .15]].map((position, index) => <mesh key={index} position={position}><sphereGeometry args={[.45 + index * .12, 14, 10]} /><meshStandardMaterial color="#7b8790" transparent opacity={.36 - index * .06} /></mesh>)}</group>}{id === "combined-risk-obstacle" && <mesh position={[1.5, .55, 0]}><boxGeometry args={[1.2, 1.1, 1.2]} /><meshStandardMaterial color="#d54c45" emissive="#66211d" /></mesh>}</group>;
}

function YardModel() {
  return <group><mesh position={[0, -0.07, 0]}><boxGeometry args={[16, 0.12, 12]} /><meshStandardMaterial color="#26353a" /></mesh><mesh position={[0, 0.015, 0]}><boxGeometry args={[1.5, 0.025, 11.4]} /><meshStandardMaterial color="#827a36" /></mesh><mesh position={[0, 0.02, 0]}><boxGeometry args={[15.4, 0.025, 1.5]} /><meshStandardMaterial color="#827a36" /></mesh><mesh position={[5, 0.03, -3]}><boxGeometry args={[2.4, 0.03, 2.4]} /><meshStandardMaterial color="#8d2927" transparent opacity={0.62} /></mesh>{[[0, 0.6, -5.9, 16, 1.2, .18], [0, 0.6, 5.9, 16, 1.2, .18], [-7.9, .6, 0, .18, 1.2, 12], [7.9, .6, 0, .18, 1.2, 12]].map(([x, y, z, sx, sy, sz], index) => <mesh key={index} position={[x, y, z]}><boxGeometry args={[sx, sy, sz]} /><meshStandardMaterial color="#31434a" /></mesh>)}<gridHelper args={[16, 16, "#39545c", "#1d3037"]} position={[0, 0.04, 0]} /></group>;
}

function AssetModel({ asset }) {
  const pose = asset.pose;
  if (!pose) return null;
  const level = asset.risk?.level ?? "unknown";
  const color = level === "emergency" || level === "alert" ? "#ee6a6a" : level === "attention" ? "#f2b94b" : "#61bfa9";
  const category = String(asset.category ?? "");
  let geometry;
  if (category.includes("transformer") && !category.includes("current") && !category.includes("potential")) {
    geometry = <><mesh position={[0, .75, 0]}><boxGeometry args={[1.6, 1.5, 1.3]} /><meshStandardMaterial color={color} /></mesh>{[-.5, 0, .5].map((x) => <mesh key={x} position={[x, 1.75, 0]}><cylinderGeometry args={[.11, .11, .65, 12]} /><meshStandardMaterial color="#c8ae79" /></mesh>)}</>;
  } else if (category === "breaker") {
    geometry = <><mesh position={[0, .3, 0]}><boxGeometry args={[1, .6, .65]} /><meshStandardMaterial color={color} /></mesh>{[-.32, 0, .32].map((x) => <mesh key={x} position={[x, 1, 0]}><cylinderGeometry args={[.1, .12, 1, 12]} /><meshStandardMaterial color="#b99b72" /></mesh>)}</>;
  } else if (category.includes("disconnect_switch")) {
    geometry = <>{[-.48, .48].map((x) => <mesh key={x} position={[x, .72, 0]}><cylinderGeometry args={[.1, .12, 1.2, 12]} /><meshStandardMaterial color="#c4aa7c" /></mesh>)}<mesh position={[0, 1.32, 0]}><boxGeometry args={[1.1, .07, .08]} /><meshStandardMaterial color={color} /></mesh></>;
  } else if (category === "analog_meter") {
    geometry = <><mesh position={[0, 1.15, 0]} rotation={[Math.PI / 2, 0, 0]}><cylinderGeometry args={[.23, .23, .12, 24]} /><meshStandardMaterial color="#e2e2d8" /></mesh><mesh position={[0, 1.16, -.08]}><boxGeometry args={[.018, .16, .018]} /><meshStandardMaterial color="#c93434" /></mesh></>;
  } else if (category.includes("insulator") || category.includes("arrester") || category.includes("current_transformer")) {
    geometry = <mesh position={[0, .75, 0]}><cylinderGeometry args={[.25, .32, 1.5, 18]} /><meshStandardMaterial color={color} /></mesh>;
  } else {
    geometry = <mesh position={[0, .65, 0]}><boxGeometry args={[.7, 1.3, .7]} /><meshStandardMaterial color={color} /></mesh>;
  }
  return <group position={[pose.x_m, 0, -pose.y_m]}>{geometry}{["alert", "emergency"].includes(level) && <pointLight position={[0, 1.8, 0]} color="#ff554c" intensity={4} distance={2.5} />}</group>;
}

function RobotModel({ robot }) {
  const pose = robot.pose;
  const yaw = Math.atan2(2 * ((pose.qw ?? 1) * (pose.qz ?? 0)), 1 - 2 * (pose.qz ?? 0) ** 2);
  return <group position={[pose.x_m, .08, -pose.y_m]} rotation={[0, -yaw, 0]}><mesh position={[0, .25, 0]}><boxGeometry args={[.9, .32, .62]} /><meshStandardMaterial color="#42c3a1" emissive="#123c35" /></mesh>{[-.38, .38].flatMap((x) => [-.28, .28].map((z) => <mesh key={`${x}-${z}`} position={[x, .16, z]} rotation={[Math.PI / 2, 0, 0]}><cylinderGeometry args={[.14, .14, .1, 12]} /><meshStandardMaterial color="#12191e" /></mesh>))}<mesh position={[0, .72, 0]}><cylinderGeometry args={[.035, .05, .7, 10]} /><meshStandardMaterial color="#c9d7db" /></mesh><mesh position={[0, 1.08, -.02]}><boxGeometry args={[.26, .17, .2]} /><meshStandardMaterial color="#192b35" /></mesh><mesh position={[0, 1.08, -.13]}><circleGeometry args={[.055, 16]} /><meshStandardMaterial color="#5bb8f2" emissive="#1f6f9e" /></mesh></group>;
}

function RouteMarker({ goal, index }) {
  return <group position={[goal.x_m, .06, -goal.y_m]}><mesh><cylinderGeometry args={[.16, .16, .05, 20]} /><meshStandardMaterial color="#58aef0" emissive="#174a70" /></mesh><mesh position={[0, .3, 0]}><coneGeometry args={[.09, .25, 12]} /><meshStandardMaterial color={index === 0 ? "#ffffff" : "#8dcbf7"} /></mesh></group>;
}

function MapView({ robot, map, assets, mission }) {
  const activeTask = Array.isArray(mission?.tasks) ? mission.tasks.find((task) => task.task_id === mission.active_task_id) : null;
  return <div className="map-layout"><section className="panel map-canvas"><PanelTitle title="占据地图与任务路线" action={map ? `地图版本 ${map.map_revision}` : "等待地图"} />{map ? <OccupancyMap map={map} robot={robot} assets={assets} mission={mission} /> : <EmptyState title="地图尚未到达">正在等待二维地图数据。</EmptyState>}</section><section className="panel navigation-panel"><PanelTitle title="导航状态" action={robot?.stale ? "位姿过期" : "实时位姿"} /><p>当前坐标：{robot?.pose ? `${robot.pose.x_m.toFixed(2)}, ${robot.pose.y_m.toFixed(2)} 米` : "--"}</p><p>线速度：{robot?.twist ? `${robot.twist.linear_x_m_s.toFixed(2)} 米/秒` : "--"}</p><p>机器人模式：{robotModeLabel(robot?.mode)}</p><p>当前目标：{activeTask ? assetLabel(activeTask.asset_id) : "等待任务"}</p><div className="map-key"><span><i className="key-free" />可通行</span><span><i className="key-wall" />障碍/围栏</span><span><i className="key-asset" />设备编号</span><span><i className="key-route" />巡检路线</span></div><div className="map-device-index">{assets.map((asset, index) => <span key={asset.asset_id} className={asset.asset_id === activeTask?.asset_id ? "active" : ""}><b>{index + 1}</b>{assetLabel(asset.asset_id)}</span>)}</div></section></div>;
}

function OccupancyMap({ map, robot, assets, mission }) {
  const canvasRef = useRef(null);
  const dragRef = useRef(null);
  const [viewport, setViewport] = useState(DEFAULT_VIEWPORT);
  const width = Number(map.width_cells);
  const height = Number(map.height_cells);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || map.data_encoding !== "base64-int8-row-major-v1") return;
    let values;
    try { values = decodeOccupancyData(map.data, width, height); } catch { return; }
    const context = canvas.getContext("2d");
    const image = context.createImageData(width, height);
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        const value = values[y * width + x];
        const offset = ((height - 1 - y) * width + x) * 4;
        const color = value < 0 ? [8, 17, 23] : value >= 65 ? [186, 91, 80] : value > 10 ? [91, 105, 111] : [31, 48, 56];
        image.data.set([...color, 255], offset);
      }
    }
    context.putImageData(image, 0, 0);
  }, [height, map.data, map.data_encoding, width]);
  const robotPixel = robot?.pose ? worldToMapPixel(robot.pose, map) : null;
  const goals = Array.isArray(mission?.tasks) ? mission.tasks.map((task) => worldToMapPixel(task.goal, map)).filter(Boolean) : [];
  const route = [robotPixel, ...goals].filter(Boolean).map((point) => `${point.x},${point.y}`).join(" ");
  const activeTask = Array.isArray(mission?.tasks) ? mission.tasks.find((task) => task.task_id === mission.active_task_id) : null;
  const activeGoal = activeTask?.goal ? worldToMapPixel(activeTask.goal, map) : null;
  const handleWheel = (event) => {
    event.preventDefault();
    setViewport((current) => zoomViewport(current, event.deltaY < 0 ? 1.2 : 1 / 1.2));
  };
  const handlePointerDown = (event) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = { pointerId: event.pointerId, x: event.clientX, y: event.clientY };
  };
  const handlePointerMove = (event) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    setViewport((current) => panViewport(current, event.clientX - drag.x, event.clientY - drag.y));
    dragRef.current = { pointerId: event.pointerId, x: event.clientX, y: event.clientY };
  };
  const handlePointerUp = (event) => {
    if (dragRef.current?.pointerId === event.pointerId) dragRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  };
  const stopToolbarPointer = (event) => event.stopPropagation();
  return <div className="occupancy-wrap" style={{ aspectRatio: `${width}/${height}` }} onWheel={handleWheel} onPointerDown={handlePointerDown} onPointerMove={handlePointerMove} onPointerUp={handlePointerUp} onPointerCancel={handlePointerUp} onDoubleClick={() => setViewport(DEFAULT_VIEWPORT)}><div className="map-transform-layer" style={{ transform: viewportTransform(viewport) }}><canvas ref={canvasRef} width={width} height={height} /><svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet" aria-label="机器人、设备和任务路线叠加层">{route && <polyline points={route} className="route-line" />}{assets.map((asset, index) => { const point = asset.pose ? worldToMapPixel(asset.pose, map) : null; return point ? <g key={asset.asset_id} className="asset-map-marker"><title>{`${index + 1}. ${assetLabel(asset.asset_id)}`}</title><circle cx={point.x} cy={point.y} r="5" className={`asset-point ${asset.risk?.level ?? "unknown"}`} /><text x={point.x} y={point.y + 2.3} textAnchor="middle">{index + 1}</text></g> : null; })}{activeGoal && <g className="active-goal-marker"><circle cx={activeGoal.x} cy={activeGoal.y} r="7" className="goal-point" /><circle cx={activeGoal.x} cy={activeGoal.y} r="10" className="goal-pulse" /></g>}{robotPixel && <g transform={`translate(${robotPixel.x} ${robotPixel.y})`}><circle r="6" className="robot-map-marker" /><path d="M0 -5 L3 3 L0 2 L-3 3 Z" /></g>}</svg></div><div className="map-toolbar" onPointerDown={stopToolbarPointer}><button type="button" onClick={() => setViewport((current) => zoomViewport(current, 1.25))}>放大</button><button type="button" onClick={() => setViewport((current) => zoomViewport(current, 0.8))}>缩小</button><button type="button" onClick={() => setViewport((current) => rotateViewport(current, -15))}>向左旋转</button><button type="button" onClick={() => setViewport((current) => rotateViewport(current, 15))}>向右旋转</button><button type="button" onClick={() => setViewport(DEFAULT_VIEWPORT)}>复位地图</button></div><span className="map-origin">每格 {map.resolution_m.toFixed(2)} 米 · {width}×{height} · {viewport.scale.toFixed(2)} 倍 · {viewport.rotation}°</span><span className="map-help">滚轮缩放 · 拖拽移动 · 双击复位</span></div>;
}

function RiskView({ assets, alerts }) {
  return <div className="two-column"><section className="panel"><PanelTitle title="资产风险" action={`${assets.length} 项资产`} />{assets.length ? <AssetRows assets={assets} /> : <EmptyState title="等待风险数据">风险等级正在计算。</EmptyState>}</section><section className="panel"><PanelTitle title="风险事件" action={`${alerts.length} 条`} />{alerts.length ? alerts.map((alert, index) => <div className="alert-row" key={alert.alert_id ?? index}><span className="risk-marker alert" /><div><strong>{assetLabel(alert.asset_id ?? alert.alert_id)}</strong><small>{riskLabel(alert.current_level ?? alert.event ?? "unknown")}</small></div></div>) : <EmptyState title="当前无告警">运行事件流没有未处理风险事件。</EmptyState>}</section></div>;
}

function PerceptionView({ cameraUrl, cameraMeta, cameraFps, models }) {
  return <div className="perception-layout"><section className="panel camera-panel"><PanelTitle title="实时感知画面" action={cameraUrl ? `${cameraFps.toFixed(1)} 帧/秒 · 机器人相机` : "等待相机"} />{cameraUrl ? <><div className="camera-portrait"><img className="camera-frame camera-frame-rotated" src={cameraUrl} alt="左转九十度后的机器人实时标注相机画面" /></div><div className="camera-meta"><span>{cameraMeta?.captured_at ?? "实时机器人相机帧"}</span><span>{cameraMeta?.annotated ? "已叠加检测结果" : "原始画面"}</span></div></> : <EmptyState title="等待第一帧">数据服务已连接，正在等待机器人相机画面。</EmptyState>}</section><section className="panel model-panel"><PanelTitle title="模型状态" action="生产权重已接入" />{models.length ? <div className="model-list">{models.map((model) => <div className={`model-card ${model.installed ? "installed" : "missing"}`} key={model.logical_model}><div><strong>{modelLabel(model.logical_model)}</strong><span>{model.installed ? "运行权重已安装" : "权重缺失"}</span></div><small>{model.logical_model}</small><small>验证指标：{model.best_metric != null ? Number(model.best_metric).toFixed(3) : "--"}</small><small>{model.classes?.length ?? 0} 个识别类别 · 校验码 {model.sha256?.slice(0, 10)}…</small></div>)}</div> : <EmptyState title="模型清单不可用">正在读取生产模型清单。</EmptyState>}</section><ModelShowcase /></div>;
}

function ModelShowcase() {
  return <section className="panel model-showcase-panel"><PanelTitle title="模型检测效果" action="训练测试集预测结果" /><div className="model-showcase-grid">{MODEL_SHOWCASES.map((showcase, index) => <ModelShowcaseCard key={showcase.model} showcase={showcase} delayOffset={index * 700} />)}</div></section>;
}

function ModelShowcaseCard({ showcase, delayOffset }) {
  const [imageIndex, setImageIndex] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => setImageIndex((current) => (current + 1) % showcase.images.length), 3600 + delayOffset);
    return () => window.clearInterval(timer);
  }, [delayOffset, showcase.images.length]);
  return <article className="showcase-card"><header><div><strong>{showcase.name}</strong><span>{showcase.purpose}</span></div><small>{imageIndex + 1} / {showcase.images.length}</small></header><img src={showcase.images[imageIndex]} alt={`${showcase.name}测试集预测结果 ${imageIndex + 1}`} /><footer>{showcase.images.map((image, index) => <button key={image} className={index === imageIndex ? "active" : ""} onClick={() => setImageIndex(index)} aria-label={`查看第 ${index + 1} 张预测结果`} />)}</footer></article>;
}

function ScenarioView({ scenario, system, onCommand, disabled }) {
  const activeRun = system?.run_context?.lifecycle === "active";
  const scenarios = [
    ["normal", "基准巡检", {}],
    ["ppe", "未佩戴安全帽", { asset_id: "breaker-01" }],
    ["fire-smoke", "火焰与烟雾", { asset_id: "transformer-01", smoke_0_1: 0.8 }],
    ["gas-high", "气体超限", { asset_id: "transformer-01", gas_ppm: 180.0 }],
    ["meter-limit", "仪表越限", { asset_id: "meter-pressure-01", meter_reading: 1.6 }],
    ["combined-risk-obstacle", "组合风险与障碍", { asset_id: "transformer-01", temperature_celsius: 90.0, smoke_0_1: 0.7, gas_ppm: 180.0, obstacle_progress_0_1: 0.5 }],
  ];
  return <section className="panel scenario-panel"><PanelTitle title="仿真验收场景" action={scenario ? `${scenarioLabel(scenario.scenario_id)} · ${scenario.status === "applied" ? "已应用" : "处理中"}` : "等待状态"} />{!activeRun && <div className="scenario-notice">先在驾驶舱点击“恢复并开始自动巡检”，再触发验收场景。</div>}<div className="scenario-grid">{scenarios.map(([id, label, parameters]) => <button key={id} className={`scenario-card ${scenario?.active && scenario?.scenario_id === id ? "selected" : ""}`} onClick={() => onCommand("/api/v1/simulation/scenario", { scenario_id: id, action: "trigger", parameters, reason: "operator web scenario trigger" })} disabled={disabled || !activeRun}><span>仿真验收场景</span><strong>{label}</strong><small>{scenarioLabel(id)}</small></button>)}</div><div className="scenario-actions"><button className="secondary" onClick={() => onCommand("/api/v1/simulation/scenario", { scenario_id: scenario?.scenario_id ?? "normal", action: "reset", parameters: {}, reason: "operator web scenario reset" })} disabled={disabled || !activeRun}>复位当前场景</button><span>场景版本 {scenario?.scenario_revision ?? "0"}{scenario?.active ? " · 已激活" : " · 未激活"}</span></div></section>;
}

function ReportsView({ connection, reports }) {
  const items = Array.isArray(reports?.items) ? reports.items : [];
  return <section className="panel reports-panel"><PanelTitle title="巡检报告" action="证据不可变" />{items.length ? <div className="asset-list">{items.map((report) => <div className="report-row" key={report.report_id}><div><strong>{report.report_id}</strong><small>{report.created_at ?? report.status ?? "已归档"}</small></div>{report.download_urls && Object.entries(report.download_urls).map(([format, url]) => <a key={format} href={url}>{format === "pdf" ? "下载文档" : "查看网页"}</a>)}</div>)}</div> : <EmptyState title={connection === "live" ? "当前运行尚无报告" : "数据服务不可用"}>完成巡检任务后会生成网页、文档与证据包。</EmptyState>}</section>;
}

function SystemView({ system, models, events, onRefresh }) {
  const components = Array.isArray(system?.components) ? system.components : [];
  return <div className="two-column"><section className="panel"><PanelTitle title="组件健康" action={system?.overall === "ready" ? "运行正常" : "等待状态"} />{components.map((component) => <div className="component-row" key={component.name}><span className={`health-dot ${String(component.status).toLowerCase()}`} /><strong>{component.name}</strong><small>{component.status === "healthy" || component.status === "ok" ? "正常" : component.status}</small></div>)}{models.map((model) => <div className="component-row" key={model.logical_model}><span className={`health-dot ${model.installed ? "ok" : "error"}`} /><strong>{modelLabel(model.logical_model)}</strong><small>{model.installed ? "生产模型" : "权重缺失"}</small></div>)}{!components.length && !models.length && <EmptyState title="等待系统数据">仿真、导航、模型和服务健康状态尚未到达。</EmptyState>}<button className="secondary refresh-button" onClick={onRefresh}>重新获取数据</button></section><section className="panel"><PanelTitle title="运行上下文" action={system?.run_context?.lifecycle === "active" ? "运行中" : "未运行"} /><dl className="system-facts"><dt>运行标识</dt><dd>{system?.run_context ? "已建立" : "无"}</dd><dt>仿真模式</dt><dd>{system?.simulation_mode ? "开启" : "关闭"}</dd><dt>事件数量</dt><dd>{events.length}</dd><dt>紧急停止</dt><dd>{system?.emergency_stop_latched ? "已锁定" : "未锁定"}</dd></dl></section></div>;
}

function AssetRows({ assets }) {
  return <div className="asset-list">{assets.map((asset) => <div className="asset-row" key={asset.asset_id}><span className={`risk-marker ${String(asset.risk?.level ?? "unknown").toLowerCase()}`} /><div><strong>{assetLabel(asset.asset_id)}</strong><small>{asset.asset_id} · {categoryLabel(asset.category)} · {riskLabel(asset.risk?.level)} {asset.risk?.score_0_100 != null ? `· 风险分 ${asset.risk.score_0_100.toFixed(1)}` : ""}</small></div><span className="asset-coordinate">{asset.pose ? `${asset.pose.x_m.toFixed(1)}, ${asset.pose.y_m.toFixed(1)}` : "--"}</span></div>)}</div>;
}

function PanelTitle({ title, action }) {
  return <header className="panel-title"><h2>{title}</h2><span>{action}</span></header>;
}
