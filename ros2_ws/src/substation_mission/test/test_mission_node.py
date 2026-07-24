from substation_interfaces.msg import AssetRisk, AssetRiskArray
from rclpy.executors import ExternalShutdownException

from substation_mission import mission_node
from substation_mission.mission_engine import MissionPolicy
from substation_mission.mission_node import AssetGoal, MissionRuntime, load_or_create_runtime
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
