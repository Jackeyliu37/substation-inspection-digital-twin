from geometry_msgs.msg import Twist
from substation_interfaces.msg import (
    AssetRisk,
    AssetRiskArray,
    InspectionTaskArray,
    ManualVelocityCommand,
    ManualVelocityStatus,
)
from substation_interfaces.srv import ManageMission, SetRobotMode
from rclpy.executors import ExternalShutdownException
import rclpy
from rclpy.context import Context
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
import time

from substation_mission import mission_node
from substation_mission.mission_engine import MissionPolicy
from substation_mission.mission_node import (
    AssetGoal,
    MissionRuntime,
    TaskManagerNode,
    load_or_create_runtime,
)
from substation_mission.mission_store import MissionSnapshotStore


def test_runtime_reorders_queue_when_asset_risk_changes() -> None:
    runtime = MissionRuntime(
        MissionPolicy(normal_replan_cooldown_s=0.0),
        "run-1",
        "mission-1",
        (
            AssetGoal("breaker-01", 0.5, 1.8, 1.57),
            AssetGoal("transformer-01", 4.0, 1.0, 1.57),
        ),
    )
    risks = AssetRiskArray(run_id="run-1", assets=[
        AssetRisk(asset_id="breaker-01", score_0_100=5.0),
        AssetRisk(asset_id="transformer-01", score_0_100=70.0),
    ])

    changed = runtime.apply_risks(risks, monotonic_s=12.0)
    snapshot = runtime.snapshot()

    assert changed is True
    assert snapshot.tasks[0].asset_id == "transformer-01"
    assert snapshot.tasks[0].computed_priority > snapshot.tasks[1].computed_priority
    assert snapshot.run_id == "run-1"
    assert snapshot.queue_revision == 2


def test_runtime_restores_queue_and_emergency_latch_from_persisted_record() -> None:
    policy = MissionPolicy(normal_replan_cooldown_s=0.0)
    goals = (
        AssetGoal("breaker-01", 0.5, 1.8, 1.57),
        AssetGoal("transformer-01", 4.0, 1.0, 1.57),
    )
    runtime = MissionRuntime(policy, "run-1", "mission-1", goals)
    runtime.state_revision = 8
    runtime.queue_revision = 3
    runtime.engine.emergency_stop("operator stop")

    restored = MissionRuntime.restore(policy, goals, runtime.persistence_record())
    snapshot = restored.snapshot()

    assert snapshot.run_id == "run-1"
    assert snapshot.mission_id == "mission-1"
    assert snapshot.state_revision == 8
    assert snapshot.queue_revision == 3
    assert snapshot.emergency_stop_latched is True
    assert snapshot.robot_mode == snapshot.MODE_ESTOP
    assert [item.task_id for item in snapshot.tasks] == [
        item.task_id for item in runtime.snapshot().tasks
    ]


def test_runtime_persists_pause_resume_and_stop_lifecycle_transitions() -> None:
    policy = MissionPolicy()
    goals = (AssetGoal("transformer-01", 4.0, 1.0, 1.57),)
    runtime = MissionRuntime(policy, "run-1", "mission-1", goals)

    paused = runtime.manage(
        action="pause",
        command_id="8d0fa612-997d-430e-8dd0-9f35fc1e129b",
        mission_id="mission-1",
        route_id="",
        reason="operator pause",
    )
    assert paused.accepted is True
    assert runtime.snapshot().mission_state == runtime.snapshot().MISSION_PAUSED
    assert runtime.snapshot().transition_command_id == paused.command_id
    assert runtime.state_revision == 2

    restored = MissionRuntime.restore(policy, goals, runtime.persistence_record())
    assert restored.snapshot().mission_state == restored.snapshot().MISSION_PAUSED
    assert restored.snapshot().transition_command_id == paused.command_id

    resumed = restored.manage(
        action="resume",
        command_id="5a93fa50-e890-48b3-a8d1-88ec11ae6003",
        mission_id="mission-1",
        route_id="",
        reason="operator resume",
    )
    assert resumed.accepted is True
    assert restored.snapshot().mission_state == restored.snapshot().MISSION_RUNNING
    assert restored.state_revision == 3

    stopped = restored.manage(
        action="stop",
        command_id="62c6358c-57ce-4aac-b977-befe37e69698",
        mission_id="mission-1",
        route_id="",
        reason="operator stop",
    )
    assert stopped.accepted is True
    assert restored.snapshot().mission_state == restored.snapshot().MISSION_STOPPED
    assert restored.context_lifecycle == restored.CONTEXT_ENDED
    assert restored.context_revision == 2
    assert restored.state_revision == 4

    previous_run_id = restored.engine.run_id
    started = restored.manage(
        action="start",
        command_id="315ca78b-39ab-4234-bf19-d56d081358c5",
        mission_id="",
        route_id="default-route",
        reason="operator start",
    )
    assert started.accepted is True
    assert restored.engine.run_id != previous_run_id
    assert restored.snapshot().mission_state == restored.snapshot().MISSION_RUNNING
    assert restored.context_lifecycle == restored.CONTEXT_ACTIVE
    assert restored.context_revision == 3
    assert restored.state_revision == 5
    assert restored.queue_revision == 1
    assert len(restored.snapshot().tasks) == 1


