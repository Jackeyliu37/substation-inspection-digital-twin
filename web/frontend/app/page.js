"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Canvas } from "@react-three/fiber";

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

const SNAPSHOT_ENDPOINTS = [
  "/api/v1/system/status",
  "/api/v1/robot/state",
  "/api/v1/assets",
  "/api/v1/missions/current",
];

const now = () => new Date().toLocaleTimeString("zh-CN", { hour12: false });
const apiData = (value) => value?.data ?? value ?? null;

function socketUrl(path) {
  if (typeof window === "undefined") return path;
  return `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}${path}`;
}

function StatusPill({ connection }) {
  const label = connection === "live" ? "实时连接" : connection === "recovering" ? "正在恢复" : "Gateway 不可用";
  return <span className={`status-pill ${connection}`}>{label}</span>;
}

function Metric({ label, value, detail, tone = "neutral" }) {
  return <section className={`metric ${tone}`}><span>{label}</span><strong>{value ?? "--"}</strong><small>{detail ?? "等待 Gateway 快照"}</small></section>;
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
  const [commandNote, setCommandNote] = useState("尚未提交命令");
  const [loading, setLoading] = useState(false);
  const cameraObjectUrl = useRef(null);
  const lastMessageAt = useRef(0);

  const refresh = useCallback(async () => {
    setConnection("recovering");
    try {
      const responses = await Promise.all(SNAPSHOT_ENDPOINTS.map(async (endpoint) => {
        const response = await fetch(endpoint, { headers: { accept: "application/json" }, cache: "no-store" });
        if (!response.ok) throw new Error(`${endpoint}: ${response.status}`);
        return [endpoint, apiData(await response.json())];
      }));
      setSnapshots(Object.fromEntries(responses));
      const optional = await Promise.allSettled(["/api/v1/map", "/api/v1/reports"].map(async (endpoint) => [endpoint, apiData(await (await fetch(endpoint, { headers: { accept: "application/json" }, cache: "no-store" })).json())]));
      setSnapshots((current) => Object.fromEntries([...Object.entries(current), ...optional.flatMap((result) => result.status === "fulfilled" ? [result.value] : [])]));
      setConnection("live");
      lastMessageAt.current = Date.now();
    } catch {
      setConnection("offline");
    }
  }, []);

  const sendCommand = useCallback(async (endpoint, body = {}) => {
    setLoading(true);
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "content-type": "application/json", accept: "application/json", "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify(body),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload?.detail?.title || `HTTP ${response.status}`);
      setCommandNote(`命令已受理 ${payload.command_id ?? payload.data?.command_id ?? ""}`.trim());
    } catch (error) {
      setCommandNote(`命令未提交：${error.message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const receive = (message) => {
      if (message?.type !== "stream.open") lastMessageAt.current = Date.now();
      if (message?.type === "system.health") setSnapshots((current) => ({ ...current, "/api/v1/system/status": message.payload }));
      if (message?.type === "robot.state") setSnapshots((current) => ({ ...current, "/api/v1/robot/state": message.payload }));
      if (message?.type === "mission.state") setSnapshots((current) => ({ ...current, "/api/v1/missions/current": message.payload }));
      if (message?.type === "risk.assets") setSnapshots((current) => ({ ...current, "/api/v1/assets": message.payload }));
      if (message?.type && message.type !== "heartbeat" && message.type !== "stream.open") {
        setEvents((current) => [{ type: message.type, timestamp: message.timestamp, payload: message.payload }, ...current].slice(0, 20));
      }
      setConnection("live");
    };
    const openSocket = (path) => {
      const socket = new WebSocket(socketUrl(path), "substation.v1");
      if (path === "/ws/camera") socket.binaryType = "arraybuffer";
      socket.onmessage = (event) => {
        if (typeof event.data === "string") {
          try { receive(JSON.parse(event.data)); } catch { setConnection("offline"); }
        } else if (path === "/ws/camera") {
          const frame = new Uint8Array(event.data);
          const header = new DataView(frame.buffer, frame.byteOffset, frame.byteLength);
          const headerLength = header.getUint16(6, false);
          const metadataLength = header.getUint32(24, false);
          const jpegLength = header.getUint32(28, false);
          if (headerLength !== 64 || metadataLength < 1 || metadataLength > 16384 || jpegLength < 1 || jpegLength > 2097152 || frame.byteLength !== 64 + metadataLength + jpegLength) return;
          const jpeg = frame.slice(64 + metadataLength);
          if (jpeg[0] !== 0xff || jpeg[1] !== 0xd8 || jpeg.at(-2) !== 0xff || jpeg.at(-1) !== 0xd9) return;
          const objectUrl = URL.createObjectURL(new Blob([jpeg], { type: "image/jpeg" }));
          if (cameraObjectUrl.current) URL.revokeObjectURL(cameraObjectUrl.current);
          cameraObjectUrl.current = objectUrl;
          setCameraUrl(objectUrl);
          lastMessageAt.current = Date.now();
        }
      };
      socket.onerror = () => setConnection((state) => state === "live" ? "recovering" : "offline");
      socket.onclose = () => setConnection((state) => state === "live" ? "recovering" : state);
      return socket;
    };
    const sockets = [openSocket("/ws/telemetry"), openSocket("/ws/events"), openSocket("/ws/camera")];
    const timer = window.setInterval(() => {
      if (lastMessageAt.current && Date.now() - lastMessageAt.current > 5000) setConnection("offline");
    }, 1000);
    return () => {
      sockets.forEach((socket) => socket.close());
      window.clearInterval(timer);
      if (cameraObjectUrl.current) URL.revokeObjectURL(cameraObjectUrl.current);
    };
  }, [refresh]);

  const system = snapshots["/api/v1/system/status"];
  const robot = snapshots["/api/v1/robot/state"];
  const assets = snapshots["/api/v1/assets"];
  const mission = snapshots["/api/v1/missions/current"];
  const map = snapshots["/api/v1/map"];
  const reports = snapshots["/api/v1/reports"];
  const controlsDisabled = connection !== "live" || loading;
  const assetItems = Array.isArray(assets?.assets) ? assets.assets : [];
  const alertItems = Array.isArray(assets?.alerts) ? assets.alerts : [];
  const renderView = useMemo(() => ({
    dashboard: <Dashboard robot={robot} mission={mission} assets={assetItems} alerts={alertItems} events={events} onCommand={sendCommand} disabled={controlsDisabled} />,
    twin: <TwinView assets={assetItems} />,
    map: <MapView robot={robot} map={map} onCommand={sendCommand} disabled={controlsDisabled} />,
    risk: <RiskView assets={assetItems} alerts={alertItems} onCommand={sendCommand} disabled={controlsDisabled} />,
    perception: <PerceptionView cameraUrl={cameraUrl} />,
    scenario: <ScenarioView onCommand={sendCommand} disabled={controlsDisabled} />,
    reports: <ReportsView connection={connection} reports={reports} />,
    system: <SystemView system={system} events={events} onRefresh={refresh} />,
  }), [alertItems, assetItems, cameraUrl, connection, controlsDisabled, events, map, mission, refresh, reports, robot, sendCommand]);

  return <main className="control-center">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">S</span><div><strong>变电站巡检</strong><small>控制中心</small></div></div>
      <nav aria-label="主导航">{VIEWS.map(([id, label, short]) => <button key={id} className={view === id ? "nav-item active" : "nav-item"} onClick={() => setView(id)}><span>{short.slice(0, 1)}</span>{label}</button>)}</nav>
      <div className="sidebar-foot"><span>产品入口</span><small>仅通过 Gateway /api 与 /ws</small></div>
    </aside>
    <section className="workbench">
      <header className="topbar"><div><span className="eyebrow">OPERATIONS / {VIEWS.find(([id]) => id === view)?.[1]}</span><h1>{VIEWS.find(([id]) => id === view)?.[1]}</h1></div><div className="top-actions"><span className="clock">{now()}</span><StatusPill connection={connection} /><button className="icon-button" title="刷新 Gateway 快照" onClick={refresh}>R</button><button className="emergency" onClick={() => sendCommand("/api/v1/robot/emergency-stop")} disabled={loading}>紧急停止</button></div></header>
      {connection !== "live" && <div className="connection-banner"><strong>Gateway 不可用</strong><span>无法读取实时状态。普通控制已禁用；紧急停止会继续尝试通过独立 HTTP 请求提交。</span></div>}
      <div className="command-note" aria-live="polite">{commandNote}</div>
      <div className="view-content">{renderView[view]}</div>
    </section>
  </main>;
}

function Dashboard({ robot, mission, assets, alerts, events, onCommand, disabled }) {
  return <><div className="metric-grid"><Metric label="机器人模式" value={robot?.mode} detail={robot?.task_id ? `任务 ${robot.task_id}` : "等待机器人状态"} /><Metric label="电量" value={robot?.battery_percent != null ? `${robot.battery_percent}%` : "--"} detail="Gateway 归一化模拟值" /><Metric label="高风险资产" value={assets.filter((asset) => asset.risk_level === "HIGH" || asset.risk_level === "CRITICAL").length} detail="来自资产风险快照" tone="warning" /><Metric label="未确认告警" value={alerts.filter((alert) => !alert.acknowledged_at).length} detail="需要操作员确认" tone="danger" /></div><div className="dashboard-grid"><section className="panel mission-panel"><PanelTitle title="巡检任务" action="查看队列" /><div className="progress"><i style={{ width: `${mission?.progress_percent ?? 0}%` }} /></div><div className="mission-stats"><strong>{mission?.state ?? "等待任务"}</strong><span>{mission?.progress_percent ?? 0}% 完成</span></div><div className="button-row"><button onClick={() => onCommand("/api/v1/missions/start")} disabled={disabled}>开始巡检</button><button className="secondary" onClick={() => onCommand("/api/v1/missions/pause")} disabled={disabled}>暂停</button><button className="secondary" onClick={() => onCommand("/api/v1/missions/resume")} disabled={disabled}>继续</button><button className="secondary" onClick={() => onCommand("/api/v1/missions/stop")} disabled={disabled}>停止</button><button className="secondary" onClick={() => onCommand("/api/v1/missions/return-home")} disabled={disabled}>返航</button></div></section><section className="panel"><PanelTitle title="风险优先级" action="打开风险" />{assets.length ? <AssetRows assets={assets.slice(0, 4)} /> : <EmptyState title="等待资产快照">风险由 Gateway 聚合后显示。</EmptyState>}</section><section className="panel event-panel"><PanelTitle title="事件流" action="最近 20 条" />{events.length ? events.slice(0, 6).map((event, index) => <div className="event" key={`${event.type}-${index}`}><span className="event-dot" /><div><strong>{event.type}</strong><small>{event.timestamp ?? "实时事件"}</small></div></div>) : <EmptyState title="没有实时事件">连接建立后会在此显示命令与告警状态。</EmptyState>}</section></div></>;
}

function TwinView({ assets }) {
  return <section className="panel twin-panel"><PanelTitle title="三维数字孪生" action={assets.length ? `${assets.length} 个 Gateway 资产` : "等待资产快照"} /><div className="twin-stage"><Canvas camera={{ position: [5, 4, 7], fov: 45 }} dpr={[1, 1.5]}><color attach="background" args={["#081117"]} /><ambientLight intensity={1.2} /><directionalLight position={[4, 7, 3]} intensity={3} /><gridHelper args={[12, 12, "#29434c", "#172930"]} /><mesh position={[0, -0.2, 0]}><boxGeometry args={[5.5, 0.35, 3.5]} /><meshStandardMaterial color="#1a3740" /></mesh>{assets.slice(0, 12).map((asset, index) => <AssetMesh key={asset.asset_id ?? index} asset={asset} index={index} />)}<mesh position={[0, 0.45, 1.6]}><boxGeometry args={[0.75, 0.45, 0.55]} /><meshStandardMaterial color="#42c3a1" /></mesh></Canvas>{!assets.length && <div className="twin-overlay">资产几何体将在 Gateway `/api/v1/assets` 快照到达后绑定 asset_id 和风险颜色。</div>}</div><p className="twin-note">这是当前运行快照的三维视图；前端不读取 ROS Topic，也不把静态模型当作生产设备状态。</p></section>;
}

function AssetMesh({ asset, index }) {
  const risk = String(asset.risk_level ?? "").toLowerCase();
  const color = risk === "critical" || risk === "high" ? "#ee6a6a" : risk === "medium" ? "#f2b94b" : "#42c3a1";
  const x = ((index % 4) - 1.5) * 1.25;
  const z = (Math.floor(index / 4) - 1) * 1.05;
  return <mesh position={[x, 0.32 + (index % 2) * 0.22, z]}><boxGeometry args={[0.42, 0.65 + (index % 3) * 0.18, 0.42]} /><meshStandardMaterial color={color} /></mesh>;
}

function MapView({ robot, map, onCommand, disabled }) { return <div className="map-layout"><section className="panel map-canvas"><PanelTitle title="作业地图" action={map ? `revision ${map.map_revision ?? "已同步"}` : "等待地图"} /><div className="grid-map"><span className="robot-dot">R</span><span className="map-label">地图数据将由 Gateway `/api/v1/map` 和 telemetry map.update 提供</span></div></section><section className="panel navigation-panel"><PanelTitle title="导航控制" action="目标需经 Gateway 验证" /><p>当前位姿：{robot?.pose ? `${robot.pose.x}, ${robot.pose.y}` : "--"}</p><button onClick={() => onCommand("/api/v1/missions/return-home")} disabled={disabled}>返回停靠点</button><p className="muted">地图点击目标仅在 Gateway 提供地图快照后可用，不在前端猜测坐标。</p></section></div>; }
function RiskView({ assets, alerts, onCommand, disabled }) { return <div className="two-column"><section className="panel"><PanelTitle title="资产风险" action={`${assets.length} 项资产`} />{assets.length ? <AssetRows assets={assets} actions={(asset) => <button className="compact" onClick={() => onCommand(`/api/v1/assets/${asset.asset_id}/prioritize`)} disabled={disabled}>优先巡检</button>} /> : <EmptyState title="等待风险快照">风险等级和分数不由浏览器推导。</EmptyState>}</section><section className="panel"><PanelTitle title="告警确认" action={`${alerts.length} 条`} />{alerts.length ? alerts.map((alert) => <div className="alert-row" key={alert.alert_id}><div><strong>{alert.asset_id ?? alert.alert_id}</strong><small>{alert.message ?? alert.level}</small></div><button className="compact" onClick={() => onCommand(`/api/v1/alerts/${alert.alert_id}/acknowledge`)} disabled={disabled || Boolean(alert.acknowledged_at)}>确认</button></div>) : <EmptyState title="无待确认告警">Gateway 事件流会同步最新告警。</EmptyState>}</section></div>; }
function PerceptionView({ cameraUrl }) { return <div className="perception-layout"><section className="panel camera-panel"><PanelTitle title="检测视频" action="Gateway camera stream" />{cameraUrl ? <img className="camera-frame" src={cameraUrl} alt="Gateway 标注相机帧" /> : <EmptyState title="等待相机帧">仅显示 Gateway `/ws/camera` 提供的带框 JPEG，不订阅 ROS 图像 Topic。</EmptyState>}</section><section className="panel model-panel"><PanelTitle title="模型状态" action="生产集成待定" /><strong>production model unavailable</strong><p>当前官方 YOLO11n 仅是开发占位；生产权重、指标和 manifest 尚未由训练发布物接入。</p></section></div>; }
function ScenarioView({ onCommand, disabled }) { const scenarios = [["normal", "基准巡检"], ["smoke", "烟雾风险"], ["gas", "气体风险"], ["meter_fault", "仪表异常"], ["combined_risk_obstacle", "组合风险与障碍"]]; return <section className="panel scenario-panel"><PanelTitle title="Gazebo 仿真场景" action="仅 Gateway 控制" /><div className="scenario-grid">{scenarios.map(([id, label]) => <button key={id} className="scenario-card" onClick={() => onCommand("/api/v1/simulation/scenario", { scenario_id: id })} disabled={disabled}><span>SCN</span><strong>{label}</strong><small>{id}</small></button>)}</div></section>; }
function ReportsView({ connection, reports }) { const items = Array.isArray(reports?.reports) ? reports.reports : Array.isArray(reports) ? reports : []; return <section className="panel reports-panel"><PanelTitle title="巡检报告" action="证据不可变" />{items.length ? <div className="asset-list">{items.map((report) => <div className="report-row" key={report.report_id}><div><strong>{report.report_id}</strong><small>{report.generated_at ?? report.status ?? "已归档"}</small></div>{report.download_url && <a href={report.download_url}>下载</a>}</div>)}</div> : <EmptyState title={connection === "live" ? "等待报告列表" : "Gateway 不可用"}>{connection === "live" ? "报告将从 `/api/v1/reports` 读取并保留下载摘要。" : "恢复连接后加载报告与诊断包。"}</EmptyState>}</section>; }
function SystemView({ system, events, onRefresh }) { const components = Array.isArray(system?.components) ? system.components : []; return <div className="two-column"><section className="panel"><PanelTitle title="组件健康" action={system?.overall ?? "等待状态"} />{components.length ? components.map((component) => <div className="component-row" key={component.name}><span className={`health-dot ${String(component.status).toLowerCase()}`} /><strong>{component.name}</strong><small>{component.status}</small></div>) : <EmptyState title="等待系统快照">Gazebo、GPU、模型和服务健康由 Gateway 汇总。</EmptyState>}<button className="secondary refresh-button" onClick={onRefresh}>重新获取快照</button></section><section className="panel"><PanelTitle title="系统事件" action={`${events.length} 条`} />{events.length ? events.map((event, index) => <div className="event" key={`${event.type}-${index}`}><span className="event-dot" /><div><strong>{event.type}</strong><small>{event.timestamp ?? "实时"}</small></div></div>) : <EmptyState title="没有事件">事件 WebSocket 建立后显示。</EmptyState>}</section></div>; }
function AssetRows({ assets, actions }) { return <div className="asset-list">{assets.map((asset) => <div className="asset-row" key={asset.asset_id}><span className={`risk-marker ${String(asset.risk_level ?? "unknown").toLowerCase()}`} /><div><strong>{asset.name ?? asset.asset_id}</strong><small>{asset.risk_level ?? "UNKNOWN"} {asset.risk_score != null ? `· ${asset.risk_score}` : ""}</small></div>{actions?.(asset)}</div>)}</div>; }
function PanelTitle({ title, action }) { return <header className="panel-title"><h2>{title}</h2><span>{action}</span></header>; }
