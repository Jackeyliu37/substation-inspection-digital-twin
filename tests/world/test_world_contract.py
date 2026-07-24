from __future__ import annotations

import ast
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
DESCRIPTION = ROOT / "ros2_ws/src/substation_description"
GAZEBO = ROOT / "ros2_ws/src/substation_gazebo"


def required_file(relative: str) -> Path:
    path = ROOT / relative
    assert path.is_file(), f"required Phase 2 file is missing: {relative}"
    return path


def test_world_contains_registered_assets_and_layout() -> None:
    devices = yaml.safe_load(required_file("configs/devices.yaml").read_text(encoding="utf-8"))
    world = ET.parse(
        required_file("ros2_ws/src/substation_gazebo/worlds/substation_world.sdf")
    )
    model_names = {model.attrib["name"] for model in world.findall(".//model[@name]")}
    assert {asset["asset_id"] for asset in devices["assets"]}.issubset(model_names)
    assert {
        "inspection_lane_ns",
        "inspection_lane_ew",
        "transformer_exclusion_zone",
        "static_pallets",
        "scenario_dynamic_obstacle",
        "scenario_person_no_hardhat",
        "scenario_smoke",
        "scenario_fire",
        "scenario_unreachable_blocker",
    }.issubset(model_names)
    assert len(world.findall(".//world/model[@name='perimeter_wall']/link/collision")) >= 4
    plugins = {plugin.attrib.get("filename") for plugin in world.findall(".//world/plugin")}
    assert {
        "gz-sim-physics-system",
        "gz-sim-sensors-system",
        "gz-sim-scene-broadcaster-system",
        "gz-sim-user-commands-system",
    }.issubset(plugins)
    assert world.find(".//plugin[@filename='gz-sim-sensors-system']/render_engine").text == "ogre2"


def test_world_uses_100_hz_physics_clock() -> None:
    world = ET.parse(
        required_file("ros2_ws/src/substation_gazebo/worlds/substation_world.sdf")
    )
    physics = world.find(".//world/physics")

    assert physics is not None
    assert physics.findtext("max_step_size") == "0.01"
    assert physics.findtext("real_time_factor") == "1.0"


def test_every_sdf_link_child_entity_name_is_unique() -> None:
    for relative in (
        "ros2_ws/src/substation_gazebo/worlds/substation_world.sdf",
        "ros2_ws/src/substation_gazebo/models/inspection_robot/model.sdf",
    ):
        tree = ET.parse(required_file(relative))
        for link in tree.findall(".//link"):
            names = [
                child.attrib["name"]
                for child in link
                if child.tag in {"collision", "visual", "sensor"}
            ]
            assert len(names) == len(set(names)), (
                f"duplicate child entity name in {relative}:{link.attrib['name']}: {names}"
            )


