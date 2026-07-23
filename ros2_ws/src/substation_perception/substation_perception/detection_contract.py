from __future__ import annotations

from collections.abc import Sequence
import math
import re

from std_msgs.msg import Header
from vision_msgs.msg import Detection2D, Detection2DArray, ObjectHypothesisWithPose

from .yolo_backend import RawDetection


class DetectionContractError(ValueError):
    """Raised when frame metadata cannot define valid detection messages."""


def normalize_class_name(class_name: str) -> str:
    if not isinstance(class_name, str):
        return ""
    return re.sub(r"[^a-z0-9]+", "_", class_name.strip().lower()).strip("_")


def _valid_score(score: object) -> bool:
    try:
        value = float(score)
    except (TypeError, ValueError):
        return False
    return math.isfinite(value) and 0.0 <= value <= 1.0


def _clip_xyxy(
    xyxy: object, image_width: int, image_height: int
) -> tuple[float, float, float, float] | None:
    if not isinstance(xyxy, Sequence) or isinstance(xyxy, (str, bytes)):
        return None
    if len(xyxy) != 4:
        return None
    try:
        x1, y1, x2, y2 = (float(value) for value in xyxy)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in (x1, y1, x2, y2)):
        return None
    if x2 <= x1 or y2 <= y1:
        return None

    x1 = min(max(x1, 0.0), float(image_width))
    y1 = min(max(y1, 0.0), float(image_height))
    x2 = min(max(x2, 0.0), float(image_width))
    y2 = min(max(y2, 0.0), float(image_height))
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def to_development_detections(
    header: Header,
    image_width: int,
    image_height: int,
    detections: Sequence[RawDetection],
) -> Detection2DArray:
    if image_width <= 0 or image_height <= 0:
        raise DetectionContractError("IMAGE_DIMENSIONS_INVALID")

    output = Detection2DArray()
    output.header = header
    for ordinal, candidate in enumerate(detections):
        class_name = normalize_class_name(candidate.class_name)
        bounded = _clip_xyxy(candidate.xyxy, image_width, image_height)
        if not class_name or not _valid_score(candidate.score) or bounded is None:
            continue

        x1, y1, x2, y2 = bounded
        item = Detection2D()
        item.header = header
        item.id = f"development-{ordinal:06d}"
        item.bbox.center.position.x = (x1 + x2) / 2.0
        item.bbox.center.position.y = (y1 + y2) / 2.0
        item.bbox.center.theta = 0.0
        item.bbox.size_x = x2 - x1
        item.bbox.size_y = y2 - y1

        hypothesis = ObjectHypothesisWithPose()
        hypothesis.hypothesis.class_id = f"placeholder/coco/{class_name}"
        hypothesis.hypothesis.score = float(candidate.score)
        item.results.append(hypothesis)
        output.detections.append(item)
    return output
