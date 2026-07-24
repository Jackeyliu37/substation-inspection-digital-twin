const labels = (entries) => Object.freeze(Object.fromEntries(entries));

const ASSETS = labels([
  ["arrester-01", "避雷器"],
  ["breaker-01", "断路器"],
  ["current-transformer-01", "电流互感器"],
  ["disconnect-switch-01", "隔离开关"],
  ["glass-insulator-01", "玻璃盘式绝缘子"],
  ["meter-oil-01", "油位表"],
  ["meter-pressure-01", "压力表"],
  ["porcelain-insulator-01", "瓷针式绝缘子"],
  ["potential-transformer-01", "电压互感器"],
  ["transformer-01", "主变压器"],
]);

const CATEGORIES = labels([
  ["lightning_arrester", "避雷器"],
  ["breaker", "断路器"],
  ["current_transformer", "电流互感器"],
  ["closed_blade_disconnect_switch", "闭合刀闸隔离开关"],
  ["open_blade_disconnect_switch", "断开刀闸隔离开关"],
  ["glass_disc_insulator", "玻璃盘式绝缘子"],
  ["analog_meter", "指针式仪表"],
  ["porcelain_pin_insulator", "瓷针式绝缘子"],
  ["potential_transformer", "电压互感器"],
  ["power_transformer", "电力变压器"],
]);

const RISKS = labels([
  ["unknown", "待评估"],
  ["normal", "正常"],
  ["attention", "注意"],
  ["alert", "告警"],
  ["emergency", "紧急"],
  ["low", "低风险"],
  ["medium", "中风险"],
  ["high", "高风险"],
  ["critical", "严重"],
]);

const MISSIONS = labels([
  ["idle", "空闲"],
  ["ready", "准备就绪"],
  ["running", "巡检中"],
  ["paused", "已暂停"],
  ["stopping", "正在停止"],
  ["stopped", "已停止"],
  ["succeeded", "已完成"],
  ["failed", "失败"],
]);

const MODES = labels([
  ["autonomous", "自动巡检"],
  ["manual", "手动模式"],
  ["estop", "紧急停止"],
]);

const SCENARIOS = labels([
  ["normal", "基准巡检"],
  ["ppe", "未佩戴安全帽"],
  ["fire-smoke", "火焰与烟雾"],
  ["gas-high", "气体浓度超限"],
  ["meter-limit", "仪表读数越限"],
  ["combined-risk-obstacle", "组合风险与障碍"],
]);

const MODELS = labels([
  ["yolo11n_safety", "人员与安全风险检测模型"],
  ["yolo11n_equipment", "电力设备检测模型"],
  ["yolo11n_fault", "设备缺陷分类模型"],
  ["meter_locator", "仪表定位模型"],
]);

const EVENTS = labels([
  ["system.health", "系统健康状态"],
  ["robot.state", "机器人状态"],
  ["mission.state", "巡检任务状态"],
  ["risk.assets", "资产风险更新"],
  ["risk.alert", "风险告警"],
  ["command.status", "控制命令状态"],
]);

const ERRORS = labels([
  ["MOTION_SAFETY_BARRIER_PENDING", "请先停止当前任务，等待机器人保持静止后再解除紧急停止。"],
  ["wait for no active goal and 0.5 seconds of zero velocity", "请先停止当前任务，等待机器人保持静止至少半秒后再解除紧急停止。"],
  ["EMERGENCY_STOP_LATCHED", "紧急停止仍处于锁定状态，请先执行恢复。"],
  ["LATCH_REVISION_MISMATCH", "紧急停止状态已变化，请刷新后重试。"],
  ["STATE_REVISION_MISMATCH", "任务状态已变化，请刷新后重试。"],
  ["INVALID_STATE_TRANSITION", "当前状态不允许执行此操作。"],
  ["RUN_CONTEXT_MISMATCH", "运行上下文已变化，请刷新页面后重试。"],
  ["MISSION_NOT_FOUND", "当前巡检任务不存在，请重新开始巡检。"],
  ["required snapshot unavailable", "部分实时数据暂时不可用，请稍后重试。"],
]);

const lookup = (table, value) => table[String(value ?? "")] ?? String(value ?? "未知");

export const assetLabel = (value) => lookup(ASSETS, value);
export const categoryLabel = (value) => lookup(CATEGORIES, value);
export const riskLabel = (value) => lookup(RISKS, value);
export const missionStateLabel = (value) => lookup(MISSIONS, value);
export const robotModeLabel = (value) => lookup(MODES, value);
export const scenarioLabel = (value) => lookup(SCENARIOS, value);
export const modelLabel = (value) => lookup(MODELS, value);
export const eventLabel = (value) => lookup(EVENTS, value);

export function commandErrorLabel(value) {
  const text = String(value ?? "命令执行失败");
  if (ERRORS[text]) return ERRORS[text];
  for (const [key, translated] of Object.entries(ERRORS)) {
    if (text.includes(key)) return translated;
  }
  return text;
}
