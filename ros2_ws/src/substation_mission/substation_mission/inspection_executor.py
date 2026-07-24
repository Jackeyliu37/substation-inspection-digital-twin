from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import math
from typing import Awaitable, Callable, Sequence

from action_msgs.msg import GoalStatus
from nav2_msgs.action import NavigateToPose
import rclpy
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from substation_interfaces.action import ExecuteInspection
from substation_interfaces.msg import InspectionTask, InspectionTaskArray


class NavigationOutcome(IntEnum):
    SUCCEEDED = 0
    FAILED = 1
    CANCELLED = 2


class Interruption(IntEnum):
    NONE = 0
    CANCELLED = 1
    EMERGENCY_STOP = 2


class ExecutionState(IntEnum):
    SUCCEEDED = 0
    STOPPED = 1
    FAILED = 2
    CANCELLED = 3


@dataclass(frozen=True)
class ExecutionFeedback:
    active_task_id: str
    progress_0_1: float


@dataclass(frozen=True)
class ExecutionSummary:
    state: ExecutionState
    completed_tasks: int
    skipped_tasks: int
    error_code: str = ""
    error_message: str = ""


def validate_execute_goal(goal: ExecuteInspection.Goal) -> bool:
    if (
        goal.schema_version != ExecuteInspection.Goal.SCHEMA_VERSION
        or goal.header.frame_id != "map"
        or not goal.command_id
        or not goal.run_id
        or not goal.mission_id
        or not goal.route_id
        or goal.state_revision < 1
        or goal.queue_revision < 1
        or not goal.tasks
    ):
        return False
    for item in goal.tasks:
        pose = item.goal.pose
        quaternion = pose.orientation
        values = (
            pose.position.x,
            pose.position.y,
            pose.position.z,
            quaternion.x,
            quaternion.y,
            quaternion.z,
            quaternion.w,
        )
        if (
            item.schema_version != InspectionTask.SCHEMA_VERSION
            or item.mission_id != goal.mission_id
            or not item.task_id
            or item.state != InspectionTask.STATE_QUEUED
            or item.goal.header.frame_id != "map"
            or not all(math.isfinite(value) for value in values)
            or not math.isclose(
                sum(value * value for value in (
                    quaternion.x, quaternion.y, quaternion.z, quaternion.w
                )),
                1.0,
                rel_tol=0.0,
                abs_tol=1e-3,
            )
        ):
            return False
    return True


class InspectionSequenceRunner:
    def __init__(
        self,
        *,
        navigate: Callable[[InspectionTask], Awaitable[NavigationOutcome]],
        publish_feedback: Callable[[ExecutionFeedback], None],
        interruption: Callable[[], Interruption],
    ) -> None:
        self._navigate = navigate
        self._publish_feedback = publish_feedback
        self._interruption = interruption

    async def execute(
        self,
        tasks: Sequence[InspectionTask],
        continue_on_unreachable: bool,
    ) -> ExecutionSummary:
        completed = 0
        skipped = 0
        total = len(tasks)
        for item in tasks:
            interrupted = self._interrupted(completed, skipped)
            if interrupted is not None:
                return interrupted
            self._publish_feedback(ExecutionFeedback(
                active_task_id=item.task_id,
                progress_0_1=(completed + skipped) / total,
            ))
            outcome = await self._navigate(item)
            interrupted = self._interrupted(completed, skipped)
            if interrupted is not None:
                return interrupted
            if outcome == NavigationOutcome.SUCCEEDED:
                completed += 1
                continue
            if outcome == NavigationOutcome.FAILED and continue_on_unreachable:
                skipped += 1
                continue
            if outcome == NavigationOutcome.CANCELLED:
                return ExecutionSummary(
                    state=ExecutionState.CANCELLED,
                    completed_tasks=completed,
                    skipped_tasks=skipped,
                )
            return ExecutionSummary(
                state=ExecutionState.FAILED,
                completed_tasks=completed,
                skipped_tasks=skipped,
                error_code="NAVIGATION_UNAVAILABLE",
                error_message=f"navigation failed for task {item.task_id}",
            )
        self._publish_feedback(ExecutionFeedback(active_task_id="", progress_0_1=1.0))
        return ExecutionSummary(
            state=ExecutionState.SUCCEEDED,
            completed_tasks=completed,
            skipped_tasks=skipped,
        )

    def _interrupted(self, completed: int, skipped: int) -> ExecutionSummary | None:
        reason = self._interruption()
        if reason == Interruption.CANCELLED:
            return ExecutionSummary(
                state=ExecutionState.CANCELLED,
                completed_tasks=completed,
                skipped_tasks=skipped,
            )
        if reason == Interruption.EMERGENCY_STOP:
            return ExecutionSummary(
                state=ExecutionState.STOPPED,
                completed_tasks=completed,
                skipped_tasks=skipped,
                error_code="EMERGENCY_STOP_ACTIVATED",
                error_message="inspection stopped by the emergency-stop latch",
            )
        return None


