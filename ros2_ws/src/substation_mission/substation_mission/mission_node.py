from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import time
import uuid

from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import Twist
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from substation_description.asset_registry import load_asset_registry
from substation_interfaces.msg import AssetRiskArray, InspectionTask as InspectionTaskMessage
from substation_interfaces.msg import InspectionTaskArray, RunContext
from substation_interfaces.srv import EmergencyStop, ResetEmergencyStop

from .mission_engine import InspectionTask, MissionEngine, MissionPolicy, load_mission_policy


@dataclass(frozen=True)
class AssetGoal:
    asset_id: str
    x: float
    y: float
    yaw: float


class MissionRuntime:
    def __init__(
        self,
        policy: MissionPolicy,
        run_id: str,
        mission_id: str,
        goals: tuple[AssetGoal, ...],
    ) -> None:
        self.engine = MissionEngine(policy)
        self.engine.start(run_id=run_id, mission_id=mission_id, route_id="default-route")
        self.goals = {goal.asset_id: goal for goal in goals}
        self.engine.replace_tasks(tuple(
            InspectionTask(
                task_id=str(uuid.uuid4()),
                asset_id=goal.asset_id,
                base_priority=10,
                path_length_m=math.hypot(goal.x, goal.y),
            )
            for goal in goals
        ))
        self.state_revision = 1
        self.queue_revision = 1

    def apply_risks(self, risks: AssetRiskArray, *, monotonic_s: float) -> bool:
        if risks.run_id != self.engine.run_id:
            return False
        changed = self.engine.apply_risk(
            {item.asset_id: float(item.score_0_100) for item in risks.assets},
            monotonic_s=monotonic_s,
        )
        if changed:
            self.state_revision += 1
            self.queue_revision += 1
        return changed

    def snapshot(self) -> InspectionTaskArray:
        output = InspectionTaskArray()
        output.schema_version = 1
        output.run_id = self.engine.run_id
        output.mission_id = self.engine.mission_id
        output.route_id = self.engine.route_id
        output.state_revision = self.state_revision
        output.queue_revision = self.queue_revision
        output.mission_state = InspectionTaskArray.MISSION_RUNNING
        output.robot_mode = int(self.engine.robot_mode)
        output.emergency_stop_latched = self.engine.emergency_stop_latched
        output.emergency_stop_latch_revision = self.engine.latch_revision
        output.transition_reason_code = "RISK_REPLAN" if self.state_revision > 1 else "MISSION_STARTED"
        output.total_tasks = len(self.engine.tasks)
        for task in self.engine.tasks:
            message = InspectionTaskMessage()
            message.schema_version = 1
            message.task_id = task.task_id
            message.mission_id = self.engine.mission_id
            message.asset_id = task.asset_id
            message.task_type = InspectionTaskMessage.TYPE_INSPECT_ASSET
            message.state = InspectionTaskMessage.STATE_QUEUED
            message.base_priority = task.base_priority
            message.risk_score_0_100 = task.risk_score_0_100
            message.risk_gain = self.engine.policy.risk_gain
            message.path_length_m = task.path_length_m
            message.distance_penalty = self.engine.policy.distance_penalty
            message.computed_priority = task.computed_priority
            message.safety_standoff_m = task.safety_standoff_m
            goal = self.goals.get(task.asset_id)
            if goal is not None:
                message.goal.header.frame_id = "map"
                message.goal.pose.position.x = goal.x
                message.goal.pose.position.y = goal.y
                message.goal.pose.orientation.z = math.sin(goal.yaw / 2.0)
                message.goal.pose.orientation.w = math.cos(goal.yaw / 2.0)
            output.tasks.append(message)
        return output


class TaskManagerNode(Node):
    def __init__(self) -> None:
        super().__init__("task_manager")
        run_id = str(self.declare_parameter("run_id", str(uuid.uuid4())).value)
        mission_id = str(self.declare_parameter("mission_id", str(uuid.uuid4())).value)
        description = Path(get_package_share_directory("substation_description"))
        mission_share = Path(get_package_share_directory("substation_mission"))
        registry = load_asset_registry(description / "config/devices.yaml")
        goals = tuple(AssetGoal(
            item.asset_id, item.inspection_x, item.inspection_y, item.inspection_yaw
        ) for item in registry.assets)
        self._runtime = MissionRuntime(
            load_mission_policy(mission_share / "config/mission_ordering.yaml"),
            run_id,
            mission_id,
            goals,
        )
        self._context_revision = 1
        q_state = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        q_control = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        self._context_pub = self.create_publisher(RunContext, "/system/run_context", q_state)
        self._tasks_pub = self.create_publisher(InspectionTaskArray, "/mission/inspection_tasks", q_state)
        self._cmd_vel_pub = self.create_publisher(Twist, "/cmd_vel", q_control)
        self.create_subscription(AssetRiskArray, "/risk/assets", self._on_risk, q_state)
        self.create_service(EmergencyStop, "/mission/emergency_stop", self._emergency_stop)
        self.create_service(ResetEmergencyStop, "/mission/emergency_stop_reset", self._reset_stop)
        self.create_timer(0.5, self._publish)

    def _on_risk(self, message: AssetRiskArray) -> None:
        if self._runtime.apply_risks(message, monotonic_s=time.monotonic()):
            self._publish()

    def _emergency_stop(self, request, response):
        result = self._runtime.engine.emergency_stop(request.reason)
        self._runtime.state_revision += 1
        response.schema_version = 1
        response.accepted = result.accepted
        response.latched = result.latched
        response.latch_revision = result.latch_revision
        response.state_revision = self._runtime.state_revision
        if result.accepted:
            self._cmd_vel_pub.publish(Twist())
        else:
            response.error_code = "VALIDATION_FAILED"
        self._publish()
        return response

    def _reset_stop(self, request, response):
        result = self._runtime.engine.reset_emergency_stop(
            request.observed_latch_revision,
            confirm=request.confirm,
        )
        self._runtime.state_revision += 1
        response.schema_version = 1
        response.accepted = result.accepted
        response.latched = result.latched
        response.latch_revision = result.latch_revision
        response.state_revision = self._runtime.state_revision
        if not result.accepted:
            response.error_code = "LATCH_REVISION_MISMATCH"
        self._publish()
        return response

    def _publish(self) -> None:
        stamp = self.get_clock().now().to_msg()
        context = RunContext()
        context.schema_version = 1
        context.header.stamp = stamp
        context.context_revision = self._context_revision
        context.lifecycle = RunContext.LIFECYCLE_ACTIVE
        context.run_id = self._runtime.engine.run_id
        context.started_at = stamp
        context.reason_code = "MISSION_ACTIVE"
        context.reason = "risk-driven inspection runtime"
        tasks = self._runtime.snapshot()
        tasks.header.stamp = stamp
        tasks.header.frame_id = "map"
        self._context_pub.publish(context)
        self._tasks_pub.publish(tasks)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = TaskManagerNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
