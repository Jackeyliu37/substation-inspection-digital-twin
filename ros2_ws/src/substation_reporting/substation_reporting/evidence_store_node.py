from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Callable

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from substation_interfaces.msg import RunContext
from substation_interfaces.srv import (
    FreezeEvidence,
    GenerateReport,
    GetReportingReadiness,
    QueryEvidence,
    QueryRunTimeMapping,
    ReadEvidenceChunk,
    RecordRunTimeMapping,
    StoreEvidence,
)

from .evidence_store import EvidenceConflict, EvidenceStore


SCHEMA_VERSION = 1
ALLOWED_MEDIA_TYPES = {
    "image/jpeg",
    "application/json",
    "application/pdf",
    "application/zip",
    "text/html",
}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class EvidenceServiceRuntime:
    def __init__(
        self,
        store: EvidenceStore,
        *,
        report_generator_ready: Callable[[], bool],
    ) -> None:
        self._store = store
        self._report_generator_ready = report_generator_ready
        self._contexts: dict[str, tuple[int, int]] = {}
        self._current_run_id = ""

    def observe_run_context(self, message: RunContext) -> None:
        if (
            message.schema_version != SCHEMA_VERSION
            or not message.run_id
            or message.context_revision < 1
        ):
            return
        current = self._contexts.get(message.run_id)
        if current is not None and message.context_revision < current[0]:
            return
        self._contexts[message.run_id] = (
            message.context_revision,
            message.lifecycle,
        )
        if message.lifecycle in (
            RunContext.LIFECYCLE_ACTIVE,
            RunContext.LIFECYCLE_ENDING,
        ):
            self._current_run_id = message.run_id
        elif self._current_run_id == message.run_id:
            self._current_run_id = ""

    @staticmethod
    def _prepare(response):
        response.schema_version = SCHEMA_VERSION
        return response

    @classmethod
    def _reject(cls, response, code: str, message: str = ""):
        cls._prepare(response)
        if hasattr(response, "accepted"):
            response.accepted = False
        response.error_code = code
        response.error_message = message or code
        return response

    def _run_context_matches(
        self,
        run_id: str,
        context_revision: int,
        *,
        allow_ending: bool,
    ) -> bool:
        context = self._contexts.get(run_id)
        allowed = {RunContext.LIFECYCLE_ACTIVE}
        if allow_ending:
            allowed.add(RunContext.LIFECYCLE_ENDING)
        return bool(
            context is not None
            and context[0] == context_revision
            and context[1] in allowed
        )

    @staticmethod
    def _parse_anchor_utc(value: str) -> datetime:
        try:
            parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
                tzinfo=timezone.utc
            )
        except ValueError as exc:
            raise ValueError("TIME_MAPPING_INVALID") from exc
        if parsed.strftime("%Y-%m-%dT%H:%M:%S.%fZ") != value:
            raise ValueError("TIME_MAPPING_INVALID")
        return parsed

    @staticmethod
    def _canonical_metadata(request) -> dict[str, object]:
        try:
            metadata = json.loads(request.metadata_canonical_json)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("EVIDENCE_SOURCE_INVALID") from exc
        if not isinstance(metadata, dict):
            raise ValueError("EVIDENCE_SOURCE_INVALID")
        canonical = json.dumps(
            metadata,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        expected = {
            "source_topic": request.source_topic,
            "source_ros_sec": request.source_ros_sec,
            "source_ros_nanosec": request.source_ros_nanosec,
            "source_frame_id": request.source_frame_id,
            "source_message_type": request.source_message_type,
            "source_index": request.source_index,
        }
        if canonical != request.metadata_canonical_json or any(
            metadata.get(name) != value for name, value in expected.items()
        ):
            raise ValueError("EVIDENCE_SOURCE_INVALID")
        return metadata

    def record_run_time_mapping(self, request, response):
        self._prepare(response)
        if request.schema_version != SCHEMA_VERSION:
            return self._reject(response, "INTERFACE_VERSION_UNSUPPORTED")
        if not self._run_context_matches(
            request.run_id,
            request.context_revision,
            allow_ending=False,
        ):
            return self._reject(response, "RUN_CONTEXT_MISMATCH")
        try:
            self._store.record_run_time_mapping(
                request.run_id,
                request.context_revision,
                request.anchor_ros_sec,
                request.anchor_ros_nanosec,
                self._parse_anchor_utc(request.anchor_utc),
            )
        except (ValueError, EvidenceConflict) as exc:
            return self._reject(response, str(exc))
        response.accepted = True
        return response

    def query_run_time_mapping(self, request, response):
        self._prepare(response)
        if request.schema_version != SCHEMA_VERSION:
            return self._reject(response, "INTERFACE_VERSION_UNSUPPORTED")
        try:
            mapping = self._store.query_run_time_mapping(request.run_id)
        except ValueError as exc:
            return self._reject(response, str(exc))
        if mapping is None:
            response.found = False
            response.error_code = "TIME_MAPPING_UNAVAILABLE"
            response.error_message = response.error_code
            return response
        response.found = True
        response.context_revision = mapping["context_revision"]
        response.anchor_ros_sec = mapping["anchor_ros_sec"]
        response.anchor_ros_nanosec = mapping["anchor_ros_nanosec"]
        response.anchor_utc = mapping["anchor_utc"]
        return response

    def store_evidence(self, request, response):
        self._prepare(response)
        if request.schema_version != SCHEMA_VERSION:
            return self._reject(response, "INTERFACE_VERSION_UNSUPPORTED")
        if not self._run_context_matches(
            request.run_id,
            request.context_revision,
            allow_ending=True,
        ):
            return self._reject(response, "RUN_CONTEXT_MISMATCH")
        try:
            payload = bytes(request.content)
            if (
                request.media_type not in ALLOWED_MEDIA_TYPES
                or (
                    request.media_type == "text/html"
                    and (
                        request.source_topic != "/reporting/generate_report"
                        or request.source_message_type
                        != "substation_interfaces/srv/GenerateReport"
                    )
                )
                or not SHA256_PATTERN.fullmatch(request.content_sha256)
                or hashlib.sha256(payload).hexdigest() != request.content_sha256
                or not request.source_topic.startswith("/")
                or not request.source_message_type
                or request.source_ros_nanosec >= 1_000_000_000
            ):
                raise ValueError("EVIDENCE_SOURCE_INVALID")
            metadata = self._canonical_metadata(request)
            record = self._store.store_bytes(
                request.run_id,
                request.context_revision,
                request.media_type,
                payload,
                metadata,
                evidence_id=request.evidence_id,
            )
        except (ValueError, EvidenceConflict) as exc:
            return self._reject(response, str(exc))
        response.accepted = True
        response.evidence_revision = record.evidence_revision
        return response

    def freeze_evidence(self, request, response):
        self._prepare(response)
        if request.schema_version != SCHEMA_VERSION:
            return self._reject(response, "INTERFACE_VERSION_UNSUPPORTED")
        if not self._run_context_matches(
            request.run_id,
            request.context_revision,
            allow_ending=False,
        ):
            return self._reject(response, "RUN_CONTEXT_MISMATCH")
        try:
            payload = bytes(request.jpeg)
            metadata = json.loads(request.metadata_canonical_json)
            canonical = json.dumps(
                metadata,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            )
            expected = {
                "source_topic": request.source_topic,
                "source_ros_sec": request.source_ros_sec,
                "source_ros_nanosec": request.source_ros_nanosec,
                "source_frame_id": request.source_frame_id,
            }
            if (
                not isinstance(metadata, dict)
                or canonical != request.metadata_canonical_json
                or any(metadata.get(name) != value for name, value in expected.items())
                or request.source_topic not in {
                    "/camera/image_raw",
                    "/perception/annotated_image",
                }
                or not request.source_frame_id
                or request.source_ros_nanosec >= 1_000_000_000
                or not SHA256_PATTERN.fullmatch(request.content_sha256)
                or hashlib.sha256(payload).hexdigest() != request.content_sha256
                or not payload.startswith(b"\xff\xd8")
                or not payload.endswith(b"\xff\xd9")
            ):
                raise ValueError("EVIDENCE_SOURCE_INVALID")
            record = self._store.store_bytes(
                request.run_id,
                request.context_revision,
                "image/jpeg",
                payload,
                metadata,
                evidence_id=request.evidence_id,
            )
        except (json.JSONDecodeError, ValueError, EvidenceConflict) as exc:
            code = (
                "EVIDENCE_SOURCE_INVALID"
                if isinstance(exc, json.JSONDecodeError)
                else str(exc)
            )
            return self._reject(response, code)
        response.accepted = True
        response.evidence_revision = record.evidence_revision
        return response

    def query_evidence(self, request, response):
        self._prepare(response)
        if request.schema_version != SCHEMA_VERSION:
            return self._reject(response, "INTERFACE_VERSION_UNSUPPORTED")
        try:
            record = self._store.query_evidence(request.evidence_id)
        except ValueError as exc:
            return self._reject(response, str(exc))
        if record is None:
            response.found = False
            response.error_code = "EVIDENCE_NOT_FOUND"
            response.error_message = "EVIDENCE_NOT_FOUND"
            return response
        response.found = True
        response.run_id = record.run_id
        response.context_revision = record.context_revision
        response.evidence_revision = record.evidence_revision
        response.media_type = record.media_type
        response.content_sha256 = record.content_sha256
        response.size_bytes = record.size_bytes
        response.metadata_canonical_json = record.metadata_json
        return response

    def read_evidence_chunk(self, request, response):
        self._prepare(response)
        if request.schema_version != SCHEMA_VERSION:
            return self._reject(response, "INTERFACE_VERSION_UNSUPPORTED")
        if not 1 <= request.max_bytes <= 1_048_576:
            return self._reject(response, "INVALID_RANGE")
        try:
            record = self._store.query_evidence(request.evidence_id)
            if record is None:
                response.found = False
                response.error_code = "EVIDENCE_NOT_FOUND"
                response.error_message = "EVIDENCE_NOT_FOUND"
                return response
            if request.offset_bytes > record.size_bytes:
                raise ValueError("INVALID_RANGE")
            end = min(record.size_bytes, request.offset_bytes + request.max_bytes)
            content = self._store.read_evidence_chunk(
                request.evidence_id,
                request.offset_bytes,
                end,
            )
        except (ValueError, KeyError) as exc:
            return self._reject(response, str(exc))
        response.found = True
        response.size_bytes = record.size_bytes
        response.content_sha256 = record.content_sha256
        response.content = list(content)
        response.eof = end == record.size_bytes
        return response

    def get_readiness(self, request, response):
        self._prepare(response)
        if request.schema_version != SCHEMA_VERSION:
            return self._reject(response, "INTERFACE_VERSION_UNSUPPORTED")
        response.evidence_store_writable = self._store.check_writable()
        response.report_generator_ready = bool(self._report_generator_ready())
        response.time_mapping_ready = bool(
            self._current_run_id
            and self._store.query_run_time_mapping(self._current_run_id) is not None
        )
        if not response.evidence_store_writable:
            response.error_code = "AUDIT_STORAGE_UNAVAILABLE"
            response.error_message = response.error_code
        elif not response.report_generator_ready or not response.time_mapping_ready:
            response.error_code = "REPORTING_UNAVAILABLE"
            response.error_message = response.error_code
        return response


class EvidenceStoreNode(Node):
    def __init__(self) -> None:
        super().__init__("evidence_store")
        object_root = str(self.declare_parameter(
            "evidence_object_root",
            "/var/lib/substation/evidence",
        ).value)
        database_path = str(self.declare_parameter(
            "evidence_database_path",
            "/var/lib/substation/sqlite/evidence.sqlite3",
        ).value)
        self._report_generator = self.create_client(
            GenerateReport,
            "/reporting/generate_report",
        )
        self._runtime = EvidenceServiceRuntime(
            EvidenceStore(object_root, database_path),
            report_generator_ready=self._report_generator.service_is_ready,
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
        for service_type, name, callback in (
            (
                RecordRunTimeMapping,
                "/reporting/record_run_time_mapping",
                self._runtime.record_run_time_mapping,
            ),
            (
                QueryRunTimeMapping,
                "/reporting/query_run_time_mapping",
                self._runtime.query_run_time_mapping,
            ),
            (
                StoreEvidence,
                "/reporting/store_evidence",
                self._runtime.store_evidence,
            ),
            (
                FreezeEvidence,
                "/reporting/freeze_evidence",
                self._runtime.freeze_evidence,
            ),
            (
                QueryEvidence,
                "/reporting/query_evidence",
                self._runtime.query_evidence,
            ),
            (
                ReadEvidenceChunk,
                "/reporting/read_evidence_chunk",
                self._runtime.read_evidence_chunk,
            ),
            (
                GetReportingReadiness,
                "/reporting/readiness",
                self._runtime.get_readiness,
            ),
        ):
            self.create_service(service_type, name, callback)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = EvidenceStoreNode()
    try:
        rclpy.spin(node)
    except ExternalShutdownException:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
