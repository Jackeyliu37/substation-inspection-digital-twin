from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
import threading
import time
from uuid import uuid4

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from substation_interfaces.msg import RunContext
from substation_interfaces.srv import (
    FreezeEvidence,
    GetReportingReadiness,
    QueryEvidence,
    QueryRunTimeMapping,
    ReadEvidenceChunk,
    RecordRunTimeMapping,
    StoreEvidence,
)

from substation_reporting.evidence_store import EvidenceStore


PACKAGE = Path(__file__).resolve().parents[1]


def node_module():
    return importlib.import_module("substation_reporting.evidence_store_node")


def active_context(run_id: str, revision: int = 7) -> RunContext:
    value = RunContext()
    value.schema_version = 1
    value.run_id = run_id
    value.context_revision = revision
    value.lifecycle = RunContext.LIFECYCLE_ACTIVE
    return value


def test_runtime_records_mapping_and_round_trips_chunked_evidence(tmp_path) -> None:
    module = node_module()
    run_id = str(uuid4())
    evidence_id = str(uuid4())
    runtime = module.EvidenceServiceRuntime(
        EvidenceStore(tmp_path),
        report_generator_ready=lambda: True,
    )
    runtime.observe_run_context(active_context(run_id))

    mapping = RecordRunTimeMapping.Request(
        schema_version=1,
        run_id=run_id,
        context_revision=7,
        anchor_ros_sec=123,
        anchor_ros_nanosec=400_000_000,
        anchor_utc="2026-07-24T01:02:03.000000Z",
    )
    mapping_response = runtime.record_run_time_mapping(
        mapping,
        RecordRunTimeMapping.Response(),
    )
    assert mapping_response.accepted is True
    mapping_query = runtime.query_run_time_mapping(
        QueryRunTimeMapping.Request(schema_version=1, run_id=run_id),
        QueryRunTimeMapping.Response(),
    )
    assert mapping_query.found is True
    assert mapping_query.context_revision == 7
    assert mapping_query.anchor_utc == mapping.anchor_utc

    payload = b'{"risk":68}'
    metadata = {
        "source_frame_id": "map",
        "source_index": 0,
        "source_message_type": "substation_interfaces/msg/AssetRiskArray",
        "source_ros_nanosec": 9,
        "source_ros_sec": 123,
        "source_topic": "/risk/assets",
    }
    store = StoreEvidence.Request(
        schema_version=1,
        evidence_id=evidence_id,
        run_id=run_id,
        context_revision=7,
        media_type="application/json",
        content_sha256=hashlib.sha256(payload).hexdigest(),
        metadata_canonical_json=json.dumps(
            metadata, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        ),
        source_topic="/risk/assets",
        source_ros_sec=123,
        source_ros_nanosec=9,
        source_frame_id="map",
        source_message_type="substation_interfaces/msg/AssetRiskArray",
        source_index=0,
        content=list(payload),
    )
    stored = runtime.store_evidence(store, StoreEvidence.Response())
    assert stored.accepted is True
    assert stored.evidence_revision == 1

    queried = runtime.query_evidence(
        QueryEvidence.Request(schema_version=1, evidence_id=evidence_id),
        QueryEvidence.Response(),
    )
    assert queried.found is True
    assert queried.run_id == run_id
    assert queried.content_sha256 == store.content_sha256
    assert queried.metadata_canonical_json == store.metadata_canonical_json

    chunk = runtime.read_evidence_chunk(
        ReadEvidenceChunk.Request(
            schema_version=1,
            evidence_id=evidence_id,
            offset_bytes=2,
            max_bytes=4,
        ),
        ReadEvidenceChunk.Response(),
    )
    assert bytes(chunk.content) == payload[2:6]
    assert chunk.eof is False

    readiness = runtime.get_readiness(
        GetReportingReadiness.Request(schema_version=1),
        GetReportingReadiness.Response(),
    )
    assert readiness.evidence_store_writable is True
    assert readiness.report_generator_ready is True
    assert readiness.time_mapping_ready is True
    assert readiness.error_code == ""


