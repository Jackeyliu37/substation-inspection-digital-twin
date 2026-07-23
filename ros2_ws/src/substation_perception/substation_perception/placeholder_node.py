from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Condition, Event, Lock, Thread

from cv_bridge import CvBridge
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2DArray

from .detection_contract import to_development_detections
from .model_identity import VerifiedModel, verify_development_placeholder
from .yolo_backend import RawDetection, YoloBackend


MODEL_PATH = Path(
    "/var/lib/substation/models/base/"
    "0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1/"
    "yolo11n.pt"
)
MODEL_SHA256 = "0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1"
MODEL_SIZE_BYTES = 5613764


@dataclass(frozen=True)
class FrameOutcome:
    detections: Detection2DArray | None
    annotated_image: Image | None
    error_code: str


@dataclass
class RuntimeCounters:
    frames_received: int = 0
    frames_processed: int = 0
    frames_replaced: int = 0
    frames_failed: int = 0


class LatestFrameBuffer:
    def __init__(self) -> None:
        self._condition = Condition()
        self._pending: Image | None = None

    def offer(self, message: Image) -> bool:
        with self._condition:
            replaced = self._pending is not None
            self._pending = message
            self._condition.notify()
            return replaced

    def take(self) -> Image | None:
        with self._condition:
            message, self._pending = self._pending, None
            return message

    def wait_and_take(self, stop: Event) -> Image | None:
        with self._condition:
            while self._pending is None and not stop.is_set():
                self._condition.wait(timeout=0.25)
            message, self._pending = self._pending, None
            return message

    def wake(self) -> None:
        with self._condition:
            self._condition.notify_all()


