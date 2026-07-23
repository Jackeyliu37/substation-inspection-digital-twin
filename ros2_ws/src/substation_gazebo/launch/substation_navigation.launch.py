from __future__ import annotations

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import GroupAction
from launch.actions import IncludeLaunchDescription
from launch.actions import SetEnvironmentVariable
from launch.actions import UnsetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.actions import SetParameter


def generate_launch_description() -> LaunchDescription:
    gazebo_share = get_package_share_directory("substation_gazebo")
    nav2_share = get_package_share_directory("nav2_bringup")
    world_launch = os.path.join(
        gazebo_share, "launch", "substation_world.launch.py"
    )
    localization_launch = os.path.join(
        nav2_share, "launch", "localization_launch.py"
    )
    map_path = os.path.join(gazebo_share, "maps", "substation.yaml")
    params_path = os.path.join(gazebo_share, "config", "nav2_params.yaml")
    run_id = LaunchConfiguration("run_id")
    gz_partition = LaunchConfiguration("gz_partition")
    tf_remappings = [("/tf", "tf"), ("/tf_static", "tf_static")]

    world = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(world_launch),
        launch_arguments={
            "run_id": run_id,
            "gz_partition": gz_partition,
        }.items(),
    )
    localization = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(localization_launch),
        launch_arguments={
            "map": map_path,
            "params_file": params_path,
            "use_sim_time": "True",
            "autostart": "True",
            "use_composition": "False",
        }.items(),
    )
    navigation_nodes = GroupAction(
        actions=[
            SetParameter("use_sim_time", True),
            Node(
                package="nav2_controller",
                executable="controller_server",
                name="controller_server",
                output="screen",
                parameters=[params_path],
                remappings=tf_remappings + [("cmd_vel", "cmd_vel_nav")],
            ),
            Node(
                package="nav2_smoother",
                executable="smoother_server",
                name="smoother_server",
                output="screen",
                parameters=[params_path],
                remappings=tf_remappings,
            ),
            Node(
                package="nav2_planner",
                executable="planner_server",
                name="planner_server",
                output="screen",
                parameters=[params_path],
                remappings=tf_remappings,
            ),
            Node(
                package="nav2_behaviors",
                executable="behavior_server",
                name="behavior_server",
                output="screen",
                parameters=[params_path],
                remappings=tf_remappings + [("cmd_vel", "cmd_vel_nav")],
            ),
            Node(
                package="nav2_bt_navigator",
                executable="bt_navigator",
                name="bt_navigator",
                output="screen",
                parameters=[params_path],
                remappings=tf_remappings,
            ),
            Node(
                package="nav2_velocity_smoother",
                executable="velocity_smoother",
                name="velocity_smoother",
                output="screen",
                parameters=[params_path],
                remappings=tf_remappings
                + [("cmd_vel", "cmd_vel_nav"), ("cmd_vel_smoothed", "cmd_vel")],
            ),
            Node(
                package="nav2_lifecycle_manager",
                executable="lifecycle_manager",
                name="lifecycle_manager_navigation",
                output="screen",
                parameters=[
                    {
                        "autostart": True,
                        "node_names": [
                            "controller_server",
                            "smoother_server",
                            "planner_server",
                            "behavior_server",
                            "velocity_smoother",
                            "bt_navigator",
                        ],
                    }
                ],
            ),
        ]
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("run_id", default_value=""),
            DeclareLaunchArgument(
                "gz_partition", default_value="substation-phase3-navigation-default"
            ),
            UnsetEnvironmentVariable("DISPLAY"),
            SetEnvironmentVariable("ROS_LOCALHOST_ONLY", "1"),
            SetEnvironmentVariable("GZ_PARTITION", gz_partition),
            world,
            localization,
            navigation_nodes,
        ]
    )
