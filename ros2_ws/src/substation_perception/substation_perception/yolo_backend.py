from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import math
from typing import Any

import numpy as np

from .model_identity import VerifiedModel


class BackendError(RuntimeError):
    """Raised when the YOLO backend cannot produce a valid result."""


@dataclass(frozen=True)
class RawDetection:
    class_id: int
    class_name: str
    score: float
    xyxy: tuple[float, float, float, float]


def _tensor_values(value: object) -> list[Any]:
    try:
        detached = value.detach()  # type: ignore[attr-defined]
        on_cpu = detached.cpu()
        values = on_cpu.tolist()
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        raise BackendError("YOLO_OUTPUT_INVALID") from error
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise BackendError("YOLO_OUTPUT_INVALID")
    return list(values)


def _parse_single_result(results: object) -> list[RawDetection]:
    if not isinstance(results, Sequence) or isinstance(results, (str, bytes)):
        raise BackendError("YOLO_OUTPUT_INVALID")
    if len(results) != 1:
        raise BackendError("YOLO_OUTPUT_INVALID")

    result = results[0]
    try:
        boxes = result.boxes
        names = result.names
        classes = _tensor_values(boxes.cls)
        scores = _tensor_values(boxes.conf)
        coordinates = _tensor_values(boxes.xyxy)
    except (AttributeError, TypeError) as error:
        raise BackendError("YOLO_OUTPUT_INVALID") from error

    if not isinstance(names, Mapping):
        raise BackendError("YOLO_OUTPUT_INVALID")
    if not (len(classes) == len(scores) == len(coordinates)):
        raise BackendError("YOLO_OUTPUT_INVALID")

    parsed: list[RawDetection] = []
    for raw_class, raw_score, raw_xyxy in zip(classes, scores, coordinates, strict=True):
        try:
            class_value = float(raw_class)
            score = float(raw_score)
            xyxy_values = tuple(float(value) for value in raw_xyxy)
        except (TypeError, ValueError) as error:
            raise BackendError("YOLO_OUTPUT_INVALID") from error
        if (
            not math.isfinite(class_value)
            or not class_value.is_integer()
            or not math.isfinite(score)
            or len(xyxy_values) != 4
            or not all(math.isfinite(value) for value in xyxy_values)
        ):
            raise BackendError("YOLO_OUTPUT_INVALID")

        class_id = int(class_value)
        class_name = names.get(class_id)
        if not isinstance(class_name, str) or not class_name.strip():
            raise BackendError("YOLO_OUTPUT_INVALID")
        parsed.append(
            RawDetection(
                class_id=class_id,
                class_name=class_name,
                score=score,
                xyxy=xyxy_values,
            )
        )
    return parsed


class YoloBackend:
    def __init__(
        self,
        identity: VerifiedModel,
        model_factory: Callable[[str], object] | None = None,
    ) -> None:
        self._identity = identity
        self._model_factory = model_factory
        self._loaded_model: object | None = None

    def _model(self) -> object:
        if self._loaded_model is None:
            factory = self._model_factory
            if factory is None:
                from ultralytics import YOLO

                factory = YOLO
            try:
                self._loaded_model = factory(str(self._identity.path))
            except Exception as error:
                raise BackendError("YOLO_LOAD_FAILED") from error
        return self._loaded_model

    def infer(self, image_rgb: np.ndarray) -> list[RawDetection]:
        if (
            not isinstance(image_rgb, np.ndarray)
            or image_rgb.dtype != np.uint8
            or image_rgb.ndim != 3
            or image_rgb.shape[2] != 3
            or image_rgb.shape[0] <= 0
            or image_rgb.shape[1] <= 0
        ):
            raise BackendError("IMAGE_RGB_INVALID")

        model = self._model()
        try:
            results = model(image_rgb, verbose=False)  # type: ignore[operator]
        except BackendError:
            raise
        except Exception as error:
            raise BackendError("YOLO_INFERENCE_FAILED") from error
        return _parse_single_result(results)
