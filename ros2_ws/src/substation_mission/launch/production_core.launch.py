from __future__ import annotations

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.actions import SetEnvironmentVariable, UnsetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def _include(package: str, launch_name: str, arguments=None):
    path = os.path.join(
        get_package_share_directory(package), "launch", launch_name
    )
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(path),
        launch_arguments=(arguments or {}).items(),
    )


def generate_launch_description() -> LaunchDescription:
    run_id = LaunchConfiguration("run_id")
    return LaunchDescription([
        DeclareLaunchArgument("run_id"),
        UnsetEnvironmentVariable("DISPLAY"),
        SetEnvironmentVariable("ROS_LOCALHOST_ONLY", "1"),
        _include("substation_reporting", "reporting.launch.py"),
        _include(
            "substation_mission",
            "substation_core.launch.py",
            {"run_id": run_id},
        ),
        _include(
            "substation_mission",
            "inspection_executor.launch.py",
            {"use_sim_time": "true"},
        ),
        _include(
            "substation_perception",
            "production_perception.launch.py",
            {"run_id": run_id},
        ),
    ])
