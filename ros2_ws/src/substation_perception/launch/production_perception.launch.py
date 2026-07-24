from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable, UnsetEnvironmentVariable
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


PACKAGE_SHARE = Path(get_package_share_directory("substation_perception"))


def repository_root_from_share(package_share: Path) -> Path:
    install_root = package_share.parents[2]
    candidate = install_root.parent
    return candidate.parent if candidate.name == "ros2_ws" else candidate


REPOSITORY_ROOT = repository_root_from_share(PACKAGE_SHARE)
AI_PYTHON = str(REPOSITORY_ROOT / ".venv/bin/python")
MODEL_MANIFEST = str(REPOSITORY_ROOT / "models/manifest.yaml")


def _node(executable: str, name: str, parameters: dict | None = None) -> Node:
    values = {
        "model_manifest": MODEL_MANIFEST,
        "model_root": "/var/lib/substation/models/production",
        "use_sim_time": True,
    }
    values.update(parameters or {})
    return Node(
        package="substation_perception",
        executable=executable,
        name=name,
        prefix=[AI_PYTHON],
        output="screen",
        parameters=[values],
    )


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        DeclareLaunchArgument("run_id", default_value=""),
        UnsetEnvironmentVariable("DISPLAY"),
        SetEnvironmentVariable("ROS_LOCALHOST_ONLY", "1"),
        _node("safety_detector", "safety_detector"),
        _node("equipment_detector", "equipment_detector"),
        _node("defect_classifier", "defect_classifier"),
        _node("meter_reader", "meter_reader", {"meter_config": str(REPOSITORY_ROOT / "configs/meter_reader.yaml")}),
        _node("detection_aggregator", "detection_aggregator"),
    ])
