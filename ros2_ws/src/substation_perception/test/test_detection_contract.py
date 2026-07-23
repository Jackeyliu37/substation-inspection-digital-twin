from __future__ import annotations

import math

import pytest
from std_msgs.msg import Header

from substation_perception.detection_contract import (
    DetectionContractError,
    normalize_class_name,
    to_development_detections,
)
from substation_perception.yolo_backend import RawDetection


def _raw(
    *,
    class_name: str = "person",
    score: float = 0.75,
    xyxy: tuple[float, ...] = (1.0, 2.0, 20.0, 22.0),
) -> RawDetection:
    return RawDetection(class_id=0, class_name=class_name, score=score, xyxy=xyxy)


def test_conversion_preserves_header_clips_box_and_prefixes_class() -> None:
    header = Header(frame_id="camera_optical_frame")
    header.stamp.sec = 17
    header.stamp.nanosec = 42

    output = to_development_detections(
        header,
        image_width=100,
        image_height=80,
        detections=[
            _raw(
                class_name="Fire Extinguisher",
                xyxy=(-5.0, 5.0, 120.0, 60.0),
            )
        ],
    )

    assert output.header == header
    assert len(output.detections) == 1
    item = output.detections[0]
    assert item.header == header
    assert item.id == "development-000000"
    assert item.bbox.center.position.x == 50.0
    assert item.bbox.center.position.y == 32.5
    assert item.bbox.center.theta == 0.0
    assert item.bbox.size_x == 100.0
    assert item.bbox.size_y == 55.0
    assert len(item.results) == 1
    assert (
        item.results[0].hypothesis.class_id
        == "placeholder/coco/fire_extinguisher"
    )
    assert item.results[0].hypothesis.score == 0.75


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (" Fire Extinguisher ", "fire_extinguisher"),
        ("traffic--light", "traffic_light"),
        ("Potted_Plant", "potted_plant"),
        ("123", "123"),
        ("***", ""),
    ],
)
def test_class_name_normalization_is_deterministic(
    source: str, expected: str
) -> None:
    assert normalize_class_name(source) == expected


@pytest.mark.parametrize(
    "candidate",
    [
        _raw(class_name=""),
        _raw(class_name="***"),
        _raw(score=-0.01),
        _raw(score=1.01),
        _raw(score=math.nan),
        _raw(xyxy=(math.inf, 1.0, 5.0, 5.0)),
        _raw(xyxy=(8.0, 8.0, 2.0, 2.0)),
        _raw(xyxy=(-5.0, 1.0, -1.0, 5.0)),
        _raw(xyxy=(1.0, 11.0, 5.0, 15.0)),
        _raw(xyxy=(1.0, 2.0, 3.0)),
    ],
)
def test_conversion_omits_invalid_candidate(candidate: RawDetection) -> None:
    output = to_development_detections(
        Header(), image_width=10, image_height=10, detections=[candidate]
    )

    assert output.detections == []


@pytest.mark.parametrize(("width", "height"), [(0, 10), (10, 0), (-1, 10)])
def test_conversion_rejects_non_positive_image_dimensions(
    width: int, height: int
) -> None:
    with pytest.raises(DetectionContractError, match="IMAGE_DIMENSIONS_INVALID"):
        to_development_detections(Header(), width, height, [])


def test_ids_track_source_candidate_order_without_production_semantics() -> None:
    output = to_development_detections(
        Header(),
        image_width=30,
        image_height=30,
        detections=[_raw(score=math.nan), _raw(class_name="person")],
    )

    assert output.detections[0].id == "development-000001"
    hypothesis = output.detections[0].results[0].hypothesis
    assert hypothesis.class_id == "placeholder/coco/person"
    assert not hypothesis.class_id.startswith(
        ("safety/", "equipment/", "defect/", "meter/")
    )
