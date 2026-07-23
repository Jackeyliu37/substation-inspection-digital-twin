from __future__ import annotations

import ast
from pathlib import Path
import xml.etree.ElementTree as ET


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
LAUNCH = PACKAGE_ROOT / "launch/placeholder_perception.launch.py"
PACKAGE_XML = PACKAGE_ROOT / "package.xml"


def _source() -> str:
    assert LAUNCH.is_file(), f"missing launch file: {LAUNCH}"
    source = LAUNCH.read_text(encoding="utf-8")
    ast.parse(source, filename=str(LAUNCH))
    return source


def test_launch_locks_development_identity() -> None:
    source = _source()

    assert '"development_placeholder"' in source
    assert '"yolo11n_base"' in source
    assert (
        '"0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1"'
        in source
    )
    assert "5613764" in source
    assert '"production_ready": False' in source
    for forbidden in (
        "yolo11n_safety",
        "yolo11n_equipment",
        "yolo11n_fault",
        "meter_locator",
    ):
        assert forbidden not in source


def test_launch_is_headless_localhost_only_and_sets_partition() -> None:
    source = _source()

    assert 'UnsetEnvironmentVariable("DISPLAY")' in source
    assert 'SetEnvironmentVariable("ROS_LOCALHOST_ONLY", "1")' in source
    assert 'SetEnvironmentVariable("GZ_PARTITION", gz_partition)' in source
    assert 'DeclareLaunchArgument("gz_partition", default_value=' in source


def test_launch_starts_only_placeholder_executable_with_sim_time() -> None:
    source = _source()

    assert source.count("Node(") == 1
    assert 'package="substation_perception"' in source
    assert 'executable="placeholder_detector"' in source
    assert 'name="placeholder_detector"' in source
    assert '"use_sim_time": True' in source
    assert '"model_path": MODEL_PATH' in source


def test_package_declares_runtime_and_launch_dependencies() -> None:
    package = ET.parse(PACKAGE_XML)
    dependencies = {node.text for node in package.findall("exec_depend")}

    assert {
        "cv_bridge",
        "diagnostic_msgs",
        "launch",
        "launch_ros",
        "rclpy",
        "sensor_msgs",
        "std_msgs",
        "vision_msgs",
    }.issubset(dependencies)
