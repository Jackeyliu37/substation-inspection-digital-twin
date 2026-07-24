from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
LAUNCH = (
    ROOT
    / "ros2_ws/src/substation_gazebo/launch/substation_world.launch.py"
)


def source() -> str:
    assert LAUNCH.is_file(), "substation_world.launch.py must exist"
    text = LAUNCH.read_text(encoding="utf-8")
    ast.parse(text, filename=str(LAUNCH))
    return text


def test_launch_forces_headless_local_runtime() -> None:
    text = source()
    assert 'UnsetEnvironmentVariable("DISPLAY")' in text
    assert 'SetEnvironmentVariable("ROS_LOCALHOST_ONLY", "1")' in text
    assert 'SetEnvironmentVariable("GZ_PARTITION"' in text
    assert "--headless-rendering" in text
    assert '"-g"' not in text
    assert "Xvfb" not in text
    assert "VirtualGL" not in text


def test_launch_starts_exact_phase2_components() -> None:
    text = source()
    for pair in (
        ('package="ros_gz_bridge"', 'executable="parameter_bridge"'),
        ('package="ros_gz_image"', 'executable="image_bridge"'),
        ('package="robot_state_publisher"', 'executable="robot_state_publisher"'),
        ('package="substation_description"', 'executable="asset_tf_broadcaster"'),
        ('package="substation_gazebo"', 'executable="scenario_manager"'),
    ):
        assert pair[0] in text and pair[1] in text
    assert "/world/substation/set_pose@ros_gz_interfaces/srv/SetEntityPose" not in text
    assert "/camera/image_raw" in text


def test_launch_uses_installed_package_resources() -> None:
    text = source()
    assert 'get_package_share_directory("substation_gazebo")' in text
    assert 'get_package_share_directory("substation_description")' in text
    assert 'get_package_share_directory("turtlebot3_gazebo")' in text
    assert "GZ_SIM_RESOURCE_PATH" in text
    assert 'DeclareLaunchArgument("run_id"' in text
    assert '"gz_partition", default_value="substation-phase2-default"' in text


def test_gazebo_package_declares_runtime_dependencies() -> None:
    package = ET.parse(ROOT / "ros2_ws/src/substation_gazebo/package.xml")
    dependencies = {node.text for node in package.findall("exec_depend")}
    assert {
        "ament_index_python",
        "builtin_interfaces",
        "diagnostic_msgs",
        "geometry_msgs",
        "launch",
        "launch_ros",
        "nav_msgs",
        "python3-yaml",
        "rcl_interfaces",
        "rclpy",
        "robot_state_publisher",
        "ros_gz_bridge",
        "ros_gz_image",
        "ros_gz_interfaces",
        "ros_gz_sim",
        "rosgraph_msgs",
        "sensor_msgs",
        "substation_description",
        "tf2_msgs",
        "turtlebot3_gazebo",
        "xacro",
    }.issubset(dependencies)


def test_workspace_packages_are_identified_as_ament_python() -> None:
    result = subprocess.run(
        [
            "colcon",
            "list",
            "--base-paths",
            "src/substation_description",
            "src/substation_gazebo",
        ],
        cwd=ROOT / "ros2_ws",
        check=True,
        capture_output=True,
        text=True,
    )
    package_types = {
        columns[0]: columns[2]
        for line in result.stdout.splitlines()
        if len(columns := line.split("\t")) == 3
    }
    assert package_types == {
        "substation_description": "(ros.ament_python)",
        "substation_gazebo": "(ros.ament_python)",
    }