def test_robot_sensor_and_drive_contract() -> None:
    robot = ET.parse(
        required_file(
            "ros2_ws/src/substation_gazebo/models/inspection_robot/model.sdf"
        )
    )
    camera = robot.find(".//sensor[@type='camera']")
    assert camera is not None
    assert camera.findtext("topic") == "camera/image_raw"
    assert camera.findtext("gz_frame_id") == "camera_optical_frame"
    assert camera.findtext("update_rate") == "15"
    assert camera.findtext("camera/image/width") == "640"
    assert camera.findtext("camera/image/height") == "480"
    assert camera.findtext("camera/image/format") == "R8G8B8"

    lidar = robot.find(".//sensor[@type='gpu_lidar']")
    assert lidar is not None
    assert lidar.findtext("topic") == "scan"
    assert lidar.findtext("gz_frame_id") == "laser_frame"
    assert lidar.findtext("update_rate") == "10"
    assert lidar.findtext("ray/scan/horizontal/samples") == "360"
    assert lidar.findtext("ray/range/min") == "0.12"
    assert lidar.findtext("ray/range/max") == "10.0"

    laser_pose = [
        float(value)
        for value in robot.find(".//link[@name='laser_frame']/pose").text.split()
    ]
    base_collision = robot.find(
        ".//link[@name='base_link']/collision[@name='base_collision']"
    )
    base_collision_pose = [
        float(value) for value in base_collision.findtext("pose").split()
    ]
    base_collision_size = [
        float(value) for value in base_collision.findtext("geometry/box/size").split()
    ]
    assert laser_pose[2] > base_collision_pose[2] + base_collision_size[2] / 2.0

    description = ET.parse(
        required_file(
            "ros2_ws/src/substation_description/urdf/inspection_robot.urdf.xacro"
        )
    )
    laser_origin = description.find(".//joint[@name='laser_joint']/origin")
    assert laser_origin is not None
    assert [float(value) for value in laser_origin.attrib["xyz"].split()] == laser_pose[:3]

    drive = robot.find(".//plugin[@filename='gz-sim-diff-drive-system']")
    assert drive is not None
    assert drive.findtext("topic") == "cmd_vel"
    assert drive.findtext("odom_topic") == "odom"
    assert drive.findtext("frame_id") == "odom"
    assert drive.findtext("child_frame_id") == "base_footprint"
    assert drive.findtext("odom_publisher_frequency") == "30"

    world = ET.parse(
        required_file("ros2_ws/src/substation_gazebo/worlds/substation_world.sdf")
    )
    ground = world.find(".//world/model[@name='yard_ground']/link/collision")
    robot_include = world.find(".//world/include[name='inspection_robot']/pose")
    model_pose = robot.findtext("model/pose")
    base_link_pose = robot.findtext(".//link[@name='base_link']/pose")
    wheel_pose = robot.findtext(".//link[@name='wheel_left_link']/pose")
    wheel_radius = float(
        robot.findtext(
            ".//link[@name='wheel_left_link']/collision/geometry/cylinder/radius"
        )
    )
    ground_size_z = float(ground.findtext("geometry/box/size").split()[2])
    ground_top = ground_size_z / 2.0
    assert [float(value) for value in model_pose.split()][2] == 0.0
    assert float(robot_include.text.split()[2]) == ground_top
    base_z = float(base_link_pose.split()[2])
    wheel_z = float(wheel_pose.split()[2])
    assert abs(base_z + wheel_z - wheel_radius) < 1e-6


def test_bridge_has_exact_core_topics_and_directions() -> None:
    bridge = yaml.safe_load(
        required_file("ros2_ws/src/substation_gazebo/config/bridge.yaml").read_text(
            encoding="utf-8"
        )
    )
    by_topic = {row["ros_topic_name"]: row for row in bridge}
    assert set(by_topic) == {
        "clock",
        "joint_states",
        "odom",
        "tf",
        "cmd_vel",
        "scan",
        "camera/camera_info",
    }
    assert by_topic["clock"] == {
        "ros_topic_name": "clock",
        "gz_topic_name": "clock",
        "ros_type_name": "rosgraph_msgs/msg/Clock",
        "gz_type_name": "gz.msgs.Clock",
        "direction": "GZ_TO_ROS",
        "qos_profile": "CLOCK",
    }
    assert by_topic["scan"]["ros_type_name"] == "sensor_msgs/msg/LaserScan"
    assert by_topic["cmd_vel"]["direction"] == "ROS_TO_GZ"


def test_robot_description_has_contract_frames_with_unique_parents() -> None:
    xacro = required_file(
        "ros2_ws/src/substation_description/urdf/inspection_robot.urdf.xacro"
    ).read_text(encoding="utf-8")
    for frame in (
        "base_footprint",
        "base_link",
        "camera_link",
        "camera_optical_frame",
        "laser_frame",
    ):
        assert len(re.findall(rf'<link\s+name="{re.escape(frame)}"', xacro)) == 1
    assert '<parent link="camera_link"/>' in xacro
    assert '<child link="camera_optical_frame"/>' in xacro
    assert 'rpy="-1.57079632679 0 -1.57079632679"' in xacro


def test_asset_tf_broadcaster_uses_rclpy_logger_signature() -> None:
    source = required_file(
        "ros2_ws/src/substation_description/substation_description/asset_tf_broadcaster.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    info_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "info"
    ]
    assert info_calls
    assert all(len(call.args) == 1 for call in info_calls)
