from __future__ import annotations

import importlib
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace

from builtin_interfaces.msg import Time
from diagnostic_msgs.msg import DiagnosticStatus
from substation_interfaces.msg import RunContext


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PACKAGE_ROOT / "substation_gazebo/scenario_manager.py"


def load_module():
    assert MODULE_PATH.is_file(), "scenario_manager.py must exist"
    sys.path.insert(0, str(PACKAGE_ROOT))
    return importlib.import_module("substation_gazebo.scenario_manager")


def values(status) -> dict[str, str]:
    return {item.key: item.value for item in status.values}


def test_temperature_measurement_has_exact_contract_keys() -> None:
    module = load_module()
    stamp = Time(sec=12, nanosec=34)
    message = module.build_measurement_array(
        stamp=stamp,
        asset_id="transformer-01",
        sensor_id="transformer-temperature-01",
        run_id="4ce58f68-1fcc-45e5-9834-1e3c674c57a8",
        value_key="value_celsius",
        value=90.0,
    )
    assert message.header.stamp == stamp
    assert len(message.status) == 1
    status = message.status[0]
    assert status.name == "transformer-01"
    assert status.hardware_id == "transformer-temperature-01"
    assert status.level == DiagnosticStatus.OK
    assert status.message == "SIMULATION_VALID"
    assert values(status) == {
        "run_id": "4ce58f68-1fcc-45e5-9834-1e3c674c57a8",
        "value_celsius": "90.0",
        "confidence_0_1": "1.0",
        "valid": "true",
    }


def test_scenario_state_has_exact_contract_keys() -> None:
    module = load_module()
    stamp = Time(sec=21, nanosec=43)
    message = module.build_scenario_state(
        stamp=stamp,
        scenario_id="temperature-high",
        run_id="4ce58f68-1fcc-45e5-9834-1e3c674c57a8",
        command_id="e941fc04-d843-49e8-aa90-3ee0a20e8b59",
        action="trigger",
        status="applied",
        active=True,
        revision=2,
        error_code="",
    )
    status = message.status[0]
    assert status.name == "temperature-high"
    assert status.hardware_id == "gazebo"
    assert values(status) == {
        "run_id": "4ce58f68-1fcc-45e5-9834-1e3c674c57a8",
        "command_id": "e941fc04-d843-49e8-aa90-3ee0a20e8b59",
        "action": "trigger",
        "status": "applied",
        "active": "true",
        "scenario_revision": "2",
        "applied_ros_sec": "21",
        "applied_ros_nanosec": "43",
        "error_code": "",
    }


def test_scenario_truth_has_exact_contract_keys() -> None:
    module = load_module()
    stamp = Time(sec=30, nanosec=40)
    started = Time(sec=28, nanosec=10)
    message = module.build_scenario_truth(
        stamp=stamp,
        started_stamp=started,
        scenario_id="fire-smoke",
        run_id="4ce58f68-1fcc-45e5-9834-1e3c674c57a8",
        active=True,
        revision=3,
    )
    assert values(message.status[0]) == {
        "run_id": "4ce58f68-1fcc-45e5-9834-1e3c674c57a8",
        "active": "true",
        "scenario_revision": "3",
        "started_ros_sec": "28",
        "started_ros_nanosec": "10",
    }


def test_manager_source_names_topics_and_atomic_parameters() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    for topic in (
        "/simulation/environment/temperature_raw",
        "/simulation/environment/smoke_raw",
        "/simulation/environment/gas_raw",
        "/simulation/scenario_truth",
        "/simulation/scenario_state",
        "/battery_state",
    ):
        assert topic in source
    for parameter in (
        '"command_id"',
        '"scenario_id"',
        '"scenario_action"',
        '"scenario_parameters_json"',
    ):
        assert parameter in source


def test_pending_scenario_application_does_not_block_the_ros_executor() -> None:
    module = load_module()
    manager = object.__new__(module.ScenarioManager)
    command = SimpleNamespace(
        command_id="b77391cc-2e27-4788-a858-b59b22197495",
        scenario_id="fire-smoke",
        parameters={},
    )
    started = threading.Event()
    release = threading.Event()
    published = []

    class Engine:
        def apply(self, observed_command, pose_setter):
            assert observed_command is command
            started.set()
            assert release.wait(timeout=1.0)
            return module.ApplyResult(
                status="failed",
                revision=0,
                active=False,
                scenario_id="fire-smoke",
                error_code="GAZEBO_SET_POSE_FAILED",
            )

    manager.engine = Engine()
    manager._pending_lock = threading.Lock()
    manager._pending = command
    manager._applying_command = None
    manager._apply_thread = None
    manager._completed_application = None
    manager._set_pose = lambda *_args: False
    manager._publish_result = lambda observed_command, result: published.append(
        (observed_command, result)
    )

    before = time.monotonic()
    manager._process_pending()
    elapsed = time.monotonic() - before

    assert elapsed < 0.1
    assert started.wait(timeout=0.5)
    release.set()
    deadline = time.monotonic() + 1.0
    while not published and time.monotonic() < deadline:
        manager._process_pending()
        time.sleep(0.01)
    assert published[0][0] is command
    assert published[0][1].error_code == "GAZEBO_SET_POSE_FAILED"


def test_manager_tracks_the_active_run_context_instead_of_the_deployment_run() -> None:
    module = load_module()
    manager = object.__new__(module.ScenarioManager)
    manager.run_id = "9cb0230d-68bf-4774-86ea-934fc01271a3"
    manager._run_context_revision = -1

    manager._on_run_context(RunContext(
        schema_version=1,
        run_id="e73647f3-54dd-47d0-b699-2ed130b6cafb",
        context_revision=4,
        lifecycle=RunContext.LIFECYCLE_ACTIVE,
    ))

    assert manager.run_id == "e73647f3-54dd-47d0-b699-2ed130b6cafb"
    assert manager._run_context_revision == 4


def test_native_gazebo_pose_service_uses_the_active_partition_transport(monkeypatch) -> None:
    module = load_module()
    assert hasattr(module, "set_entity_pose_with_gz")
    calls = []

    def run(arguments, **options):
        calls.append((arguments, options))
        return SimpleNamespace(returncode=0, stdout="data: true\n", stderr="")

    monkeypatch.setattr(module.subprocess, "run", run)
    applied = module.set_entity_pose_with_gz(
        "/opt/ros/jazzy/opt/gz_tools_vendor/bin/gz",
        "scenario_fire",
        (4.3, 3.0, -10.0, 0.0, 0.0, 0.0),
    )

    assert applied is True
    arguments, options = calls[0]
    assert arguments[:4] == [
        "/opt/ros/jazzy/opt/gz_tools_vendor/bin/gz",
        "service",
        "-s",
        "/world/substation/set_pose",
    ]
    assert "gz.msgs.Pose" in arguments
    assert "gz.msgs.Boolean" in arguments
    assert 'name: "scenario_fire"' in arguments[-1]
    assert "position: {x: 4.3, y: 3.0, z: -10.0}" in arguments[-1]
    assert options["timeout"] == 3.0
