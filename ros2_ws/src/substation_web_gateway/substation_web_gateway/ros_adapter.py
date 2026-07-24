"""ROS 2 to Web Gateway projection and runtime adapter.

The projector is deliberately independent from the executor thread so its
validation and JSON mapping can be tested without a live ROS graph.  The
runtime adapter owns the rclpy node and is the only place where the Gateway
touches ROS.
"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import json
import math
import threading
from typing import Any

import cv2
from diagnostic_msgs.msg import DiagnosticArray
from map_msgs.msg import OccupancyGridUpdate
from nav_msgs.msg import OccupancyGrid, Odometry, Path as NavigationPath
import numpy as np
import rclpy
from rcl_interfaces.srv import SetParametersAtomically
from rclpy.clock import Clock, ClockType
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from sensor_msgs.msg import BatteryState, Image
from substation_interfaces.msg import (
    AssetRiskArray,
    InspectionTaskArray,
    ManualVelocityCommand,
    ManualVelocityStatus,
    RiskAlert,
    RunContext,
)
from substation_interfaces.srv import (
    EmergencyStop,
    GetReportingReadiness,
    ListReportingArtifacts,
    ManageMission,
    QueryEvidence,
    QueryRunTimeMapping,
    ReadEvidenceChunk,
    RecordRunTimeMapping,
    ResetEmergencyStop,
    SetRobotMode,
)
from tf2_ros import Buffer, TransformException, TransformListener

from .app import GatewayState, _utc_now


_LIFECYCLES = ("idle", "starting", "active", "ending", "ended")
_MISSION_STATES = (
    "idle", "ready", "running", "paused", "stopping", "succeeded", "failed", "stopped"
)
_ROBOT_MODES = ("autonomous", "manual", "estop")
_TASK_TYPES = ("inspect_asset", "navigation_goal", "return_home")
_TASK_STATES = ("queued", "active", "succeeded", "skipped", "failed", "cancelled")
_RISK_LEVELS = ("normal", "attention", "alert", "emergency")


def _yaw(x: float, y: float, z: float, w: float) -> float:
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def _normalized_quaternion(
    x: float, y: float, z: float, w: float
) -> tuple[float, float, float, float] | None:
    values = tuple(float(value) for value in (x, y, z, w))
    if not all(math.isfinite(value) for value in values):
        return None
    norm = math.sqrt(sum(value * value for value in values))
    if norm <= 1e-12:
        return None
    return tuple(value / norm for value in values)


def _quaternion_multiply(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    lx, ly, lz, lw = left
    rx, ry, rz, rw = right
    return (
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
        lw * rw - lx * rx - ly * ry - lz * rz,
    )


def _rotate_vector(
    rotation: tuple[float, float, float, float],
    vector: tuple[float, float, float],
) -> tuple[float, float, float]:
    x, y, z, w = rotation
    vx, vy, vz = vector
    dot_uv = x * vx + y * vy + z * vz
    dot_uu = x * x + y * y + z * z
    cross_x = y * vz - z * vy
    cross_y = z * vx - x * vz
    cross_z = x * vy - y * vx
    scale = w * w - dot_uu
    return (
        2.0 * dot_uv * x + scale * vx + 2.0 * w * cross_x,
        2.0 * dot_uv * y + scale * vy + 2.0 * w * cross_y,
        2.0 * dot_uv * z + scale * vz + 2.0 * w * cross_z,
    )


def _optional_float(value: str) -> float | None:
    if value == "":
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("non-finite numeric field")
    return result


def _float32(value: float) -> float:
    """Remove transport noise while retaining more precision than Web schemas require."""
    return float(f"{float(value):.6g}")


class RosStateProjector:
    """Validate authoritative ROS snapshots before exposing Web state."""

    def __init__(
        self,
        state: GatewayState,
        *,
        command_observer=None,
        scenario_command_observer=None,
    ) -> None:
        self.state = state
        self.state.authoritative_required = True
        self._command_observer = command_observer
        self._scenario_command_observer = scenario_command_observer
        self._context: RunContext | None = None
        self._twin_by_asset: dict[str, dict[str, Any]] = {}
        self._risk_by_asset: dict[str, dict[str, Any]] = {}
        self._risk_revision = 0
        self._risk_snapshot_received = False
        self._robot_mode = InspectionTaskArray.MODE_AUTONOMOUS
        self._emergency_stop_latched = False
        self._latch_revision = 0
        self._time_mapping: dict[str, Any] | None = None
        self._map_bytes: bytearray | None = None
        self._map_width = 0
        self._map_height = 0
        self._planned_path: list[dict[str, float]] = []
        self._plan_source_ros_time: dict[str, int] | None = None
        self._battery_percent: float | None = None

    def _bump(self) -> None:
        self.state.snapshot_revision += 1

    def _append_event(self, event: dict[str, Any]) -> None:
        event.setdefault("occurred_at", _utc_now())
        self.state.events.append(event)
        if len(self.state.events) > 200:
            del self.state.events[:-200]

    def on_annotated_image(self, message: Image) -> None:
        if (
            message.header.frame_id != "camera_optical_frame"
            or message.encoding != "rgb8"
            or message.width <= 0
            or message.height <= 0
            or message.step != message.width * 3
            or len(message.data) != message.step * message.height
        ):
            return
        try:
            image = np.frombuffer(bytes(message.data), dtype=np.uint8).reshape(
                (message.height, message.width, 3)
            )
            ok, encoded = cv2.imencode(
                ".jpg", cv2.cvtColor(image, cv2.COLOR_RGB2BGR),
                [int(cv2.IMWRITE_JPEG_QUALITY), 85],
            )
        except (ValueError, cv2.error):
            return
        if not ok:
            return
        self.state.camera_jpeg = bytes(encoded)
        self.state.camera_metadata = {
            "source_topic": "/perception/annotated_image",
            "source_frame_id": message.header.frame_id,
            "source_ros_time": {
                "sec": int(message.header.stamp.sec),
                "nanosec": int(message.header.stamp.nanosec),
            },
            "width": int(message.width),
            "height": int(message.height),
            "encoding": "jpeg",
        }
        captured_at = self.ros_time_to_utc(
            message.header.stamp.sec, message.header.stamp.nanosec
        )
        if captured_at is not None:
            self.state.camera_metadata["captured_at"] = captured_at

    def set_ros_graph_ready(self, *, ros: bool, gazebo: bool, nav2: bool) -> None:
        changed = any(
            self.state.ready_dependencies[key] != value
            for key, value in (("ros", ros), ("gazebo", gazebo), ("nav2", nav2))
        )
        self.state.ready_dependencies.update(ros=ros, gazebo=gazebo, nav2=nav2)
        self._refresh_overall()
        if changed:
            self._bump()

    def set_reporting_readiness(
        self,
        *,
        evidence_store_writable: bool,
        report_generator_ready: bool,
        time_mapping_ready: bool,
    ) -> None:
        mapping_matches = (
            self.state.run_id is None
            or (
                self._time_mapping is not None
                and self._time_mapping["run_id"] == self.state.run_id
            )
        )
        values = {
            "storage": evidence_store_writable,
            "reporting": report_generator_ready,
            "time_mapping": time_mapping_ready and mapping_matches,
        }
        changed = any(self.state.ready_dependencies[key] != value for key, value in values.items())
        self.state.ready_dependencies.update(values)
        self.state.system["storage"] = {
            "status": "ok" if evidence_store_writable else "error",
            "free_bytes": None,
            "audit_writable": evidence_store_writable,
        }
        self._refresh_overall()
        if changed:
            self._bump()

    def set_time_mapping(
        self,
        *,
        run_id: str,
        context_revision: int,
        anchor_ros_sec: int,
        anchor_ros_nanosec: int,
        anchor_utc: str,
    ) -> bool:
        try:
            anchor = datetime.fromisoformat(anchor_utc.replace("Z", "+00:00"))
        except ValueError:
            return False
        if anchor.tzinfo is None or run_id != self.state.run_id:
            return False
        self._time_mapping = {
            "run_id": run_id,
            "context_revision": int(context_revision),
            "anchor_ros_ns": int(anchor_ros_sec) * 1_000_000_000 + int(anchor_ros_nanosec),
            "anchor_utc": anchor.astimezone(timezone.utc),
        }
        self._render_context()
        self._render_assets()
        return True

    def ros_time_to_utc(self, sec: int, nanosec: int) -> str | None:
        mapping = self._time_mapping
        if mapping is None or mapping["run_id"] != self.state.run_id:
            return None
        source_ns = int(sec) * 1_000_000_000 + int(nanosec)
        delta = timedelta(microseconds=(source_ns - mapping["anchor_ros_ns"]) / 1_000)
        return (mapping["anchor_utc"] + delta).isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        )

    def on_run_context(self, message: RunContext) -> bool:
        if message.schema_version != RunContext.SCHEMA_VERSION:
            return False
        if message.lifecycle >= len(_LIFECYCLES):
            return False
        active_run = message.run_id or None
        if message.lifecycle in (RunContext.LIFECYCLE_STARTING, RunContext.LIFECYCLE_ACTIVE,
                                 RunContext.LIFECYCLE_ENDING, RunContext.LIFECYCLE_ENDED):
            if not active_run:
                return False
        if self._context is not None and active_run == self.state.run_id:
            if int(message.context_revision) < int(self._context.context_revision):
                return False
            if message == self._context:
                return True
        if active_run != self.state.run_id:
            self._twin_by_asset.clear()
            self._risk_by_asset.clear()
            self._risk_revision = 0
            self._risk_snapshot_received = False
            self._time_mapping = None
            self._planned_path = []
            self._plan_source_ros_time = None
            self.state.assets = []
            self.state.ready_dependencies.update(mission=False, risk=False, time_mapping=False)
        self._context = message
        self.state.run_id = active_run
        self.state.ready_dependencies["run_context"] = True
        self._render_context()
        self._refresh_overall()
        self._bump()
        return True

    def _render_context(self) -> None:
        message = self._context
        if message is None:
            return
        self.state.system["run_context"] = {
            "lifecycle": _LIFECYCLES[message.lifecycle],
            "context_revision": str(message.context_revision),
            "started_at": self.ros_time_to_utc(message.started_at.sec, message.started_at.nanosec)
            if message.started_at.sec or message.started_at.nanosec
            else None,
            "ended_at": self.ros_time_to_utc(message.ended_at.sec, message.ended_at.nanosec)
            if message.ended_at.sec or message.ended_at.nanosec
            else None,
            "transition_command_id": message.transition_command_id or None,
            "reason_code": message.reason_code,
            "reason": message.reason,
        }

    def on_mission(self, message: InspectionTaskArray) -> bool:
        if message.schema_version != InspectionTaskArray.SCHEMA_VERSION:
            return False
        if message.run_id != (self.state.run_id or ""):
            return False
        if message.mission_state >= len(_MISSION_STATES) or message.robot_mode >= len(_ROBOT_MODES):
            return False
        tasks = []
        for item in message.tasks:
            if item.schema_version != item.SCHEMA_VERSION:
                return False
            if item.task_type >= len(_TASK_TYPES) or item.state >= len(_TASK_STATES):
                return False
            orientation = item.goal.pose.orientation
            tasks.append({
                "task_id": item.task_id,
                "command_id": item.command_id or None,
                "asset_id": item.asset_id or None,
                "type": _TASK_TYPES[item.task_type],
                "state": _TASK_STATES[item.state],
                "computed_priority": _float32(item.computed_priority),
                "risk_score_0_100": _float32(item.risk_score_0_100),
                "goal": {
                    "frame_id": item.goal.header.frame_id,
                    "x_m": float(item.goal.pose.position.x),
                    "y_m": float(item.goal.pose.position.y),
                    "yaw_rad": _yaw(orientation.x, orientation.y, orientation.z, orientation.w),
                },
                "attempt": int(item.attempt),
                "last_error_code": item.last_error_code or None,
            })
        mission = {
            "mission_id": message.mission_id or None,
            "route_id": message.route_id or None,
            "state": _MISSION_STATES[message.mission_state],
            "state_revision": str(message.state_revision),
            "queue_revision": str(message.queue_revision),
            "transition_command_id": message.transition_command_id or None,
            "transition_reason_code": message.transition_reason_code,
            "transition_reason": message.transition_reason,
            "active_task_id": message.active_task_id or None,
            "completed_tasks": int(message.completed_tasks),
            "total_tasks": int(message.total_tasks),
            "progress_0_1": _float32(message.progress_0_1),
            "tasks": tasks,
        }
        if (
            mission == self.state.mission
            and self.state.system["emergency_stop_latched"]
            == bool(message.emergency_stop_latched)
            and self.state.ready_dependencies["mission"]
        ):
            return True
        previous_tasks = {
            item.get("task_id"): item for item in self.state.mission.get("tasks", [])
        }
        previous_state = self.state.mission.get("state")
        self.state.mission = mission
        self.state.system["emergency_stop_latched"] = bool(message.emergency_stop_latched)
        self._robot_mode = int(message.robot_mode)
        self._emergency_stop_latched = bool(message.emergency_stop_latched)
        self._latch_revision = int(message.emergency_stop_latch_revision)
        self._sync_robot_mission_fields(self._latch_revision)
        self.state.ready_dependencies["mission"] = True
        for item in tasks:
            previous = previous_tasks.get(item["task_id"])
            if previous is not None and previous.get("state") == item["state"]:
                continue
            if item["state"] == "active":
                self._append_event({
                    "kind": "task.active",
                    "asset_id": item["asset_id"],
                    "task_id": item["task_id"],
                    "result": "active",
                    "description": f"开始检查设备 {item['asset_id']}",
                })
            elif item["state"] in {"succeeded", "skipped", "failed"}:
                descriptions = {
                    "succeeded": "检查完成",
                    "skipped": "设备不可达，已跳过",
                    "failed": "检查失败",
                }
                self._append_event({
                    "kind": f"task.{item['state']}",
                    "asset_id": item["asset_id"],
                    "task_id": item["task_id"],
                    "result": item["state"],
                    "description": f"设备 {item['asset_id']} {descriptions[item['state']]}",
                })
        if mission["state"] != previous_state and mission["state"] in {
            "succeeded", "failed", "stopped"
        }:
            descriptions = {
                "succeeded": "自动巡检全部完成，正在生成报告",
                "failed": "自动巡检失败",
                "stopped": "自动巡检已停止",
            }
            self._append_event({
                "kind": f"mission.{mission['state']}",
                "mission_id": mission["mission_id"],
                "result": mission["state"],
                "description": descriptions[mission["state"]],
            })
        if self._command_observer is not None and message.transition_command_id:
            observation = dict(mission)
            observation.update(
                robot_mode=_ROBOT_MODES[self._robot_mode],
                emergency_stop_latched=self._emergency_stop_latched,
                emergency_stop_latch_revision=str(self._latch_revision),
            )
            self._command_observer(
                message.transition_command_id, observation, self.state.run_id
            )
        self._refresh_overall()
        self._bump()
        return True

    def _sync_robot_mission_fields(self, latch_revision: int) -> None:
        if self.state.robot is None:
            return
        self.state.robot["mode"] = _ROBOT_MODES[self._robot_mode]
        self.state.robot["emergency_stop"] = {
            "latched": self._emergency_stop_latched,
            "latch_revision": str(latch_revision),
        }
        self.state.robot["current_mission_id"] = self.state.mission["mission_id"]
        self.state.robot["current_task_id"] = self.state.mission["active_task_id"]

    def on_odom(self, message: Odometry, map_from_odom: Any) -> bool:
        if message.header.frame_id != "odom" or message.child_frame_id != "base_footprint":
            return False
        pose = message.pose.pose
        twist = message.twist.twist
        translation = map_from_odom.transform.translation
        transform_rotation = map_from_odom.transform.rotation
        numeric_values = (
            pose.position.x,
            pose.position.y,
            pose.position.z,
            translation.x,
            translation.y,
            translation.z,
            twist.linear.x,
            twist.linear.y,
            twist.angular.z,
        )
        if not all(math.isfinite(float(value)) for value in numeric_values):
            return False
        map_rotation = _normalized_quaternion(
            transform_rotation.x,
            transform_rotation.y,
            transform_rotation.z,
            transform_rotation.w,
        )
        odom_rotation = _normalized_quaternion(
            pose.orientation.x,
            pose.orientation.y,
            pose.orientation.z,
            pose.orientation.w,
        )
        if map_rotation is None or odom_rotation is None:
            return False
        rotated = _rotate_vector(
            map_rotation,
            (float(pose.position.x), float(pose.position.y), float(pose.position.z)),
        )
        orientation = _normalized_quaternion(
            *_quaternion_multiply(map_rotation, odom_rotation)
        )
        if orientation is None:
            return False
        qx, qy, qz, qw = orientation
        robot = {
            "frame_id": "map",
            "pose": {
                "x_m": rotated[0] + float(translation.x),
                "y_m": rotated[1] + float(translation.y),
                "z_m": rotated[2] + float(translation.z),
                "qx": qx,
                "qy": qy,
                "qz": qz,
                "qw": qw,
            },
            "twist": {
                "linear_x_m_s": float(twist.linear.x),
                "linear_y_m_s": float(twist.linear.y),
                "angular_z_rad_s": float(twist.angular.z),
            },
            "battery_percent": self._battery_percent,
            "mode": _ROBOT_MODES[self._robot_mode],
            "stale": False,
            "emergency_stop": {
                "latched": self._emergency_stop_latched,
                "latch_revision": str(self._latch_revision),
            },
            "current_mission_id": self.state.mission["mission_id"],
            "current_task_id": self.state.mission["active_task_id"],
            "source_ros_time": {
                "sec": int(message.header.stamp.sec),
                "nanosec": int(message.header.stamp.nanosec),
            },
        }
        if robot == self.state.robot:
            return True
        self.state.robot = robot
        self._bump()
        return True

    def update_robot_staleness(self, now_sec: int, now_nanosec: int) -> bool:
        if self.state.robot is None:
            return False
        source = self.state.robot["source_ros_time"]
        age_ns = (
            (int(now_sec) - int(source["sec"])) * 1_000_000_000
            + int(now_nanosec)
            - int(source["nanosec"])
        )
        stale = age_ns > 500_000_000 or age_ns < -20_000_000
        if bool(self.state.robot["stale"]) == stale:
            return True
        self.state.robot["stale"] = stale
        self._bump()
        return True

    def on_battery(self, message: BatteryState) -> bool:
        percentage = float(message.percentage)
        if (
            message.header.frame_id != "base_link"
            or not math.isfinite(percentage)
            or percentage < 0.0
            or percentage > 1.0
        ):
            return False
        battery_percent = _float32(percentage * 100.0)
        if battery_percent == self._battery_percent:
            return True
        self._battery_percent = battery_percent
        if self.state.robot is not None:
            self.state.robot["battery_percent"] = battery_percent
            self._bump()
        return True

    def on_twin(self, message: DiagnosticArray) -> bool:
        accepted: dict[str, dict[str, Any]] = {}
        for status in message.status:
            values = {item.key: item.value for item in status.values}
            if values.get("run_id") != self.state.run_id:
                continue
            try:
                accepted[status.name] = {
                    "asset_id": status.name,
                    "category": values["category"],
                    "state": values["state"],
                    "pose": {
                        "frame_id": "map",
                        "x_m": _optional_float(values["pose_x_m"]),
                        "y_m": _optional_float(values["pose_y_m"]),
                        "z_m": _optional_float(values["pose_z_m"]),
                        "qx": _optional_float(values["orientation_x"]),
                        "qy": _optional_float(values["orientation_y"]),
                        "qz": _optional_float(values["orientation_z"]),
                        "qw": _optional_float(values["orientation_w"]),
                    },
                    "measurements": {
                        "temperature_celsius": _optional_float(values["temperature_celsius"]),
                        "smoke_0_1": _optional_float(values["smoke_0_1"]),
                        "gas_ppm": _optional_float(values["gas_ppm"]),
                        "meter_reading": _optional_float(values["meter_reading"]),
                        "meter_unit": values["meter_unit"] or None,
                    },
                    "latest_evidence_id": values["latest_evidence_id"] or None,
                    "observed_sec": int(values["last_observed_ros_sec"]),
                    "observed_nanosec": int(values["last_observed_ros_nanosec"]),
                }
            except (KeyError, ValueError):
                continue
        if not accepted:
            return False
        if accepted == self._twin_by_asset:
            return True
        self._twin_by_asset = accepted
        self._render_assets()
        self._refresh_risk_ready()
        self._bump()
        return True

    def on_risk(self, message: AssetRiskArray) -> bool:
        if message.schema_version != AssetRiskArray.SCHEMA_VERSION or message.run_id != self.state.run_id:
            return False
        if int(message.risk_revision) < self._risk_revision:
            return False
        accepted: dict[str, dict[str, Any]] = {}
        for item in message.assets:
            if item.schema_version != item.SCHEMA_VERSION or item.level >= len(_RISK_LEVELS):
                return False
            accepted[item.asset_id] = {
                "score_0_100": _float32(item.score_0_100),
                "level": _RISK_LEVELS[item.level],
                "visual_0_1": _float32(item.visual_0_1),
                "temperature_0_1": _float32(item.temperature_0_1),
                "smoke_0_1": _float32(item.smoke_0_1),
                "gas_0_1": _float32(item.gas_0_1),
                "context_0_1": _float32(item.context_0_1),
            }
        first_snapshot = not self._risk_snapshot_received
        self._risk_snapshot_received = True
        if (
            not first_snapshot
            and int(message.risk_revision) == self._risk_revision
            and accepted == self._risk_by_asset
        ):
            return True
        previous_risks = self._risk_by_asset
        self._risk_by_asset = accepted
        self._risk_revision = int(message.risk_revision)
        self._render_assets()
        for asset_id, risk in accepted.items():
            previous = previous_risks.get(asset_id)
            if previous == risk:
                continue
            self._append_event({
                "kind": "risk.evaluated",
                "asset_id": asset_id,
                "result": risk["level"],
                "score_0_100": risk["score_0_100"],
                "description": (
                    f"设备 {asset_id} 风险评分 {risk['score_0_100']:.1f}，"
                    f"等级 {risk['level']}"
                ),
            })
        self._refresh_risk_ready()
        self._bump()
        return True

    def _refresh_risk_ready(self) -> None:
        self.state.ready_dependencies["risk"] = bool(
            self.state.run_id and self._twin_by_asset and self._risk_snapshot_received
        )
        self._refresh_overall()

    def _render_assets(self) -> None:
        items = []
        for asset_id in sorted(self._twin_by_asset):
            twin = self._twin_by_asset[asset_id]
            risk = self._risk_by_asset.get(asset_id, {
                "score_0_100": 0.0,
                "level": "unknown",
                "visual_0_1": 0.0,
                "temperature_0_1": 0.0,
                "smoke_0_1": 0.0,
                "gas_0_1": 0.0,
                "context_0_1": 0.0,
            })
            items.append({
                "asset_id": asset_id,
                "category": twin["category"],
                "state": twin["state"],
                "pose": twin["pose"],
                "measurements": twin["measurements"],
                "risk": risk,
                "latest_evidence_id": twin["latest_evidence_id"],
                "observed_at": self.ros_time_to_utc(
                    twin["observed_sec"], twin["observed_nanosec"]
                ),
                "stale": False,
            })
        self.state.assets = items

    def on_scenario_state(self, message: DiagnosticArray) -> bool:
        accepted = None
        for status in message.status:
            values = {item.key: item.value for item in status.values}
            if values.get("run_id") != self.state.run_id:
                continue
            try:
                active_text = values["active"]
                if active_text not in {"true", "false"}:
                    continue
                accepted = {
                    "scenario_id": status.name,
                    "command_id": values["command_id"] or None,
                    "action": values["action"],
                    "status": values["status"],
                    "active": active_text == "true",
                    "scenario_revision": str(int(values["scenario_revision"])),
                    "source_ros_time": {
                        "sec": int(values["applied_ros_sec"]),
                        "nanosec": int(values["applied_ros_nanosec"]),
                    },
                    "error_code": values["error_code"] or None,
                }
            except (KeyError, ValueError):
                continue
        if accepted is None:
            return False
        if accepted == self.state.scenario:
            return True
        self.state.scenario = accepted
        if (
            self._scenario_command_observer is not None
            and accepted.get("command_id")
            and accepted.get("status") in {"applied", "failed"}
        ):
            self._scenario_command_observer(
                accepted["command_id"], accepted, self.state.run_id
            )
        self._bump()
        return True

    def on_alert(self, message: RiskAlert) -> bool:
        if message.schema_version != RiskAlert.SCHEMA_VERSION or message.run_id != self.state.run_id:
            return False
        if message.event_type >= 3 or message.previous_level >= 4 or message.current_level >= 4:
            return False
        self._append_event({
            "type": "risk.alert",
            "alert_id": message.alert_id,
            "asset_id": message.asset_id,
            "event": ("opened", "level_changed", "cleared")[message.event_type],
            "previous_level": _RISK_LEVELS[message.previous_level],
            "current_level": _RISK_LEVELS[message.current_level],
            "score_0_100": _float32(message.score_0_100),
            "evidence_ids": list(message.evidence_ids),
        })
        self._bump()
        return True

    def on_map(self, message: OccupancyGrid) -> bool:
        width = int(message.info.width)
        height = int(message.info.height)
        values = list(message.data)
        if (
            message.header.frame_id != "map"
            or width <= 0
            or height <= 0
            or len(values) != width * height
            or any(value < -1 or value > 100 for value in values)
        ):
            self.state.map_snapshot = None
            self._map_bytes = None
            return False
        orientation = message.info.origin.orientation
        self._map_bytes = bytearray(value & 0xFF for value in values)
        self._map_width = width
        self._map_height = height
        revision = int((self.state.map_snapshot or {}).get("map_revision", "0")) + 1
        self.state.map_snapshot = {
            "map_revision": str(revision),
            "frame_id": "map",
            "source_ros_time": {
                "sec": int(message.header.stamp.sec),
                "nanosec": int(message.header.stamp.nanosec),
            },
            "resolution_m": float(message.info.resolution),
            "width_cells": width,
            "height_cells": height,
            "origin": {
                "x_m": float(message.info.origin.position.x),
                "y_m": float(message.info.origin.position.y),
                "yaw_rad": _yaw(orientation.x, orientation.y, orientation.z, orientation.w),
            },
            "data_encoding": "base64-int8-row-major-v1",
            "data": base64.b64encode(self._map_bytes).decode("ascii"),
            "planned_path": list(self._planned_path),
            "plan_source_ros_time": self._plan_source_ros_time,
        }
        self._bump()
        return True

    def on_plan(self, message: NavigationPath) -> bool:
        if message.header.frame_id != "map":
            return False
        points: list[dict[str, float]] = []
        for stamped in message.poses:
            if stamped.header.frame_id not in ("", "map"):
                return False
            x = float(stamped.pose.position.x)
            y = float(stamped.pose.position.y)
            if not math.isfinite(x) or not math.isfinite(y):
                return False
            points.append({"x_m": x, "y_m": y})
        if len(points) > 400:
            stride = math.ceil(len(points) / 400)
            points = points[::stride]
            final = message.poses[-1].pose.position
            endpoint = {"x_m": float(final.x), "y_m": float(final.y)}
            if points[-1] != endpoint:
                points.append(endpoint)
        source_time = {
            "sec": int(message.header.stamp.sec),
            "nanosec": int(message.header.stamp.nanosec),
        }
        if points == self._planned_path and source_time == self._plan_source_ros_time:
            return True
        self._planned_path = points
        self._plan_source_ros_time = source_time
        if self.state.map_snapshot is not None:
            snapshot = dict(self.state.map_snapshot)
            snapshot["planned_path"] = list(points)
            snapshot["plan_source_ros_time"] = source_time
            self.state.map_snapshot = snapshot
        self._bump()
        return True

    def on_map_update(self, message: OccupancyGridUpdate) -> bool:
        if self._map_bytes is None or message.header.frame_id != "map":
            return False
        x, y = int(message.x), int(message.y)
        width, height = int(message.width), int(message.height)
        values = list(message.data)
        if (
            width <= 0 or height <= 0 or len(values) != width * height
            or x + width > self._map_width or y + height > self._map_height
            or any(value < -1 or value > 100 for value in values)
        ):
            self.state.map_snapshot = None
            self._map_bytes = None
            return False
        for row in range(height):
            source = row * width
            target = (y + row) * self._map_width + x
            self._map_bytes[target:target + width] = bytes(value & 0xFF for value in values[source:source + width])
        snapshot = dict(self.state.map_snapshot or {})
        snapshot["map_revision"] = str(int(snapshot["map_revision"]) + 1)
        snapshot["source_ros_time"] = {
            "sec": int(message.header.stamp.sec), "nanosec": int(message.header.stamp.nanosec)
        }
        snapshot["data"] = base64.b64encode(self._map_bytes).decode("ascii")
        self.state.map_snapshot = snapshot
        self._bump()
        return True

    def on_diagnostics(self, message: DiagnosticArray) -> None:
        components = []
        for status in sorted(message.status, key=lambda item: item.name):
            level = status.level[0] if isinstance(status.level, bytes) else int(status.level)
            components.append({
                "name": status.name,
                "kind": "ros_node",
                "status": ("ok", "degraded", "error", "stale")[max(0, min(level, 3))],
                "message": status.message,
                "last_seen_at": self.ros_time_to_utc(
                    message.header.stamp.sec, message.header.stamp.nanosec
                ),
            })
        self.state.system["components"] = components
        self._bump()

    def _refresh_overall(self) -> None:
        dependencies = self.state.ready_dependencies
        self.state.system["overall"] = "ready" if all(dependencies.values()) else (
            "degraded" if any(dependencies.values()) else "unavailable"
        )


class RosGatewayNode(Node):
    """Live ROS subscriptions and reporting-readiness clients."""

    def __init__(
        self,
        state: GatewayState,
        *,
        context=None,
        command_observer=None,
        manual_command_observer=None,
        scenario_command_observer=None,
    ) -> None:
        super().__init__(
            "web_gateway",
            context=context,
            parameter_overrides=[Parameter("use_sim_time", Parameter.Type.BOOL, True)],
        )
        self.projector = RosStateProjector(
            state,
            command_observer=command_observer,
            scenario_command_observer=scenario_command_observer,
        )
        self._manual_command_observer = manual_command_observer
        self._manual_command_context: dict[str, tuple[str, int]] = {}
        self._mapping_query_inflight = False
        self._mapping_record_inflight = False
        self._mapping_creation_runs: set[str] = set()
        self._readiness_inflight = False
        self._pending_mapping: dict[str, Any] | None = None
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
        q_control = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        q_sensor = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=5,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        q_stream = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        q_tf = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=100,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        q_tf_static = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self._tf_buffer = Buffer(node=self)
        self._tf_listener = TransformListener(
            self._tf_buffer,
            self,
            spin_thread=False,
            qos=q_tf,
            static_qos=q_tf_static,
        )
        self.create_subscription(RunContext, "/system/run_context", self._on_context, q_state)
        self.create_subscription(DiagnosticArray, "/digital_twin/assets", self.projector.on_twin, q_state)
        self.create_subscription(AssetRiskArray, "/risk/assets", self.projector.on_risk, q_state)
        self.create_subscription(RiskAlert, "/risk/alerts", self.projector.on_alert, q_event)
        self.create_subscription(
            InspectionTaskArray, "/mission/inspection_tasks", self.projector.on_mission, q_state
        )
        self.create_subscription(OccupancyGrid, "/map", self.projector.on_map, q_state)
        self.create_subscription(NavigationPath, "/plan", self.projector.on_plan, q_stream)
        self.create_subscription(
            OccupancyGridUpdate, "/map_updates", self.projector.on_map_update, q_event
        )
        self.create_subscription(DiagnosticArray, "/diagnostics", self.projector.on_diagnostics, q_event)
        self.create_subscription(
            DiagnosticArray,
            "/simulation/scenario_state",
            self.projector.on_scenario_state,
            q_state,
        )
        self.create_subscription(Odometry, "/odom", self._on_odom, q_sensor)
        self.create_subscription(BatteryState, "/battery_state", self.projector.on_battery, q_stream)
        self.create_subscription(
            Image,
            "/perception/annotated_image",
            self.projector.on_annotated_image,
            q_sensor,
        )
        self.create_subscription(
            ManualVelocityStatus,
            "/mission/manual_velocity_status",
            self._on_manual_velocity_status,
            q_event,
        )
        self._query_mapping = self.create_client(
            QueryRunTimeMapping, "/reporting/query_run_time_mapping"
        )
        self._record_mapping = self.create_client(
            RecordRunTimeMapping, "/reporting/record_run_time_mapping"
        )
        self._reporting_readiness = self.create_client(
            GetReportingReadiness, "/reporting/readiness"
        )
        self._manual_velocity = self.create_publisher(
            ManualVelocityCommand, "/cmd_vel_manual", q_control
        )
        self._manage_mission = self.create_client(ManageMission, "/mission/manage")
        self._emergency_stop = self.create_client(
            EmergencyStop, "/mission/emergency_stop"
        )
        self._emergency_reset = self.create_client(
            ResetEmergencyStop, "/mission/emergency_stop_reset"
        )
        self._set_robot_mode = self.create_client(
            SetRobotMode, "/mission/set_robot_mode"
        )
        self._set_scenario_parameters = self.create_client(
            SetParametersAtomically, "/scenario_manager/set_parameters_atomically"
        )
        self._query_evidence = self.create_client(QueryEvidence, "/reporting/query_evidence")
        self._list_reporting_artifacts = self.create_client(
            ListReportingArtifacts, "/reporting/list_reporting_artifacts"
        )
        self._read_evidence = self.create_client(
            ReadEvidenceChunk, "/reporting/read_evidence_chunk"
        )
        # Readiness and dependency polling must continue while simulation time is
        # paused or before /clock starts; only pose freshness uses ROS time.
        self.create_timer(1.0, self._poll, clock=Clock(clock_type=ClockType.STEADY_TIME))

    @staticmethod
    def _wait_for_service_future(future, timeout_s: float) -> Any | None:
        event = threading.Event()
        future.add_done_callback(lambda _completed: event.set())
        if not event.wait(timeout_s):
            return None
        try:
            return future.result()
        except Exception:
            return None

    def query_evidence(self, evidence_id: str) -> dict[str, Any]:
        if not self._query_evidence.service_is_ready():
            return {
                "found": False,
                "error_code": "EVIDENCE_STORAGE_UNAVAILABLE",
                "error_message": "/reporting/query_evidence is unavailable.",
            }
        request = QueryEvidence.Request()
        request.schema_version = 1
        request.evidence_id = evidence_id
        response = self._wait_for_service_future(self._query_evidence.call_async(request), 2.0)
        if response is None:
            return {
                "found": False,
                "error_code": "EVIDENCE_STORAGE_UNAVAILABLE",
                "error_message": "/reporting/query_evidence timed out.",
            }
        return {
            "found": bool(response.found),
            "run_id": response.run_id,
            "context_revision": int(response.context_revision),
            "evidence_revision": int(response.evidence_revision),
            "media_type": response.media_type,
            "content_sha256": response.content_sha256,
            "size_bytes": int(response.size_bytes),
            "metadata_canonical_json": response.metadata_canonical_json,
            "error_code": response.error_code,
            "error_message": response.error_message,
        }

    def list_reporting_artifacts(
        self,
        *,
        run_id: str | None = None,
        artifact_group_id: str | None = None,
        format_name: str | None = None,
    ) -> dict[str, Any]:
        if not self._list_reporting_artifacts.service_is_ready():
            return {
                "available": False,
                "entries": [],
                "error_code": "REPORT_INDEX_UNAVAILABLE",
                "error_message": "/reporting/list_reporting_artifacts is unavailable.",
            }
        request = ListReportingArtifacts.Request()
        request.schema_version = 1
        request.run_id = run_id or ""
        request.artifact_group_id = artifact_group_id or ""
        request.format = format_name or ""
        response = self._wait_for_service_future(
            self._list_reporting_artifacts.call_async(request), 2.0
        )
        if response is None or not response.available:
            return {
                "available": False,
                "entries": [],
                "error_code": getattr(response, "error_code", None)
                or "REPORT_INDEX_UNAVAILABLE",
                "error_message": getattr(response, "error_message", None)
                or "Reporting artifact index is unavailable.",
            }
        entries: list[dict[str, Any]] = []
        try:
            for raw in response.entries_json:
                entry = json.loads(raw)
                if not isinstance(entry, dict):
                    raise ValueError("entry must be an object")
                for field in (
                    "evidence_id", "run_id", "context_revision", "evidence_revision",
                    "media_type", "content_sha256", "size_bytes", "metadata",
                ):
                    if field not in entry:
                        raise ValueError(f"entry missing {field}")
                entries.append(entry)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {
                "available": False,
                "entries": [],
                "error_code": "REPORT_INDEX_INVALID",
                "error_message": "Reporting artifact index returned invalid data.",
            }
        return {"available": True, "entries": entries, "error_code": "", "error_message": ""}

    def dispatch_emergency_stop(
        self, *, command_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if not self._emergency_stop.service_is_ready():
            return {
                "accepted": False,
                "error_code": "EMERGENCY_STOP_PATH_UNAVAILABLE",
                "error_message": "/mission/emergency_stop is unavailable.",
            }
        request = EmergencyStop.Request()
        request.schema_version = 1
        request.command_id = command_id
        request.reason = str(payload.get("reason") or "")
        response = self._wait_for_service_future(
            self._emergency_stop.call_async(request), 2.0
        )
        if response is None:
            return {
                "accepted": False,
                "error_code": "EMERGENCY_STOP_PATH_UNAVAILABLE",
                "error_message": "/mission/emergency_stop timed out.",
            }
        return {
            "accepted": bool(response.accepted),
            "latched": bool(response.latched),
            "latch_revision": int(response.latch_revision),
            "state_revision": int(response.state_revision),
            "error_code": response.error_code,
            "error_message": response.error_message,
        }

    def dispatch_robot_mode(
        self, *, command_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if not self._set_robot_mode.service_is_ready():
            return {
                "accepted": False,
                "error_code": "ROBOT_STATE_UNAVAILABLE",
                "error_message": "/mission/set_robot_mode is unavailable.",
            }
        request = SetRobotMode.Request()
        request.schema_version = 1
        request.command_id = command_id
        request.mission_id = str(payload.get("mission_id") or "")
        request.target_mode = (
            SetRobotMode.Request.MODE_MANUAL
            if payload.get("target_mode") == "manual"
            else SetRobotMode.Request.MODE_AUTONOMOUS
        )
        request.observed_state_revision = int(payload["observed_state_revision"])
        request.observed_latch_revision = int(payload["observed_latch_revision"])
        request.reason = str(payload.get("reason") or "")
        response = self._wait_for_service_future(
            self._set_robot_mode.call_async(request), 2.0
        )
        if response is None:
            return {
                "accepted": False,
                "error_code": "ROBOT_STATE_UNAVAILABLE",
                "error_message": "/mission/set_robot_mode timed out.",
            }
        return {
            "accepted": bool(response.accepted),
            "robot_mode": int(response.robot_mode),
            "state_revision": int(response.state_revision),
            "latch_revision": int(response.latch_revision),
            "error_code": response.error_code,
            "error_message": response.error_message,
        }

    def dispatch_emergency_reset(
        self, *, command_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if not self._emergency_reset.service_is_ready():
            return {
                "accepted": False,
                "error_code": "EMERGENCY_STOP_PATH_UNAVAILABLE",
                "error_message": "/mission/emergency_stop_reset is unavailable.",
            }
        request = ResetEmergencyStop.Request()
        request.schema_version = 1
        request.command_id = command_id
        request.observed_latch_revision = int(payload["observed_latch_revision"])
        request.confirm = bool(payload.get("confirm"))
        request.reason = str(payload.get("reason") or "")
        response = self._wait_for_service_future(
            self._emergency_reset.call_async(request), 2.0
        )
        if response is None:
            return {
                "accepted": False,
                "error_code": "EMERGENCY_STOP_PATH_UNAVAILABLE",
                "error_message": "/mission/emergency_stop_reset timed out.",
            }
        return {
            "accepted": bool(response.accepted),
            "latched": bool(response.latched),
            "latch_revision": int(response.latch_revision),
            "state_revision": int(response.state_revision),
            "error_code": response.error_code,
            "error_message": response.error_message,
        }

    def dispatch_manual_velocity(
        self, *, command_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        robot = self.projector.state.robot
        if robot is None or bool(robot.get("stale", True)):
            return {
                "accepted": False,
                "error_code": "ROBOT_STATE_UNAVAILABLE",
                "error_message": "A fresh validated robot pose is required.",
            }
        context = self.projector._context
        if (
            context is None
            or context.lifecycle != RunContext.LIFECYCLE_ACTIVE
            or context.run_id != self.projector.state.run_id
        ):
            return {
                "accepted": False,
                "error_code": "RUN_CONTEXT_MISMATCH",
                "error_message": "An ACTIVE RunContext is required.",
            }
        if self.projector._robot_mode != InspectionTaskArray.MODE_MANUAL:
            return {
                "accepted": False,
                "error_code": "MANUAL_MODE_REQUIRED",
                "error_message": "Manual robot mode is required.",
            }
        if self.projector._emergency_stop_latched:
            return {
                "accepted": False,
                "error_code": "EMERGENCY_STOP_LATCHED",
                "error_message": "Emergency stop is latched.",
            }
        message = ManualVelocityCommand()
        message.schema_version = 1
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = "base_link"
        message.command_id = command_id
        message.run_id = context.run_id
        message.context_revision = context.context_revision
        message.twist.linear.x = float(payload["linear_x_m_s"])
        message.twist.angular.z = float(payload["angular_z_rad_s"])
        message.duration_s = float(payload["duration_s"])
        self._manual_command_context[command_id] = (
            context.run_id,
            int(context.context_revision),
        )
        self._manual_velocity.publish(message)
        return {"accepted": True, "error_code": "", "error_message": ""}

    def dispatch_scenario(
        self, *, command_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if not self._set_scenario_parameters.service_is_ready():
            return {
                "accepted": False,
                "error_code": "GAZEBO_UNAVAILABLE",
                "error_message": "/scenario_manager/set_parameters_atomically is unavailable.",
            }
        action = payload.get("action")
        scenario_id = payload.get("scenario_id")
        parameters = payload.get("parameters")
        reason = payload.get("reason")
        if action not in {"start", "trigger", "reset"}:
            return {
                "accepted": False,
                "error_code": "SCENARIO_ACTION_INVALID",
                "error_message": "action must be start, trigger, or reset.",
            }
        if not isinstance(scenario_id, str) or not scenario_id or not isinstance(parameters, dict):
            return {
                "accepted": False,
                "error_code": "SCENARIO_PARAMETER_INVALID",
                "error_message": "scenario_id and parameters are required.",
            }
        if not isinstance(reason, str) or not reason.strip():
            return {
                "accepted": False,
                "error_code": "VALIDATION_FAILED",
                "error_message": "reason is required.",
            }
        if any(
            not isinstance(key, str)
            or not isinstance(value, (str, int, float, bool))
            or isinstance(value, (dict, list))
            for key, value in parameters.items()
        ):
            return {
                "accepted": False,
                "error_code": "SCENARIO_PARAMETER_INVALID",
                "error_message": "Scenario parameters must be scalar values.",
            }
        baseline_revision = int(
            self.projector.state.scenario.get("scenario_revision", "0")
        )
        request = SetParametersAtomically.Request()
        request.parameters = [
            Parameter("command_id", value=command_id).to_parameter_msg(),
            Parameter("scenario_id", value=scenario_id).to_parameter_msg(),
            Parameter("scenario_action", value=action).to_parameter_msg(),
            Parameter(
                "scenario_parameters_json",
                value=json.dumps(parameters, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            ).to_parameter_msg(),
        ]
        response = self._wait_for_service_future(
            self._set_scenario_parameters.call_async(request), 3.0
        )
        if response is None:
            return {
                "accepted": False,
                "error_code": "GAZEBO_UNAVAILABLE",
                "error_message": "Scenario parameter service timed out.",
            }
        if not response.result.successful:
            code = response.result.reason or "SCENARIO_CONFLICT"
            return {"accepted": False, "error_code": code, "error_message": code}
        return {
            "accepted": True,
            "scenario_revision": baseline_revision,
            "error_code": "",
            "error_message": "",
        }

    def read_evidence_range(self, evidence_id: str, offset: int, length: int) -> bytes:
        if not self._read_evidence.service_is_ready():
            raise RuntimeError("/reporting/read_evidence_chunk is unavailable")
        remaining = length
        cursor = offset
        chunks: list[bytes] = []
        expected_digest: str | None = None
        while remaining:
            request = ReadEvidenceChunk.Request()
            request.schema_version = 1
            request.evidence_id = evidence_id
            request.offset_bytes = cursor
            request.max_bytes = min(remaining, 1024 * 1024)
            response = self._wait_for_service_future(self._read_evidence.call_async(request), 2.0)
            if response is None or not response.found or response.error_code:
                raise RuntimeError("evidence chunk read failed")
            if expected_digest is None:
                expected_digest = response.content_sha256
            elif response.content_sha256 != expected_digest:
                raise RuntimeError("evidence digest changed between chunks")
            chunk = bytes(response.content)
            if not chunk or len(chunk) > remaining:
                raise RuntimeError("invalid evidence chunk length")
            chunks.append(chunk)
            cursor += len(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def dispatch_mission(
        self,
        *,
        command_id: str,
        action: str,
        payload: dict[str, Any],
        timeout_s: float = 2.0,
    ) -> dict[str, Any]:
        if not self._manage_mission.service_is_ready():
            return {
                "accepted": False,
                "error_code": "DEPENDENCY_UNAVAILABLE",
                "error_message": "/mission/manage is unavailable.",
            }
        actions = {
            "start": ManageMission.Request.ACTION_START,
            "pause": ManageMission.Request.ACTION_PAUSE,
            "resume": ManageMission.Request.ACTION_RESUME,
            "stop": ManageMission.Request.ACTION_STOP,
            "return-home": ManageMission.Request.ACTION_RETURN_HOME,
        }
        if action not in actions:
            return {
                "accepted": False,
                "error_code": "VALIDATION_FAILED",
                "error_message": "Unsupported mission action.",
            }
        request = ManageMission.Request()
        request.schema_version = 1
        request.command_id = command_id
        request.mission_id = str(payload.get("mission_id") or "")
        request.action = actions[action]
        request.route_id = str(payload.get("route_id") or "")
        request.reason = str(payload.get("reason") or "")
        event = threading.Event()
        result: dict[str, Any] = {}

        def completed(future) -> None:
            try:
                response = future.result()
                result.update(
                    accepted=bool(response.accepted),
                    run_id=response.run_id,
                    mission_id=response.mission_id,
                    run_context_revision=int(response.run_context_revision),
                    state_revision=int(response.state_revision),
                    queue_revision=int(response.queue_revision),
                    error_code=response.error_code,
                    error_message=response.error_message,
                )
            except Exception:
                result.update(
                    accepted=False,
                    error_code="DEPENDENCY_UNAVAILABLE",
                    error_message="/mission/manage call failed.",
                )
            finally:
                event.set()

        self._manage_mission.call_async(request).add_done_callback(completed)
        if not event.wait(timeout_s):
            return {
                "accepted": False,
                "error_code": "DEPENDENCY_UNAVAILABLE",
                "error_message": "/mission/manage timed out.",
            }
        return result

    def _on_context(self, message: RunContext) -> None:
        if not self.projector.on_run_context(message):
            return
        if message.lifecycle == RunContext.LIFECYCLE_STARTING:
            self._mapping_creation_runs.add(message.run_id)
            return
        if message.run_id and message.lifecycle != RunContext.LIFECYCLE_IDLE:
            self._ensure_time_mapping(message)
        if message.lifecycle in (
            RunContext.LIFECYCLE_IDLE,
            RunContext.LIFECYCLE_ENDED,
        ):
            self._mapping_creation_runs.discard(message.run_id)

    def _on_odom(self, message: Odometry) -> None:
        if message.header.frame_id != "odom" or message.child_frame_id != "base_footprint":
            return
        try:
            transform = self._tf_buffer.lookup_transform(
                "map", "odom", Time.from_msg(message.header.stamp)
            )
        except TransformException:
            return
        self.projector.on_odom(message, transform)

    def _on_manual_velocity_status(self, message: ManualVelocityStatus) -> None:
        if (
            message.schema_version != ManualVelocityStatus.SCHEMA_VERSION
            or message.header.frame_id != "base_link"
            or not message.command_id
            or int(message.state) > ManualVelocityStatus.STATE_CANCELLED
        ):
            return
        command_context = self._manual_command_context.get(message.command_id)
        if command_context is None or self._manual_command_observer is None:
            return
        run_id, context_revision = command_context
        applied_at = None
        if message.state == ManualVelocityStatus.STATE_APPLIED:
            applied_at = self.projector.ros_time_to_utc(
                message.header.stamp.sec, message.header.stamp.nanosec
            )
        self._manual_command_observer(
            message, run_id, context_revision, applied_at
        )
        if message.state != ManualVelocityStatus.STATE_ACCEPTED:
            self._manual_command_context.pop(message.command_id, None)

    def _ensure_time_mapping(self, message: RunContext) -> None:
        if self._mapping_query_inflight or not self._query_mapping.service_is_ready():
            return
        request = QueryRunTimeMapping.Request()
        request.schema_version = 1
        request.run_id = message.run_id
        self._mapping_query_inflight = True
        future = self._query_mapping.call_async(request)
        future.add_done_callback(lambda completed, context=message: self._mapping_query_done(completed, context))

    def _mapping_query_done(self, future, context: RunContext) -> None:
        self._mapping_query_inflight = False
        try:
            response = future.result()
        except Exception:
            return
        if response.found:
            self._mapping_creation_runs.discard(context.run_id)
            self.projector.set_time_mapping(
                run_id=context.run_id,
                context_revision=response.context_revision,
                anchor_ros_sec=response.anchor_ros_sec,
                anchor_ros_nanosec=response.anchor_ros_nanosec,
                anchor_utc=response.anchor_utc,
            )
            return
        if (
            response.error_code != "TIME_MAPPING_UNAVAILABLE"
            or context.run_id not in self._mapping_creation_runs
            or self._mapping_record_inflight
            or not self._record_mapping.service_is_ready()
        ):
            return
        request = RecordRunTimeMapping.Request()
        request.schema_version = 1
        request.run_id = context.run_id
        request.context_revision = context.context_revision
        request.anchor_ros_sec = context.header.stamp.sec
        request.anchor_ros_nanosec = context.header.stamp.nanosec
        request.anchor_utc = _utc_now()
        self._pending_mapping = {
            "run_id": request.run_id,
            "context_revision": request.context_revision,
            "anchor_ros_sec": request.anchor_ros_sec,
            "anchor_ros_nanosec": request.anchor_ros_nanosec,
            "anchor_utc": request.anchor_utc,
        }
        self._mapping_record_inflight = True
        future = self._record_mapping.call_async(request)
        future.add_done_callback(self._mapping_record_done)

    def _mapping_record_done(self, future) -> None:
        self._mapping_record_inflight = False
        pending, self._pending_mapping = self._pending_mapping, None
        try:
            response = future.result()
        except Exception:
            return
        if response.accepted and pending is not None:
            self._mapping_creation_runs.discard(pending["run_id"])
            self.projector.set_time_mapping(**pending)

    def _poll(self) -> None:
        topics = {name for name, _types in self.get_topic_names_and_types()}
        nodes = set(self.get_node_names())
        self.projector.set_ros_graph_ready(
            ros=True,
            gazebo="/camera/image_raw" in topics or "/scan" in topics,
            nav2=bool(nodes & {"bt_navigator", "controller_server", "planner_server"})
            or "/navigate_to_pose/_action/status" in topics,
        )
        now = self.get_clock().now().to_msg()
        self.projector.update_robot_staleness(now.sec, now.nanosec)
        context = self.projector._context
        if context is not None and context.run_id and context.lifecycle != RunContext.LIFECYCLE_IDLE:
            self._ensure_time_mapping(context)
        if self._readiness_inflight or not self._reporting_readiness.service_is_ready():
            self.projector.set_reporting_readiness(
                evidence_store_writable=False,
                report_generator_ready=False,
                time_mapping_ready=False,
            )
            return
        request = GetReportingReadiness.Request()
        request.schema_version = 1
        self._readiness_inflight = True
        future = self._reporting_readiness.call_async(request)
        future.add_done_callback(self._readiness_done)

    def _readiness_done(self, future) -> None:
        self._readiness_inflight = False
        try:
            response = future.result()
        except Exception:
            self.projector.set_reporting_readiness(
                evidence_store_writable=False,
                report_generator_ready=False,
                time_mapping_ready=False,
            )
            return
        self.projector.set_reporting_readiness(
            evidence_store_writable=response.evidence_store_writable,
            report_generator_ready=response.report_generator_ready,
            time_mapping_ready=response.time_mapping_ready,
        )


class RosGatewayAdapter:
    """Own an rclpy executor thread for the FastAPI process lifespan."""

    def __init__(self, state: GatewayState) -> None:
        self._state = state
        self._context = rclpy.context.Context()
        self._node: RosGatewayNode | None = None
        self._executor: MultiThreadedExecutor | None = None
        self._thread: threading.Thread | None = None
        self._command_store = None
        self._terminal_observations: dict[str, tuple[Any, ...]] = {}

    def attach_command_store(self, store) -> None:
        self._command_store = store

    def _observe_mission_command(
        self, command_id: str, mission: dict[str, Any], run_id: str | None
    ) -> None:
        if self._command_store is None:
            return
        if self._command_store.complete_from_mission(command_id, mission, run_id):
            self._terminal_observations.pop(command_id, None)
        elif self._command_store.get(command_id) is None:
            self._terminal_observations[command_id] = ("mission", mission, run_id)

    def _observe_manual_command(
        self,
        message: ManualVelocityStatus,
        run_id: str | None,
        context_revision: int,
        applied_at: str | None,
    ) -> None:
        if self._command_store is None:
            return
        if self._command_store.complete_from_manual_velocity(
            message,
            run_id=run_id,
            context_revision=context_revision,
            applied_at=applied_at,
        ):
            if message.state != ManualVelocityStatus.STATE_ACCEPTED:
                self._terminal_observations.pop(message.command_id, None)
        elif self._command_store.get(message.command_id) is None:
            self._terminal_observations[message.command_id] = (
                "manual", message, run_id, context_revision, applied_at
            )

    def _observe_scenario_command(
        self,
        command_id: str,
        scenario: dict[str, Any],
        run_id: str | None,
    ) -> None:
        if self._command_store is None:
            return
        if self._command_store.complete_from_scenario(command_id, scenario, run_id):
            self._terminal_observations.pop(command_id, None)
        elif self._command_store.get(command_id) is None:
            self._terminal_observations[command_id] = (
                "scenario", scenario, run_id
            )

    def replay_terminal(self, command_id: str) -> None:
        observation = self._terminal_observations.get(command_id)
        if observation is None:
            return
        if observation[0] == "mission":
            _, mission, run_id = observation
            self._observe_mission_command(command_id, mission, run_id)
        elif observation[0] == "manual":
            _, message, run_id, context_revision, applied_at = observation
            self._observe_manual_command(
                message, run_id, context_revision, applied_at
            )
        else:
            _, scenario, run_id = observation
            self._observe_scenario_command(command_id, scenario, run_id)

    def start(self) -> None:
        if self._thread is not None:
            return
        rclpy.init(context=self._context)
        self._node = RosGatewayNode(
            self._state,
            context=self._context,
            command_observer=self._observe_mission_command,
            manual_command_observer=self._observe_manual_command,
            scenario_command_observer=self._observe_scenario_command,
        )
        self._executor = MultiThreadedExecutor(num_threads=2, context=self._context)
        self._executor.add_node(self._node)
        self._thread = threading.Thread(target=self._executor.spin, name="gateway-rclpy", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread is None:
            return
        assert self._executor is not None and self._node is not None
        self._executor.shutdown(timeout_sec=5.0)
        self._node.destroy_node()
        self._context.shutdown()
        self._thread.join(timeout=5.0)
        self._thread = None
        self._executor = None
        self._node = None

    def dispatch_mission(
        self, *, command_id: str, action: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if self._node is None:
            return {
                "accepted": False,
                "error_code": "DEPENDENCY_UNAVAILABLE",
                "error_message": "Gateway ROS adapter is not running.",
            }
        return self._node.dispatch_mission(
            command_id=command_id,
            action=action,
            payload=payload,
        )

    def query_evidence(self, evidence_id: str) -> dict[str, Any]:
        if self._node is None:
            return {
                "found": False,
                "error_code": "EVIDENCE_STORAGE_UNAVAILABLE",
                "error_message": "Gateway ROS adapter is not running.",
            }
        return self._node.query_evidence(evidence_id)

    def list_reporting_artifacts(
        self,
        *,
        run_id: str | None = None,
        artifact_group_id: str | None = None,
        format_name: str | None = None,
    ) -> dict[str, Any]:
        if self._node is None:
            return {
                "available": False,
                "entries": [],
                "error_code": "REPORT_INDEX_UNAVAILABLE",
                "error_message": "Gateway ROS adapter is not running.",
            }
        return self._node.list_reporting_artifacts(
            run_id=run_id,
            artifact_group_id=artifact_group_id,
            format_name=format_name,
        )

    def dispatch_emergency_stop(
        self, *, command_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if self._node is None:
            return {
                "accepted": False,
                "error_code": "EMERGENCY_STOP_PATH_UNAVAILABLE",
                "error_message": "Gateway ROS adapter is not running.",
            }
        return self._node.dispatch_emergency_stop(
            command_id=command_id, payload=payload
        )

    def dispatch_robot_mode(
        self, *, command_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if self._node is None:
            return {
                "accepted": False,
                "error_code": "ROBOT_STATE_UNAVAILABLE",
                "error_message": "Gateway ROS adapter is not running.",
            }
        return self._node.dispatch_robot_mode(command_id=command_id, payload=payload)

    def dispatch_emergency_reset(
        self, *, command_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if self._node is None:
            return {
                "accepted": False,
                "error_code": "EMERGENCY_STOP_PATH_UNAVAILABLE",
                "error_message": "Gateway ROS adapter is not running.",
            }
        return self._node.dispatch_emergency_reset(command_id=command_id, payload=payload)

    def dispatch_manual_velocity(
        self, *, command_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if self._node is None:
            return {
                "accepted": False,
                "error_code": "ROBOT_STATE_UNAVAILABLE",
                "error_message": "Gateway ROS adapter is not running.",
            }
        return self._node.dispatch_manual_velocity(command_id=command_id, payload=payload)

    def dispatch_scenario(
        self, *, command_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if self._node is None:
            return {
                "accepted": False,
                "error_code": "GAZEBO_UNAVAILABLE",
                "error_message": "Gateway ROS adapter is not running.",
            }
        return self._node.dispatch_scenario(command_id=command_id, payload=payload)

    def read_evidence_range(self, evidence_id: str, offset: int, length: int) -> bytes:
        if self._node is None:
            raise RuntimeError("Gateway ROS adapter is not running")
        return self._node.read_evidence_range(evidence_id, offset, length)
