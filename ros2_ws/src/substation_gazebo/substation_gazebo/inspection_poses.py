from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Mapping

import yaml
from geometry_msgs.msg import PoseStamped

from substation_description.asset_registry import load_asset_registry


ROBOT_CLEARANCE_M = 0.25


class InspectionPoseError(ValueError):
    """Inspection-pose contract failure."""


@dataclass(frozen=True)
class InspectionPose:
    asset_id: str
    frame_id: str
    x: float
    y: float
    yaw: float


def _read_pgm(path: Path) -> tuple[int, int, bytes]:
    payload = path.read_bytes()
    try:
        magic, dimensions, maximum, pixels = payload.split(b"\n", 3)
        width, height = (int(value) for value in dimensions.split())
    except (ValueError, OSError) as error:
        raise InspectionPoseError(f"MAP_IMAGE_INVALID: {path}") from error
    if magic != b"P5" or maximum != b"255" or len(pixels) != width * height:
        raise InspectionPoseError(f"MAP_IMAGE_INVALID: {path}")
    return width, height, pixels


def _map_data(map_path: Path) -> tuple[float, float, float, int, int, bytes]:
    try:
        config = yaml.safe_load(map_path.read_text(encoding="utf-8"))
        image = config["image"]
        resolution = float(config["resolution"])
        origin_x, origin_y, _ = config["origin"]
        width, height, pixels = _read_pgm(map_path.with_name(image))
    except (KeyError, OSError, TypeError, ValueError, yaml.YAMLError) as error:
        raise InspectionPoseError(f"MAP_CONFIG_INVALID: {map_path}") from error
    if not math.isfinite(resolution) or resolution <= 0.0:
        raise InspectionPoseError(f"MAP_CONFIG_INVALID: {map_path}")
    return float(origin_x), float(origin_y), resolution, width, height, pixels


def is_free_for_robot(pose: InspectionPose, map_path: Path) -> bool:
    origin_x, origin_y, resolution, width, height, pixels = _map_data(map_path)
    radius_cells = math.ceil(ROBOT_CLEARANCE_M / resolution)
    center_x = int((pose.x - origin_x) / resolution)
    center_y = height - 1 - int((pose.y - origin_y) / resolution)
    for row in range(center_y - radius_cells, center_y + radius_cells + 1):
        for column in range(center_x - radius_cells, center_x + radius_cells + 1):
            if not (0 <= row < height and 0 <= column < width):
                return False
            if math.hypot(row - center_y, column - center_x) > radius_cells:
                continue
            if pixels[row * width + column] < 166:
                return False
    return True


def load_inspection_poses(
    devices_path: Path, map_path: Path
) -> dict[str, InspectionPose]:
    registry = load_asset_registry(devices_path)
    poses: dict[str, InspectionPose] = {}
    for asset in registry.assets:
        pose = InspectionPose(
            asset_id=asset.asset_id,
            frame_id="map",
            x=asset.inspection_x,
            y=asset.inspection_y,
            yaw=asset.inspection_yaw,
        )
        if not is_free_for_robot(pose, map_path):
            raise InspectionPoseError(f"INSPECTION_POSE_NOT_FREE: {asset.asset_id}")
        poses[asset.asset_id] = pose
    return poses


def pose_stamped(
    asset_id: str,
    poses: Mapping[str, InspectionPose],
    *,
    stamp_sec: int,
    stamp_nanosec: int,
) -> PoseStamped:
    try:
        pose = poses[asset_id]
    except KeyError as error:
        raise InspectionPoseError(f"INSPECTION_POSE_UNKNOWN: {asset_id}") from error
    message = PoseStamped()
    message.header.frame_id = pose.frame_id
    message.header.stamp.sec = stamp_sec
    message.header.stamp.nanosec = stamp_nanosec
    message.pose.position.x = pose.x
    message.pose.position.y = pose.y
    message.pose.orientation.z = math.sin(pose.yaw / 2.0)
    message.pose.orientation.w = math.cos(pose.yaw / 2.0)
    return message