class InspectionExecutorNode(Node):
    def __init__(self) -> None:
        super().__init__("inspection_executor")
        self._nav2_server_timeout_s = float(self.declare_parameter(
            "nav2_server_timeout_s", 2.0
        ).value)
        self._goal_reserved = False
        self._active_action_goal = None
        self._active_navigation_goal = None
        self._emergency_stop_latched = False
        self._mission_state_revision = 0
        self._navigation = ActionClient(self, NavigateToPose, "/navigate_to_pose")
        self._action_server = ActionServer(
            self,
            ExecuteInspection,
            "/mission/execute_inspection",
            execute_callback=self._execute_action,
            goal_callback=self._accept_goal,
            cancel_callback=self._cancel_goal,
        )
        state_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.create_subscription(
            InspectionTaskArray,
            "/mission/inspection_tasks",
            self._on_mission_state,
            state_qos,
        )

    def _accept_goal(self, request: ExecuteInspection.Goal) -> GoalResponse:
        if (
            self._goal_reserved
            or self._emergency_stop_latched
            or not validate_execute_goal(request)
        ):
            return GoalResponse.REJECT
        self._goal_reserved = True
        return GoalResponse.ACCEPT

    def _cancel_goal(self, _goal_handle) -> CancelResponse:
        self._cancel_active_navigation()
        return CancelResponse.ACCEPT

    def _on_mission_state(self, message: InspectionTaskArray) -> None:
        if (
            message.schema_version != InspectionTaskArray.SCHEMA_VERSION
            or message.state_revision < self._mission_state_revision
        ):
            return
        self._mission_state_revision = message.state_revision
        self._emergency_stop_latched = message.emergency_stop_latched
        if self._emergency_stop_latched:
            self._cancel_active_navigation()

    def _cancel_active_navigation(self) -> None:
        if self._active_navigation_goal is not None:
            self._active_navigation_goal.cancel_goal_async()

    def _interruption(self, goal_handle) -> Interruption:
        if self._emergency_stop_latched:
            return Interruption.EMERGENCY_STOP
        if goal_handle.is_cancel_requested:
            return Interruption.CANCELLED
        return Interruption.NONE

    async def _navigate(self, task: InspectionTask) -> NavigationOutcome:
        if not self._navigation.wait_for_server(
            timeout_sec=self._nav2_server_timeout_s
        ):
            return NavigationOutcome.FAILED
        goal = NavigateToPose.Goal()
        goal.pose = task.goal
        nav_goal = await self._navigation.send_goal_async(goal)
        if nav_goal is None or not nav_goal.accepted:
            return NavigationOutcome.FAILED
        self._active_navigation_goal = nav_goal
        if self._active_action_goal is not None and (
            self._emergency_stop_latched
            or self._active_action_goal.is_cancel_requested
        ):
            nav_goal.cancel_goal_async()
        try:
            response = await nav_goal.get_result_async()
        finally:
            self._active_navigation_goal = None
        if (
            response.status == GoalStatus.STATUS_SUCCEEDED
            and response.result.error_code == NavigateToPose.Result.NONE
        ):
            return NavigationOutcome.SUCCEEDED
        if response.status == GoalStatus.STATUS_CANCELED:
            return NavigationOutcome.CANCELLED
        return NavigationOutcome.FAILED

    async def _execute_action(self, goal_handle) -> ExecuteInspection.Result:
        self._active_action_goal = goal_handle
        request = goal_handle.request

        def publish_feedback(progress: ExecutionFeedback) -> None:
            feedback = ExecuteInspection.Feedback()
            feedback.schema_version = ExecuteInspection.Goal.SCHEMA_VERSION
            feedback.stamp = self.get_clock().now().to_msg()
            feedback.command_id = request.command_id
            feedback.mission_id = request.mission_id
            feedback.mission_state = (
                ExecuteInspection.Feedback.MISSION_STOPPING
                if self._emergency_stop_latched
                else ExecuteInspection.Feedback.MISSION_RUNNING
            )
            feedback.active_task_id = progress.active_task_id
            feedback.progress_0_1 = progress.progress_0_1
            feedback.state_revision = request.state_revision
            feedback.queue_revision = request.queue_revision
            goal_handle.publish_feedback(feedback)

        runner = InspectionSequenceRunner(
            navigate=self._navigate,
            publish_feedback=publish_feedback,
            interruption=lambda: self._interruption(goal_handle),
        )
        try:
            summary = await runner.execute(
                request.tasks,
                request.continue_on_unreachable,
            )
            result = ExecuteInspection.Result()
            result.schema_version = ExecuteInspection.Goal.SCHEMA_VERSION
            result.command_id = request.command_id
            result.mission_id = request.mission_id
            result.result_state = int(summary.state)
            result.completed_tasks = summary.completed_tasks
            result.skipped_tasks = summary.skipped_tasks
            result.error_code = summary.error_code
            result.error_message = summary.error_message
            if summary.state == ExecutionState.SUCCEEDED:
                goal_handle.succeed()
            elif summary.state == ExecutionState.CANCELLED:
                goal_handle.canceled()
            else:
                goal_handle.abort()
            return result
        finally:
            self._cancel_active_navigation()
            self._active_action_goal = None
            self._goal_reserved = False


def main(args=None) -> None:
    rclpy.init(args=args)
    node = InspectionExecutorNode()
    try:
        rclpy.spin(node)
    except ExternalShutdownException:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