def test_runtime_rejects_wrong_mission_transition_without_advancing_revision() -> None:
    runtime = MissionRuntime(
        MissionPolicy(),
        "run-1",
        "mission-1",
        (AssetGoal("transformer-01", 4.0, 1.0, 1.57),),
    )
    result = runtime.manage(
        action="pause",
        command_id="9f7cb868-0ae7-4138-90f7-1f50a6c0a8ae",
        mission_id="mission-other",
        route_id="",
        reason="operator pause",
    )
    assert result.accepted is False
    assert result.error_code == "MISSION_NOT_FOUND"
    assert runtime.state_revision == 1


def test_runtime_persists_action_feedback_and_successful_task_terminal_states() -> None:
    goals = (
        AssetGoal("breaker-01", 0.5, 1.8, 1.57),
        AssetGoal("transformer-01", 4.0, 1.0, 1.57),
    )
    runtime = MissionRuntime(MissionPolicy(), "run-1", "mission-1", goals)
    first_task_id = runtime.snapshot().tasks[0].task_id

    assert runtime.apply_execution_feedback(first_task_id, progress_0_1=0.25) is True
    active = runtime.snapshot()
    assert active.active_task_id == first_task_id
    assert active.tasks[0].state == active.tasks[0].STATE_ACTIVE
    assert active.tasks[0].attempt == 1

    assert runtime.finish_execution(
        result_state=0,
        completed_tasks=2,
        skipped_tasks=0,
        error_code="",
    ) is True
    terminal = runtime.snapshot()
    assert terminal.mission_state == terminal.MISSION_SUCCEEDED
    assert terminal.active_task_id == ""
    assert terminal.completed_tasks == 2
    assert terminal.progress_0_1 == 1.0
    assert [task.state for task in terminal.tasks] == [
        terminal.tasks[0].STATE_SUCCEEDED,
        terminal.tasks[0].STATE_SUCCEEDED,
    ]

    restored = MissionRuntime.restore(
        MissionPolicy(), goals, runtime.persistence_record()
    ).snapshot()
    assert restored.mission_state == restored.MISSION_SUCCEEDED
    assert [task.state for task in restored.tasks] == [
        restored.tasks[0].STATE_SUCCEEDED,
        restored.tasks[0].STATE_SUCCEEDED,
    ]


def test_cancelled_action_result_does_not_override_paused_mission() -> None:
    runtime = MissionRuntime(
        MissionPolicy(),
        "run-1",
        "mission-1",
        (AssetGoal("transformer-01", 4.0, 1.0, 1.57),),
    )
    runtime.manage(
        action="pause",
        command_id="8d0fa612-997d-430e-8dd0-9f35fc1e129b",
        mission_id="mission-1",
        route_id="",
        reason="operator pause",
    )
    revision = runtime.state_revision
    assert runtime.finish_execution(
        result_state=3,
        completed_tasks=0,
        skipped_tasks=0,
        error_code="CANCELLED",
    ) is False
    assert runtime.snapshot().mission_state == runtime.snapshot().MISSION_PAUSED
    assert runtime.state_revision == revision


