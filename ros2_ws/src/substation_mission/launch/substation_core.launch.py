from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    run_id = LaunchConfiguration("run_id")
    return LaunchDescription([
        DeclareLaunchArgument("run_id"),
        SetEnvironmentVariable("ROS_LOCALHOST_ONLY", "1"),
        Node(
            package="substation_mission",
            executable="task_manager",
            name="task_manager",
            parameters=[{"use_sim_time": True, "run_id": run_id}],
            output="screen",
        ),
        Node(
            package="substation_perception",
            executable="environment_normalizer",
            name="environment_normalizer",
            parameters=[{"use_sim_time": True}],
            output="screen",
        ),
        Node(
            package="substation_digital_twin",
            executable="digital_twin",
            name="digital_twin",
            parameters=[{"use_sim_time": True}],
            output="screen",
        ),
        Node(
            package="substation_risk",
            executable="risk",
            name="risk",
            parameters=[{"use_sim_time": True}],
            output="screen",
        ),
    ])
