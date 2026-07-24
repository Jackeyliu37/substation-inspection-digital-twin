from __future__ import annotations

from datetime import datetime, timezone
import importlib
import io
from pathlib import Path
import threading
import time
import uuid
import zipfile
from uuid import uuid4

from substation_interfaces.msg import (
    AssetRisk,
    AssetRiskArray,
    InspectionTask,
    InspectionTaskArray,
    RunContext,
)
from substation_interfaces.srv import GenerateDiagnosticBundle, GenerateReport
from substation_interfaces.srv import (
    GetReportingReadiness,
    QueryEvidence,
    RecordRunTimeMapping,
)
import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

from substation_reporting.report_generator import ReportGenerator
from substation_reporting.evidence_store_node import EvidenceStoreNode


PACKAGE = Path(__file__).resolve().parents[1]

def node_module():
    return importlib.import_module("substation_reporting.report_generator_node")


def test_runtime_generates_selected_report_artifacts_and_diagnostic_bundle() -> None:
    module = node_module()
    run_id = str(uuid4())
    mission_id = str(uuid4())
    command_id = str(uuid4())
    submitted: list[tuple[str, str, bytes]] = []
    runtime = module.ReportServiceRuntime(
        ReportGenerator(),
        implementation_commit="a" * 40,
        model_versions={"safety": "development-placeholder"},
        dataset_versions={"meter": "synthetic-v1"},
        submit_artifact=lambda artifact_id, format_name, _run, _revision, payload, _media: (
            submitted.append((artifact_id, format_name, payload)) or True
        ),
        utc_now=lambda: datetime(2026, 7, 24, 3, 4, 5, tzinfo=timezone.utc),
    )
    context = RunContext(
        schema_version=1,
        run_id=run_id,
        context_revision=7,
        lifecycle=RunContext.LIFECYCLE_ACTIVE,
    )
    runtime.observe_run_context(context)
    runtime.observe_risks(AssetRiskArray(
        schema_version=1,
        run_id=run_id,
        assets=[AssetRisk(asset_id="transformer-01", score_0_100=68.0, level=2)],
    ))
    runtime.observe_tasks(InspectionTaskArray(
        schema_version=1,
        run_id=run_id,
        mission_id=mission_id,
        tasks=[InspectionTask(
            schema_version=1,
            task_id=str(uuid4()),
            mission_id=mission_id,
            asset_id="transformer-01",
            computed_priority=77.0,
        )],
    ))

    report = runtime.generate_report(GenerateReport.Request(
        schema_version=1,
        command_id=command_id,
        run_id=run_id,
        mission_id=mission_id,
        formats=["evidence", "html", "pdf"],
    ), GenerateReport.Response())

    assert report.accepted is True
    assert report.report_id
    assert [item[1] for item in submitted] == ["evidence", "html", "pdf"]
    assert submitted[1][2].startswith(b"<!doctype html>")
    assert submitted[2][2].startswith(b"%PDF-1.4")

    submitted.clear()
    diagnostic = runtime.generate_diagnostic_bundle(
        GenerateDiagnosticBundle.Request(
            schema_version=1,
            command_id=str(uuid4()),
            run_id=run_id,
            reason="operator diagnostic",
        ),
        GenerateDiagnosticBundle.Response(),
    )
    assert diagnostic.accepted is True
    assert diagnostic.diagnostic_id
    with zipfile.ZipFile(io.BytesIO(submitted[0][2])) as archive:
        assert archive.namelist() == ["manifest.json"]


def test_runtime_rejects_unsorted_or_duplicate_report_formats() -> None:
    module = node_module()
    runtime = module.ReportServiceRuntime(
        ReportGenerator(),
        implementation_commit="a" * 40,
        model_versions={},
        dataset_versions={},
        submit_artifact=lambda *_args: True,
    )
    rejected = runtime.generate_report(GenerateReport.Request(
        schema_version=1,
        command_id=str(uuid4()),
        run_id=str(uuid4()),
        mission_id=str(uuid4()),
        formats=["pdf", "html"],
    ), GenerateReport.Response())
    assert rejected.accepted is False
    assert rejected.error_code == "VALIDATION_FAILED"


def wait_future(future, timeout_s: float):
    deadline = time.monotonic() + timeout_s
    while not future.done() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert future.done(), "timed out waiting for reporting pipeline"
    return future.result()


