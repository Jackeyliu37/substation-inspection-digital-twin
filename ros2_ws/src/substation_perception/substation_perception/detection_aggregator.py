from __future__ import annotations

from collections.abc import Sequence

from cv_bridge import CvBridge
import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import Header
from substation_interfaces.msg import RunContext
from vision_msgs.msg import Detection2DArray

from .production_nodes import ProductionRuntimeGate


def _header_key(header: Header) -> tuple[str, int, int]:
    return header.frame_id, int(header.stamp.sec), int(header.stamp.nanosec)


def merge_detection_arrays(
    header: Header, arrays: Sequence[Detection2DArray]
) -> Detection2DArray:
    expected = _header_key(header)
    output = Detection2DArray(header=header)
    seen: set[str] = set()
    for array in arrays:
        if _header_key(array.header) != expected:
            raise ValueError("DETECTION_HEADER_MISMATCH")
        for item in array.detections:
            if _header_key(item.header) != expected:
                raise ValueError("DETECTION_HEADER_MISMATCH")
            if not item.id or item.id in seen:
                raise ValueError("EVIDENCE_ID_INVALID")
            seen.add(item.id)
            output.detections.append(item)
    return output


def _qos(depth: int, *, reliable: bool, transient: bool = False) -> QoSProfile:
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=depth,
        reliability=ReliabilityPolicy.RELIABLE if reliable else ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.TRANSIENT_LOCAL if transient else DurabilityPolicy.VOLATILE,
    )


class DetectionAggregatorNode(Node):
    _MODULES = ("safety", "equipment", "defect")

    def __init__(self) -> None:
        super().__init__("detection_aggregator")
        self._gate = ProductionRuntimeGate()
        self._bridge = CvBridge()
        self._images: dict[tuple[str, int, int], Image] = {}
        self._arrays: dict[tuple[str, int, int], dict[str, Detection2DArray]] = {}
        self._detections = self.create_publisher(
            Detection2DArray, "/perception/detections", _qos(10, reliable=True)
        )
        self._annotated = self.create_publisher(
            Image, "/perception/annotated_image", _qos(2, reliable=False)
        )
        self.create_subscription(
            RunContext, "/system/run_context", self._gate.update, _qos(1, reliable=True, transient=True)
        )
        self.create_subscription(Image, "/camera/image_raw", self._on_image, _qos(2, reliable=False))
        for module, topic in (
            ("safety", "/perception/safety/detections"),
            ("equipment", "/perception/equipment/detections"),
            ("defect", "/perception/defects/detections"),
        ):
            self.create_subscription(
                Detection2DArray,
                topic,
                lambda message, source=module: self._on_detections(source, message),
                _qos(10, reliable=True),
            )

    def _on_image(self, message: Image) -> None:
        if not self._gate.active or message.encoding != "rgb8":
            return
        self._images[_header_key(message.header)] = message
        self._trim()
        self._try_publish(_header_key(message.header))

    def _on_detections(self, module: str, message: Detection2DArray) -> None:
        if not self._gate.active:
            return
        key = _header_key(message.header)
        self._arrays.setdefault(key, {})[module] = message
        self._trim()
        self._try_publish(key)

    def _trim(self) -> None:
        while len(self._images) > 8:
            self._images.pop(next(iter(self._images)))
        while len(self._arrays) > 8:
            self._arrays.pop(next(iter(self._arrays)))

    def _try_publish(self, key: tuple[str, int, int]) -> None:
        image_message = self._images.get(key)
        modules = self._arrays.get(key, {})
        if image_message is None or set(modules) != set(self._MODULES):
            return
        try:
            merged = merge_detection_arrays(
                image_message.header, [modules[name] for name in self._MODULES]
            )
            rgb = np.asarray(
                self._bridge.imgmsg_to_cv2(image_message, desired_encoding="rgb8")
            ).copy()
            for detection in merged.detections:
                center = detection.bbox.center.position
                half_w = detection.bbox.size_x / 2.0
                half_h = detection.bbox.size_y / 2.0
                p1 = (int(center.x - half_w), int(center.y - half_h))
                p2 = (int(center.x + half_w), int(center.y + half_h))
                label = detection.results[0].hypothesis.class_id if detection.results else "unknown"
                cv2.rectangle(rgb, p1, p2, (0, 255, 0), 2)
                cv2.putText(rgb, label, (p1[0], max(12, p1[1] - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
            annotated = self._bridge.cv2_to_imgmsg(rgb, encoding="rgb8")
            annotated.header = image_message.header
        except Exception:
            return
        self._detections.publish(merged)
        self._annotated.publish(annotated)
        self._images.pop(key, None)
        self._arrays.pop(key, None)


def main() -> None:
    rclpy.init()
    node = DetectionAggregatorNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