def test_runtime_rejects_digest_or_run_context_mismatch(tmp_path) -> None:
    module = node_module()
    run_id = str(uuid4())
    runtime = module.EvidenceServiceRuntime(
        EvidenceStore(tmp_path),
        report_generator_ready=lambda: False,
    )
    runtime.observe_run_context(active_context(run_id))
    request = StoreEvidence.Request(
        schema_version=1,
        evidence_id=str(uuid4()),
        run_id=run_id,
        context_revision=8,
        media_type="application/json",
        content_sha256="0" * 64,
        metadata_canonical_json="{}",
        source_topic="/risk/assets",
        source_ros_sec=1,
        source_ros_nanosec=0,
        source_frame_id="map",
        source_message_type="substation_interfaces/msg/AssetRiskArray",
        source_index=0,
        content=list(b"{}"),
    )

    rejected = runtime.store_evidence(request, StoreEvidence.Response())

    assert rejected.accepted is False
    assert rejected.error_code == "RUN_CONTEXT_MISMATCH"


def test_report_html_is_allowed_only_from_report_generator(tmp_path) -> None:
    module = node_module()
    assert "text/html" in module.ALLOWED_MEDIA_TYPES
    run_id = str(uuid4())
    runtime = module.EvidenceServiceRuntime(
        EvidenceStore(tmp_path),
        report_generator_ready=lambda: True,
    )
    runtime.observe_run_context(active_context(run_id))
    payload = b"<html></html>"
    metadata = {
        "source_frame_id": "map",
        "source_index": 0,
        "source_message_type": "substation_interfaces/msg/AssetRiskArray",
        "source_ros_nanosec": 0,
        "source_ros_sec": 1,
        "source_topic": "/risk/assets",
    }
    request = StoreEvidence.Request(
        schema_version=1,
        evidence_id=str(uuid4()),
        run_id=run_id,
        context_revision=7,
        media_type="text/html",
        content_sha256=hashlib.sha256(payload).hexdigest(),
        metadata_canonical_json=json.dumps(
            metadata, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        ),
        source_topic="/risk/assets",
        source_ros_sec=1,
        source_ros_nanosec=0,
        source_frame_id="map",
        source_message_type="substation_interfaces/msg/AssetRiskArray",
        source_index=0,
        content=list(payload),
    )
    rejected = runtime.store_evidence(request, StoreEvidence.Response())
    assert rejected.accepted is False
    assert rejected.error_code == "EVIDENCE_SOURCE_INVALID"


def test_runtime_freezes_valid_jpeg_and_rejects_non_jpeg(tmp_path) -> None:
    module = node_module()
    run_id = str(uuid4())
    runtime = module.EvidenceServiceRuntime(
        EvidenceStore(tmp_path),
        report_generator_ready=lambda: True,
    )
    runtime.observe_run_context(active_context(run_id))
    jpeg = b"\xff\xd8camera-frame\xff\xd9"
    metadata = {
        "source_frame_id": "camera_optical_frame",
        "source_ros_nanosec": 22,
        "source_ros_sec": 10,
        "source_topic": "/perception/annotated_image",
    }
    request = FreezeEvidence.Request(
        schema_version=1,
        evidence_id=str(uuid4()),
        run_id=run_id,
        context_revision=7,
        source_topic="/perception/annotated_image",
        source_ros_sec=10,
        source_ros_nanosec=22,
        source_frame_id="camera_optical_frame",
        content_sha256=hashlib.sha256(jpeg).hexdigest(),
        metadata_canonical_json=json.dumps(
            metadata, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        ),
        jpeg=list(jpeg),
    )

    frozen = runtime.freeze_evidence(request, FreezeEvidence.Response())

    assert frozen.accepted is True
    assert frozen.evidence_revision == 1
    request.evidence_id = str(uuid4())
    request.jpeg = list(b"not-jpeg")
    request.content_sha256 = hashlib.sha256(b"not-jpeg").hexdigest()
    rejected = runtime.freeze_evidence(request, FreezeEvidence.Response())
    assert rejected.accepted is False
    assert rejected.error_code == "EVIDENCE_SOURCE_INVALID"


