from __future__ import annotations

import importlib
import math
from pathlib import Path
import sys

import pytest
import yaml


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ROOT = PACKAGE_ROOT.parents[2]
MODULE_PATH = PACKAGE_ROOT / "substation_gazebo/inspection_poses.py"
MAP_PATH = PACKAGE_ROOT / "maps/substation.yaml"
DEVICES_PATH = ROOT / "configs/devices.yaml"
SLAM_PATH = PACKAGE_ROOT / "config/slam_toolbox.yaml"
NAV2_PATH = PACKAGE_ROOT / "config/nav2_params.yaml"


def load_module():
    assert MODULE_PATH.is_file(), "inspection_poses.py must exist"
    sys.path.insert(0, str(PACKAGE_ROOT))
    sys.path.insert(0, str(ROOT / "ros2_ws/src/substation_description"))
    return importlib.import_module("substation_gazebo.inspection_poses")


def test_static_map_has_phase_three_world_geometry() -> None:
    assert MAP_PATH.is_file(), "substation.yaml must exist"
    data = yaml.safe_load(MAP_PATH.read_text(encoding="utf-8"))
    assert data == {
        "image": "substation.pgm",
        "mode": "trinary",
        "resolution": 0.05,
        "origin": [-8.0, -6.0, 0.0],
        "negate": 0,
        "occupied_thresh": 0.65,
        "free_thresh": 0.25,
    }
    image = MAP_PATH.with_name(data["image"])
    assert image.is_file(), "substation.pgm must exist"
    header = image.read_bytes().split(maxsplit=4)[:4]
    assert header == [b"P5", b"320", b"240", b"255"]


def test_navigation_configuration_has_single_transform_owner_per_mode() -> None:
    assert SLAM_PATH.is_file(), "slam_toolbox.yaml must exist"
    assert NAV2_PATH.is_file(), "nav2_params.yaml must exist"
    slam = yaml.safe_load(SLAM_PATH.read_text(encoding="utf-8"))["slam_toolbox"][
        "ros__parameters"
    ]
    nav2 = yaml.safe_load(NAV2_PATH.read_text(encoding="utf-8"))
    assert slam["map_frame"] == "map"
    assert slam["odom_frame"] == "odom"
    assert slam["base_frame"] == "base_footprint"
    assert slam["scan_topic"] == "/scan"
    assert slam["mode"] == "mapping"
    assert nav2["amcl"]["ros__parameters"]["global_frame_id"] == "map"
    assert nav2["amcl"]["ros__parameters"]["odom_frame_id"] == "odom"
    assert nav2["local_costmap"]["local_costmap"]["ros__parameters"][
        "observation_sources"
    ] == "scan"
    assert nav2["local_costmap"]["local_costmap"]["ros__parameters"][
        "obstacle_layer"
    ]["scan"]["topic"] == "/scan"
    controller = nav2["controller_server"]["ros__parameters"]
    assert controller["progress_checker"]["movement_time_allowance"] == 30.0
    assert controller["FollowPath"]["plugin"] == (
        "nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController"
    )
    assert controller["FollowPath"]["desired_linear_vel"] == 0.22
    assert controller["FollowPath"]["use_rotate_to_heading"] is True


def test_every_registered_asset_has_free_map_inspection_pose() -> None:
    module = load_module()
    poses = module.load_inspection_poses(DEVICES_PATH, MAP_PATH)
    registered = yaml.safe_load(DEVICES_PATH.read_text(encoding="utf-8"))["assets"]
    assert list(poses) == sorted(asset["asset_id"] for asset in registered)
    for pose in poses.values():
        assert pose.frame_id == "map"
        assert math.isfinite(pose.x)
        assert math.isfinite(pose.y)
        assert math.isfinite(pose.yaw)
        assert module.is_free_for_robot(pose, MAP_PATH)


def test_unknown_asset_pose_is_rejected() -> None:
    module = load_module()
    poses = module.load_inspection_poses(DEVICES_PATH, MAP_PATH)
    with pytest.raises(module.InspectionPoseError, match="INSPECTION_POSE_UNKNOWN"):
        module.pose_stamped("not-a-device", poses, stamp_sec=42, stamp_nanosec=7)


def test_pose_stamped_has_map_frame_and_normalized_quaternion() -> None:
    module = load_module()
    poses = module.load_inspection_poses(DEVICES_PATH, MAP_PATH)
    message = module.pose_stamped(
        "breaker-01", poses, stamp_sec=42, stamp_nanosec=7
    )
    assert message.header.frame_id == "map"
    assert (message.header.stamp.sec, message.header.stamp.nanosec) == (42, 7)
    assert (message.pose.position.x, message.pose.position.y) == (0.5, 1.8)
    assert math.isclose(
        message.pose.orientation.z, math.sin(math.pi / 4), abs_tol=1e-12
    )
    assert math.isclose(
        message.pose.orientation.w, math.cos(math.pi / 4), abs_tol=1e-12
    )
