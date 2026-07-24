from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.substitutions import EnvironmentVariable, LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        DeclareLaunchArgument(
            "evidence_database_path",
            default_value="/var/lib/substation/sqlite/evidence.sqlite3",
        ),
        DeclareLaunchArgument(
            "evidence_object_root",
            default_value="/var/lib/substation/evidence",
        ),
        DeclareLaunchArgument(
            "report_work_directory",
            default_value="/var/lib/substation/reports/.work",
        ),
        DeclareLaunchArgument(
            "implementation_commit",
            default_value=EnvironmentVariable(
                "SUBSTATION_IMPLEMENTATION_COMMIT",
                default_value="",
            ),
        ),
        SetEnvironmentVariable("ROS_LOCALHOST_ONLY", "1"),
        Node(
            package="substation_reporting",
            executable="evidence_store",
            name="evidence_store",
            parameters=[{
                "evidence_database_path": LaunchConfiguration(
                    "evidence_database_path"
                ),
                "evidence_object_root": LaunchConfiguration("evidence_object_root"),
            }],
            output="screen",
        ),
        Node(
            package="substation_reporting",
            executable="report_generator",
            name="report_generator",
            parameters=[{
                "report_work_directory": LaunchConfiguration(
                    "report_work_directory"
                ),
                "implementation_commit": LaunchConfiguration(
                    "implementation_commit"
                ),
            }],
            output="screen",
        ),
    ])
