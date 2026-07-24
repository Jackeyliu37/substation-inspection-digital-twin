#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import time
import uuid

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Image
from substation_interfaces.msg import InspectionTaskArray, RunContext
from substation_interfaces.srv import (
    EmergencyStop,
    GenerateReport,
    ResetEmergencyStop,
)
from vision_msgs.msg import Detection2DArray
import rclpy
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)

from substation_perception.production_identity import load_production_models


def measured_fps(count: int, duration_s: float) -> float:
    if count < 0 or not math.isfinite(duration_s) or duration_s <= 0.0:
        raise ValueError("FPS_INPUT_INVALID")
    return count / duration_s


def require_fps(count: int, duration_s: float, threshold: float) -> float:
    value = measured_fps(count, duration_s)
    if value < threshold:
        raise RuntimeError(
            f"PRODUCTION_FPS_BELOW_THRESHOLD:{value:.6f}<{threshold:.6f}"
        )
    return value


def qos(
    depth: int,
    *,
    reliable: bool,
    transient: bool = False,
) -> QoSProfile:
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=depth,
        reliability=(
            ReliabilityPolicy.RELIABLE
            if reliable else ReliabilityPolicy.BEST_EFFORT
        ),
        durability=(
            DurabilityPolicy.TRANSIENT_LOCAL
            if transient else DurabilityPolicy.VOLATILE
        ),
    )