class FrameProcessor:
    def __init__(
        self,
        backend: object,
        bridge: object,
        confidence_threshold: float,
    ) -> None:
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError("CONFIDENCE_THRESHOLD_INVALID")
        self._backend = backend
        self._bridge = bridge
        self._confidence_threshold = confidence_threshold

    def process(self, message: Image) -> FrameOutcome:
        if message.encoding != "rgb8":
            return FrameOutcome(None, None, "IMAGE_ENCODING_UNSUPPORTED")
        try:
            decoded = self._bridge.imgmsg_to_cv2(message, desired_encoding="rgb8")
            image_rgb = np.asarray(decoded)
        except Exception:
            return FrameOutcome(None, None, "IMAGE_DECODE_FAILED")

        try:
            raw_detections = self._backend.infer(image_rgb)
        except Exception:
            return FrameOutcome(None, None, "INFERENCE_FAILED")

        selected = [
            candidate
            for candidate in raw_detections
            if candidate.score >= self._confidence_threshold
        ]
        try:
            detections = to_development_detections(
                message.header,
                image_width=image_rgb.shape[1],
                image_height=image_rgb.shape[0],
                detections=selected,
            )
            annotated = self._annotate(image_rgb, detections, selected)
            annotated_message = self._bridge.cv2_to_imgmsg(annotated, encoding="rgb8")
            annotated_message.header = message.header
        except Exception:
            return FrameOutcome(None, None, "OUTPUT_INVALID")
        return FrameOutcome(detections, annotated_message, "")

    @staticmethod
    def _annotate(
        image_rgb: np.ndarray,
        detections: Detection2DArray,
        selected: list[RawDetection],
    ) -> np.ndarray:
        annotated = image_rgb.copy()
        accepted_by_id = {
            f"development-{ordinal:06d}": candidate
            for ordinal, candidate in enumerate(selected)
        }
        for detection in detections.detections:
            candidate = accepted_by_id.get(detection.id)
            if candidate is None:
                continue
            center = detection.bbox.center.position
            half_width = detection.bbox.size_x / 2.0
            half_height = detection.bbox.size_y / 2.0
            top_left = (int(center.x - half_width), int(center.y - half_height))
            bottom_right = (int(center.x + half_width), int(center.y + half_height))
            cv2.rectangle(annotated, top_left, bottom_right, (0, 255, 0), 2)
            label = detection.results[0].hypothesis.class_id.removeprefix(
                "placeholder/coco/"
            )
            cv2.putText(
                annotated,
                f"{label} {candidate.score:.2f}",
                (top_left[0], max(12, top_left[1] - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (0, 255, 0),
                1,
                cv2.LINE_AA,
            )
        return annotated


def make_diagnostic_status(
    identity: VerifiedModel,
    counters: RuntimeCounters,
    last_error_code: str,
) -> DiagnosticStatus:
    status = DiagnosticStatus()
    status.level = DiagnosticStatus.ERROR if last_error_code else DiagnosticStatus.OK
    status.name = "substation_perception/placeholder_detector"
    status.message = last_error_code or "PLACEHOLDER_READY"
    status.hardware_id = identity.sha256
    values = {
        "runtime_mode": "development_placeholder",
        "production_ready": "false",
        "logical_model": "yolo11n_base",
        "model_sha256": identity.sha256,
        "model_size_bytes": str(identity.size_bytes),
        "frames_received": str(counters.frames_received),
        "frames_processed": str(counters.frames_processed),
        "frames_replaced": str(counters.frames_replaced),
        "frames_failed": str(counters.frames_failed),
        "last_error_code": last_error_code,
    }
    status.values = [KeyValue(key=key, value=value) for key, value in values.items()]
    return status


def _qos(depth: int, reliable: bool) -> QoSProfile:
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=depth,
        reliability=(
            ReliabilityPolicy.RELIABLE
            if reliable
            else ReliabilityPolicy.BEST_EFFORT
        ),
        durability=DurabilityPolicy.VOLATILE,
    )


class PlaceholderPerceptionNode(Node):
    def __init__(self) -> None:
        super().__init__("placeholder_detector")
        model_path = Path(str(self.declare_parameter("model_path", str(MODEL_PATH)).value))
        runtime_mode = str(
            self.declare_parameter("runtime_mode", "development_placeholder").value
        )
        logical_model = str(self.declare_parameter("logical_model", "yolo11n_base").value)
        production_ready = bool(
            self.declare_parameter("production_ready", False).value
        )
        confidence_threshold = float(
            self.declare_parameter("confidence_threshold", 0.25).value
        )
        self.identity = verify_development_placeholder(
            path=model_path,
            expected_path=MODEL_PATH,
            expected_sha256=MODEL_SHA256,
            expected_size_bytes=MODEL_SIZE_BYTES,
            runtime_mode=runtime_mode,
            logical_model=logical_model,
            production_ready=production_ready,
        )

        self._buffer = LatestFrameBuffer()
        self._stop = Event()
        self._counter_lock = Lock()
        self._counters = RuntimeCounters()
        self._last_error_code = ""
        self._processor = FrameProcessor(
            YoloBackend(self.identity), CvBridge(), confidence_threshold
        )

        image_qos = _qos(depth=2, reliable=False)
        stream_qos = _qos(depth=10, reliable=True)
        diagnostic_qos = _qos(depth=10, reliable=True)
        self._detection_publisher = self.create_publisher(
            Detection2DArray,
            "/perception/development/detections",
            stream_qos,
        )
        self._annotation_publisher = self.create_publisher(
            Image,
            "/perception/development/annotated_image",
            image_qos,
        )
        self._diagnostic_publisher = self.create_publisher(
            DiagnosticArray, "/diagnostics", diagnostic_qos
        )
        self.create_subscription(Image, "/camera/image_raw", self._on_image, image_qos)
        self.create_timer(1.0, self._publish_diagnostic)
        self._worker = Thread(target=self._run_worker, name="placeholder-inference")
        self._worker.start()

    def _on_image(self, message: Image) -> None:
        replaced = self._buffer.offer(message)
        with self._counter_lock:
            self._counters.frames_received += 1
            if replaced:
                self._counters.frames_replaced += 1

    def _run_worker(self) -> None:
        while not self._stop.is_set():
            message = self._buffer.wait_and_take(self._stop)
            if message is None:
                continue
            outcome = self._processor.process(message)
            with self._counter_lock:
                if outcome.error_code:
                    self._counters.frames_failed += 1
                    self._last_error_code = outcome.error_code
                else:
                    self._counters.frames_processed += 1
                    self._last_error_code = ""
            if outcome.error_code:
                self._publish_diagnostic()
                continue
            self._detection_publisher.publish(outcome.detections)
            self._annotation_publisher.publish(outcome.annotated_image)

    def _publish_diagnostic(self) -> None:
        with self._counter_lock:
            counters = RuntimeCounters(**vars(self._counters))
            last_error_code = self._last_error_code
        array = DiagnosticArray()
        array.header.stamp = self.get_clock().now().to_msg()
        array.status = [
            make_diagnostic_status(self.identity, counters, last_error_code)
        ]
        self._diagnostic_publisher.publish(array)

    def destroy_node(self) -> None:
        self._stop.set()
        self._buffer.wake()
        self._worker.join(timeout=5.0)
        super().destroy_node()


def main() -> None:
    rclpy.init()
    node: PlaceholderPerceptionNode | None = None
    try:
        node = PlaceholderPerceptionNode()
        rclpy.spin(node)
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()
