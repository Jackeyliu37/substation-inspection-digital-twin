#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import time
from uuid import uuid4

from action_msgs.msg import GoalStatus
from diagnostic_msgs.msg import DiagnosticArray
from lifecycle_msgs.msg import State
from lifecycle_msgs.srv import GetState
from nav2_msgs.action import NavigateToPose
from nav2_msgs.msg import Costmap
from nav_msgs.msg import OccupancyGrid
import rclpy
from rcl_interfaces.msg import Parameter, ParameterType, ParameterValue
from rcl_interfaces.srv import SetParametersAtomically
from rclpy.action import ActionClient
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from tf2_ros import Buffer, TransformException, TransformListener

from substation_gazebo.inspection_poses import load_inspection_poses, pose_stamped


DYNAMIC_OBSTACLE_X = 1.5
DYNAMIC_OBSTACLE_Y = 0.0
DYNAMIC_OBSTACLE_SEARCH_RADIUS_M = 0.5


def qos(depth: int, transient: bool = False) -> QoSProfile:
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=depth,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=(
            DurabilityPolicy.TRANSIENT_LOCAL
            if transient
            else DurabilityPolicy.VOLATILE
        ),
    )


def diagnostic_values(message: DiagnosticArray) -> dict[str, str]:
    if len(message.status) != 1:
        return {}
    result = {item.key: item.value for item in message.status[0].values}
    result["name"] = message.status[0].name
    return result


