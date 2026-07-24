from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event, Thread
import uuid

from cv_bridge import CvBridge
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import Header
from substation_interfaces.msg import RunContext
from vision_msgs.msg import Detection2D, Detection2DArray, ObjectHypothesisWithPose

from .detection_contract import normalize_class_name, to_production_detections
from .placeholder_node import LatestFrameBuffer
from .production_identity import ProductionModel, load_production_models
from .yolo_backend import FaultClassifierBackend, YoloBackend


@dataclass
class ProductionRuntimeGate:
    run_id: str = ""
    context_revision: int = 0
    active: bool = False

    def update(self, context: RunContext) -> None:
        self.run_id = str(context.run_id)
        self.context_revision = int(context.context_revision)
        self.active = bool(
            self.run_id
            and context.lifecycle == RunContext.LIFECYCLE_ACTIVE
            and self.context_revision > 0
        )


def _header_key(header: Header) -> tuple[int, int]:
    return int(header.stamp.sec), int(header.stamp.nanosec)


def classify_equipment_crops(
    header: Header,
    image_rgb: np.ndarray,
    equipment: Detection2DArray,
    backend: object,
    *,
    id_factory=uuid.uuid4,
) -> Detection2DArray:
    if equipment.header != header or image_rgb.ndim != 3 or image_rgb.shape[2] != 3:
        raise ValueError("DETECTION_HEADER_MISMATCH")
    output = Detection2DArray(header=header)
    height, width = image_rgb.shape[:2]
    for source in equipment.detections:
        center = source.bbox.center.position
        x1 = max(0, int(round(center.x - source.bbox.size_x / 2.0)))
        y1 = max(0, int(round(center.y - source.bbox.size_y / 2.0)))
        x2 = min(width, int(round(center.x + source.bbox.size_x / 2.0)))
        y2 = min(height, int(round(center.y + source.bbox.size_y / 2.0)))
        if x2 <= x1 or y2 <= y1:
            continue
        class_name, score = backend.classify(image_rgb[y1:y2, x1:x2])
        normalized = normalize_class_name(class_name)
        if not normalized or not 0.0 <= float(score) <= 1.0:
            continue
        item = Detection2D(header=header, id=str(id_factory()), bbox=source.bbox)
        hypothesis = ObjectHypothesisWithPose()
        hypothesis.hypothesis.class_id = f"defect/{normalized}"
        hypothesis.hypothesis.score = float(score)
        item.results.append(hypothesis)
        output.detections.append(item)
    return output


def _qos(depth: int, *, reliable: bool, transient: bool = False) -> QoSProfile:
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=depth,
        reliability=ReliabilityPolicy.RELIABLE if reliable else ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.TRANSIENT_LOCAL if transient else DurabilityPolicy.VOLATILE,
    )


