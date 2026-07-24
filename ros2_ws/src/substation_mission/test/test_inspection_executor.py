from __future__ import annotations

import asyncio
import importlib
import threading
import time
from uuid import uuid4

from nav2_msgs.action import NavigateToPose
import rclpy
from rclpy.action import ActionClient, ActionServer, CancelResponse
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from rclpy.task import Future
from substation_interfaces.action import ExecuteInspection
from substation_interfaces.msg import AssetRisk, AssetRiskArray, InspectionTask, InspectionTaskArray
from substation_mission.mission_node import TaskManagerNode


def executor_module():
    return importlib.import_module("substation_mission.inspection_executor")


def task(task_id: str) -> InspectionTask:
    value = InspectionTask()
    value.schema_version = 1
    value.task_id = task_id
    value.mission_id = "mission-1"
    value.state = InspectionTask.STATE_QUEUED
    value.goal.header.frame_id = "map"
    value.goal.pose.orientation.w = 1.0
    return value


def execute_goal(*tasks: InspectionTask) -> ExecuteInspection.Goal:
    value = ExecuteInspection.Goal()
    value.schema_version = 1
    value.header.frame_id = "map"
    value.command_id = "command-1"
    value.run_id = "run-1"
    value.mission_id = "mission-1"
    value.route_id = "default-route"
    value.state_revision = 1
    value.queue_revision = 1
    value.tasks = list(tasks)
    return value


def test_sequence_executes_tasks_in_order_and_reports_progress() -> None:
    module = executor_module()
    visited: list[str] = []
    feedback: list[tuple[str, float]] = []

    async def navigate(item: InspectionTask):
        visited.append(item.task_id)
        return module.NavigationOutcome.SUCCEEDED

    runner = module.InspectionSequenceRunner(
        navigate=navigate,
        publish_feedback=lambda item: feedback.append(
            (item.active_task_id, item.progress_0_1)
        ),
        interruption=lambda: module.Interruption.NONE,
    )

    result = asyncio.run(runner.execute((task("task-1"), task("task-2")), False))

    assert visited == ["task-1", "task-2"]
    assert feedback == [("task-1", 0.0), ("task-2", 0.5), ("", 1.0)]
    assert result.state == module.ExecutionState.SUCCEEDED
    assert result.completed_tasks == 2
    assert result.skipped_tasks == 0


def test_sequence_can_skip_unreachable_task_and_continue() -> None:
    module = executor_module()
    outcomes = iter((module.NavigationOutcome.FAILED, module.NavigationOutcome.SUCCEEDED))

    async def navigate(_item: InspectionTask):
        return next(outcomes)

    runner = module.InspectionSequenceRunner(
        navigate=navigate,
        publish_feedback=lambda _item: None,
        interruption=lambda: module.Interruption.NONE,
    )

    result = asyncio.run(runner.execute((task("blocked"), task("reachable")), True))

    assert result.state == module.ExecutionState.SUCCEEDED
    assert result.completed_tasks == 1
    assert result.skipped_tasks == 1


def test_sequence_fails_closed_when_unreachable_task_cannot_be_skipped() -> None:
    module = executor_module()

    async def navigate(_item: InspectionTask):
        return module.NavigationOutcome.FAILED

    runner = module.InspectionSequenceRunner(
        navigate=navigate,
        publish_feedback=lambda _item: None,
        interruption=lambda: module.Interruption.NONE,
    )

    result = asyncio.run(runner.execute((task("blocked"),), False))

    assert result.state == module.ExecutionState.FAILED
    assert result.error_code == "NAVIGATION_UNAVAILABLE"
    assert result.completed_tasks == 0
    assert result.skipped_tasks == 0


def test_sequence_distinguishes_operator_cancel_from_emergency_stop() -> None:
    module = executor_module()

    async def navigate(_item: InspectionTask):
        return module.NavigationOutcome.CANCELLED

    for interruption, expected_state, expected_code in (
        (module.Interruption.CANCELLED, module.ExecutionState.CANCELLED, ""),
        (
            module.Interruption.EMERGENCY_STOP,
            module.ExecutionState.STOPPED,
            "EMERGENCY_STOP_ACTIVATED",
        ),
    ):
        runner = module.InspectionSequenceRunner(
            navigate=navigate,
            publish_feedback=lambda _item: None,
            interruption=lambda value=interruption: value,
        )

        result = asyncio.run(runner.execute((task("active"),), False))

        assert result.state == expected_state
        assert result.error_code == expected_code


def test_execute_goal_validation_rejects_stale_or_cross_mission_snapshot() -> None:
    module = executor_module()
    valid = execute_goal(task("task-1"))
    assert module.validate_execute_goal(valid) is True

    valid.queue_revision = 0
    assert module.validate_execute_goal(valid) is False
    valid.queue_revision = 1
    valid.tasks[0].mission_id = "other-mission"
    assert module.validate_execute_goal(valid) is False


