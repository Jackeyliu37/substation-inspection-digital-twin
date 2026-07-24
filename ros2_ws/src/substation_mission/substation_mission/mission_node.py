from __future__ import annotations

from dataclasses import dataclass, replace
import math
from pathlib import Path
import time
import uuid

from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import Twist
import rclpy
from rclpy.action import ActionClient
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from substation_description.asset_registry import load_asset_registry
from substation_interfaces.action import ExecuteInspection
from substation_interfaces.msg import AssetRiskArray, InspectionTask as InspectionTaskMessage
from substation_interfaces.msg import InspectionTaskArray, RunContext
from substation_interfaces.srv import EmergencyStop, ManageMission, ResetEmergencyStop

from .mission_engine import (
    InspectionTask,
    MissionEngine,
    MissionPolicy,
    RobotMode,
    TaskState,
    load_mission_policy,
)
from .mission_store import MissionSnapshotStore


@dataclass(frozen=True)
class AssetGoal:
    asset_id: str
    x: float
    y: float
    yaw: float


@dataclass(frozen=True)
class MissionTransitionResult:
    accepted: bool
    command_id: str
    error_code: str = ""
    error_message: str = ""


class MissionRuntime:
    CONTEXT_ACTIVE = RunContext.LIFECYCLE_ACTIVE
    CONTEXT_ENDED = RunContext.LIFECYCLE_ENDED

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
        self.engine.replace_tasks(self._initial_tasks())
        self.state_revision = 1
        self.queue_revision = 1
        self.mission_state = InspectionTaskArray.MISSION_RUNNING
        self.context_lifecycle = self.CONTEXT_ACTIVE
        self.context_revision = 1
        self.transition_command_id = ""
        self.transition_reason_code = "MISSION_STARTED"
        self.transition_reason = "risk-driven inspection runtime"
        self.active_task_id = ""
        self.completed_tasks = 0
        self.progress_0_1 = 0.0

    def _initial_tasks(self) -> tuple[InspectionTask, ...]:
        return tuple(
            InspectionTask(
                task_id=str(uuid.uuid4()),
                asset_id=goal.asset_id,
                base_priority=10,
                path_length_m=math.hypot(goal.x, goal.y),
            )
            for goal in self.goals.values()
        )

    def persistence_record(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "run_id": self.engine.run_id,
            "mission_id": self.engine.mission_id,
            "state_revision": self.state_revision,
            "queue_revision": self.queue_revision,
            "mission_state": self.mission_state,
            "context_lifecycle": self.context_lifecycle,
            "context_revision": self.context_revision,
            "transition_command_id": self.transition_command_id,
            "transition_reason_code": self.transition_reason_code,
            "transition_reason": self.transition_reason,
            "active_task_id": self.active_task_id,
            "completed_tasks": self.completed_tasks,
            "progress_0_1": self.progress_0_1,
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
                    "state": int(task.state),
                    "attempt": task.attempt,
                    "last_error_code": task.last_error_code,
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
        runtime.mission_state = int(record.get(
            "mission_state", InspectionTaskArray.MISSION_RUNNING
        ))
        runtime.context_lifecycle = int(record.get(
            "context_lifecycle", RunContext.LIFECYCLE_ACTIVE
        ))
        runtime.context_revision = int(record.get("context_revision", 1))
        runtime.transition_command_id = str(record.get("transition_command_id", ""))
        runtime.transition_reason_code = str(record.get(
            "transition_reason_code", "MISSION_RECOVERED"
        ))
        runtime.transition_reason = str(record.get("transition_reason", ""))
        runtime.active_task_id = str(record.get("active_task_id", ""))
        runtime.completed_tasks = int(record.get("completed_tasks", 0))
        runtime.progress_0_1 = float(record.get("progress_0_1", 0.0))
        return runtime

    def manage(
        self,
        *,
        action: str,
        command_id: str,
        mission_id: str,
        route_id: str,
        reason: str,
    ) -> MissionTransitionResult:
        if not command_id or not reason:
            return MissionTransitionResult(
                False, command_id, "VALIDATION_FAILED", "command_id and reason are required"
            )
        if action == "start":
            if mission_id or route_id != "default-route":
                return MissionTransitionResult(
                    False, command_id, "VALIDATION_FAILED", "start requires the default route and no mission_id"
                )
            if self.mission_state not in (
                InspectionTaskArray.MISSION_SUCCEEDED,
                InspectionTaskArray.MISSION_FAILED,
                InspectionTaskArray.MISSION_STOPPED,
            ):
                return MissionTransitionResult(
                    False, command_id, "INVALID_STATE_TRANSITION", "mission state does not allow start"
                )
            if self.engine.emergency_stop_latched:
                return MissionTransitionResult(
                    False, command_id, "EMERGENCY_STOP_LATCHED", "emergency stop is latched"
                )
            self.engine = MissionEngine(self.engine.policy)
            self.engine.start(
                run_id=str(uuid.uuid4()),
                mission_id=str(uuid.uuid4()),
                route_id=route_id,
            )
            self.engine.replace_tasks(self._initial_tasks())
            self.mission_state = InspectionTaskArray.MISSION_RUNNING
            self.context_lifecycle = self.CONTEXT_ACTIVE
            self.context_revision += 1
            self.state_revision += 1
            self.queue_revision = 1
            self.transition_command_id = command_id
            self.transition_reason_code = "MISSION_STARTED"
            self.transition_reason = reason
            self.active_task_id = ""
            self.completed_tasks = 0
            self.progress_0_1 = 0.0
            return MissionTransitionResult(True, command_id)
        if mission_id != self.engine.mission_id:
            return MissionTransitionResult(
                False, command_id, "MISSION_NOT_FOUND", "mission_id is not current"
            )
        transitions = {
            "pause": (
                InspectionTaskArray.MISSION_RUNNING,
                InspectionTaskArray.MISSION_PAUSED,
                "MISSION_PAUSED",
            ),
            "resume": (
                InspectionTaskArray.MISSION_PAUSED,
                InspectionTaskArray.MISSION_RUNNING,
                "MISSION_RESUMED",
            ),
        }
        if action in transitions:
            required, target, reason_code = transitions[action]
            if self.mission_state != required:
                return MissionTransitionResult(
                    False, command_id, "INVALID_STATE_TRANSITION", "mission state does not allow action"
                )
            if action == "resume" and self.engine.emergency_stop_latched:
                return MissionTransitionResult(
                    False, command_id, "EMERGENCY_STOP_LATCHED", "emergency stop is latched"
                )
            self.mission_state = target
            self.state_revision += 1
            self.transition_command_id = command_id
            self.transition_reason_code = reason_code
            self.transition_reason = reason
            return MissionTransitionResult(True, command_id)
        if action == "stop":
            if self.mission_state not in (
                InspectionTaskArray.MISSION_READY,
                InspectionTaskArray.MISSION_RUNNING,
                InspectionTaskArray.MISSION_PAUSED,
                InspectionTaskArray.MISSION_STOPPING,
            ):
                return MissionTransitionResult(
                    False, command_id, "INVALID_STATE_TRANSITION", "mission state does not allow stop"
                )
            self.mission_state = InspectionTaskArray.MISSION_STOPPED
            self.context_lifecycle = self.CONTEXT_ENDED
            self.context_revision += 1
            self.state_revision += 1
            self.transition_command_id = command_id
            self.transition_reason_code = "MISSION_STOPPED"
            self.transition_reason = reason
            return MissionTransitionResult(True, command_id)
        return MissionTransitionResult(
            False, command_id, "INVALID_STATE_TRANSITION", f"unsupported action: {action}"
        )

    def apply_execution_feedback(self, task_id: str, *, progress_0_1: float) -> bool:
        if self.mission_state != InspectionTaskArray.MISSION_RUNNING:
            return False
        if not 0.0 <= progress_0_1 <= 1.0:
            return False
        target = next((item for item in self.engine.tasks if item.task_id == task_id), None)
        if target is None:
            return False
        changed = self.active_task_id != task_id or progress_0_1 > self.progress_0_1
        updated = []
        for task in self.engine.tasks:
            if task.task_id == task_id:
                next_task = replace(
                    task,
                    state=TaskState.ACTIVE,
                    attempt=max(1, task.attempt),
                    last_error_code="",
                )
                changed = changed or next_task != task
                updated.append(next_task)
            else:
                updated.append(task)
        if not changed:
            return False
        self.engine.tasks = tuple(updated)
        self.active_task_id = task_id
        self.progress_0_1 = max(self.progress_0_1, float(progress_0_1))
        self.state_revision += 1
        self.transition_command_id = ""
        self.transition_reason_code = "TASK_ACTIVE"
        self.transition_reason = "inspection task entered active state"
        return True

    def finish_execution(
        self,
        *,
        result_state: int,
        completed_tasks: int,
        skipped_tasks: int,
        error_code: str,
    ) -> bool:
        if self.mission_state != InspectionTaskArray.MISSION_RUNNING:
            return False
        task_count = len(self.engine.tasks)
        succeeded = result_state == ExecuteInspection.Result.RESULT_SUCCEEDED
        counts_valid = completed_tasks >= 0 and skipped_tasks >= 0 and (
            completed_tasks + skipped_tasks == task_count
        )
        updated = []
        for index, task in enumerate(self.engine.tasks):
            if succeeded and counts_valid:
                state = TaskState.SUCCEEDED if index < completed_tasks else TaskState.SKIPPED
                last_error = "" if state == TaskState.SUCCEEDED else "UNREACHABLE_SKIPPED"
            else:
                state = TaskState.FAILED if task.state == TaskState.ACTIVE else TaskState.CANCELLED
                last_error = error_code or "EXECUTION_RESULT_INVALID"
            updated.append(replace(task, state=state, last_error_code=last_error))
        self.engine.tasks = tuple(updated)
        self.active_task_id = ""
        self.completed_tasks = completed_tasks if succeeded and counts_valid else sum(
            item.state == TaskState.SUCCEEDED for item in updated
        )
        self.progress_0_1 = 1.0 if succeeded and counts_valid else self.progress_0_1
        self.mission_state = (
            InspectionTaskArray.MISSION_SUCCEEDED
            if succeeded and counts_valid
            else InspectionTaskArray.MISSION_FAILED
        )
        self.context_lifecycle = self.CONTEXT_ENDED
        self.context_revision += 1
        self.state_revision += 1
        self.transition_command_id = ""
        self.transition_reason_code = (
            "MISSION_SUCCEEDED" if self.mission_state == InspectionTaskArray.MISSION_SUCCEEDED
            else "MISSION_EXECUTION_FAILED"
        )
        self.transition_reason = error_code
        return True

    def apply_risks(self, risks: AssetRiskArray, *, monotonic_s: float) -> bool:
        if self.mission_state not in (
            InspectionTaskArray.MISSION_RUNNING,
            InspectionTaskArray.MISSION_PAUSED,
        ):
            return False
        if risks.run_id != self.engine.run_id:
            return False
        changed = self.engine.apply_risk(
            {item.asset_id: float(item.score_0_100) for item in risks.assets},
            monotonic_s=monotonic_s,
        )
        if changed:
            self.engine.tasks = tuple(
                replace(task, state=TaskState.QUEUED)
                if task.state == TaskState.ACTIVE else task
                for task in self.engine.tasks
            )
            self.active_task_id = ""
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
        output.mission_state = self.mission_state
        output.robot_mode = int(self.engine.robot_mode)
        output.emergency_stop_latched = self.engine.emergency_stop_latched
        output.emergency_stop_latch_revision = self.engine.latch_revision
        output.transition_command_id = self.transition_command_id
        output.transition_reason_code = self.transition_reason_code
        output.transition_reason = self.transition_reason
        output.active_task_id = self.active_task_id
        output.completed_tasks = self.completed_tasks
        output.progress_0_1 = self.progress_0_1
        output.total_tasks = len(self.engine.tasks)
        for task in self.engine.tasks:
            message = InspectionTaskMessage()
            message.schema_version = 1
            message.task_id = task.task_id
            message.mission_id = self.engine.mission_id
            message.asset_id = task.asset_id
            message.task_type = InspectionTaskMessage.TYPE_INSPECT_ASSET
            message.state = int(task.state)
            message.base_priority = task.base_priority
            message.risk_score_0_100 = task.risk_score_0_100
            message.risk_gain = self.engine.policy.risk_gain
            message.path_length_m = task.path_length_m
            message.distance_penalty = self.engine.policy.distance_penalty
            message.computed_priority = task.computed_priority
            message.safety_standoff_m = task.safety_standoff_m
            message.attempt = task.attempt
            message.last_error_code = task.last_error_code
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
    def __init__(self, **node_kwargs) -> None:
        super().__init__("task_manager", **node_kwargs)
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
        self._continue_on_unreachable = bool(self.declare_parameter(
            "continue_on_unreachable", True
        ).value)
        self._inspection_client = ActionClient(
            self,
            ExecuteInspection,
            "/mission/execute_inspection",
        )
        self._inspection_goal_handle = None
        self._inspection_send_future = None
        self._inspection_cancel_future = None
        self._dispatched_execution_signature: tuple[int, int] | None = None
        self._replacement_requested = False
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
        self.create_service(ManageMission, "/mission/manage", self._manage_mission)
        self.create_service(EmergencyStop, "/mission/emergency_stop", self._emergency_stop)
        self.create_service(ResetEmergencyStop, "/mission/emergency_stop_reset", self._reset_stop)
        self.create_timer(0.5, self._publish)

    def _on_risk(self, message: AssetRiskArray) -> None:
        if self._runtime.apply_risks(message, monotonic_s=time.monotonic()):
            self._publish()

    def _manage_mission(self, request, response):
        actions = {
            ManageMission.Request.ACTION_START: "start",
            ManageMission.Request.ACTION_PAUSE: "pause",
            ManageMission.Request.ACTION_RESUME: "resume",
            ManageMission.Request.ACTION_STOP: "stop",
            ManageMission.Request.ACTION_RETURN_HOME: "return-home",
        }
        action = actions.get(request.action, "unknown")
        result = self._runtime.manage(
            action=action,
            command_id=request.command_id,
            mission_id=request.mission_id,
            route_id=request.route_id,
            reason=request.reason,
        )
        response.schema_version = 1
        response.accepted = result.accepted
        response.run_id = self._runtime.engine.run_id
        response.mission_id = self._runtime.engine.mission_id
        response.run_context_revision = self._runtime.context_revision
        response.state_revision = self._runtime.state_revision
        response.queue_revision = self._runtime.queue_revision
        response.error_code = result.error_code
        response.error_message = result.error_message
        if result.accepted and action in {"pause", "stop"}:
            self._replacement_requested = False
            self._cancel_execution_goal()
            self._cmd_vel_pub.publish(Twist())
        elif result.accepted and action in {"resume", "start"}:
            self._dispatched_execution_signature = None
        self._publish()
        return response

    def _emergency_stop(self, request, response):
        result = self._runtime.engine.emergency_stop(request.reason)
        self._runtime.state_revision += 1
        response.schema_version = 1
        response.accepted = result.accepted
        response.latched = result.latched
        response.latch_revision = result.latch_revision
        response.state_revision = self._runtime.state_revision
        if result.accepted:
            self._replacement_requested = False
            self._cancel_execution_goal()
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

    def _publish(self, *, dispatch_execution: bool = True) -> None:
        self._store.save(self._runtime.persistence_record())
        stamp = self.get_clock().now().to_msg()
        context = RunContext()
        context.schema_version = 1
        context.header.stamp = stamp
        context.context_revision = self._runtime.context_revision
        context.lifecycle = self._runtime.context_lifecycle
        context.run_id = self._runtime.engine.run_id
        context.started_at = stamp
        if context.lifecycle == RunContext.LIFECYCLE_ENDED:
            context.ended_at = stamp
        context.transition_command_id = self._runtime.transition_command_id
        context.reason_code = self._runtime.transition_reason_code
        context.reason = self._runtime.transition_reason
        tasks = self._current_stamped_snapshot(stamp)
        self._context_pub.publish(context)
        self._tasks_pub.publish(tasks)
        if dispatch_execution:
            self._dispatch_execution_snapshot(tasks)

    def _current_stamped_snapshot(self, stamp=None) -> InspectionTaskArray:
        tasks = self._runtime.snapshot()
        tasks.header.stamp = stamp or self.get_clock().now().to_msg()
        tasks.header.frame_id = "map"
        return tasks

    def _dispatch_execution_snapshot(self, snapshot: InspectionTaskArray) -> None:
        if (
            snapshot.emergency_stop_latched
            or snapshot.robot_mode != InspectionTaskArray.MODE_AUTONOMOUS
            or snapshot.mission_state != InspectionTaskArray.MISSION_RUNNING
        ):
            self._cancel_execution_goal()
            return
        signature = (self._runtime.context_revision, snapshot.queue_revision)
        if self._dispatched_execution_signature == signature:
            return
        if not self._inspection_client.server_is_ready():
            return
        if self._inspection_send_future is not None:
            self._replacement_requested = True
            return
        if self._inspection_goal_handle is not None:
            self._replacement_requested = True
            self._cancel_execution_goal()
            return

        goal = ExecuteInspection.Goal()
        goal.schema_version = ExecuteInspection.Goal.SCHEMA_VERSION
        goal.header = snapshot.header
        goal.command_id = str(uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{snapshot.run_id}:{snapshot.mission_id}:{signature[0]}:{signature[1]}",
        ))
        goal.run_id = snapshot.run_id
        goal.mission_id = snapshot.mission_id
        goal.route_id = snapshot.route_id
        goal.state_revision = snapshot.state_revision
        goal.queue_revision = snapshot.queue_revision
        goal.tasks = [
            task for task in snapshot.tasks
            if task.state == InspectionTaskMessage.STATE_QUEUED
        ]
        if not goal.tasks:
            return
        goal.continue_on_unreachable = self._continue_on_unreachable
        self._dispatched_execution_signature = signature
        self._inspection_send_future = self._inspection_client.send_goal_async(
            goal,
            feedback_callback=self._on_execution_feedback,
        )
        self._inspection_send_future.add_done_callback(self._on_execution_goal_response)

    def _on_execution_goal_response(self, future) -> None:
        self._inspection_send_future = None
        goal_handle = future.result()
        if goal_handle is None or not goal_handle.accepted:
            self._dispatched_execution_signature = None
            return
        self._inspection_goal_handle = goal_handle
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(
            lambda completed, expected=goal_handle: self._on_execution_result(
                completed, expected
            )
        )
        if self._replacement_requested:
            self._cancel_execution_goal()

    def _on_execution_feedback(self, message) -> None:
        feedback = message.feedback
        if self._runtime.apply_execution_feedback(
            feedback.active_task_id,
            progress_0_1=float(feedback.progress_0_1),
        ):
            self._publish(dispatch_execution=False)

    def _on_execution_result(self, future, expected_goal_handle) -> None:
        self._inspection_cancel_future = None
        if self._replacement_requested:
            self._replacement_requested = False
            if self._inspection_goal_handle is expected_goal_handle:
                self._inspection_goal_handle = None
            self._dispatch_execution_snapshot(self._current_stamped_snapshot())
            return
        if self._runtime.engine.emergency_stop_latched:
            if self._inspection_goal_handle is expected_goal_handle:
                self._inspection_goal_handle = None
            return
        wrapped = future.result()
        result = wrapped.result
        if self._runtime.finish_execution(
            result_state=int(result.result_state),
            completed_tasks=int(result.completed_tasks),
            skipped_tasks=int(result.skipped_tasks),
            error_code=result.error_code,
        ):
            self._publish(dispatch_execution=False)
        if self._inspection_goal_handle is expected_goal_handle:
            self._inspection_goal_handle = None

    def _cancel_execution_goal(self) -> None:
        if (
            self._inspection_goal_handle is None
            or self._inspection_cancel_future is not None
        ):
            return
        self._inspection_cancel_future = self._inspection_goal_handle.cancel_goal_async()
        self._inspection_cancel_future.add_done_callback(self._on_execution_cancelled)

    def _on_execution_cancelled(self, _future) -> None:
        self._inspection_cancel_future = None


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
