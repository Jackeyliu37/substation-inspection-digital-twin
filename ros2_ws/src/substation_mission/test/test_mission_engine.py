from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
MODULE_PATH = ROOT / "ros2_ws/src/substation_mission/substation_mission/mission_engine.py"


def load_module():
    assert MODULE_PATH.is_file(), "mission_engine.py must exist"
    spec = importlib.util.spec_from_file_location("mission_engine_under_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_alert_risk_reorders_queued_tasks_by_contract_priority() -> None:
    module = load_module()
    engine = module.MissionEngine(module.MissionPolicy())
    engine.start(run_id="run-1", mission_id="mission-1", route_id="normal-route")
    engine.replace_tasks((
        module.InspectionTask("task-b", "breaker-01", 10, 4.0),
        module.InspectionTask("task-a", "transformer-01", 10, 4.0),
    ))

    changed = engine.apply_risk({"transformer-01": 70.0, "breaker-01": 5.0}, monotonic_s=20.0)

    assert changed is True
    assert [task.task_id for task in engine.tasks] == ["task-a", "task-b"]
    assert engine.tasks[0].computed_priority == 79.0


def test_identical_risk_snapshot_does_not_replan_after_cooldown() -> None:
    module = load_module()
    engine = module.MissionEngine(
        module.MissionPolicy(normal_replan_cooldown_s=10.0)
    )
    engine.start(run_id="run-1", mission_id="mission-1", route_id="normal-route")
    engine.replace_tasks((
        module.InspectionTask("task-a", "breaker-01", 10, 4.0),
        module.InspectionTask("task-b", "transformer-01", 10, 4.0),
    ))

    first = engine.apply_risk(
        {"breaker-01": 0.0, "transformer-01": 0.0}, monotonic_s=20.0
    )
    repeated = engine.apply_risk(
        {"breaker-01": 0.0, "transformer-01": 0.0}, monotonic_s=31.0
    )

    assert first is True
    assert repeated is False


def test_mission_policy_loads_ordering_values_from_versioned_config(tmp_path: Path) -> None:
    module = load_module()
    path = tmp_path / "mission_ordering.yaml"
    path.write_text(
        """schema_version: 1
risk_gain: 2.0
distance_penalty: 0.5
minimum_active_hold_s: 5.0
normal_replan_cooldown_s: 10.0
emergency_score_0_100: 80.0
""",
        encoding="utf-8",
    )
    policy = module.load_mission_policy(path)
    assert policy.risk_gain == 2.0
    assert policy.distance_penalty == 0.5


def test_emergency_bypasses_cooldown_and_inserts_safe_observation_task() -> None:
    module = load_module()
    engine = module.MissionEngine(module.MissionPolicy(normal_replan_cooldown_s=10.0))
    engine.start(run_id="run-1", mission_id="mission-1", route_id="normal-route")
    engine.replace_tasks((module.InspectionTask("task-a", "breaker-01", 10, 1.0),))
    engine.apply_risk({"breaker-01": 65.0}, monotonic_s=20.0)

    changed = engine.apply_risk({"transformer-01": 85.0}, monotonic_s=21.0)

    assert changed is True
    assert engine.tasks[0].asset_id == "transformer-01"
    assert engine.tasks[0].emergency is True
    assert engine.tasks[0].safety_standoff_m > 0.0


def test_emergency_stop_latches_and_reset_requires_matching_revision() -> None:
    module = load_module()
    engine = module.MissionEngine(module.MissionPolicy())
    engine.start(run_id="run-1", mission_id="mission-1", route_id="normal-route")
    latched = engine.emergency_stop("operator stop")

    assert latched.latched is True
    assert latched.robot_mode == module.RobotMode.ESTOP
    assert engine.reset_emergency_stop(latched.latch_revision - 1, confirm=True).accepted is False
    reset = engine.reset_emergency_stop(latched.latch_revision, confirm=True)
    assert reset.accepted is True
    assert reset.robot_mode == module.RobotMode.MANUAL
    assert reset.latched is False