class ProductionProbe(Node):
    MODULE_TOPICS = {
        "safety": "/perception/safety/detections",
        "equipment": "/perception/equipment/detections",
        "defect": "/perception/defects/detections",
    }

    def __init__(self, run_id: str) -> None:
        super().__init__("production_acceptance_probe")
        self.run_id = run_id
        self.context: RunContext | None = None
        self.mission: InspectionTaskArray | None = None
        self.raw_count = 0
        self.annotated_count = 0
        self.aggregated_count = 0
        self.module_counts = {name: 0 for name in self.MODULE_TOPICS}
        self.meter_count = 0
        self.raw_stamps: set[tuple[int, int]] = set()
        self.annotated_stamps: set[tuple[int, int]] = set()
        self.camera_frame_sha256 = ""
        self.camera_width = 0
        self.camera_height = 0
        self.diagnostic_errors: list[str] = []
        self.stop_started_at: float | None = None
        self.last_nonzero_after_stop: float | None = None
        self.create_subscription(
            RunContext,
            "/system/run_context",
            self._on_context,
            qos(1, reliable=True, transient=True),
        )
        self.create_subscription(
            InspectionTaskArray,
            "/mission/inspection_tasks",
            self._on_mission,
            qos(1, reliable=True, transient=True),
        )
        self.create_subscription(
            Image,
            "/camera/image_raw",
            self._on_raw,
            qos(5, reliable=False),
        )
        self.create_subscription(
            Image,
            "/perception/annotated_image",
            self._on_annotated,
            qos(5, reliable=False),
        )
        self.create_subscription(
            Detection2DArray,
            "/perception/detections",
            lambda _message: self._increment("aggregated"),
            qos(20, reliable=True),
        )
        for name, topic in self.MODULE_TOPICS.items():
            self.create_subscription(
                Detection2DArray,
                topic,
                lambda _message, module=name: self._increment(module),
                qos(20, reliable=True),
            )
        self.create_subscription(
            DiagnosticArray,
            "/perception/meters/readings",
            self._on_meter,
            qos(20, reliable=True),
        )
        self.create_subscription(
            DiagnosticArray,
            "/diagnostics",
            self._on_diagnostics,
            qos(100, reliable=True),
        )
        self.create_subscription(
            Twist,
            "/cmd_vel",
            self._on_velocity,
            qos(50, reliable=True),
        )
        self.emergency = self.create_client(
            EmergencyStop, "/mission/emergency_stop"
        )
        self.reset = self.create_client(
            ResetEmergencyStop, "/mission/emergency_stop_reset"
        )

    def _increment(self, name: str) -> None:
        if name == "aggregated":
            self.aggregated_count += 1
        else:
            self.module_counts[name] += 1

    def _on_context(self, message: RunContext) -> None:
        if message.run_id == self.run_id:
            self.context = message

    def _on_mission(self, message: InspectionTaskArray) -> None:
        if message.run_id == self.run_id:
            self.mission = message

    def _on_raw(self, message: Image) -> None:
        if message.encoding != "rgb8" or not message.data:
            return
        self.raw_count += 1
        self.raw_stamps.add((message.header.stamp.sec, message.header.stamp.nanosec))
        if not self.camera_frame_sha256:
            self.camera_frame_sha256 = hashlib.sha256(bytes(message.data)).hexdigest()
            self.camera_width = int(message.width)
            self.camera_height = int(message.height)

    def _on_annotated(self, message: Image) -> None:
        if message.encoding == "rgb8" and message.data:
            self.annotated_count += 1
            self.annotated_stamps.add(
                (message.header.stamp.sec, message.header.stamp.nanosec)
            )

    def _on_meter(self, message: DiagnosticArray) -> None:
        if any(
            any(item.key == "run_id" and item.value == self.run_id for item in status.values)
            for status in message.status
        ):
            self.meter_count += 1

    def _on_diagnostics(self, message: DiagnosticArray) -> None:
        for status in message.status:
            if (
                status.name.startswith("substation_perception/")
                and status.level == DiagnosticStatus.ERROR
            ):
                value = f"{status.name}:{status.message}"
                if value not in self.diagnostic_errors:
                    self.diagnostic_errors.append(value)

    def _on_velocity(self, message: Twist) -> None:
        if self.stop_started_at is None:
            return
        values = (
            message.linear.x,
            message.linear.y,
            message.linear.z,
            message.angular.x,
            message.angular.y,
            message.angular.z,
        )
        if any(abs(value) > 1e-9 for value in values):
            self.last_nonzero_after_stop = time.monotonic()

    def spin_until(self, predicate, timeout_s: float, label: str) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if predicate():
                return
        raise RuntimeError(f"TIMEOUT:{label}")

    def ready(self) -> bool:
        return bool(
            self.context is not None
            and self.context.lifecycle == RunContext.LIFECYCLE_ACTIVE
            and self.mission is not None
            and self.raw_count > 0
            and self.annotated_count > 0
            and self.aggregated_count > 0
            and all(value > 0 for value in self.module_counts.values())
        )

    def reset_measurement(self) -> None:
        self.raw_count = 0
        self.annotated_count = 0
        self.aggregated_count = 0
        self.module_counts = {name: 0 for name in self.MODULE_TOPICS}
        self.meter_count = 0
        self.raw_stamps.clear()
        self.annotated_stamps.clear()

    def measure(self, duration_s: float) -> float:
        self.reset_measurement()
        started = time.monotonic()
        deadline = started + duration_s
        while time.monotonic() < deadline:
            rclpy.spin_once(
                self,
                timeout_sec=max(0.0, min(0.1, deadline - time.monotonic())),
            )
        return time.monotonic() - started

    def call(self, client, request, timeout_s: float):
        future = client.call_async(request)
        self.spin_until(future.done, timeout_s, "service response")
        response = future.result()
        if response is None:
            raise RuntimeError("SERVICE_NO_RESPONSE")
        return response

    def verify_emergency_barrier(self) -> dict[str, object]:
        if not self.emergency.wait_for_service(timeout_sec=10.0):
            raise RuntimeError("EMERGENCY_SERVICE_UNAVAILABLE")
        if not self.reset.wait_for_service(timeout_sec=10.0):
            raise RuntimeError("RESET_SERVICE_UNAVAILABLE")
        self.stop_started_at = time.monotonic()
        stop = self.call(
            self.emergency,
            EmergencyStop.Request(
                schema_version=1,
                command_id=str(uuid.uuid4()),
                reason="production acceptance barrier",
            ),
            10.0,
        )
        if not stop.accepted or not stop.latched:
            raise RuntimeError(f"EMERGENCY_STOP_REJECTED:{stop.error_code}")
        reset_request = ResetEmergencyStop.Request(
            schema_version=1,
            command_id=str(uuid.uuid4()),
            observed_latch_revision=stop.latch_revision,
            confirm=True,
            reason="production acceptance area clear",
        )
        first = self.call(self.reset, reset_request, 10.0)
        if first.accepted or first.error_code != "MOTION_SAFETY_BARRIER_PENDING":
            raise RuntimeError("RESET_DID_NOT_ENFORCE_MOTION_SAFETY_BARRIER_PENDING")
        first_pending_at = time.monotonic()
        accepted = None
        deadline = first_pending_at + 20.0
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            response = self.call(self.reset, reset_request, 5.0)
            if response.accepted:
                accepted = response
                break
            if response.error_code != "MOTION_SAFETY_BARRIER_PENDING":
                raise RuntimeError(f"RESET_REJECTED:{response.error_code}")
        if accepted is None:
            raise RuntimeError("RESET_BARRIER_TIMEOUT")
        accepted_at = time.monotonic()
        zero_origin = self.last_nonzero_after_stop or self.stop_started_at
        zero_duration = accepted_at - zero_origin
        if zero_duration < 0.5:
            raise RuntimeError("ZERO_VELOCITY_BARRIER_TOO_SHORT")
        return {
            "emergency_stop_accepted": True,
            "latch_revision": int(stop.latch_revision),
            "initial_reset_error": first.error_code,
            "reset_accepted": True,
            "zero_velocity_duration_s": zero_duration,
            "active_goal_cleared": True,
        }


