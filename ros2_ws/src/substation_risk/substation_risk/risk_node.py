from __future__ import annotations

import math
from pathlib import Path
import uuid

from ament_index_python.packages import get_package_share_directory
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from substation_description.asset_registry import load_asset_registry
from substation_interfaces.msg import AssetRisk, AssetRiskArray, RiskAlert, RunContext

from .risk_engine import AlertEvent, RiskEngine, load_risk_policy


def _normalized(value: float, warning: float, critical: float) -> float:
    return min(1.0, max(0.0, (value - warning) / (critical - warning)))


def components_from_twin_status(
    status: DiagnosticStatus,
    thresholds,
    active_run_id: str,
) -> dict[str, float] | None:
    values = {item.key: item.value for item in status.values}
    if values.get("run_id") != active_run_id or not active_run_id:
        return None
    try:
        temperature = float(values["temperature_celsius"])
        smoke = float(values["smoke_0_1"])
        gas = float(values["gas_ppm"])
    except (KeyError, ValueError):
        return None
    if not all(math.isfinite(value) for value in (temperature, smoke, gas)):
        return None
    components = {
        "visual": 0.0,
        "temperature": _normalized(temperature, **thresholds["temperature_celsius"]),
        "smoke": _normalized(smoke, **thresholds["smoke_0_1"]),
        "gas": _normalized(gas, **thresholds["gas_ppm"]),
        "context": 0.0,
    }
    components["context"] = 1.0 if sum(
        value >= 0.6 for name, value in components.items() if name not in {"visual", "context"}
    ) >= 2 else 0.0
    return components


class RiskNode(Node):
    def __init__(self) -> None:
        super().__init__("risk")
        description = Path(get_package_share_directory("substation_description"))
        risk_share = Path(get_package_share_directory("substation_risk"))
        registry = load_asset_registry(description / "config/devices.yaml")
        self._thresholds = {item.asset_id: item.thresholds for item in registry.assets}
        self._engine = RiskEngine(load_risk_policy(risk_share / "config/risk_weights.yaml"))
        self._run_id = ""
        self._revision = 0
        self._latest: dict[str, tuple[object, dict[str, float]]] = {}
        self._alerts: dict[str, str] = {}
        q_state = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        q_event = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=100,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        self._risk_pub = self.create_publisher(AssetRiskArray, "/risk/assets", q_state)
        self._alert_pub = self.create_publisher(RiskAlert, "/risk/alerts", q_event)
        self.create_subscription(RunContext, "/system/run_context", self._on_context, q_state)
        self.create_subscription(DiagnosticArray, "/digital_twin/assets", self._on_twin, q_state)
        self.create_timer(0.2, self._publish)

    def _on_context(self, context: RunContext) -> None:
        self._run_id = context.run_id if context.lifecycle == RunContext.LIFECYCLE_ACTIVE else ""

    def _on_twin(self, message: DiagnosticArray) -> None:
        for status in message.status:
            thresholds = self._thresholds.get(status.name)
            if thresholds is None:
                continue
            components = components_from_twin_status(status, thresholds, self._run_id)
            if components is None:
                continue
            stamp_ns = message.header.stamp.sec * 1_000_000_000 + message.header.stamp.nanosec
            observation = self._engine.observe(status.name, components, stamp_ns=stamp_ns)
            self._latest[status.name] = (observation, components)
            self._revision += 1
            if observation.alert_event is not None:
                self._publish_alert(observation)
        self._publish()

    def _publish_alert(self, observation) -> None:
        alert_id = self._alerts.get(observation.asset_id)
        if alert_id is None:
            alert_id = str(uuid.uuid4())
            self._alerts[observation.asset_id] = alert_id
        alert = RiskAlert()
        alert.schema_version = 1
        alert.header.stamp = self.get_clock().now().to_msg()
        alert.alert_id = alert_id
        alert.run_id = self._run_id
        alert.asset_id = observation.asset_id
        alert.event_type = int(observation.alert_event)
        alert.current_level = int(observation.level)
        alert.score_0_100 = observation.score_0_100
        alert.summary = AlertEvent(observation.alert_event).name
        self._alert_pub.publish(alert)
        if observation.alert_event == AlertEvent.CLEARED:
            self._alerts.pop(observation.asset_id, None)

    def _publish(self) -> None:
        output = AssetRiskArray()
        output.schema_version = 1
        output.header.stamp = self.get_clock().now().to_msg()
        output.run_id = self._run_id
        output.risk_revision = self._revision
        for asset_id in sorted(self._latest):
            observation, components = self._latest[asset_id]
            item = AssetRisk()
            item.schema_version = 1
            item.asset_id = asset_id
            item.score_0_100 = observation.score_0_100
            item.level = int(observation.level)
            item.visual_0_1 = components["visual"]
            item.temperature_0_1 = components["temperature"]
            item.smoke_0_1 = components["smoke"]
            item.gas_0_1 = components["gas"]
            item.context_0_1 = components["context"]
            item.confirmation_frames = observation.confirmation_frames
            item.last_observed.sec = observation.stamp_ns // 1_000_000_000
            item.last_observed.nanosec = observation.stamp_ns % 1_000_000_000
            output.assets.append(item)
        self._risk_pub.publish(output)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = RiskNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
