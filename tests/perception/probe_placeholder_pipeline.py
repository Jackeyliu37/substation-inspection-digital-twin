#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2DArray


MODEL_SHA256 = "0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1"


def qos(depth: int, reliable: bool) -> QoSProfile:
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


def header_key(header) -> tuple[int, int, str]:
    return header.stamp.sec, header.stamp.nanosec, header.frame_id


class PlaceholderPipelineProbe(Node):
    def __init__(self) -> None:
        super().__init__("placeholder_pipeline_probe")
        self.counts = {"camera": 0, "detections": 0, "annotated": 0, "diagnostics": 0}
        self.source_headers: set[tuple[int, int, str]] = set()
        self.source_arrivals: dict[tuple[int, int, str], float] = {}
        self.detection_header_matches = 0
        self.annotation_header_matches = 0
        self.class_prefixes_valid = True
        self.detection_latencies: list[float] = []
        self.annotation_latencies: list[float] = []
        self.diagnostic_values: dict[str, str] = {}
        self.diagnostic_ok = False

        self.create_subscription(Image, "/camera/image_raw", self.on_camera, qos(2, False))
        self.create_subscription(
            Detection2DArray,
            "/perception/development/detections",
            self.on_detections,
            qos(10, True),
        )
        self.create_subscription(
            Image,
            "/perception/development/annotated_image",
            self.on_annotated,
            qos(2, False),
        )
        self.create_subscription(
            DiagnosticArray, "/diagnostics", self.on_diagnostics, qos(10, True)
        )

    def on_camera(self, message: Image) -> None:
        self.counts["camera"] += 1
        key = header_key(message.header)
        self.source_headers.add(key)
        self.source_arrivals.setdefault(key, time.monotonic())

    def on_detections(self, message: Detection2DArray) -> None:
        self.counts["detections"] += 1
        key = header_key(message.header)
        if key in self.source_headers:
            self.detection_header_matches += 1
            self.detection_latencies.append(time.monotonic() - self.source_arrivals[key])
        for detection in message.detections:
            for result in detection.results:
                self.class_prefixes_valid = self.class_prefixes_valid and (
                    result.hypothesis.class_id.startswith("placeholder/coco/")
                )

    def on_annotated(self, message: Image) -> None:
        self.counts["annotated"] += 1
        key = header_key(message.header)
        if (
            message.encoding == "rgb8"
            and key in self.source_headers
            and message.width > 0
            and message.height > 0
        ):
            self.annotation_header_matches += 1
            self.annotation_latencies.append(time.monotonic() - self.source_arrivals[key])

    def on_diagnostics(self, message: DiagnosticArray) -> None:
        self.counts["diagnostics"] += 1
        for status in message.status:
            if status.name != "substation_perception/placeholder_detector":
                continue
            values = {item.key: item.value for item in status.values}
            self.diagnostic_values = values
            self.diagnostic_ok = (
                status.level == DiagnosticStatus.OK
                and status.message == "PLACEHOLDER_READY"
                and values.get("runtime_mode") == "development_placeholder"
                and values.get("production_ready") == "false"
                and values.get("logical_model") == "yolo11n_base"
                and values.get("model_sha256") == MODEL_SHA256
                and values.get("model_size_bytes") == "5613764"
                and values.get("inference_device") == "cuda:0"
                and int(values.get("frames_processed", "0")) >= 1
                and values.get("last_error_code") == ""
            )

    def ready(self) -> bool:
        return (
            self.counts["camera"] >= 1
            and self.counts["detections"] >= 1
            and self.counts["annotated"] >= 1
            and self.detection_header_matches >= 1
            and self.annotation_header_matches >= 1
            and self.class_prefixes_valid
            and self.diagnostic_ok
        )

    def summary(self) -> dict[str, object]:
        return {
            "status": "passed" if self.ready() else "failed",
            "counts": self.counts,
            "detection_header_matches": self.detection_header_matches,
            "annotation_header_matches": self.annotation_header_matches,
            "class_prefixes_valid": self.class_prefixes_valid,
            "backend_ready": self.diagnostic_ok and self.counts["detections"] >= 1,
            "diagnostic_values": self.diagnostic_values,
            "detection_latency_seconds": self._latency(self.detection_latencies),
            "annotation_latency_seconds": self._latency(self.annotation_latencies),
        }

    @staticmethod
    def _latency(values: list[float]) -> dict[str, float | int]:
        if not values:
            return {"count": 0, "min": 0.0, "max": 0.0}
        return {"count": len(values), "min": min(values), "max": max(values)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()

    rclpy.init()
    probe = PlaceholderPipelineProbe()
    started = time.monotonic()
    try:
        while time.monotonic() - started < 85.0 and not probe.ready():
            rclpy.spin_once(probe, timeout_sec=0.2)
        summary = probe.summary()
        arguments.output.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if not probe.ready():
            raise RuntimeError(json.dumps(summary, sort_keys=True))
    finally:
        probe.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