def wait_future(future, timeout_s: float):
    deadline = time.monotonic() + timeout_s
    while not future.done() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert future.done(), "timed out waiting for reporting service"
    return future.result()


def test_ros_node_exposes_time_mapping_and_readiness_services(tmp_path) -> None:
    module = node_module()
    run_id = str(uuid4())
    database = tmp_path / "sqlite/evidence.sqlite3"
    object_root = tmp_path / "evidence"
    rclpy.init(args=[
        "--ros-args",
        "-p", f"evidence_database_path:={database}",
        "-p", f"evidence_object_root:={object_root}",
    ])
    evidence_node = module.EvidenceStoreNode()
    client_node = Node(f"evidence_client_{uuid4().hex}")
    state_qos = QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=1,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
    )
    contexts = client_node.create_publisher(
        RunContext,
        "/system/run_context",
        state_qos,
    )
    record = client_node.create_client(
        RecordRunTimeMapping,
        "/reporting/record_run_time_mapping",
    )
    query = client_node.create_client(
        QueryRunTimeMapping,
        "/reporting/query_run_time_mapping",
    )
    readiness = client_node.create_client(
        GetReportingReadiness,
        "/reporting/readiness",
    )
    executor = MultiThreadedExecutor(num_threads=3)
    executor.add_node(evidence_node)
    executor.add_node(client_node)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    try:
        assert record.wait_for_service(timeout_sec=5.0)
        assert query.wait_for_service(timeout_sec=5.0)
        assert readiness.wait_for_service(timeout_sec=5.0)
        contexts.publish(active_context(run_id))
        time.sleep(0.1)
        recorded = wait_future(record.call_async(RecordRunTimeMapping.Request(
            schema_version=1,
            run_id=run_id,
            context_revision=7,
            anchor_ros_sec=2,
            anchor_ros_nanosec=3,
            anchor_utc="2026-07-24T02:03:04.000000Z",
        )), 5.0)
        assert recorded.accepted is True
        queried = wait_future(query.call_async(QueryRunTimeMapping.Request(
            schema_version=1,
            run_id=run_id,
        )), 5.0)
        assert queried.found is True
        state = wait_future(readiness.call_async(GetReportingReadiness.Request(
            schema_version=1,
        )), 5.0)
        assert state.evidence_store_writable is True
        assert state.report_generator_ready is False
        assert state.time_mapping_ready is True
        assert state.error_code == "REPORTING_UNAVAILABLE"
        assert database.is_file()
        assert (object_root / "objects").is_dir()
    finally:
        executor.shutdown(timeout_sec=2.0)
        thread.join(timeout=2.0)
        evidence_node.destroy_node()
        client_node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def test_evidence_store_node_is_packaged_with_explicit_storage_paths() -> None:
    launch = PACKAGE / "launch/reporting.launch.py"
    assert launch.is_file()
    source = launch.read_text(encoding="utf-8")
    assert 'package="substation_reporting"' in source
    assert 'executable="evidence_store"' in source
    assert '"evidence_database_path"' in source
    assert '"evidence_object_root"' in source

    setup = (PACKAGE / "setup.py").read_text(encoding="utf-8")
    manifest = (PACKAGE / "package.xml").read_text(encoding="utf-8")
    assert "evidence_store = substation_reporting.evidence_store_node:main" in setup
    assert "<exec_depend>rclpy</exec_depend>" in manifest
    assert "<exec_depend>substation_interfaces</exec_depend>" in manifest
