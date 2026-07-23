from __future__ import annotations

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import AppendEnvironmentVariable
from launch.actions import DeclareLaunchArgument
from launch.actions import IncludeLaunchDescription
from launch.actions import SetEnvironmentVariable
from launch.actions import UnsetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description() -> LaunchDescription:
    gazebo_share = get_package_share_directory("substation_gazebo")
    description_share = get_package_share_directory("substation_description")
    turtlebot_gazebo_share = get_package_share_directory("turtlebot3_gazebo")
    ros_gz_sim_share = get_package_share_directory("ros_gz_sim")

    default_world = os.path.join(gazebo_share, "worlds", "substation_world.sdf")
    bridge_path = os.path.join(gazebo_share, "config", "bridge.yaml")
    scenarios_path = os.path.join(gazebo_share, "config", "scenarios.yaml")
    robot_xacro = os.path.join(
        description_share, "urdf", "inspection_robot.urdf.xacro"
    )
    devices_path = os.path.join(description_share, "config", "devices.yaml")
    model_paths = os.pathsep.join(
        [
            os.path.join(gazebo_share, "models"),
            os.path.join(turtlebot_gazebo_share, "models"),
        ]
    )
    world = LaunchConfiguration("world")
    run_id = LaunchConfiguration("run_id")
    gz_partition = LaunchConfiguration("gz_partition")

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ros_gz_sim_share, "launch", "gz_sim.launch.py")
        ),
        launch_arguments={
            "gz_args": ["-r -s -v 3 --headless-rendering ", world],
        }.items(),
    )

    topic_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="substation_topic_bridge",
        arguments=["--ros-args", "-p", f"config_file:={bridge_path}"],
        output="screen",
    )
    set_pose_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="substation_set_pose_bridge",
        arguments=[
            "/world/substation/set_pose@ros_gz_interfaces/srv/SetEntityPose"
        ],
        output="screen",
    )
    image_bridge = Node(
        package="ros_gz_image",
        executable="image_bridge",
        name="substation_image_bridge",
        arguments=["/camera/image_raw"],
        output="screen",
    )
    robot_description = ParameterValue(
        Command(["xacro ", robot_xacro]), value_type=str
    )
    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        parameters=[{"use_sim_time": True, "robot_description": robot_description}],
        output="screen",
    )
    asset_tf = Node(
        package="substation_description",
        executable="asset_tf_broadcaster",
        name="asset_tf_broadcaster",
        parameters=[{"registry_path": devices_path, "use_sim_time": True}],
        output="screen",
    )
    scenario_manager = Node(
        package="substation_gazebo",
        executable="scenario_manager",
        name="scenario_manager",
        parameters=[
            {
                "catalog_path": scenarios_path,
                "registry_path": devices_path,
                "run_id": run_id,
                "use_sim_time": True,
            }
        ],
        output="screen",
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("world", default_value=default_world),
            DeclareLaunchArgument("run_id", default_value=""),
            DeclareLaunchArgument(
                "gz_partition", default_value="substation-phase2-default"
            ),
            UnsetEnvironmentVariable("DISPLAY"),
            SetEnvironmentVariable("ROS_LOCALHOST_ONLY", "1"),
            SetEnvironmentVariable("GZ_PARTITION", gz_partition),
            AppendEnvironmentVariable("GZ_SIM_RESOURCE_PATH", model_paths),
            gazebo,
            topic_bridge,
            set_pose_bridge,
            image_bridge,
            robot_state_publisher,
            asset_tf,
            scenario_manager,
        ]
    )
