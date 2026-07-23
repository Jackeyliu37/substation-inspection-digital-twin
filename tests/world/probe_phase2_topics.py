#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import time
from uuid import uuid4

from diagnostic_msgs.msg import DiagnosticArray
from nav_msgs.msg import Odometry
import rclpy
from rcl_interfaces.msg import Parameter, ParameterType, ParameterValue
from rcl_interfaces.srv import SetParametersAtomically
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import BatteryState, CameraInfo, Image, LaserScan
from tf2_msgs.msg import TFMessage


ASSET_IDS = {
    "arrester-01",
    "breaker-01",
    "current-transformer-01",
    "disconnect-switch-01",
    "glass-insulator-01",
    "meter-oil-01",
    "meter-pressure-01",
    "porcelain-insulator-01",
    "potential-transformer-01",
    "transformer-01",
}
REQUIRED_COUNTS = {
    "/clock": 2,
    "/camera/image_raw": 2,
    "/camera/camera_info": 2,
    "/scan": 2,
    "/odom": 2,
    "/tf": 2,
    "/tf_static": 1,
    "/simulation/environment/temperature_raw": 2,
    "/simulation/environment/smoke_raw": 2,
    "/simulation/environment/gas_raw": 2,
    "/simulation/scenario_truth": 2,
    "/simulation/scenario_state": 2,
    "/battery_state": 2,
}


def qos(depth: int, reliable: bool, transient: bool = False) -> QoSProfile:
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=depth,
        reliability=(
            ReliabilityPolicy.RELIABLE
            if reliable
            else ReliabilityPolicy.BEST_EFFORT
        ),
        durability=(
            DurabilityPolicy.TRANSIENT_LOCAL
            if transient
            else DurabilityPolicy.VOLATILE
        ),
    )


def stamp_tuple(stamp) -> tuple[int, int]:
    return stamp.sec, stamp.nanosec


def diagnostic_values(message: DiagnosticArray) -> dict[str, str]:
    if len(message.status) != 1:
        return {}
    return {item.key: item.value for item in message.status[0].values}