def generate_report(
    node: ProductionProbe,
    *,
    rosbag_metadata: Path,
    work_root: Path,
) -> dict[str, str]:
    node.spin_until(rosbag_metadata.is_file, 30.0, "rosbag2 metadata")
    client = node.create_client(GenerateReport, "/reporting/generate_report")
    if not client.wait_for_service(timeout_sec=15.0):
        raise RuntimeError("REPORT_SERVICE_UNAVAILABLE")
    if node.mission is None:
        raise RuntimeError("MISSION_SNAPSHOT_UNAVAILABLE")
    response = node.call(
        client,
        GenerateReport.Request(
            schema_version=1,
            command_id=str(uuid.uuid4()),
            run_id=node.run_id,
            mission_id=node.mission.mission_id,
            formats=["evidence", "html", "pdf"],
        ),
        20.0,
    )
    if not response.accepted:
        raise RuntimeError(f"REPORT_REJECTED:{response.error_code}")
    directory = work_root / response.report_id
    node.spin_until(
        lambda: all((directory / name).is_file() for name in (
            "evidence.zip", "report.html", "report.pdf"
        )),
        20.0,
        "report files",
    )
    return {
        "report_id": response.report_id,
        "evidence_zip": str(directory / "evidence.zip"),
        "html": str(directory / "report.html"),
        "pdf": str(directory / "report.pdf"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--duration-s", type=float, default=300.0)
    parser.add_argument("--fps-threshold", type=float, default=15.0)
    parser.add_argument("--model-manifest", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--meter-evaluation", type=Path, required=True)
    parser.add_argument("--rosbag-metadata", type=Path, required=True)
    parser.add_argument("--report-work-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.duration_s < 300.0 or args.fps_threshold < 15.0:
        raise RuntimeError("ACCEPTANCE_THRESHOLDS_WEAKENED")

    models = load_production_models(args.model_manifest, args.model_root)
    required_models = {
        "yolo11n_safety",
        "yolo11n_equipment",
        "yolo11n_fault",
        "meter_locator",
    }
    if set(models) != required_models:
        raise RuntimeError("PRODUCTION_MODEL_SET_INVALID")
    meter_evaluation = json.loads(args.meter_evaluation.read_text(encoding="utf-8"))
    if meter_evaluation.get("sample_count") != 200:
        raise RuntimeError("METER_EVALUATION_INVALID")

    rclpy.init()
    node = ProductionProbe(args.run_id)
    try:
        node.spin_until(node.ready, 180.0, "production pipeline readiness")
        measured_duration = node.measure(args.duration_s)
        aggregate_fps = require_fps(
            node.aggregated_count, measured_duration, args.fps_threshold
        )
        annotated_fps = require_fps(
            node.annotated_count, measured_duration, args.fps_threshold
        )
        if not node.camera_frame_sha256 or len(node.raw_stamps) < 2:
            raise RuntimeError("REAL_CAMERA_FRAME_INVALID")
        if node.aggregated_count != node.annotated_count:
            raise RuntimeError("ANNOTATED_DETECTION_COUNT_MISMATCH")
        if any(value == 0 for value in node.module_counts.values()):
            raise RuntimeError("PRODUCTION_MODULE_SILENT")
        barrier = node.verify_emergency_barrier()
        report = generate_report(
            node,
            rosbag_metadata=args.rosbag_metadata,
            work_root=args.report_work_root,
        )
        result = {
            "schema_version": 1,
            "status": "passed",
            "run_id": args.run_id,
            "duration_s": measured_duration,
            "fps_threshold": args.fps_threshold,
            "aggregate_fps": aggregate_fps,
            "annotated_fps": annotated_fps,
            "raw_camera_fps": measured_fps(node.raw_count, measured_duration),
            "counts": {
                "raw_camera": node.raw_count,
                "annotated": node.annotated_count,
                "aggregated": node.aggregated_count,
                "modules": node.module_counts,
                "meter_readings": node.meter_count,
            },
            "camera_frame_sha256": node.camera_frame_sha256,
            "camera_width": node.camera_width,
            "camera_height": node.camera_height,
            "unique_raw_stamps": len(node.raw_stamps),
            "unique_annotated_stamps": len(node.annotated_stamps),
            "model_sha256": {
                logical: identity.sha256
                for logical, identity in sorted(models.items())
            },
            "safety_threshold_waived": models["yolo11n_safety"].threshold_waived,
            "meter_evaluation": {
                "sample_count": meter_evaluation["sample_count"],
                "valid_count": meter_evaluation["valid_count"],
                "valid_rate": meter_evaluation["valid_rate"],
                "absolute_error": meter_evaluation["absolute_error"],
            },
            "mission_safety_barrier": barrier,
            "diagnostic_errors": node.diagnostic_errors,
            "report": report,
        }
        args.output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    finally:
        node.destroy_node()
        rclpy.shutdown()
    print("production-probe: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
