from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable, UnsetEnvironmentVariable
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


MODEL_PATH = (
    "/var/lib/substation/models/base/"
    "0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1/"
    "yolo11n.pt"
)
MODEL_SHA256 = "0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1"
MODEL_SIZE_BYTES = 5613764


def generate_launch_description() -> LaunchDescription:
    gz_partition = LaunchConfiguration("gz_partition")
    return LaunchDescription(
        [
            DeclareLaunchArgument("gz_partition", default_value="substation-placeholder"),
            UnsetEnvironmentVariable("DISPLAY"),
            SetEnvironmentVariable("ROS_LOCALHOST_ONLY", "1"),
            SetEnvironmentVariable("GZ_PARTITION", gz_partition),
            Node(
                package="substation_perception",
                executable="placeholder_detector",
                name="placeholder_detector",
                output="screen",
                parameters=[
                    {
                        "model_path": MODEL_PATH,
                        "runtime_mode": "development_placeholder",
                        "logical_model": "yolo11n_base",
                        "production_ready": False,
                        "confidence_threshold": 0.25,
                        "use_sim_time": True,
                    }
                ],
            ),
        ]
    )
