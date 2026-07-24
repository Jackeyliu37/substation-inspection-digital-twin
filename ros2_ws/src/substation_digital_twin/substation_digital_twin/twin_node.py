from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from substation_description.asset_registry import load_asset_registry
from substation_interfaces.msg import RunContext


@dataclass
class _Telemetry:
    temperature_celsius: float | None = None
    smoke_0_1: float | None = None
    gas_ppm: float | None = None
    meter_reading: float | None = None
    meter_unit: str = ""
    latest_evidence_id: str = ""
    sec: int = 0
    nanosec: int = 0


class TwinTelemetry:
    def __init__(self, assets: dict[str, tuple[str, tuple[float, float, float]]]) -> None:
        self._assets = assets
        self._telemetry = {asset_id: _Telemetry() for asset_id in assets}

    def apply(
        self,
        message: DiagnosticArray,
        field: str,
        value_key: str,
        active_run_id: str,
    ) -> None:
        for status in message.status:
            values = {item.key: item.value for item in status.values}
            if status.name not in self._telemetry or values.get("run_id") != active_run_id:
                continue
            try:
                value = float(values[value_key])
            except (KeyError, ValueError):
                continue
            if not math.isfinite(value):
                continue
            telemetry = self._telemetry[status.name]
            setattr(telemetry, field, value)
            telemetry.sec = message.header.stamp.sec
            telemetry.nanosec = message.header.stamp.nanosec

    def snapshot(self, run_id: str) -> DiagnosticArray:
        output = DiagnosticArray()
        output.header.frame_id = "map"
        for asset_id in sorted(self._assets):
            telemetry = self._telemetry[asset_id]
            if not run_id:
                continue
            category, pose = self._assets[asset_id]
            values = {
                "run_id": run_id,
                "category": category,
                "state": "normal",
                "pose_x_m": pose[0], "pose_y_m": pose[1], "pose_z_m": pose[2],
                "orientation_x": 0.0, "orientation_y": 0.0,
                "orientation_z": 0.0, "orientation_w": 1.0,
                "temperature_celsius": "" if telemetry.temperature_celsius is None else telemetry.temperature_celsius,
                "smoke_0_1": "" if telemetry.smoke_0_1 is None else telemetry.smoke_0_1,
                "gas_ppm": "" if telemetry.gas_ppm is None else telemetry.gas_ppm,
                "meter_reading": "" if telemetry.meter_reading is None else telemetry.meter_reading,
                "meter_unit": telemetry.meter_unit,
                "last_observed_ros_sec": telemetry.sec,
                "last_observed_ros_nanosec": telemetry.nanosec,
                "latest_evidence_id": telemetry.latest_evidence_id,
            }
            output.status.append(DiagnosticStatus(
                level=DiagnosticStatus.OK,
                name=asset_id,
                hardware_id=category,
                message="ASSET_STATE",
                values=[KeyValue(key=key, value=str(value)) for key, value in values.items()],
            ))
        return output

    def apply_meter(self, message: DiagnosticArray, active_run_id: str) -> None:
        for status in message.status:
            values = {item.key: item.value for item in status.values}
            if (
                status.name not in self._telemetry
                or values.get("run_id") != active_run_id
                or values.get("valid") != "true"
            ):
                continue
            try:
                reading = float(values["reading"])
            except (KeyError, ValueError):
                continue
            unit = values.get("unit", "")
            if not math.isfinite(reading) or not unit:
                continue
            telemetry = self._telemetry[status.name]
            telemetry.meter_reading = reading
            telemetry.meter_unit = unit
            telemetry.latest_evidence_id = values.get("evidence_id", "")
            telemetry.sec = message.header.stamp.sec
            telemetry.nanosec = message.header.stamp.nanosec


class DigitalTwinNode(Node):
    def __init__(self) -> None:
        super().__init__("digital_twin")
        registry_path = Path(get_package_share_directory("substation_description")) / "config/devices.yaml"
        registry = load_asset_registry(registry_path)
        assets = {
            item.asset_id: (item.category, (item.pose.x, item.pose.y, item.pose.z))
            for item in registry.assets
        }
        self._twin = TwinTelemetry(assets)
        self._run_id = ""
        q_state = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        q_stream = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        self._publisher = self.create_publisher(DiagnosticArray, "/digital_twin/assets", q_state)
        self.create_subscription(RunContext, "/system/run_context", self._on_context, q_state)
        for topic, field, key in (
            ("temperature", "temperature_celsius", "value_celsius"),
            ("smoke", "smoke_0_1", "value_0_1"),
            ("gas", "gas_ppm", "value_ppm"),
        ):
            self.create_subscription(
                DiagnosticArray,
                f"/environment/{topic}",
                lambda message, f=field, k=key: self._on_measurement(message, f, k),
                q_stream,
            )
        self.create_subscription(
            DiagnosticArray,
            "/perception/meters/readings",
            self._on_meter,
            q_stream,
        )
        self.create_timer(0.5, self._publish)

    def _on_context(self, context: RunContext) -> None:
        self._run_id = context.run_id if context.lifecycle == RunContext.LIFECYCLE_ACTIVE else ""

    def _on_measurement(self, message: DiagnosticArray, field: str, key: str) -> None:
        self._twin.apply(message, field, key, self._run_id)
        self._publish()

    def _on_meter(self, message: DiagnosticArray) -> None:
        self._twin.apply_meter(message, self._run_id)
        self._publish()

    def _publish(self) -> None:
        snapshot = self._twin.snapshot(self._run_id)
        snapshot.header.stamp = self.get_clock().now().to_msg()
        self._publisher.publish(snapshot)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = DigitalTwinNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