def wait_future(future, timeout_s: float):
    deadline = time.monotonic() + timeout_s
    while not future.done() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert future.done(), "timed out waiting for ROS future"
    return future.result()


def wait_condition(predicate, timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while not predicate() and time.monotonic() < deadline:
        time.sleep(0.01)
    return bool(predicate())


def test_ros_executor_forwards_tasks_to_standard_nav2_action_in_order() -> None:
    module = executor_module()
    rclpy.init()
    nav_node = Node(f"fake_nav2_{uuid4().hex}")
    client_node = Node(f"inspection_client_{uuid4().hex}")
    visited: list[float] = []

    async def execute_navigation(goal_handle):
        visited.append(goal_handle.request.pose.pose.position.x)
        goal_handle.succeed()
        return NavigateToPose.Result(error_code=NavigateToPose.Result.NONE)

    nav_server = ActionServer(
        nav_node,
        NavigateToPose,
        "/navigate_to_pose",
        execute_callback=execute_navigation,
    )
    inspection_node = module.InspectionExecutorNode()
    client = ActionClient(client_node, ExecuteInspection, "/mission/execute_inspection")
    executor = MultiThreadedExecutor(num_threads=4)
    for node in (nav_node, inspection_node, client_node):
        executor.add_node(node)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    try:
        assert client.wait_for_server(timeout_sec=5.0)
        first = task("task-1")
        first.goal.pose.position.x = 1.0
        second = task("task-2")
        second.goal.pose.position.x = 2.0
        accepted = wait_future(client.send_goal_async(execute_goal(first, second)), 5.0)
        assert accepted.accepted is True
        response = wait_future(accepted.get_result_async(), 5.0)

        assert response.result.result_state == ExecuteInspection.Result.RESULT_SUCCEEDED
        assert response.result.completed_tasks == 2
        assert response.result.skipped_tasks == 0
        assert visited == [1.0, 2.0]
    finally:
        executor.shutdown(timeout_sec=2.0)
        thread.join(timeout=2.0)
        client.destroy()
        nav_server.destroy()
        for node in (client_node, inspection_node, nav_node):
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def test_ros_executor_cancels_nav2_when_emergency_stop_latches() -> None:
    module = executor_module()
    rclpy.init()
    nav_node = Node(f"fake_nav2_cancel_{uuid4().hex}")
    client_node = Node(f"inspection_estop_client_{uuid4().hex}")
    navigation_started = threading.Event()
    navigation_cancelled = threading.Event()
    release_navigation = Future()

    async def execute_navigation(goal_handle):
        navigation_started.set()
        await release_navigation
        if goal_handle.is_cancel_requested:
            navigation_cancelled.set()
            goal_handle.canceled()
        else:
            goal_handle.abort()
        return NavigateToPose.Result(error_code=NavigateToPose.Result.NONE)

    def cancel_navigation(_goal_handle):
        if not release_navigation.done():
            release_navigation.set_result(True)
        return CancelResponse.ACCEPT

    nav_server = ActionServer(
        nav_node,
        NavigateToPose,
        "/navigate_to_pose",
        execute_callback=execute_navigation,
        cancel_callback=cancel_navigation,
    )
    inspection_node = module.InspectionExecutorNode()
    client = ActionClient(client_node, ExecuteInspection, "/mission/execute_inspection")
    state_qos = QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=1,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
    )
    mission_state = client_node.create_publisher(
        InspectionTaskArray,
        "/mission/inspection_tasks",
        state_qos,
    )
    executor = MultiThreadedExecutor(num_threads=4)
    for node in (nav_node, inspection_node, client_node):
        executor.add_node(node)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    try:
        assert client.wait_for_server(timeout_sec=5.0)
        accepted = wait_future(client.send_goal_async(execute_goal(task("active"))), 5.0)
        assert accepted.accepted is True
        assert navigation_started.wait(timeout=5.0)
        state = InspectionTaskArray()
        state.schema_version = 1
        state.state_revision = 2
        state.emergency_stop_latched = True
        mission_state.publish(state)
        response = wait_future(accepted.get_result_async(), 5.0)

        assert navigation_cancelled.is_set()
        assert response.result.result_state == ExecuteInspection.Result.RESULT_STOPPED
        assert response.result.error_code == "EMERGENCY_STOP_ACTIVATED"
    finally:
        if not release_navigation.done():
            release_navigation.set_result(True)
        executor.shutdown(timeout_sec=2.0)
        thread.join(timeout=2.0)
        client.destroy()
        nav_server.destroy()
        for node in (client_node, inspection_node, nav_node):
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def test_task_manager_dispatches_its_complete_snapshot_to_executor(tmp_path) -> None:
    module = executor_module()
    database = tmp_path / "mission.sqlite3"
    rclpy.init(args=[
        "--ros-args",
        "-p", f"mission_db_path:={database}",
        "-p", "run_id:=run-integration",
        "-p", "mission_id:=mission-integration",
    ])
    nav_node = Node(f"fake_nav2_manager_{uuid4().hex}")
    visited: list[tuple[float, float]] = []

    async def execute_navigation(goal_handle):
        pose = goal_handle.request.pose.pose.position
        visited.append((pose.x, pose.y))
        goal_handle.succeed()
        return NavigateToPose.Result(error_code=NavigateToPose.Result.NONE)

    nav_server = ActionServer(
        nav_node,
        NavigateToPose,
        "/navigate_to_pose",
        execute_callback=execute_navigation,
    )
    inspection_node = module.InspectionExecutorNode()
    manager_node = TaskManagerNode()
    executor = MultiThreadedExecutor(num_threads=4)
    for node in (nav_node, inspection_node, manager_node):
        executor.add_node(node)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    try:
        assert wait_condition(
            lambda: (
                len(visited) == 10
                and manager_node._inspection_goal_handle is None
                and manager_node._inspection_send_future is None
                and manager_node._inspection_cancel_future is None
                and inspection_node._goal_reserved is False
            ),
            8.0,
        )
        assert len(set(visited)) == 10
        snapshot = manager_node._runtime.snapshot()
        assert snapshot.mission_state == snapshot.MISSION_SUCCEEDED
        assert snapshot.completed_tasks == 10
        assert all(task.state == task.STATE_SUCCEEDED for task in snapshot.tasks)
        persisted = manager_node._store.load_latest()
        assert persisted["mission_state"] == snapshot.MISSION_SUCCEEDED
        assert persisted["completed_tasks"] == 10
    finally:
        executor.shutdown(timeout_sec=2.0)
        thread.join(timeout=2.0)
        nav_server.destroy()
        for node in (manager_node, inspection_node, nav_node):
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def test_risk_replan_cancels_current_goal_and_dispatches_new_queue_head(tmp_path) -> None:
    module = executor_module()
    database = tmp_path / "mission.sqlite3"
    rclpy.init(args=[
        "--ros-args",
        "-p", f"mission_db_path:={database}",
        "-p", "run_id:=run-replan",
        "-p", "mission_id:=mission-replan",
    ])
    nav_node = Node(f"fake_nav2_replan_{uuid4().hex}")
    first_navigation_started = threading.Event()
    release_first_navigation = Future()
    visited: list[tuple[float, float]] = []

    async def execute_navigation(goal_handle):
        pose = goal_handle.request.pose.pose.position
        visited.append((pose.x, pose.y))
        if len(visited) == 1:
            first_navigation_started.set()
            await release_first_navigation
            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
            else:
                goal_handle.abort()
        else:
            goal_handle.succeed()
        return NavigateToPose.Result(error_code=NavigateToPose.Result.NONE)

    def cancel_navigation(_goal_handle):
        if not release_first_navigation.done():
            release_first_navigation.set_result(True)
        return CancelResponse.ACCEPT

    nav_server = ActionServer(
        nav_node,
        NavigateToPose,
        "/navigate_to_pose",
        execute_callback=execute_navigation,
        cancel_callback=cancel_navigation,
    )
    class TrackingInspectionExecutor(module.InspectionExecutorNode):
        def __init__(self) -> None:
            self.received_goal_frames: list[str] = []
            super().__init__()

        def _accept_goal(self, request):
            self.received_goal_frames.append(request.header.frame_id)
            return super()._accept_goal(request)

    inspection_node = TrackingInspectionExecutor()
    manager_node = TaskManagerNode()
    risk_qos = QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=1,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
    )
    risks = nav_node.create_publisher(AssetRiskArray, "/risk/assets", risk_qos)
    executor = MultiThreadedExecutor(num_threads=4)
    for node in (nav_node, inspection_node, manager_node):
        executor.add_node(node)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    try:
        assert first_navigation_started.wait(timeout=5.0)
        message = AssetRiskArray()
        message.schema_version = 1
        message.run_id = "run-replan"
        message.risk_revision = 2
        message.assets = [
            AssetRisk(asset_id="arrester-01", score_0_100=0.0),
            AssetRisk(asset_id="transformer-01", score_0_100=70.0),
        ]
        risks.publish(message)

        assert wait_condition(
            lambda: (
                len(visited) == 11
                and manager_node._inspection_goal_handle is None
                and manager_node._inspection_send_future is None
                and manager_node._inspection_cancel_future is None
                and inspection_node._goal_reserved is False
            ),
            8.0,
        )
        assert visited[:2] == [(3.5, -2.5), (2.8, 3.0)]
        assert inspection_node.received_goal_frames == ["map", "map"]
    finally:
        if not release_first_navigation.done():
            release_first_navigation.set_result(True)
        executor.shutdown(timeout_sec=2.0)
        thread.join(timeout=2.0)
        nav_server.destroy()
        for node in (manager_node, inspection_node, nav_node):
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
