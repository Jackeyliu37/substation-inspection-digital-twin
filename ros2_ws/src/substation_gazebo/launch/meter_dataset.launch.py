from __future__ import annotations

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import AppendEnvironmentVariable, DeclareLaunchArgument
from launch.actions import IncludeLaunchDescription, SetEnvironmentVariable
from launch.actions import UnsetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    gazebo_share = get_package_share_directory("substation_gazebo")
    description_share = get_package_share_directory("substation_description")
    ros_gz_share = get_package_share_directory("ros_gz_sim")
    world = os.path.join(gazebo_share, "worlds", "meter_dataset_world.sdf")
    bridge = os.path.join(gazebo_share, "config", "meter_dataset_bridge.yaml")
    default_config = os.path.join(gazebo_share, "config", "meter_dataset_generation.yaml")
    default_registry = os.path.join(description_share, "config", "devices.yaml")

    run_id = LaunchConfiguration("run_id")
    output_dir = LaunchConfiguration("output_dir")
    generation_config = LaunchConfiguration("generation_config")
    registry_path = LaunchConfiguration("registry_path")
    expected_commit = LaunchConfiguration("expected_commit")
    sample_mode = LaunchConfiguration("sample_mode")
    gz_partition = LaunchConfiguration("gz_partition")

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(ros_gz_share, "launch", "gz_sim.launch.py")),
        launch_arguments={"gz_args": ["-r -s -v 3 --headless-rendering ", world]}.items(),
    )
    topic_bridge = Node(
        package="ros_gz_bridge", executable="parameter_bridge", name="meter_dataset_bridge",
        arguments=["--ros-args", "-p", f"config_file:={bridge}"], output="screen",
    )
    pose_bridge = Node(
        package="ros_gz_bridge", executable="parameter_bridge", name="meter_dataset_pose_bridge",
        arguments=["/world/meter_dataset/set_pose@ros_gz_interfaces/srv/SetEntityPose"], output="screen",
    )
    image_bridge = Node(
        package="ros_gz_image", executable="image_bridge", name="meter_dataset_image_bridge",
        arguments=["/meter_dataset/camera/image_raw"], output="screen",
    )
    generator = Node(
        package="substation_gazebo", executable="meter_dataset_generator", name="meter_dataset_generator",
        parameters=[{
            "run_id": run_id, "output_dir": output_dir,
            "generation_config": generation_config, "registry_path": registry_path,
            "expected_commit": expected_commit, "sample_mode": sample_mode,
        }], output="screen",
    )
    return LaunchDescription([
        DeclareLaunchArgument("run_id"), DeclareLaunchArgument("output_dir"),
        DeclareLaunchArgument("generation_config", default_value=default_config),
        DeclareLaunchArgument("registry_path", default_value=default_registry),
        DeclareLaunchArgument("expected_commit"),
        DeclareLaunchArgument("sample_mode", default_value="smoke"),
        DeclareLaunchArgument("gz_partition"),
        UnsetEnvironmentVariable("DISPLAY"),
        SetEnvironmentVariable("ROS_LOCALHOST_ONLY", "1"),
        SetEnvironmentVariable("GZ_PARTITION", gz_partition),
        AppendEnvironmentVariable("GZ_SIM_RESOURCE_PATH", os.path.join(gazebo_share, "models")),
        gazebo, topic_bridge, pose_bridge, image_bridge, generator,
    ])
