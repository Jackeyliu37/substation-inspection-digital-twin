from __future__ import annotations

from pathlib import Path

from diagnostic_msgs.msg import DiagnosticStatus
import numpy as np
import pytest
from sensor_msgs.msg import Image

from substation_perception.model_identity import VerifiedModel
from substation_perception.placeholder_node import (
    FrameProcessor,
    LatestFrameBuffer,
    RuntimeCounters,
    make_diagnostic_status,
)
from substation_perception.yolo_backend import BackendError, RawDetection


MODULE = Path(__file__).resolve().parents[1] / "substation_perception/placeholder_node.py"


def make_image(sequence: int, encoding: str = "rgb8") -> Image:
    message = Image()
    message.header.frame_id = "camera_optical_frame"
    message.header.stamp.sec = sequence
    message.header.stamp.nanosec = sequence * 10
    message.encoding = encoding
    message.width = 16
    message.height = 12
    return message


class FakeBridge:
    def __init__(self, fail_input: bool = False, fail_output: bool = False) -> None:
        self.fail_input = fail_input
        self.fail_output = fail_output
        self.source = np.zeros((12, 16, 3), dtype=np.uint8)
        self.converted_images: list[np.ndarray] = []

    def imgmsg_to_cv2(self, message: Image, *, desired_encoding: str) -> np.ndarray:
        assert desired_encoding == "rgb8"
        if self.fail_input:
            raise ValueError("decode failed")
        return self.source

    def cv2_to_imgmsg(self, image: np.ndarray, *, encoding: str) -> Image:
        assert encoding == "rgb8"
        if self.fail_output:
            raise ValueError("encode failed")
        self.converted_images.append(image.copy())
        result = Image()
        result.encoding = encoding
        result.width = image.shape[1]
        result.height = image.shape[0]
        return result


class FakeBackend:
    def __init__(
        self,
        detections: list[RawDetection] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.detections = detections or []
        self.error = error
        self.images: list[np.ndarray] = []

    def infer(self, image: np.ndarray) -> list[RawDetection]:
        self.images.append(image)
        if self.error is not None:
            raise self.error
        return self.detections


def test_latest_frame_buffer_replaces_pending_message() -> None:
    buffer = LatestFrameBuffer()

    assert buffer.offer(make_image(1)) is False
    assert buffer.offer(make_image(2)) is True
    assert buffer.take().header.stamp.sec == 2
    assert buffer.take() is None


def test_processor_rejects_unsupported_encoding_without_output() -> None:
    processor = FrameProcessor(FakeBackend(), FakeBridge(), confidence_threshold=0.25)

    outcome = processor.process(make_image(3, encoding="bgr8"))

    assert outcome.detections is None
    assert outcome.annotated_image is None
    assert outcome.error_code == "IMAGE_ENCODING_UNSUPPORTED"


def test_processor_preserves_headers_and_filters_confidence() -> None:
    bridge = FakeBridge()
    backend = FakeBackend(
        [
            RawDetection(0, "person", 0.20, (1.0, 1.0, 4.0, 5.0)),
            RawDetection(1, "traffic light", 0.80, (5.0, 2.0, 12.0, 10.0)),
        ]
    )
    processor = FrameProcessor(backend, bridge, confidence_threshold=0.25)
    source = make_image(4)

    outcome = processor.process(source)

    assert outcome.error_code == ""
    assert outcome.detections is not None
    assert outcome.annotated_image is not None
    assert outcome.detections.header == source.header
    assert outcome.annotated_image.header == source.header
    assert outcome.annotated_image.encoding == "rgb8"
    assert len(outcome.detections.detections) == 1
    assert (
        outcome.detections.detections[0].results[0].hypothesis.class_id
        == "placeholder/coco/traffic_light"
    )
    assert np.count_nonzero(bridge.source) == 0
    assert np.count_nonzero(bridge.converted_images[0]) > 0


@pytest.mark.parametrize(
    ("bridge", "backend", "expected_code"),
    [
        (FakeBridge(fail_input=True), FakeBackend(), "IMAGE_DECODE_FAILED"),
        (
            FakeBridge(),
            FakeBackend(error=BackendError("YOLO_INFERENCE_FAILED")),
            "INFERENCE_FAILED",
        ),
        (FakeBridge(fail_output=True), FakeBackend(), "OUTPUT_INVALID"),
    ],
)
def test_frame_failure_suppresses_both_outputs(
    bridge: FakeBridge, backend: FakeBackend, expected_code: str
) -> None:
    outcome = FrameProcessor(backend, bridge, confidence_threshold=0.25).process(
        make_image(5)
    )

    assert outcome.detections is None
    assert outcome.annotated_image is None
    assert outcome.error_code == expected_code


def test_diagnostic_reports_identity_mode_counters_and_last_error(tmp_path: Path) -> None:
    identity = VerifiedModel(tmp_path / "yolo11n.pt", "a" * 64, 5613764)
    counters = RuntimeCounters(
        frames_received=8,
        frames_processed=5,
        frames_replaced=2,
        frames_failed=1,
    )

    status = make_diagnostic_status(identity, counters, "INFERENCE_FAILED")
    values = {item.key: item.value for item in status.values}

    assert status.level == DiagnosticStatus.ERROR
    assert status.message == "INFERENCE_FAILED"
    assert status.name == "substation_perception/placeholder_detector"
    assert values == {
        "runtime_mode": "development_placeholder",
        "production_ready": "false",
        "logical_model": "yolo11n_base",
        "model_sha256": "a" * 64,
        "model_size_bytes": "5613764",
        "frames_received": "8",
        "frames_processed": "5",
        "frames_replaced": "2",
        "frames_failed": "1",
        "last_error_code": "INFERENCE_FAILED",
    }


def test_module_has_no_production_or_truth_topics() -> None:
    source = MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "/perception/safety",
        "/perception/equipment",
        "/perception/defects",
        "/perception/meters",
        '"/perception/detections"',
        '"/perception/annotated_image"',
        "/simulation/scenario_truth",
    ):
        assert forbidden not in source
