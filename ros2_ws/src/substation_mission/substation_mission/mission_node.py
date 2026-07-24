from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import time
import uuid

from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import Twist
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from substation_description.asset_registry import load_asset_registry
from substation_interfaces.msg import AssetRiskArray, InspectionTask as InspectionTaskMessage
from substation_interfaces.msg import InspectionTaskArray, RunContext
from substation_interfaces.srv import EmergencyStop, ResetEmergencyStop

from .mission_engine import (
    InspectionTask,
    MissionEngine,
    MissionPolicy,
    RobotMode,
    load_mission_policy,
)
from .mission_store import MissionSnapshotStore


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

    def persistence_record(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "run_id": self.engine.run_id,
            "mission_id": self.engine.mission_id,
            "state_revision": self.state_revision,
            "queue_revision": self.queue_revision,
            "robot_mode": int(self.engine.robot_mode),
            "emergency_stop_latched": self.engine.emergency_stop_latched,
            "emergency_stop_latch_revision": self.engine.latch_revision,
            "tasks": [
                {
                    "task_id": task.task_id,
                    "asset_id": task.asset_id,
                    "base_priority": task.base_priority,
                    "path_length_m": task.path_length_m,
                    "risk_score_0_100": task.risk_score_0_100,
                    "computed_priority": task.computed_priority,
                    "safety_standoff_m": task.safety_standoff_m,
                    "emergency": task.emergency,
                }
                for task in self.engine.tasks
            ],
        }

    @classmethod
    def restore(
        cls,
        policy: MissionPolicy,
        goals: tuple[AssetGoal, ...],
        record: dict[str, object],
    ) -> "MissionRuntime":
        runtime = cls.__new__(cls)
        runtime.engine = MissionEngine(policy)
        runtime.engine.start(
            run_id=str(record["run_id"]),
            mission_id=str(record["mission_id"]),
            route_id="default-route",
        )
        tasks = record.get("tasks")
        if not isinstance(tasks, list):
            raise ValueError("MISSION_SNAPSHOT_TASKS_INVALID")
        runtime.engine.replace_tasks(tuple(InspectionTask(**item) for item in tasks))
        runtime.engine.robot_mode = RobotMode(int(record["robot_mode"]))
        runtime.engine.emergency_stop_latched = bool(record["emergency_stop_latched"])
        runtime.engine.latch_revision = int(record["emergency_stop_latch_revision"])
        runtime.goals = {goal.asset_id: goal for goal in goals}
        runtime.state_revision = int(record["state_revision"])
        runtime.queue_revision = int(record["queue_revision"])
        return runtime

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


def load_or_create_runtime(
    policy: MissionPolicy,
    goals: tuple[AssetGoal, ...],
    run_id: str,
    mission_id: str,
    store: MissionSnapshotStore,
) -> MissionRuntime:
    latest = store.load_latest()
    if (
        latest is not None
        and latest["run_id"] == run_id
        and latest["mission_id"] == mission_id
    ):
        return MissionRuntime.restore(policy, goals, latest)
    runtime = MissionRuntime(policy, run_id, mission_id, goals)
    if latest is not None:
        runtime.state_revision = int(latest["state_revision"]) + 1
        if latest["emergency_stop_latched"]:
            runtime.engine.emergency_stop_latched = True
            runtime.engine.latch_revision = int(latest["emergency_stop_latch_revision"])
            runtime.engine.robot_mode = RobotMode.ESTOP
    store.save(runtime.persistence_record())
    return runtime


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
        mission_db_path = str(self.declare_parameter(
            "mission_db_path", "/var/lib/substation/sqlite/mission.sqlite3"
        ).value)
        self._store = MissionSnapshotStore(mission_db_path)
        self._runtime = load_or_create_runtime(
            load_mission_policy(mission_share / "config/mission_ordering.yaml"), goals,
            run_id,
            mission_id,
            self._store,
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
        self._store.save(self._runtime.persistence_record())
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
    except ExternalShutdownException:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
