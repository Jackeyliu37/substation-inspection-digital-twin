from __future__ import annotations

from dataclasses import dataclass
import math


class MeterDatasetProjectionError(ValueError):
    pass


def _fail(code: str, detail: str) -> None:
    raise MeterDatasetProjectionError(f"{code}: {detail}")


@dataclass(frozen=True)
class CameraIntrinsics:
    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float


@dataclass(frozen=True)
class Pose3D:
    x: float
    y: float
    z: float
    roll: float
    pitch: float
    yaw: float


@dataclass(frozen=True)
class BoundingBox:
    x_min: float
    y_min: float
    x_max: float
    y_max: float


@dataclass(frozen=True)
class Projection:
    bbox_pixels: BoundingBox
    bbox_yolo: tuple[float, float, float, float]
    dial_corners_pixels: tuple[tuple[float, float], ...]


def _rotation(roll: float, pitch: float, yaw: float) -> tuple[tuple[float, ...], ...]:
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return (
        (cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr),
        (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr),
        (-sp, cp * sr, cp * cr),
    )


def project_dial(
    intrinsics: CameraIntrinsics,
    pose_camera: Pose3D,
    radius_m: float,
    boundary_points: int = 64,
) -> Projection:
    if boundary_points < 8 or radius_m <= 0.0:
        _fail("PROJECTION_INPUT_INVALID", "radius or boundary_points")
    matrix = _rotation(pose_camera.roll, pose_camera.pitch, pose_camera.yaw)
    pixels: list[tuple[float, float]] = []
    for index in range(boundary_points):
        angle = 2.0 * math.pi * index / boundary_points
        local = (radius_m * math.cos(angle), radius_m * math.sin(angle), 0.0)
        x = pose_camera.x + sum(matrix[0][axis] * local[axis] for axis in range(3))
        y = pose_camera.y + sum(matrix[1][axis] * local[axis] for axis in range(3))
        z = pose_camera.z + sum(matrix[2][axis] * local[axis] for axis in range(3))
        if z <= 0.0 or not all(math.isfinite(value) for value in (x, y, z)):
            _fail("PROJECTION_BEHIND_CAMERA", f"point={index}")
        pixels.append((intrinsics.fx * x / z + intrinsics.cx, intrinsics.fy * y / z + intrinsics.cy))
    x_values = [item[0] for item in pixels]
    y_values = [item[1] for item in pixels]
    bbox = BoundingBox(min(x_values), min(y_values), max(x_values), max(y_values))
    center_x = (bbox.x_min + bbox.x_max) / 2.0 / intrinsics.width
    center_y = (bbox.y_min + bbox.y_max) / 2.0 / intrinsics.height
    width = (bbox.x_max - bbox.x_min) / intrinsics.width
    height = (bbox.y_max - bbox.y_min) / intrinsics.height
    corners = tuple(pixels[index] for index in (0, boundary_points // 4, boundary_points // 2, 3 * boundary_points // 4))
    return Projection(bbox_pixels=bbox, bbox_yolo=(center_x, center_y, width, height), dial_corners_pixels=corners)


def validate_projection(projection: Projection, minimum_bbox_pixels: int) -> None:
    bbox = projection.bbox_pixels
    values = (bbox.x_min, bbox.y_min, bbox.x_max, bbox.y_max, *projection.bbox_yolo)
    if not all(math.isfinite(value) for value in values):
        _fail("PROJECTION_NOT_FINITE", repr(values))
    width = bbox.x_max - bbox.x_min
    height = bbox.y_max - bbox.y_min
    if width < minimum_bbox_pixels or height < minimum_bbox_pixels:
        _fail("PROJECTION_TOO_SMALL", f"{width}x{height}")
    if bbox.x_min < 0.0 or bbox.y_min < 0.0:
        _fail("PROJECTION_OUTSIDE_IMAGE", repr(bbox))
    center_x, center_y, normalized_width, normalized_height = projection.bbox_yolo
    if not (
        0.0 < center_x < 1.0
        and 0.0 < center_y < 1.0
        and 0.0 < normalized_width <= 1.0
        and 0.0 < normalized_height <= 1.0
        and center_x - normalized_width / 2.0 >= 0.0
        and center_x + normalized_width / 2.0 <= 1.0
        and center_y - normalized_height / 2.0 >= 0.0
        and center_y + normalized_height / 2.0 <= 1.0
    ):
        _fail("PROJECTION_OUTSIDE_IMAGE", repr(projection.bbox_yolo))
