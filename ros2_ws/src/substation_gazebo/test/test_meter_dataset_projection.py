from __future__ import annotations

import pytest

from substation_gazebo.meter_dataset_projection import (
    CameraIntrinsics,
    MeterDatasetProjectionError,
    Pose3D,
    project_dial,
    validate_projection,
)


INTRINSICS = CameraIntrinsics(
    width=640,
    height=480,
    fx=500.0,
    fy=500.0,
    cx=320.0,
    cy=240.0,
)


def test_centered_dial_projects_inside_image_and_distance_reduces_box() -> None:
    near = project_dial(INTRINSICS, Pose3D(0.0, 0.0, 1.0, 0.0, 0.0, 0.0), 0.18)
    far = project_dial(INTRINSICS, Pose3D(0.0, 0.0, 1.5, 0.0, 0.0, 0.0), 0.18)
    validate_projection(near, minimum_bbox_pixels=32)
    near_width = near.bbox_pixels.x_max - near.bbox_pixels.x_min
    far_width = far.bbox_pixels.x_max - far.bbox_pixels.x_min
    assert near.bbox_pixels.x_min < 320 < near.bbox_pixels.x_max
    assert near.bbox_pixels.y_min < 240 < near.bbox_pixels.y_max
    assert near_width > far_width
    assert all(0.0 < value <= 1.0 for value in near.bbox_yolo)


def test_tilt_changes_projected_corner_geometry() -> None:
    flat = project_dial(INTRINSICS, Pose3D(0.0, 0.0, 1.0, 0.0, 0.0, 0.0), 0.18)
    tilted = project_dial(INTRINSICS, Pose3D(0.0, 0.0, 1.0, 0.25, -0.35, 0.0), 0.18)
    assert flat.dial_corners_pixels != tilted.dial_corners_pixels


def test_projection_behind_camera_is_rejected() -> None:
    with pytest.raises(MeterDatasetProjectionError, match="PROJECTION_BEHIND_CAMERA"):
        project_dial(INTRINSICS, Pose3D(0.0, 0.0, -1.0, 0.0, 0.0, 0.0), 0.18)


def test_projection_below_minimum_size_is_rejected() -> None:
    tiny = project_dial(INTRINSICS, Pose3D(0.0, 0.0, 10.0, 0.0, 0.0, 0.0), 0.18)
    with pytest.raises(MeterDatasetProjectionError, match="PROJECTION_TOO_SMALL"):
        validate_projection(tiny, minimum_bbox_pixels=32)