def test_ros_report_generator_submits_artifacts_through_evidence_service(tmp_path) -> None:
    module = node_module()
    run_id = str(uuid4())
    mission_id = str(uuid4())
    database = tmp_path / "sqlite/evidence.sqlite3"
    object_root = tmp_path / "evidence"
    work_root = tmp_path / "report-work"
    rclpy.init(args=[
        "--ros-args",
        "-p", f"evidence_database_path:={database}",
        "-p", f"evidence_object_root:={object_root}",
        "-p", f"report_work_directory:={work_root}",
        "-p", f"implementation_commit:={'a' * 40}",
    ])
    evidence_node = EvidenceStoreNode()
    report_node = module.ReportGeneratorNode()
    client_node = Node(f"report_client_{uuid4().hex}")
    state_qos = QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=1,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
    )
    contexts = client_node.create_publisher(RunContext, "/system/run_context", state_qos)
    risks = client_node.create_publisher(AssetRiskArray, "/risk/assets", state_qos)
    tasks = client_node.create_publisher(
        InspectionTaskArray,
        "/mission/inspection_tasks",
        state_qos,
    )
    mapping = client_node.create_client(
        RecordRunTimeMapping,
        "/reporting/record_run_time_mapping",
    )
    generate = client_node.create_client(GenerateReport, "/reporting/generate_report")
    query = client_node.create_client(QueryEvidence, "/reporting/query_evidence")
    readiness = client_node.create_client(GetReportingReadiness, "/reporting/readiness")
    executor = MultiThreadedExecutor(num_threads=5)
    for node in (evidence_node, report_node, client_node):
        executor.add_node(node)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    try:
        assert generate.wait_for_service(timeout_sec=5.0)
        assert mapping.wait_for_service(timeout_sec=5.0)
        context = RunContext(
            schema_version=1,
            run_id=run_id,
            context_revision=7,
            lifecycle=RunContext.LIFECYCLE_ACTIVE,
        )
        contexts.publish(context)
        risks.publish(AssetRiskArray(
            schema_version=1,
            run_id=run_id,
            assets=[AssetRisk(asset_id="transformer-01", score_0_100=68.0, level=2)],
        ))
        tasks.publish(InspectionTaskArray(
            schema_version=1,
            run_id=run_id,
            mission_id=mission_id,
            tasks=[InspectionTask(
                schema_version=1,
                task_id=str(uuid4()),
                mission_id=mission_id,
                asset_id="transformer-01",
            )],
        ))
        time.sleep(0.1)
        recorded = wait_future(mapping.call_async(RecordRunTimeMapping.Request(
            schema_version=1,
            run_id=run_id,
            context_revision=7,
            anchor_ros_sec=1,
            anchor_ros_nanosec=0,
            anchor_utc="2026-07-24T04:05:06.000000Z",
        )), 5.0)
        assert recorded.accepted is True
        report = wait_future(generate.call_async(GenerateReport.Request(
            schema_version=1,
            command_id=str(uuid4()),
            run_id=run_id,
            mission_id=mission_id,
            formats=["html", "pdf"],
        )), 5.0)
        assert report.accepted is True

        html_id = str(uuid.uuid5(uuid.UUID(report.report_id), "html"))
        queried = None
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            queried = wait_future(query.call_async(QueryEvidence.Request(
                schema_version=1,
                evidence_id=html_id,
            )), 2.0)
            if queried.found:
                break
            time.sleep(0.05)
        assert queried is not None and queried.found is True
        assert queried.media_type == "text/html"
        state = wait_future(readiness.call_async(GetReportingReadiness.Request(
            schema_version=1,
        )), 5.0)
        assert state.evidence_store_writable is True
        assert state.report_generator_ready is True
        assert state.time_mapping_ready is True
        assert (work_root / report.report_id / "report.html").is_file()
    finally:
        executor.shutdown(timeout_sec=2.0)
        thread.join(timeout=2.0)
        for node in (client_node, report_node, evidence_node):
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def test_report_generator_is_packaged_in_reporting_launch() -> None:
    source = (PACKAGE / "launch/reporting.launch.py").read_text(encoding="utf-8")
    assert 'executable="report_generator"' in source
    assert '"report_work_directory"' in source
    assert '"implementation_commit"' in source
    setup = (PACKAGE / "setup.py").read_text(encoding="utf-8")
    assert "report_generator = substation_reporting.report_generator_node:main" in setup


def test_ros_report_generator_does_not_advertise_service_without_commit(tmp_path) -> None:
    module = node_module()
    rclpy.init(args=[
        "--ros-args",
        "-p", f"report_work_directory:={tmp_path / 'work'}",
    ])
    report_node = module.ReportGeneratorNode()
    client_node = Node(f"unconfigured_report_client_{uuid4().hex}")
    client = client_node.create_client(GenerateReport, "/reporting/generate_report")
    try:
        assert client.wait_for_service(timeout_sec=0.5) is False
    finally:
        report_node.destroy_node()
        client_node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