class Phase2Probe(Node):
    def __init__(self, run_id: str) -> None:
        super().__init__("phase2_topic_probe")
        self.run_id = run_id
        self.counts = {topic: 0 for topic in REQUIRED_COUNTS}
        self.image_stamps: set[tuple[int, int]] = set()
        self.info_stamps: set[tuple[int, int]] = set()
        self.image_valid = False
        self.info_valid = False
        self.scan_valid = False
        self.odom_valid = False
        self.battery_valid = False
        self.dynamic_edges: set[tuple[str, str]] = set()
        self.static_edges: set[tuple[str, str]] = set()
        self.environment: dict[str, dict[str, str]] = {}
        self.states: list[dict[str, str]] = []
        self.truths: list[dict[str, str]] = []
        self.client = self.create_client(
            SetParametersAtomically, "/scenario_manager/set_parameters_atomically"
        )

        self.create_subscription(Clock, "/clock", self.on_clock, qos(1, False))
        self.create_subscription(
            Image, "/camera/image_raw", self.on_image, qos(2, False)
        )
        self.create_subscription(
            CameraInfo, "/camera/camera_info", self.on_info, qos(5, False)
        )
        self.create_subscription(LaserScan, "/scan", self.on_scan, qos(5, False))
        self.create_subscription(Odometry, "/odom", self.on_odom, qos(5, False))
        self.create_subscription(TFMessage, "/tf", self.on_tf, qos(100, True))
        self.create_subscription(
            TFMessage, "/tf_static", self.on_tf_static, qos(1, True, True)
        )
        self.create_subscription(
            DiagnosticArray,
            "/simulation/environment/temperature_raw",
            lambda message: self.on_environment("temperature", message),
            qos(5, False),
        )
        self.create_subscription(
            DiagnosticArray,
            "/simulation/environment/smoke_raw",
            lambda message: self.on_environment("smoke", message),
            qos(5, False),
        )
        self.create_subscription(
            DiagnosticArray,
            "/simulation/environment/gas_raw",
            lambda message: self.on_environment("gas", message),
            qos(5, False),
        )
        self.create_subscription(
            DiagnosticArray,
            "/simulation/scenario_truth",
            self.on_truth,
            qos(100, True),
        )
        self.create_subscription(
            DiagnosticArray,
            "/simulation/scenario_state",
            self.on_state,
            qos(1, True, True),
        )
        self.create_subscription(
            BatteryState, "/battery_state", self.on_battery, qos(10, True)
        )

    def on_clock(self, message: Clock) -> None:
        self.counts["/clock"] += 1

    def on_image(self, message: Image) -> None:
        self.counts["/camera/image_raw"] += 1
        self.image_stamps.add(stamp_tuple(message.header.stamp))
        payload = bytes(message.data)
        self.image_valid = self.image_valid or (
            message.width == 640
            and message.height == 480
            and message.encoding == "rgb8"
            and message.header.frame_id == "camera_optical_frame"
            and len(payload) == 640 * 480 * 3
            and len(set(payload)) > 1
        )

    def on_info(self, message: CameraInfo) -> None:
        self.counts["/camera/camera_info"] += 1
        self.info_stamps.add(stamp_tuple(message.header.stamp))
        self.info_valid = self.info_valid or (
            message.width == 640
            and message.height == 480
            and message.header.frame_id == "camera_optical_frame"
            and any(value != 0.0 for value in message.k)
        )

    def on_scan(self, message: LaserScan) -> None:
        self.counts["/scan"] += 1
        finite = [value for value in message.ranges if math.isfinite(value)]
        self.scan_valid = self.scan_valid or (
            message.header.frame_id == "laser_frame"
            and len(message.ranges) == 360
            and len(finite) >= 30
            and message.range_min == 0.12
            and message.range_max == 10.0
        )

    def on_odom(self, message: Odometry) -> None:
        self.counts["/odom"] += 1
        self.odom_valid = self.odom_valid or (
            message.header.frame_id == "odom"
            and message.child_frame_id == "base_footprint"
        )

    def on_tf(self, message: TFMessage) -> None:
        self.counts["/tf"] += 1
        self.dynamic_edges.update(
            (item.header.frame_id, item.child_frame_id) for item in message.transforms
        )

    def on_tf_static(self, message: TFMessage) -> None:
        self.counts["/tf_static"] += 1
        self.static_edges.update(
            (item.header.frame_id, item.child_frame_id) for item in message.transforms
        )

    def on_environment(self, name: str, message: DiagnosticArray) -> None:
        topic = f"/simulation/environment/{name}_raw"
        self.counts[topic] += 1
        self.environment[name] = diagnostic_values(message)

    def on_truth(self, message: DiagnosticArray) -> None:
        self.counts["/simulation/scenario_truth"] += 1
        values = diagnostic_values(message)
        if values:
            values["name"] = message.status[0].name
            self.truths.append(values)

    def on_state(self, message: DiagnosticArray) -> None:
        self.counts["/simulation/scenario_state"] += 1
        values = diagnostic_values(message)
        if values:
            values["name"] = message.status[0].name
            self.states.append(values)

    def on_battery(self, message: BatteryState) -> None:
        self.counts["/battery_state"] += 1
        self.battery_valid = self.battery_valid or (
            message.header.frame_id == "base_link"
            and 0.0 <= message.percentage <= 1.0
            and message.present
        )

    def spin_until(self, predicate, timeout: float, label: str) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if predicate():
                return
        raise RuntimeError(f"timeout waiting for {label}")

    def baseline_ready(self) -> bool:
        if any(self.counts[topic] < count for topic, count in REQUIRED_COUNTS.items()):
            return False
        required_static = {
            ("base_footprint", "base_link"),
            ("base_link", "camera_link"),
            ("camera_link", "camera_optical_frame"),
            ("base_link", "laser_frame"),
        } | {("map", f"asset/{asset_id}") for asset_id in ASSET_IDS}
        expected_environment = {
            "temperature": {"run_id", "value_celsius", "confidence_0_1", "valid"},
            "smoke": {"run_id", "value_0_1", "confidence_0_1", "valid"},
            "gas": {"run_id", "value_ppm", "confidence_0_1", "valid"},
        }
        environment_ok = all(
            set(self.environment.get(name, {})) == keys
            and self.environment[name]["run_id"] == self.run_id
            and self.environment[name]["valid"] == "true"
            for name, keys in expected_environment.items()
        )
        state_ok = bool(self.states) and set(self.states[-1]) == {
            "run_id",
            "command_id",
            "action",
            "status",
            "active",
            "scenario_revision",
            "applied_ros_sec",
            "applied_ros_nanosec",
            "error_code",
            "name",
        }
        truth_ok = bool(self.truths) and set(self.truths[-1]) == {
            "run_id",
            "active",
            "scenario_revision",
            "started_ros_sec",
            "started_ros_nanosec",
            "name",
        }
        return (
            self.image_valid
            and self.info_valid
            and bool(self.image_stamps & self.info_stamps)
            and self.scan_valid
            and self.odom_valid
            and self.battery_valid
            and ("odom", "base_footprint") in self.dynamic_edges
            and required_static.issubset(self.static_edges)
            and environment_ok
            and state_ok
            and truth_ok
            and self.states[-1]["run_id"] == self.run_id
            and self.truths[-1]["run_id"] == self.run_id
        )

    @staticmethod
    def string_parameter(name: str, value: str) -> Parameter:
        return Parameter(
            name=name,
            value=ParameterValue(
                type=ParameterType.PARAMETER_STRING, string_value=value
            ),
        )

    def apply_command(
        self, command_id: str, scenario_id: str, action: str, parameters_json: str
    ) -> None:
        if not self.client.wait_for_service(timeout_sec=10.0):
            raise RuntimeError("scenario parameter service unavailable")
        request = SetParametersAtomically.Request(
            parameters=[
                self.string_parameter("command_id", command_id),
                self.string_parameter("scenario_id", scenario_id),
                self.string_parameter("scenario_action", action),
                self.string_parameter("scenario_parameters_json", parameters_json),
            ]
        )
        future = self.client.call_async(request)
        self.spin_until(future.done, 10.0, f"parameter response {command_id}")
        response = future.result()
        if response is None or not response.result.successful:
            reason = "no response" if response is None else response.result.reason
            raise RuntimeError(f"scenario command rejected: {reason}")

    def matching_state(self, command_id: str, status: str) -> dict[str, str] | None:
        for state in reversed(self.states):
            if state.get("command_id") == command_id and state.get("status") == status:
                return state
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rclpy.init()
    node = Phase2Probe(args.run_id)
    try:
        node.spin_until(node.baseline_ready, 90.0, "baseline Phase 2 topics")
        baseline_revision = int(node.states[-1]["scenario_revision"])

        high_id = str(uuid4())
        high_json = '{"asset_id":"transformer-01","temperature_celsius":90.0}'
        node.apply_command(high_id, "temperature-high", "trigger", high_json)
        node.spin_until(
            lambda: node.matching_state(high_id, "applied") is not None
            and node.environment.get("temperature", {}).get("value_celsius") == "90.0",
            15.0,
            "temperature-high applied",
        )
        high_state = node.matching_state(high_id, "applied")
        assert high_state is not None
        high_revision = int(high_state["scenario_revision"])
        if high_revision != baseline_revision + 1 or high_state["active"] != "true":
            raise RuntimeError("temperature-high revision or active state invalid")

        state_count = len(node.states)
        node.apply_command(high_id, "temperature-high", "trigger", high_json)
        node.spin_until(lambda: len(node.states) > state_count, 10.0, "idempotent replay")
        replay_state = node.matching_state(high_id, "applied")
        assert replay_state is not None
        if int(replay_state["scenario_revision"]) != high_revision:
            raise RuntimeError("idempotent replay changed revision")

        reset_id = str(uuid4())
        node.apply_command(reset_id, "temperature-high", "reset", "{}")
        node.spin_until(
            lambda: node.matching_state(reset_id, "applied") is not None
            and node.environment.get("temperature", {}).get("value_celsius") == "25.0",
            15.0,
            "scenario reset",
        )
        reset_state = node.matching_state(reset_id, "applied")
        assert reset_state is not None
        if (
            int(reset_state["scenario_revision"]) != high_revision + 1
            or reset_state["active"] != "false"
        ):
            raise RuntimeError("reset revision or active state invalid")

        result = {
            "status": "passed",
            "counts": node.counts,
            "image": {"valid": node.image_valid, "matching_camera_info_stamp": True},
            "scan": {"valid": node.scan_valid},
            "odom": {"valid": node.odom_valid},
            "dynamic_edges": sorted([list(edge) for edge in node.dynamic_edges]),
            "static_edges": sorted([list(edge) for edge in node.static_edges]),
            "baseline_revision": baseline_revision,
            "temperature_high_revision": high_revision,
            "reset_revision": int(reset_state["scenario_revision"]),
            "run_id": args.run_id,
        }
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.replace(args.output)
        print("phase2-topic-probe: PASS", flush=True)
        return 0
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