class Phase3NavigationProbe(Node):
    def __init__(self, run_id: str, devices_path: Path, map_path: Path) -> None:
        super().__init__("phase3_navigation_probe")
        self.run_id = run_id
        self.poses = load_inspection_poses(devices_path, map_path)
        self.map_message: OccupancyGrid | None = None
        self.costmap_message: Costmap | None = None
        self.costmap_count = 0
        self.scenario_states: list[dict[str, str]] = []
        self.feedback_count = 0
        self.active_asset_id: str | None = None
        self.dynamic_obstacle_active = False
        self.dynamic_obstacle_seen = False
        self.nav2_active = False
        self.tf_buffer = Buffer(cache_time=Duration(seconds=30.0))
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.navigation = ActionClient(self, NavigateToPose, "/navigate_to_pose")
        self.scenario_client = self.create_client(
            SetParametersAtomically, "/scenario_manager/set_parameters_atomically"
        )
        self.nav2_state_client = self.create_client(
            GetState, "/bt_navigator/get_state"
        )
        self.create_subscription(
            OccupancyGrid, "/map", self.on_map, qos(1, transient=True)
        )
        self.create_subscription(
            Costmap, "/local_costmap/costmap_raw", self.on_costmap, qos(5)
        )
        self.create_subscription(
            DiagnosticArray,
            "/simulation/scenario_state",
            self.on_scenario_state,
            qos(1, transient=True),
        )

    def on_map(self, message: OccupancyGrid) -> None:
        self.map_message = message

    def on_costmap(self, message: Costmap) -> None:
        self.costmap_message = message
        self.costmap_count += 1
        if self.dynamic_obstacle_active and self.obstacle_cell_is_lethal(message):
            self.dynamic_obstacle_seen = True

    def on_scenario_state(self, message: DiagnosticArray) -> None:
        values = diagnostic_values(message)
        if values:
            self.scenario_states.append(values)

    def spin_until(self, predicate, timeout: float, label: str) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if predicate():
                return
        raise RuntimeError(f"timeout waiting for {label}")

    def tf_ready(self) -> bool:
        return self.tf_buffer.can_transform("map", "odom", Time())

    def baseline_ready(self) -> bool:
        return (
            self.map_message is not None
            and self.map_message.header.frame_id == "map"
            and math.isclose(
                self.map_message.info.resolution, 0.05, rel_tol=0.0, abs_tol=1e-6
            )
            and self.costmap_message is not None
            and self.costmap_count >= 2
            and self.tf_ready()
            and self.nav2_active
        )

    def baseline_state(self) -> dict[str, object]:
        return {
            "map_received": self.map_message is not None,
            "map_frame": (
                None if self.map_message is None else self.map_message.header.frame_id
            ),
            "map_resolution": (
                None if self.map_message is None else self.map_message.info.resolution
            ),
            "costmap_messages": self.costmap_count,
            "map_to_odom": self.tf_ready(),
            "navigate_to_pose_ready": self.navigation.server_is_ready(),
            "bt_navigator_active": self.nav2_active,
        }

    def wait_for_nav2_active(self, timeout: float) -> None:
        if not self.nav2_state_client.wait_for_service(timeout_sec=timeout):
            raise RuntimeError("bt_navigator lifecycle service unavailable")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            future = self.nav2_state_client.call_async(GetState.Request())
            self.spin_until(future.done, 5.0, "bt_navigator lifecycle response")
            response = future.result()
            if (
                response is not None
                and response.current_state.id == State.PRIMARY_STATE_ACTIVE
            ):
                self.nav2_active = True
                return
            rclpy.spin_once(self, timeout_sec=0.1)
        raise RuntimeError("timeout waiting for bt_navigator active")

    @staticmethod
    def string_parameter(name: str, value: str) -> Parameter:
        return Parameter(
            name=name,
            value=ParameterValue(
                type=ParameterType.PARAMETER_STRING, string_value=value
            ),
        )

    def apply_scenario(
        self, command_id: str, scenario_id: str, action: str, parameters_json: str
    ) -> None:
        if not self.scenario_client.wait_for_service(timeout_sec=10.0):
            raise RuntimeError("scenario parameter service unavailable")
        request = SetParametersAtomically.Request(
            parameters=[
                self.string_parameter("command_id", command_id),
                self.string_parameter("scenario_id", scenario_id),
                self.string_parameter("scenario_action", action),
                self.string_parameter("scenario_parameters_json", parameters_json),
            ]
        )
        future = self.scenario_client.call_async(request)
        self.spin_until(future.done, 10.0, f"scenario response {command_id}")
        response = future.result()
        if response is None or not response.result.successful:
            reason = "no response" if response is None else response.result.reason
            raise RuntimeError(f"scenario command rejected: {reason}")

    def scenario_applied(self, command_id: str) -> bool:
        return any(
            state.get("command_id") == command_id
            and state.get("status") == "applied"
            for state in self.scenario_states
        )

    def on_navigation_feedback(self, message) -> None:
        self.feedback_count += 1
        if self.feedback_count % 20 != 0:
            return
        feedback = message.feedback
        position = feedback.current_pose.pose.position
        print(
            json.dumps(
                {
                    "event": "navigation-feedback",
                    "asset_id": self.active_asset_id,
                    "x": position.x,
                    "y": position.y,
                    "distance_remaining": feedback.distance_remaining,
                    "number_of_recoveries": feedback.number_of_recoveries,
                },
                sort_keys=True,
            ),
            flush=True,
        )

    def navigate(self, asset_id: str, timeout: float) -> dict[str, object]:
        self.active_asset_id = asset_id
        now = self.get_clock().now().to_msg()
        goal = NavigateToPose.Goal()
        goal.pose = pose_stamped(
            asset_id,
            self.poses,
            stamp_sec=now.sec,
            stamp_nanosec=now.nanosec,
        )
        send_future = self.navigation.send_goal_async(
            goal, feedback_callback=self.on_navigation_feedback
        )
        self.spin_until(send_future.done, 10.0, f"goal acceptance {asset_id}")
        handle = send_future.result()
        if handle is None or not handle.accepted:
            raise RuntimeError(f"navigation goal rejected: {asset_id}")
        result_future = handle.get_result_async()
        self.spin_until(result_future.done, timeout, f"navigation result {asset_id}")
        wrapped = result_future.result()
        if (
            wrapped is None
            or wrapped.status != GoalStatus.STATUS_SUCCEEDED
            or wrapped.result.error_code != NavigateToPose.Result.NONE
        ):
            status = None if wrapped is None else wrapped.status
            code = None if wrapped is None else wrapped.result.error_code
            message = None if wrapped is None else wrapped.result.error_msg
            raise RuntimeError(
                f"navigation failed: asset={asset_id} status={status} "
                f"code={code} message={message}"
            )
        pose = self.poses[asset_id]
        return {"asset_id": asset_id, "x": pose.x, "y": pose.y, "yaw": pose.yaw}

    @staticmethod
    def transform_xy(transform, x: float, y: float) -> tuple[float, float]:
        translation = transform.transform.translation
        rotation = transform.transform.rotation
        yaw = math.atan2(
            2.0 * (rotation.w * rotation.z + rotation.x * rotation.y),
            1.0 - 2.0 * (rotation.y * rotation.y + rotation.z * rotation.z),
        )
        return (
            translation.x + math.cos(yaw) * x - math.sin(yaw) * y,
            translation.y + math.sin(yaw) * x + math.cos(yaw) * y,
        )

    def obstacle_cell_is_lethal(self, message: Costmap) -> bool:
        try:
            transform = self.tf_buffer.lookup_transform(
                message.header.frame_id, "map", Time()
            )
        except TransformException:
            return False
        x, y = self.transform_xy(
            transform, DYNAMIC_OBSTACLE_X, DYNAMIC_OBSTACLE_Y
        )
        metadata = message.metadata
        column = int((x - metadata.origin.position.x) / metadata.resolution)
        row = int((y - metadata.origin.position.y) / metadata.resolution)
        if not (0 <= column < metadata.size_x and 0 <= row < metadata.size_y):
            return False
        search_radius = math.ceil(
            DYNAMIC_OBSTACLE_SEARCH_RADIUS_M / metadata.resolution
        )
        for nearby_row in range(
            max(0, row - search_radius),
            min(metadata.size_y, row + search_radius + 1),
        ):
            for nearby_column in range(
                max(0, column - search_radius),
                min(metadata.size_x, column + search_radius + 1),
            ):
                index = nearby_row * metadata.size_x + nearby_column
                if message.data[index] >= 254:
                    return True
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--devices", type=Path, required=True)
    parser.add_argument("--map", dest="map_path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rclpy.init()
    node = Phase3NavigationProbe(args.run_id, args.devices, args.map_path)
    try:
        if not node.navigation.wait_for_server(timeout_sec=120.0):
            raise RuntimeError("NavigateToPose action server unavailable")
        node.wait_for_nav2_active(120.0)
        try:
            node.spin_until(node.baseline_ready, 120.0, "map, TF, costmap and Nav2")
        except RuntimeError:
            print(json.dumps({"baseline_state": node.baseline_state()}, sort_keys=True))
            raise
        static_goal = node.navigate("potential-transformer-01", 120.0)

        dynamic_id = str(uuid4())
        dynamic_parameters = (
            '{"asset_id":"transformer-01","gas_ppm":180.0,'
            '"obstacle_progress_0_1":0.5,"smoke_0_1":0.7,'
            '"temperature_celsius":90.0}'
        )
        node.apply_scenario(
            dynamic_id,
            "combined-risk-obstacle",
            "trigger",
            dynamic_parameters,
        )
        node.spin_until(
            lambda: node.scenario_applied(dynamic_id),
            15.0,
            "combined-risk-obstacle applied",
        )
        node.dynamic_obstacle_active = True
        dynamic_goal = node.navigate("current-transformer-01", 120.0)
        node.spin_until(
            lambda: node.dynamic_obstacle_seen,
            15.0,
            "scenario_dynamic_obstacle in local costmap",
        )

        reset_id = str(uuid4())
        node.apply_scenario(reset_id, "combined-risk-obstacle", "reset", "{}")
        node.spin_until(
            lambda: node.scenario_applied(reset_id),
            15.0,
            "combined-risk-obstacle reset",
        )
        result = {
            "status": "passed",
            "run_id": args.run_id,
            "map_frame": node.map_message.header.frame_id,
            "map_resolution": node.map_message.info.resolution,
            "map_to_odom": node.tf_ready(),
            "feedback_count": node.feedback_count,
            "static_goal": static_goal,
            "dynamic_goal": dynamic_goal,
            "dynamic_scenario": "combined-risk-obstacle",
            "dynamic_model": "scenario_dynamic_obstacle",
            "dynamic_obstacle_costmap_seen": node.dynamic_obstacle_seen,
            "local_costmap_messages": node.costmap_count,
        }
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.replace(args.output)
        print("phase3-navigation-probe: PASS", flush=True)
        return 0
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
