from __future__ import annotations

import math
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from substation_perception.model_identity import VerifiedModel
from substation_perception.yolo_backend import BackendError, RawDetection, YoloBackend
import substation_perception.yolo_backend as yolo_backend


class FakeTensor:
    def __init__(self, values: object) -> None:
        self.values = values

    def detach(self) -> FakeTensor:
        return self

    def cpu(self) -> FakeTensor:
        return self

    def tolist(self) -> object:
        return self.values

    def item(self) -> object:
        return self.values


class FakeBoxes:
    def __init__(self, classes: object, scores: object, xyxy: object) -> None:
        self.cls = FakeTensor(classes)
        self.conf = FakeTensor(scores)
        self.xyxy = FakeTensor(xyxy)


class FakeResult:
    def __init__(
        self,
        classes: object = (4.0,),
        scores: object = (0.75,),
        xyxy: object = ((1.0, 2.0, 20.0, 22.0),),
        names: object = None,
    ) -> None:
        self.boxes = FakeBoxes(classes, scores, xyxy)
        self.names = {4: "fire extinguisher"} if names is None else names


class FakeModel:
    def __init__(self, results: list[FakeResult]) -> None:
        self.results = results
        self.calls: list[tuple[tuple[int, ...], bool, int, int]] = []

    def __call__(
        self, image: np.ndarray, *, verbose: bool, device: int, quantize: int
    ) -> list[FakeResult]:
        self.calls.append((image.shape, verbose, device, quantize))
        return self.results


@pytest.fixture
def verified_model(tmp_path: Path) -> VerifiedModel:
    path = tmp_path / "yolo11n.pt"
    path.write_bytes(b"verified")
    return VerifiedModel(path=path, sha256="1" * 64, size_bytes=8)


def _backend(
    verified_model: VerifiedModel, results: list[FakeResult]
) -> tuple[YoloBackend, list[str], FakeModel]:
    constructed_paths: list[str] = []
    model = FakeModel(results)

    def factory(path: str) -> FakeModel:
        constructed_paths.append(path)
        return model

    return YoloBackend(verified_model, model_factory=factory), constructed_paths, model


def test_inference_runtime_limits_cpu_thread_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    torch_calls: list[tuple[str, int]] = []
    cv2_calls: list[int] = []
    fake_torch = SimpleNamespace(
        set_num_threads=lambda value: torch_calls.append(("intra", value)),
        set_num_interop_threads=lambda value: torch_calls.append(("interop", value)),
    )
    fake_cv2 = SimpleNamespace(setNumThreads=lambda value: cv2_calls.append(value))
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)
    monkeypatch.setattr(yolo_backend, "_RUNTIME_CONFIGURED", False)

    yolo_backend.configure_inference_runtime()

    assert torch_calls == [("intra", 1), ("interop", 1)]
    assert cv2_calls == [1]


def test_backend_loads_once_and_returns_framework_neutral_boxes(
    verified_model: VerifiedModel,
) -> None:
    backend, constructed_paths, model = _backend(verified_model, [FakeResult()])
    image = np.zeros((32, 48, 3), dtype=np.uint8)

    first = backend.infer(image)
    second = backend.infer(image)

    assert first == [
        RawDetection(
            class_id=4,
            class_name="fire extinguisher",
            score=0.75,
            xyxy=(1.0, 2.0, 20.0, 22.0),
        )
    ]
    assert second == first
    assert constructed_paths == [str(verified_model.path)]
    assert model.calls == [
        ((32, 48, 3), False, 0, 16),
        ((32, 48, 3), False, 0, 16),
    ]


def test_classifier_uses_cuda_half_precision(verified_model: VerifiedModel) -> None:
    result = FakeResult()
    result.probs = SimpleNamespace(
        top1=4,
        top1conf=FakeTensor(0.75),
    )
    backend, _, model = _backend(verified_model, [result])

    class_name, score = yolo_backend.FaultClassifierBackend(
        verified_model,
        model_factory=backend._model_factory,
    ).classify(np.zeros((32, 48, 3), dtype=np.uint8))

    assert (class_name, score) == ("fire extinguisher", 0.75)
    assert model.calls == [((32, 48, 3), False, 0, 16)]


def test_backend_accepts_empty_boxes(verified_model: VerifiedModel) -> None:
    backend, _, _ = _backend(
        verified_model, [FakeResult(classes=(), scores=(), xyxy=())]
    )

    assert backend.infer(np.zeros((10, 10, 3), dtype=np.uint8)) == []


@pytest.mark.parametrize(
    "image",
    [
        np.zeros((10, 10), dtype=np.uint8),
        np.zeros((10, 10, 4), dtype=np.uint8),
        np.zeros((10, 10, 3), dtype=np.float32),
        np.zeros((0, 10, 3), dtype=np.uint8),
    ],
)
def test_backend_rejects_invalid_rgb_input(
    verified_model: VerifiedModel, image: np.ndarray
) -> None:
    backend, constructed_paths, _ = _backend(verified_model, [FakeResult()])

    with pytest.raises(BackendError, match="IMAGE_RGB_INVALID"):
        backend.infer(image)

    assert constructed_paths == []


@pytest.mark.parametrize("results", [[], [FakeResult(), FakeResult()]])
def test_backend_requires_exactly_one_result(
    verified_model: VerifiedModel, results: list[FakeResult]
) -> None:
    backend, _, _ = _backend(verified_model, results)

    with pytest.raises(BackendError, match="YOLO_OUTPUT_INVALID"):
        backend.infer(np.zeros((10, 10, 3), dtype=np.uint8))


@pytest.mark.parametrize(
    "result",
    [
        FakeResult(classes=(9.0,)),
        FakeResult(classes=(4.0, 4.0), scores=(0.75,)),
        FakeResult(scores=(math.nan,)),
        FakeResult(xyxy=((1.0, 2.0, math.inf, 4.0),)),
        FakeResult(xyxy=((1.0, 2.0, 3.0),)),
        FakeResult(classes=(4.5,)),
        FakeResult(names=[]),
    ],
)
def test_backend_rejects_malformed_output(
    verified_model: VerifiedModel, result: FakeResult
) -> None:
    backend, _, _ = _backend(verified_model, [result])

    with pytest.raises(BackendError, match="YOLO_OUTPUT_INVALID"):
        backend.infer(np.zeros((10, 10, 3), dtype=np.uint8))
