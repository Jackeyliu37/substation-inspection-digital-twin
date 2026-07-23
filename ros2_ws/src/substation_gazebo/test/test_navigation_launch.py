from __future__ import annotations

import ast
from pathlib import Path
import xml.etree.ElementTree as ET

import yaml


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
MAPPING = PACKAGE_ROOT / "launch/substation_mapping.launch.py"
NAVIGATION = PACKAGE_ROOT / "launch/substation_navigation.launch.py"
NAV2_CONFIG = PACKAGE_ROOT / "config/nav2_params.yaml"


def launch_source(path: Path) -> str:
    assert path.is_file(), f"missing launch file: {path.name}"
    source = path.read_text(encoding="utf-8")
    ast.parse(source, filename=str(path))
    return source


def test_mapping_launch_is_headless_and_slam_owns_map_transform() -> None:
    source = launch_source(MAPPING)
    assert 'UnsetEnvironmentVariable("DISPLAY")' in source
    assert 'SetEnvironmentVariable("ROS_LOCALHOST_ONLY", "1")' in source
    assert 'SetEnvironmentVariable("GZ_PARTITION", gz_partition)' in source
    assert '"substation_world.launch.py"' in source
    assert 'package="slam_toolbox"' in source
    assert 'executable="async_slam_toolbox_node"' in source
    assert 'namespace=""' in source
    assert '"slam_toolbox.yaml"' in source
    assert 'package="nav2_amcl"' not in source


def test_navigation_launch_uses_map_amcl_and_minimal_nav2_stack() -> None:
    source = launch_source(NAVIGATION)
    assert 'UnsetEnvironmentVariable("DISPLAY")' in source
    assert 'SetEnvironmentVariable("ROS_LOCALHOST_ONLY", "1")' in source
    assert 'SetEnvironmentVariable("GZ_PARTITION", gz_partition)' in source
    assert '"substation_world.launch.py"' in source
    assert '"substation.yaml"' in source
    assert '"nav2_params.yaml"' in source
    for package, executable in (
        ("nav2_map_server", "map_server"),
        ("nav2_amcl", "amcl"),
        ("nav2_controller", "controller_server"),
        ("nav2_smoother", "smoother_server"),
        ("nav2_planner", "planner_server"),
        ("nav2_behaviors", "behavior_server"),
        ("nav2_bt_navigator", "bt_navigator"),
        ("nav2_velocity_smoother", "velocity_smoother"),
        ("nav2_lifecycle_manager", "lifecycle_manager"),
    ):
        assert f'package="{package}"' in source
        assert f'executable="{executable}"' in source
    assert '{"yaml_filename": map_path}' in source
    parameters = yaml.safe_load(NAV2_CONFIG.read_text(encoding="utf-8"))
    assert "map_server" not in parameters
    assert '"map_server",' in source
    assert '"amcl",' in source
    assert '"localization_launch.py"' not in source
    assert 'package="slam_toolbox"' not in source
    assert '("cmd_vel_smoothed", "cmd_vel")' in source


def test_navigation_launch_declares_runtime_dependencies() -> None:
    package = ET.parse(PACKAGE_ROOT / "package.xml")
    dependencies = {node.text for node in package.findall("exec_depend")}
    assert {
        "nav2_amcl",
        "nav2_behaviors",
        "nav2_bt_navigator",
        "nav2_controller",
        "nav2_lifecycle_manager",
        "nav2_map_server",
        "nav2_planner",
        "nav2_smoother",
        "nav2_velocity_smoother",
        "slam_toolbox",
    }.issubset(dependencies)