class ProductionDetectorNode(Node):
    def __init__(self, logical_model: str, module: str, topic: str) -> None:
        super().__init__(f"{module}_detector")
        manifest = Path(str(self.declare_parameter("model_manifest", "models/manifest.yaml").value))
        model_root = Path(str(self.declare_parameter("model_root", "/var/lib/substation/models/production").value))
        threshold = float(self.declare_parameter("confidence_threshold", 0.25).value)
        models = load_production_models(manifest, model_root)
        identity = models[logical_model]
        if identity.module != module or identity.task != "detect":
            raise RuntimeError("MODEL_ROLE_INVALID")
        self._logical_model = logical_model
        self._module = module
        self._identity = identity
        self._threshold = threshold
        self._gate = ProductionRuntimeGate()
        self._backend = YoloBackend(identity)
        self._bridge = CvBridge()
        self._buffer = LatestFrameBuffer()
        self._stop = Event()
        self._publisher = self.create_publisher(Detection2DArray, topic, _qos(10, reliable=True))
        self._diagnostic = self.create_publisher(DiagnosticArray, "/diagnostics", _qos(10, reliable=True))
        self.create_subscription(RunContext, "/system/run_context", self._gate.update, _qos(1, reliable=True, transient=True))
        self.create_subscription(Image, "/camera/image_raw", self._on_image, _qos(2, reliable=False))
        self._worker = Thread(target=self._run, name=f"{module}-inference")
        self._worker.start()

    def _on_image(self, message: Image) -> None:
        if self._gate.active:
            self._buffer.offer(message)

    def _run(self) -> None:
        while not self._stop.is_set():
            message = self._buffer.wait_and_take(self._stop)
            if message is None or not self._gate.active or message.encoding != "rgb8":
                continue
            try:
                image = np.asarray(self._bridge.imgmsg_to_cv2(message, desired_encoding="rgb8"))
                raw = [item for item in self._backend.infer(image) if item.score >= self._threshold]
                output = to_production_detections(
                    message.header, image.shape[1], image.shape[0], raw, module=self._module
                )
            except Exception as error:
                self._publish_diagnostic(str(error) or "INFERENCE_FAILED")
                continue
            self._publisher.publish(output)
            self._publish_diagnostic("")

    def _publish_diagnostic(self, error: str) -> None:
        status = DiagnosticStatus(
            level=DiagnosticStatus.ERROR if error else DiagnosticStatus.OK,
            name=f"substation_perception/{self._module}_detector",
            hardware_id=self._identity.sha256,
            message=error or "PRODUCTION_READY",
            values=[
                KeyValue(key="logical_model", value=self._logical_model),
                KeyValue(key="model_sha256", value=self._identity.sha256),
                KeyValue(key="run_id", value=self._gate.run_id),
                KeyValue(key="context_revision", value=str(self._gate.context_revision)),
                KeyValue(key="inference_device", value=self._backend.inference_device),
            ],
        )
        message = DiagnosticArray(status=[status])
        message.header.stamp = self.get_clock().now().to_msg()
        self._diagnostic.publish(message)

    def destroy_node(self) -> None:
        self._stop.set()
        self._buffer.wake()
        self._worker.join(timeout=5.0)
        super().destroy_node()


class FaultClassifierNode(Node):
    def __init__(self) -> None:
        super().__init__("defect_classifier")
        manifest = Path(str(self.declare_parameter("model_manifest", "models/manifest.yaml").value))
        model_root = Path(str(self.declare_parameter("model_root", "/var/lib/substation/models/production").value))
        identity = load_production_models(manifest, model_root)["yolo11n_fault"]
        if identity.task != "classify":
            raise RuntimeError("MODEL_ROLE_INVALID")
        self._gate = ProductionRuntimeGate()
        self._backend = FaultClassifierBackend(identity)
        self._bridge = CvBridge()
        self._images: dict[tuple[int, int], np.ndarray] = {}
        self._publisher = self.create_publisher(
            Detection2DArray, "/perception/defects/detections", _qos(10, reliable=True)
        )
        self.create_subscription(RunContext, "/system/run_context", self._gate.update, _qos(1, reliable=True, transient=True))
        self.create_subscription(Image, "/camera/image_raw", self._on_image, _qos(2, reliable=False))
        self.create_subscription(
            Detection2DArray,
            "/perception/equipment/detections",
            self._on_equipment,
            _qos(10, reliable=True),
        )

    def _on_image(self, message: Image) -> None:
        if not self._gate.active or message.encoding != "rgb8":
            return
        try:
            self._images[_header_key(message.header)] = np.asarray(
                self._bridge.imgmsg_to_cv2(message, desired_encoding="rgb8")
            )
        except Exception:
            return
        while len(self._images) > 8:
            self._images.pop(next(iter(self._images)))

    def _on_equipment(self, message: Detection2DArray) -> None:
        if not self._gate.active:
            return
        image = self._images.pop(_header_key(message.header), None)
        if image is None:
            return
        try:
            output = classify_equipment_crops(message.header, image, message, self._backend)
        except Exception:
            return
        self._publisher.publish(output)


def _spin(factory) -> None:
    rclpy.init()
    node = factory()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


def safety_main() -> None:
    _spin(lambda: ProductionDetectorNode("yolo11n_safety", "safety", "/perception/safety/detections"))


def equipment_main() -> None:
    _spin(lambda: ProductionDetectorNode("yolo11n_equipment", "equipment", "/perception/equipment/detections"))


def fault_main() -> None:
    _spin(FaultClassifierNode)