def test_task_manager_exposes_manage_service_and_publishes_pause_transition(tmp_path) -> None:
    context = Context()
    rclpy.init(context=context)
    task_manager = TaskManagerNode(
        context=context,
        parameter_overrides=[
            Parameter("run_id", value="run-service"),
            Parameter("mission_id", value="mission-service"),
            Parameter("mission_db_path", value=str(tmp_path / "mission.sqlite3")),
        ],
    )
    client_node = Node("mission_manage_test", context=context)
    client = client_node.create_client(ManageMission, "/mission/manage")
    executor = SingleThreadedExecutor(context=context)
    executor.add_node(task_manager)
    executor.add_node(client_node)
    try:
        assert client.wait_for_service(timeout_sec=2.0)
        request = ManageMission.Request()
        request.schema_version = 1
        request.command_id = "8d0fa612-997d-430e-8dd0-9f35fc1e129b"
        request.mission_id = "mission-service"
        request.action = ManageMission.Request.ACTION_PAUSE
        request.reason = "operator pause"
        future = client.call_async(request)
        executor.spin_until_future_complete(future, timeout_sec=2.0)
        response = future.result()
        assert response is not None
        assert response.accepted is True
        assert response.run_id == "run-service"
        assert response.mission_id == "mission-service"
        assert response.state_revision == 2
        assert task_manager._runtime.snapshot().mission_state == InspectionTaskArray.MISSION_PAUSED
        assert task_manager._runtime.snapshot().transition_command_id == request.command_id
    finally:
        executor.remove_node(client_node)
        executor.remove_node(task_manager)
        client_node.destroy_node()
        task_manager.destroy_node()
        executor.shutdown()
        context.shutdown()


def test_task_manager_arbitrates_manual_velocity_and_stops_at_deadline(tmp_path) -> None:
    context = Context()
    rclpy.init(context=context)
    task_manager = TaskManagerNode(
        context=context,
        parameter_overrides=[
            Parameter("run_id", value="run-manual"),
            Parameter("mission_id", value="mission-manual"),
            Parameter("mission_db_path", value=str(tmp_path / "mission.sqlite3")),
        ],
    )
    task_manager._runtime.engine.robot_mode = task_manager._runtime.engine.robot_mode.MANUAL
    task_manager._runtime.state_revision += 1
    task_manager._runtime.transition_reason_code = "ROBOT_MODE_MANUAL"
    task_manager._publish()
    client_node = Node("manual_velocity_test", context=context)
    commands = client_node.create_publisher(
        ManualVelocityCommand, "/cmd_vel_manual", 10
    )
    statuses = []
    velocities = []
    client_node.create_subscription(
        ManualVelocityStatus,
        "/mission/manual_velocity_status",
        lambda message: statuses.append(message),
        10,
    )
    client_node.create_subscription(
        Twist, "/cmd_vel", lambda message: velocities.append(message), 10
    )
    executor = SingleThreadedExecutor(context=context)
    executor.add_node(task_manager)
    executor.add_node(client_node)
    message = ManualVelocityCommand()
    message.schema_version = 1
    message.header.frame_id = "base_link"
    message.command_id = "3b514885-bb10-448b-92fd-ef9ec7ce9c74"
    message.run_id = "run-manual"
    message.context_revision = 1
    message.twist.linear.x = 0.2
    message.duration_s = 0.05
    try:
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not any(
            status.state == ManualVelocityStatus.STATE_APPLIED for status in statuses
        ):
            commands.publish(message)
            executor.spin_once(timeout_sec=0.02)
        assert [status.state for status in statuses[:2]] == [
            ManualVelocityStatus.STATE_ACCEPTED,
            ManualVelocityStatus.STATE_APPLIED,
        ]
        assert any(abs(item.linear.x - 0.2) < 1e-6 for item in velocities)

        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and not any(
            item.linear.x == 0.0 and item.angular.z == 0.0 for item in velocities[1:]
        ):
            executor.spin_once(timeout_sec=0.02)
        assert any(
            item.linear.x == 0.0 and item.angular.z == 0.0 for item in velocities[1:]
        )
    finally:
        executor.remove_node(client_node)
        executor.remove_node(task_manager)
        client_node.destroy_node()
        task_manager.destroy_node()
        executor.shutdown()
        context.shutdown()


