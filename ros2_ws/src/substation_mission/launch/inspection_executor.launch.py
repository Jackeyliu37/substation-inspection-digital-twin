from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="true"),
        DeclareLaunchArgument("nav2_server_timeout_s", default_value="2.0"),
        SetEnvironmentVariable("ROS_LOCALHOST_ONLY", "1"),
        Node(
            package="substation_mission",
            executable="inspection_executor",
            name="inspection_executor",
            parameters=[{
                "use_sim_time": LaunchConfiguration("use_sim_time"),
                "nav2_server_timeout_s": LaunchConfiguration("nav2_server_timeout_s"),
            }],
            output="screen",
        ),
    ])
