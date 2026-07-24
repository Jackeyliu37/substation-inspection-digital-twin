from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
from typing import Callable
import uuid
import zipfile

from nav_msgs.msg import Odometry
import rclpy
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from substation_interfaces.msg import (
    AssetRiskArray,
    InspectionTaskArray,
    RiskAlert,
    RunContext,
)
from substation_interfaces.srv import (
    GenerateDiagnosticBundle,
    GenerateReport,
    StoreEvidence,
)

from .report_generator import ReportGenerator


SCHEMA_VERSION = 1
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
REPORT_MEDIA_TYPES = {
    "evidence": "application/zip",
    "html": "text/html",
    "pdf": "application/pdf",
}


class ReportServiceRuntime:
    def __init__(
        self,
        generator: ReportGenerator,
        *,
        implementation_commit: str,
        model_versions: dict[str, str],
        dataset_versions: dict[str, str],
        submit_artifact: Callable[[str, str, str, str | None, int, bytes, str], bool],
        load_bundle_sources: Callable[[], tuple[str, str]] | None = None,
        utc_now: Callable[[], datetime] | None = None,
    ) -> None:
        self._generator = generator
        self._implementation_commit = implementation_commit
        self._model_versions = dict(model_versions)
        self._dataset_versions = dict(dataset_versions)
        self._submit_artifact = submit_artifact
        self._load_bundle_sources = load_bundle_sources or (lambda: ("", ""))
        self._utc_now = utc_now or (lambda: datetime.now(timezone.utc))
        self._context: RunContext | None = None
        self._risks: AssetRiskArray | None = None
        self._tasks: InspectionTaskArray | None = None
        self._alerts: list[dict[str, object]] = []
        self._trajectory: list[dict[str, object]] = []

    def observe_run_context(self, message: RunContext) -> None:
        if message.schema_version == SCHEMA_VERSION and message.run_id:
            if (
                self._context is None
                or message.run_id != self._context.run_id
                or message.context_revision >= self._context.context_revision
            ):
                if self._context is None or message.run_id != self._context.run_id:
                    self._alerts = []
                    self._trajectory = []
                self._context = message

    def observe_risks(self, message: AssetRiskArray) -> None:
        if message.schema_version == SCHEMA_VERSION and message.run_id:
            self._risks = message

    def observe_tasks(self, message: InspectionTaskArray) -> None:
        if message.schema_version == SCHEMA_VERSION and message.run_id:
            self._tasks = message

    def observe_alert(self, message: RiskAlert) -> None:
        if (
            message.schema_version == SCHEMA_VERSION
            and self._context is not None
            and message.run_id == self._context.run_id
        ):
            self._alerts.append({
                "alert_id": message.alert_id,
                "asset_id": message.asset_id,
                "event_type": int(message.event_type),
                "level": int(message.current_level),
                "score_0_100": float(message.score_0_100),
                "summary": message.summary,
                "evidence_ids": list(message.evidence_ids),
            })

    def observe_odometry(self, message: Odometry) -> None:
        if (
            self._context is None
            or self._context.lifecycle != RunContext.LIFECYCLE_ACTIVE
        ):
            return
        self._trajectory.append({
            "ros_sec": int(message.header.stamp.sec),
            "ros_nanosec": int(message.header.stamp.nanosec),
            "x_m": float(message.pose.pose.position.x),
            "y_m": float(message.pose.pose.position.y),
        })
        if len(self._trajectory) > 10000:
            del self._trajectory[:-10000]

    @staticmethod
    def _prepare(response):
        response.schema_version = SCHEMA_VERSION
        return response

    @classmethod
    def _reject(cls, response, code: str, message: str = ""):
        cls._prepare(response)
        response.accepted = False
        response.error_code = code
        response.error_message = message or code
        return response

    @staticmethod
    def _valid_uuid(value: str) -> bool:
        try:
            return str(uuid.UUID(value)) == value
        except (ValueError, AttributeError, TypeError):
            return False

    def _context_matches(self, run_id: str) -> bool:
        return bool(
            self._context is not None
            and self._context.run_id == run_id
            and self._context.lifecycle in (
                RunContext.LIFECYCLE_ACTIVE,
                RunContext.LIFECYCLE_ENDING,
                RunContext.LIFECYCLE_ENDED,
            )
        )

    def generate_report(self, request, response):
        self._prepare(response)
        formats = list(request.formats)
        if (
            request.schema_version != SCHEMA_VERSION
            or not self._valid_uuid(request.command_id)
            or not self._valid_uuid(request.run_id)
            or not self._valid_uuid(request.mission_id)
            or not formats
            or formats != sorted(set(formats))
            or any(name not in REPORT_MEDIA_TYPES for name in formats)
        ):
            return self._reject(response, "VALIDATION_FAILED")
        if (
            not self._context_matches(request.run_id)
            or self._risks is None
            or self._risks.run_id != request.run_id
            or self._tasks is None
            or self._tasks.run_id != request.run_id
            or self._tasks.mission_id != request.mission_id
        ):
            return self._reject(response, "RUN_CONTEXT_MISMATCH")
        if not COMMIT_PATTERN.fullmatch(self._implementation_commit):
            return self._reject(response, "REPORTING_UNAVAILABLE")
        generated_at = (
            self._utc_now().astimezone(timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
        try:
            model_manifest_yaml, rosbag_metadata_yaml = self._load_bundle_sources()
        except (OSError, ValueError):
            return self._reject(response, "REPORTING_UNAVAILABLE")
        assert self._tasks is not None
        snapshot = {
            "run_id": request.run_id,
            "generated_at": generated_at,
            "git_commit": self._implementation_commit,
            "model_versions": self._model_versions,
            "dataset_versions": self._dataset_versions,
            "assets": [
                {
                    "asset_id": item.asset_id,
                    "risk": float(item.score_0_100),
                    "level": int(item.level),
                }
                for item in self._risks.assets
            ],
            "alerts": list(self._alerts),
            "tasks": [
                {
                    "asset_id": item.asset_id,
                    "reason": item.last_error_code or "inspection",
                    "priority": float(item.computed_priority),
                }
                for item in self._tasks.tasks
            ],
            "trajectory": list(self._trajectory),
            "mission": {
                "run_id": self._tasks.run_id,
                "mission_id": self._tasks.mission_id,
                "route_id": self._tasks.route_id,
                "state_revision": int(self._tasks.state_revision),
                "queue_revision": int(self._tasks.queue_revision),
                "mission_state": int(self._tasks.mission_state),
                "robot_mode": int(self._tasks.robot_mode),
                "emergency_stop_latched": bool(
                    self._tasks.emergency_stop_latched
                ),
                "completed_tasks": int(self._tasks.completed_tasks),
                "total_tasks": int(self._tasks.total_tasks),
                "tasks": [
                    {
                        "task_id": item.task_id,
                        "asset_id": item.asset_id,
                        "state": int(item.state),
                        "computed_priority": float(item.computed_priority),
                        "last_error_code": item.last_error_code,
                    }
                    for item in self._tasks.tasks
                ],
            },
            "model_manifest_yaml": model_manifest_yaml,
            "rosbag_metadata_yaml": rosbag_metadata_yaml,
            "evidence_ids": sorted({
                evidence_id
                for alert in self._alerts
                for evidence_id in alert["evidence_ids"]
            }),
        }
        try:
            artifacts = self._generator.generate(snapshot)
        except ValueError as exc:
            return self._reject(response, str(exc))
        payloads = {
            "evidence": artifacts.evidence_zip,
            "html": artifacts.html,
            "pdf": artifacts.pdf,
        }
        report_id = str(uuid.uuid4())
        assert self._context is not None
        for format_name in formats:
            if not self._submit_artifact(
                report_id,
                format_name,
                request.run_id,
                request.mission_id,
                self._context.context_revision,
                payloads[format_name],
                REPORT_MEDIA_TYPES[format_name],
            ):
                return self._reject(response, "REPORTING_UNAVAILABLE")
        response.accepted = True
        response.report_id = report_id
        return response

    def generate_diagnostic_bundle(self, request, response):
        self._prepare(response)
        if (
            request.schema_version != SCHEMA_VERSION
            or not self._valid_uuid(request.command_id)
            or not self._valid_uuid(request.run_id)
            or not 1 <= len(request.reason) <= 256
        ):
            return self._reject(response, "DIAGNOSTIC_REASON_INVALID")
        if not self._context_matches(request.run_id):
            return self._reject(response, "RUN_CONTEXT_MISMATCH")
        if not COMMIT_PATTERN.fullmatch(self._implementation_commit):
            return self._reject(response, "REPORTING_UNAVAILABLE")
        manifest = json.dumps({
            "schema_version": 1,
            "run_id": request.run_id,
            "reason": request.reason,
            "git_commit": self._implementation_commit,
            "model_versions": self._model_versions,
            "dataset_versions": self._dataset_versions,
        }, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            info = zipfile.ZipInfo("manifest.json", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, manifest)
        diagnostic_id = str(uuid.uuid4())
        assert self._context is not None
        if not self._submit_artifact(
            diagnostic_id,
            "diagnostic",
            request.run_id,
            None,
            self._context.context_revision,
            stream.getvalue(),
            "application/zip",
        ):
            return self._reject(response, "REPORTING_UNAVAILABLE")
        response.accepted = True
        response.diagnostic_id = diagnostic_id
        return response


class ReportGeneratorNode(Node):
    def __init__(self) -> None:
        super().__init__("report_generator")
        self._work_root = Path(str(self.declare_parameter(
            "report_work_directory",
            "/var/lib/substation/reports/.work",
        ).value)).resolve()
        self._work_root.mkdir(parents=True, exist_ok=True)
        implementation_commit = str(self.declare_parameter(
            "implementation_commit",
            "",
        ).value)
        model_versions = self._version_mapping(str(self.declare_parameter(
            "model_versions_json",
            "{}",
        ).value))
        dataset_versions = self._version_mapping(str(self.declare_parameter(
            "dataset_versions_json",
            "{}",
        ).value))
        self._model_manifest_path = Path(str(self.declare_parameter(
            "model_manifest_path",
            "/opt/substation/current/models/manifest.yaml",
        ).value)).resolve()
        self._rosbag_metadata_path = Path(str(self.declare_parameter(
            "rosbag_metadata_path",
            "",
        ).value)).resolve()
        self._store_client = self.create_client(
            StoreEvidence,
            "/reporting/store_evidence",
        )
        self._pending_store_futures = set()
        self._runtime = ReportServiceRuntime(
            ReportGenerator(),
            implementation_commit=implementation_commit,
            model_versions=model_versions,
            dataset_versions=dataset_versions,
            submit_artifact=self._submit_artifact,
            load_bundle_sources=self._load_bundle_sources,
        )
        state_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.create_subscription(
            RunContext,
            "/system/run_context",
            self._runtime.observe_run_context,
            state_qos,
        )
        self.create_subscription(
            AssetRiskArray,
            "/risk/assets",
            self._runtime.observe_risks,
            state_qos,
        )
        self.create_subscription(
            InspectionTaskArray,
            "/mission/inspection_tasks",
            self._runtime.observe_tasks,
            state_qos,
        )
        event_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=100,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.create_subscription(
            RiskAlert,
            "/risk/alerts",
            self._runtime.observe_alert,
            event_qos,
        )
        self.create_subscription(
            Odometry,
            "/odom",
            self._runtime.observe_odometry,
            50,
        )
        if COMMIT_PATTERN.fullmatch(implementation_commit):
            self.create_service(
                GenerateReport,
                "/reporting/generate_report",
                self._runtime.generate_report,
            )
            self.create_service(
                GenerateDiagnosticBundle,
                "/reporting/generate_diagnostic_bundle",
                self._runtime.generate_diagnostic_bundle,
            )
        else:
            self.get_logger().warning(
                "report generator remains unavailable: implementation_commit is invalid"
            )

    @staticmethod
    def _version_mapping(value: str) -> dict[str, str]:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict) or not all(
            isinstance(name, str) and isinstance(version, str)
            for name, version in parsed.items()
        ):
            return {}
        return parsed

    def _load_bundle_sources(self) -> tuple[str, str]:
        payloads = []
        for path in (self._model_manifest_path, self._rosbag_metadata_path):
            if not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
                raise ValueError("REPORT_BUNDLE_SOURCE_INVALID")
            payloads.append(path.read_text(encoding="utf-8"))
        return payloads[0], payloads[1]

    def _submit_artifact(
        self,
        group_id: str,
        format_name: str,
        run_id: str,
        mission_id: str | None,
        context_revision: int,
        payload: bytes,
        media_type: str,
    ) -> bool:
        if not self._store_client.service_is_ready():
            return False
        filenames = {
            "diagnostic": "diagnostic.zip",
            "evidence": "evidence.zip",
            "html": "report.html",
            "pdf": "report.pdf",
        }
        filename = filenames[format_name]
        directory = self._work_root / group_id
        directory.mkdir(parents=True, exist_ok=True)
        (directory / filename).write_bytes(payload)
        stamp = self.get_clock().now().to_msg()
        source_topic = (
            "/reporting/generate_diagnostic_bundle"
            if format_name == "diagnostic"
            else "/reporting/generate_report"
        )
        metadata = {
            "artifact_group_id": group_id,
            "format": format_name,
            "run_id": run_id,
            "mission_id": mission_id,
            "created_at": datetime.now(timezone.utc).isoformat(
                timespec="microseconds"
            ).replace("+00:00", "Z"),
            "source_frame_id": "",
            "source_index": 0,
            "source_message_type": (
                "substation_interfaces/srv/GenerateDiagnosticBundle"
                if format_name == "diagnostic"
                else "substation_interfaces/srv/GenerateReport"
            ),
            "source_ros_nanosec": stamp.nanosec,
            "source_ros_sec": stamp.sec,
            "source_topic": source_topic,
        }
        request = StoreEvidence.Request()
        request.schema_version = SCHEMA_VERSION
        request.evidence_id = (
            group_id
            if format_name == "diagnostic"
            else str(uuid.uuid5(uuid.UUID(group_id), format_name))
        )
        request.run_id = run_id
        request.context_revision = context_revision
        request.media_type = media_type
        request.content_sha256 = hashlib.sha256(payload).hexdigest()
        request.metadata_canonical_json = json.dumps(
            metadata,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        request.source_topic = source_topic
        request.source_ros_sec = stamp.sec
        request.source_ros_nanosec = stamp.nanosec
        request.source_frame_id = ""
        request.source_message_type = metadata["source_message_type"]
        request.source_index = 0
        request.content = list(payload)
        future = self._store_client.call_async(request)
        self._pending_store_futures.add(future)
        future.add_done_callback(self._on_store_complete)
        return True

    def _on_store_complete(self, future) -> None:
        self._pending_store_futures.discard(future)
        response = future.result()
        if response is None or not response.accepted:
            code = "NO_RESPONSE" if response is None else response.error_code
            self.get_logger().error(
                f"evidence store rejected report artifact: {code}"
            )


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ReportGeneratorNode()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except ExternalShutdownException:
        pass
    finally:
        executor.shutdown(timeout_sec=2.0)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