def test_task_manager_changes_robot_mode_with_revision_compare_and_set(tmp_path) -> None:
    context = Context()
    rclpy.init(context=context)
    task_manager = TaskManagerNode(
        context=context,
        parameter_overrides=[
            Parameter("run_id", value="run-mode"),
            Parameter("mission_id", value="mission-mode"),
            Parameter("mission_db_path", value=str(tmp_path / "mission.sqlite3")),
        ],
    )
    client_node = Node("robot_mode_test", context=context)
    client = client_node.create_client(SetRobotMode, "/mission/set_robot_mode")
    executor = SingleThreadedExecutor(context=context)
    executor.add_node(task_manager)
    executor.add_node(client_node)
    try:
        assert client.wait_for_service(timeout_sec=2.0)
        request = SetRobotMode.Request()
        request.schema_version = 1
        request.command_id = "a999dd00-5db0-487e-9078-9c11fb9cc51d"
        request.mission_id = "mission-mode"
        request.target_mode = SetRobotMode.Request.MODE_MANUAL
        request.observed_state_revision = 1
        request.observed_latch_revision = 0
        request.reason = "operator handoff"
        future = client.call_async(request)
        executor.spin_until_future_complete(future, timeout_sec=2.0)
        response = future.result()
        assert response.accepted is True
        assert response.robot_mode == InspectionTaskArray.MODE_MANUAL
        assert response.state_revision == 2

        stale = SetRobotMode.Request()
        stale.schema_version = 1
        stale.command_id = "cccb15dd-36ef-4bdf-be29-301053a2169b"
        stale.mission_id = "mission-mode"
        stale.target_mode = SetRobotMode.Request.MODE_AUTONOMOUS
        stale.observed_state_revision = 1
        stale.observed_latch_revision = 0
        stale.reason = "stale page"
        future = client.call_async(stale)
        executor.spin_until_future_complete(future, timeout_sec=2.0)
        response = future.result()
        assert response.accepted is False
        assert response.error_code == "STATE_REVISION_MISMATCH"
        assert task_manager._runtime.engine.robot_mode == task_manager._runtime.engine.robot_mode.MANUAL
    finally:
        executor.remove_node(client_node)
        executor.remove_node(task_manager)
        client_node.destroy_node()
        task_manager.destroy_node()
        executor.shutdown()
        context.shutdown()


def test_new_run_inherits_latched_stop_and_advances_global_revision(tmp_path) -> None:
    policy = MissionPolicy()
    goals = (AssetGoal("transformer-01", 4.0, 1.0, 1.57),)
    store = MissionSnapshotStore(tmp_path / "mission.sqlite3")
    old = MissionRuntime(policy, "run-1", "mission-1", goals)
    old.state_revision = 8
    old.engine.emergency_stop("operator stop")
    store.save(old.persistence_record())

    current = load_or_create_runtime(policy, goals, "run-2", "mission-2", store)

    assert current.state_revision == 9
    assert current.engine.emergency_stop_latched is True
    assert current.engine.latch_revision == 1
    assert current.engine.robot_mode == current.engine.robot_mode.ESTOP
    assert store.load_latest()["run_id"] == "run-2"


def test_main_does_not_shutdown_twice_after_signal_driven_shutdown(monkeypatch) -> None:
    destroyed: list[bool] = []
    shutdown_calls: list[bool] = []

    class FakeNode:
        def destroy_node(self) -> None:
            destroyed.append(True)

    monkeypatch.setattr(mission_node.rclpy, "init", lambda args=None: None)
    monkeypatch.setattr(mission_node, "TaskManagerNode", FakeNode)
    monkeypatch.setattr(
        mission_node.rclpy,
        "spin",
        lambda node: (_ for _ in ()).throw(ExternalShutdownException()),
    )
    monkeypatch.setattr(mission_node.rclpy, "ok", lambda: False)
    monkeypatch.setattr(
        mission_node.rclpy,
        "shutdown",
        lambda: shutdown_calls.append(True),
    )

    mission_node.main()

    assert destroyed == [True]
    assert shutdown_calls == []
