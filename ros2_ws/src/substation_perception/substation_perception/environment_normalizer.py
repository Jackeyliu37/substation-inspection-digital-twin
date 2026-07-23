from __future__ import annotations

import math

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from substation_interfaces.msg import RunContext


REQUIRED_COMMON = {"run_id", "confidence_0_1", "valid"}


def normalize_measurement(
    message: DiagnosticArray,
    value_key: str,
    active_run_id: str,
) -> DiagnosticArray:
    output = DiagnosticArray()
    output.header = message.header
    for source in message.status:
        values = {item.key: item.value for item in source.values}
        if len(values) != len(source.values) or set(values) != REQUIRED_COMMON | {value_key}:
            continue
        try:
            value = float(values[value_key])
            confidence = float(values["confidence_0_1"])
        except ValueError:
            continue
        valid_value = (
            math.isfinite(value)
            and math.isfinite(confidence)
            and 0.0 <= confidence <= 1.0
            and values["valid"] == "true"
            and values["run_id"] == active_run_id
            and bool(active_run_id)
        )
        if value_key == "value_0_1":
            valid_value = valid_value and 0.0 <= value <= 1.0
        elif value_key == "value_ppm":
            valid_value = valid_value and value >= 0.0
        if not valid_value:
            continue
        output.status.append(DiagnosticStatus(
            level=DiagnosticStatus.OK,
            name=source.name,
            message="NORMALIZED_VALID",
            hardware_id=source.hardware_id,
            values=[KeyValue(key=item.key, value=item.value) for item in source.values],
        ))
    return output


class EnvironmentNormalizer(Node):
    def __init__(self) -> None:
        super().__init__("environment_normalizer")
        self._run_id = ""
        q_sensor = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        q_stream = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        q_state = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.create_subscription(RunContext, "/system/run_context", self._on_context, q_state)
        topics = (
            ("temperature", "value_celsius"),
            ("smoke", "value_0_1"),
            ("gas", "value_ppm"),
        )
        for name, value_key in topics:
            publisher = self.create_publisher(DiagnosticArray, f"/environment/{name}", q_stream)
            self.create_subscription(
                DiagnosticArray,
                f"/simulation/environment/{name}_raw",
                lambda message, key=value_key, pub=publisher: self._forward(message, key, pub),
                q_sensor,
            )

    def _on_context(self, context: RunContext) -> None:
        self._run_id = context.run_id if context.lifecycle == RunContext.LIFECYCLE_ACTIVE else ""

    def _forward(self, message: DiagnosticArray, key: str, publisher) -> None:
        output = normalize_measurement(message, key, self._run_id)
        if output.status:
            publisher.publish(output)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = EnvironmentNormalizer()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
