from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from threading import Event, Thread
import time
import uuid

from cv_bridge import CvBridge
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import Header
from substation_interfaces.msg import InspectionTask, InspectionTaskArray, RunContext
import yaml

from .placeholder_node import LatestFrameBuffer
from .production_identity import load_production_models
from .production_nodes import ProductionRuntimeGate
from .yolo_backend import YoloBackend


@dataclass(frozen=True)
class MeterCalibration:
    asset_id: str
    sensor_id: str
    minimum: float
    maximum: float
    unit: str
    start_angle_radians: float = -3.0 * math.pi / 4.0
    end_angle_radians: float = 3.0 * math.pi / 4.0


@dataclass(frozen=True)
class MeterReadResult:
    reading: float
    confidence_0_1: float
    valid: bool
    needle_angle_radians: float | None
    error_code: str


def read_meter_crop(image_rgb: np.ndarray, calibration: MeterCalibration) -> MeterReadResult:
    if (
        not isinstance(image_rgb, np.ndarray)
        or image_rgb.dtype != np.uint8
        or image_rgb.ndim != 3
        or image_rgb.shape[2] != 3
        or image_rgb.shape[0] < 16
        or image_rgb.shape[1] < 16
    ):
        return MeterReadResult(0.0, 0.0, False, None, "CROP_INVALID")
    hsv = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2HSV)
    low = cv2.inRange(hsv, np.array([0, 90, 45]), np.array([12, 255, 255]))
    high = cv2.inRange(hsv, np.array([168, 90, 45]), np.array([179, 255, 255]))
    mask = cv2.morphologyEx(cv2.bitwise_or(low, high), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    ys, xs = np.nonzero(mask)
    minimum_pixels = max(8, int(image_rgb.shape[0] * image_rgb.shape[1] * 0.0008))
    if len(xs) < minimum_pixels:
        return MeterReadResult(0.0, 0.0, False, None, "NEEDLE_NOT_FOUND")
    center_x = (image_rgb.shape[1] - 1) / 2.0
    center_y = (image_rgb.shape[0] - 1) / 2.0
    dx = float(np.mean(xs) - center_x)
    dy = float(np.mean(ys) - center_y)
    length = math.hypot(dx, dy)
    if length < min(image_rgb.shape[:2]) * 0.06:
        return MeterReadResult(0.0, 0.0, False, None, "NEEDLE_GEOMETRY_INVALID")
    angle = math.atan2(dy, dx)
    start = calibration.start_angle_radians
    end = calibration.end_angle_radians
    if not end > start:
        return MeterReadResult(0.0, 0.0, False, None, "CALIBRATION_INVALID")
    normalized = min(1.0, max(0.0, (angle - start) / (end - start)))
    reading = calibration.minimum + normalized * (calibration.maximum - calibration.minimum)
    radius = min(image_rgb.shape[:2]) / 2.0
    coverage = min(1.0, len(xs) / max(20.0, radius * 1.5))
    geometry = min(1.0, length / max(1.0, radius * 0.45))
    confidence = max(0.0, min(1.0, 0.5 * coverage + 0.5 * geometry))
    return MeterReadResult(reading, confidence, True, angle, "")


def make_meter_reading(
    header: Header,
    *,
    run_id: str,
    calibration: MeterCalibration,
    result: MeterReadResult,
    evidence_id: uuid.UUID,
) -> DiagnosticArray:
    status = DiagnosticStatus()
    status.level = DiagnosticStatus.OK if result.valid else DiagnosticStatus.ERROR
    status.name = calibration.asset_id
    status.hardware_id = calibration.sensor_id
    status.message = "METER_READING_VALID" if result.valid else result.error_code
    values = {
        "run_id": run_id,
        "reading": f"{result.reading:g}",
        "unit": calibration.unit,
        "confidence_0_1": f"{result.confidence_0_1:.6f}",
        "valid": "true" if result.valid else "false",
        "evidence_id": str(evidence_id),
    }
    status.values = [KeyValue(key=key, value=value) for key, value in values.items()]
    return DiagnosticArray(header=header, status=[status])


def load_meter_calibrations(path: Path) -> dict[str, MeterCalibration]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    opencv = document["opencv"]
    start = float(opencv["start_angle_radians"])
    end = float(opencv["end_angle_radians"])
    output: dict[str, MeterCalibration] = {}
    for asset_id, values in document["assets"].items():
        output[asset_id] = MeterCalibration(
            asset_id=asset_id,
            sensor_id=str(values["sensor_id"]),
            minimum=float(values["minimum"]),
            maximum=float(values["maximum"]),
            unit=str(values["unit"]),
            start_angle_radians=start,
            end_angle_radians=end,
        )
    return output


def _qos(depth: int, *, reliable: bool, transient: bool = False) -> QoSProfile:
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=depth,
        reliability=ReliabilityPolicy.RELIABLE if reliable else ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.TRANSIENT_LOCAL if transient else DurabilityPolicy.VOLATILE,
    )


