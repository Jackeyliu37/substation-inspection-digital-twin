from __future__ import annotations

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import EmitEvent
from launch.actions import IncludeLaunchDescription
from launch.actions import LogInfo
from launch.actions import RegisterEventHandler
from launch.actions import SetEnvironmentVariable
from launch.actions import UnsetEnvironmentVariable
from launch.events import matches_action
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LifecycleNode
from launch_ros.event_handlers import OnStateTransition
from launch_ros.events.lifecycle import ChangeState
from lifecycle_msgs.msg import Transition


def generate_launch_description() -> LaunchDescription:
    gazebo_share = get_package_share_directory("substation_gazebo")
    world_launch = os.path.join(
        gazebo_share, "launch", "substation_world.launch.py"
    )
    slam_params = os.path.join(gazebo_share, "config", "slam_toolbox.yaml")
    run_id = LaunchConfiguration("run_id")
    gz_partition = LaunchConfiguration("gz_partition")

    world = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(world_launch),
        launch_arguments={
            "run_id": run_id,
            "gz_partition": gz_partition,
        }.items(),
    )
    slam = LifecycleNode(
        package="slam_toolbox",
        executable="async_slam_toolbox_node",
        name="slam_toolbox",
        namespace="",
        output="screen",
        parameters=[
            slam_params,
            {"use_lifecycle_manager": False, "use_sim_time": True},
        ],
    )
    configure_slam = EmitEvent(
        event=ChangeState(
            lifecycle_node_matcher=matches_action(slam),
            transition_id=Transition.TRANSITION_CONFIGURE,
        )
    )
    activate_slam = RegisterEventHandler(
        OnStateTransition(
            target_lifecycle_node=slam,
            start_state="configuring",
            goal_state="inactive",
            entities=[
                LogInfo(msg="slam_toolbox activated for Phase 3 mapping"),
                EmitEvent(
                    event=ChangeState(
                        lifecycle_node_matcher=matches_action(slam),
                        transition_id=Transition.TRANSITION_ACTIVATE,
                    )
                ),
            ],
        )
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("run_id", default_value=""),
            DeclareLaunchArgument(
                "gz_partition", default_value="substation-phase3-mapping-default"
            ),
            UnsetEnvironmentVariable("DISPLAY"),
            SetEnvironmentVariable("ROS_LOCALHOST_ONLY", "1"),
            SetEnvironmentVariable("GZ_PARTITION", gz_partition),
            world,
            slam,
            configure_slam,
            activate_slam,
        ]
    )
