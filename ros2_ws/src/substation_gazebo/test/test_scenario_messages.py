from __future__ import annotations

import importlib
from pathlib import Path
import sys

from builtin_interfaces.msg import Time
from diagnostic_msgs.msg import DiagnosticStatus


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