class MeterReaderNode(Node):
    def __init__(self) -> None:
        super().__init__("meter_reader")
        manifest = Path(str(self.declare_parameter("model_manifest", "models/manifest.yaml").value))
        model_root = Path(str(self.declare_parameter("model_root", "/var/lib/substation/models/production").value))
        config = Path(str(self.declare_parameter("meter_config", "configs/meter_reader.yaml").value))
        identity = load_production_models(manifest, model_root)["meter_locator"]
        self._backend = YoloBackend(identity)
        self._calibrations = load_meter_calibrations(config)
        self._gate = ProductionRuntimeGate()
        self._active_asset = ""
        self._bridge = CvBridge()
        self._buffer = LatestFrameBuffer()
        self._stop = Event()
        self._last_publish = 0.0
        self._publisher = self.create_publisher(
            DiagnosticArray, "/perception/meters/readings", _qos(10, reliable=True)
        )
        self.create_subscription(RunContext, "/system/run_context", self._gate.update, _qos(1, reliable=True, transient=True))
        self.create_subscription(
            InspectionTaskArray,
            "/mission/inspection_tasks",
            self._on_mission,
            _qos(1, reliable=True, transient=True),
        )
        self.create_subscription(Image, "/camera/image_raw", self._on_image, _qos(2, reliable=False))
        self._worker = Thread(target=self._run, name="meter-reader")
        self._worker.start()

    def _on_mission(self, message: InspectionTaskArray) -> None:
        self._active_asset = next(
            (
                task.asset_id
                for task in message.tasks
                if task.state == InspectionTask.STATE_ACTIVE and task.asset_id in self._calibrations
            ),
            "",
        )

    def _on_image(self, message: Image) -> None:
        if self._gate.active and self._active_asset:
            self._buffer.offer(message)

    def _run(self) -> None:
        while not self._stop.is_set():
            message = self._buffer.wait_and_take(self._stop)
            if message is None or not self._gate.active or not self._active_asset:
                continue
            now = time.monotonic()
            if now - self._last_publish < 0.2:
                continue
            try:
                image = np.asarray(self._bridge.imgmsg_to_cv2(message, desired_encoding="rgb8"))
                detections = self._backend.infer(image)
                candidate = max(
                    (item for item in detections if item.class_name == "meter"),
                    key=lambda item: item.score,
                )
                x1, y1, x2, y2 = candidate.xyxy
                crop = image[max(0, int(y1)):min(image.shape[0], int(math.ceil(y2))), max(0, int(x1)):min(image.shape[1], int(math.ceil(x2)))]
                calibration = self._calibrations[self._active_asset]
                result = read_meter_crop(crop, calibration)
                output = make_meter_reading(
                    message.header,
                    run_id=self._gate.run_id,
                    calibration=calibration,
                    result=result,
                    evidence_id=uuid.uuid4(),
                )
            except Exception:
                continue
            self._publisher.publish(output)
            self._last_publish = now

    def destroy_node(self) -> None:
        self._stop.set()
        self._buffer.wake()
        self._worker.join(timeout=5.0)
        super().destroy_node()


def main() -> None:
    rclpy.init()
    node = MeterReaderNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
