from __future__ import annotations

import base64
from datetime import datetime, timezone
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).parents[2] / "ros2_ws/src/substation_web_gateway"))

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from nav_msgs.msg import OccupancyGrid
import rclpy
from rclpy.context import Context
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import String
from substation_interfaces.msg import (
    AssetRisk,
    AssetRiskArray,
    InspectionTask,
    InspectionTaskArray,
    RunContext,
)
from substation_interfaces.srv import GetReportingReadiness, QueryRunTimeMapping

from substation_web_gateway.app import GatewayState
from substation_web_gateway.ros_adapter import RosGatewayAdapter, RosGatewayNode, RosStateProjector


RUN_ID = "f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f"
MISSION_ID = "0c5efce1-655b-413d-9847-da203fb5ca5e"


def _run_context(run_id: str = RUN_ID) -> RunContext:
    message = RunContext()
    message.schema_version = 1
    message.header.stamp.sec = 100
    message.header.stamp.nanosec = 250_000_000
    message.context_revision = 17
    message.lifecycle = RunContext.LIFECYCLE_ACTIVE
    message.run_id = run_id
    message.started_at.sec = 90
    message.started_at.nanosec = 250_000_000
    message.reason_code = "MISSION_STARTED"
    message.reason = "operator start"
    return message


def _mission(run_id: str = RUN_ID) -> InspectionTaskArray:
    message = InspectionTaskArray()
    message.schema_version = 1
    message.header.frame_id = "map"
    message.run_id = run_id
    message.mission_id = MISSION_ID
    message.route_id = "default-route"
    message.state_revision = 63
    message.queue_revision = 42
    message.mission_state = InspectionTaskArray.MISSION_RUNNING
    message.robot_mode = InspectionTaskArray.MODE_AUTONOMOUS
    message.emergency_stop_latch_revision = 12
    message.active_task_id = "63b3e775-75cd-4443-a4a3-cc1b97ec4b3c"
    message.completed_tasks = 3
    message.total_tasks = 8
    message.progress_0_1 = 0.375
    task = InspectionTask()
    task.schema_version = 1
    task.task_id = message.active_task_id
    task.mission_id = MISSION_ID
    task.asset_id = "transformer-01"
    task.task_type = InspectionTask.TYPE_INSPECT_ASSET
    task.state = InspectionTask.STATE_ACTIVE
    task.computed_priority = 78.2
    task.risk_score_0_100 = 72.0
    task.goal.header.frame_id = "map"
    task.goal.pose.position.x = 3.0
    task.goal.pose.position.y = 2.0
    task.goal.pose.orientation.w = 1.0
    task.attempt = 1
    message.tasks = [task]
    return message


def _twin(run_id: str = RUN_ID) -> DiagnosticArray:
    message = DiagnosticArray()
    message.header.frame_id = "map"
    message.header.stamp.sec = 101
    status = DiagnosticStatus()
    status.name = "transformer-01"
    status.hardware_id = "transformer"
    values = {
        "run_id": run_id,
        "category": "transformer",
        "state": "attention",
        "pose_x_m": "4.0",
        "pose_y_m": "2.0",
        "pose_z_m": "0.0",
        "orientation_x": "0.0",
        "orientation_y": "0.0",
        "orientation_z": "0.0",
        "orientation_w": "1.0",
        "temperature_celsius": "72.4",
        "smoke_0_1": "0.05",
        "gas_ppm": "8.0",
        "meter_reading": "",
        "meter_unit": "",
        "last_observed_ros_sec": "101",
        "last_observed_ros_nanosec": "0",
        "latest_evidence_id": "",
    }
    status.values = [KeyValue(key=key, value=value) for key, value in values.items()]
    message.status = [status]
    return message


def _risk(run_id: str = RUN_ID) -> AssetRiskArray:
    message = AssetRiskArray()
    message.schema_version = 1
    message.run_id = run_id
    message.risk_revision = 72
    item = AssetRisk()
    item.schema_version = 1
    item.asset_id = "transformer-01"
    item.score_0_100 = 48.2
    item.level = AssetRisk.LEVEL_ATTENTION
    item.temperature_0_1 = 0.7
    item.smoke_0_1 = 0.05
    item.gas_0_1 = 0.08
    item.context_0_1 = 0.3
    message.assets = [item]
    return message


def test_projection_stays_fail_closed_until_matching_authoritative_snapshots() -> None:
    state = GatewayState()
    projection = RosStateProjector(state)

    projection.on_run_context(_run_context())
    projection.on_mission(_mission("4971535f-35e7-4a35-98e9-2592149f6fb9"))
    projection.on_risk(_risk("4971535f-35e7-4a35-98e9-2592149f6fb9"))
    projection.on_twin(_twin("4971535f-35e7-4a35-98e9-2592149f6fb9"))

    assert state.run_id == RUN_ID
    assert state.ready_dependencies["run_context"] is True
    assert state.ready_dependencies["mission"] is False
    assert state.ready_dependencies["risk"] is False
    assert state.assets == []


def test_republished_identical_state_snapshots_do_not_advance_web_revision() -> None:
    state = GatewayState()
    projection = RosStateProjector(state)

    assert projection.on_run_context(_run_context()) is True
    context_revision = state.snapshot_revision
    assert projection.on_run_context(_run_context()) is True
    assert state.snapshot_revision == context_revision

    assert projection.on_mission(_mission()) is True
    mission_revision = state.snapshot_revision
    assert projection.on_mission(_mission()) is True
    assert state.snapshot_revision == mission_revision

    assert projection.on_twin(_twin()) is True
    assert projection.on_risk(_risk()) is True
    asset_revision = state.snapshot_revision
    assert projection.on_twin(_twin()) is True
    assert projection.on_risk(_risk()) is True
    assert state.snapshot_revision == asset_revision


def test_projection_builds_web_snapshots_without_inventing_domain_state() -> None:
    state = GatewayState()
    projection = RosStateProjector(state)
    projection.set_ros_graph_ready(ros=True, gazebo=True, nav2=True)
    projection.on_run_context(_run_context())
    projection.set_time_mapping(
        run_id=RUN_ID,
        context_revision=17,
        anchor_ros_sec=100,
        anchor_ros_nanosec=250_000_000,
        anchor_utc="2026-07-22T14:00:00.000000Z",
    )
    projection.on_mission(_mission())
    projection.on_twin(_twin())
    projection.on_risk(_risk())
    projection.set_reporting_readiness(
        evidence_store_writable=True,
        report_generator_ready=True,
        time_mapping_ready=True,
    )

    assert all(state.ready_dependencies.values())
    assert state.system["overall"] == "ready"
    assert state.system["run_context"] == {
        "lifecycle": "active",
        "context_revision": "17",
        "started_at": "2026-07-22T13:59:50.000000Z",
        "ended_at": None,
        "transition_command_id": None,
        "reason_code": "MISSION_STARTED",
        "reason": "operator start",
    }
    assert state.mission["state"] == "running"
    assert state.mission["queue_revision"] == "42"
    assert state.mission["tasks"][0]["type"] == "inspect_asset"
    assert state.mission["tasks"][0]["goal"] == {
        "frame_id": "map",
        "x_m": 3.0,
        "y_m": 2.0,
        "yaw_rad": 0.0,
    }
    assert state.assets[0]["asset_id"] == "transformer-01"
    assert state.assets[0]["measurements"]["temperature_celsius"] == 72.4
    assert state.assets[0]["risk"]["level"] == "attention"
    assert state.assets[0]["observed_at"] == "2026-07-22T14:00:00.750000Z"
    datetime.fromisoformat(state.assets[0]["observed_at"].replace("Z", "+00:00")).astimezone(
        timezone.utc
    )


def test_projection_validates_and_encodes_standard_occupancy_grid() -> None:
    state = GatewayState()
    projection = RosStateProjector(state)
    grid = OccupancyGrid()
    grid.header.frame_id = "map"
    grid.header.stamp.sec = 123
    grid.header.stamp.nanosec = 450_000_000
    grid.info.resolution = 0.05
    grid.info.width = 2
    grid.info.height = 2
    grid.info.origin.position.x = -10.0
    grid.info.origin.position.y = -7.5
    grid.info.origin.orientation.w = 1.0
    grid.data = [-1, 0, 50, 100]

    assert projection.on_map(grid) is True
    assert state.map_snapshot == {
        "map_revision": "1",
        "frame_id": "map",
        "source_ros_time": {"sec": 123, "nanosec": 450_000_000},
        "resolution_m": 0.05,
        "width_cells": 2,
        "height_cells": 2,
        "origin": {"x_m": -10.0, "y_m": -7.5, "yaw_rad": 0.0},
        "data_encoding": "base64-int8-row-major-v1",
        "data": base64.b64encode(bytes((255, 0, 50, 100))).decode("ascii"),
    }

    invalid = OccupancyGrid()
    invalid.header.frame_id = "odom"
    invalid.info.width = 1
    invalid.info.height = 1
    invalid.data = [0]
    assert projection.on_map(invalid) is False
    assert state.map_snapshot is None


def test_adapter_source_does_not_consume_forbidden_development_or_truth_topics() -> None:
    source = (
        Path(__file__).parents[2]
        / "ros2_ws/src/substation_web_gateway/substation_web_gateway/ros_adapter.py"
    ).read_text(encoding="utf-8")
    assert "/perception/development/" not in source
    assert "/simulation/scenario_truth" not in source


def test_runtime_adapter_starts_and_stops_its_private_ros_context() -> None:
    adapter = RosGatewayAdapter(GatewayState())
    adapter.start()
    try:
        assert adapter._thread is not None
        assert adapter._thread.is_alive()
    finally:
        adapter.stop()
    assert adapter._thread is None


def test_live_ros_node_reaches_ready_only_from_real_topics_and_services() -> None:
    context = Context()
    rclpy.init(context=context)
    source = Node("gateway_test_source", context=context)
    state = GatewayState()
    gateway = RosGatewayNode(state, context=context)
    executor = SingleThreadedExecutor(context=context)
    executor.add_node(source)
    executor.add_node(gateway)
    state_qos = QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=1,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
    )
    context_pub = source.create_publisher(RunContext, "/system/run_context", state_qos)
    mission_pub = source.create_publisher(
        InspectionTaskArray, "/mission/inspection_tasks", state_qos
    )
    twin_pub = source.create_publisher(DiagnosticArray, "/digital_twin/assets", state_qos)
    risk_pub = source.create_publisher(AssetRiskArray, "/risk/assets", state_qos)
    source.create_publisher(Image, "/camera/image_raw", 1)
    source.create_publisher(String, "/navigate_to_pose/_action/status", 1)

    def query_mapping(_request, response):
        response.schema_version = 1
        response.found = True
        response.context_revision = 17
        response.anchor_ros_sec = 100
        response.anchor_ros_nanosec = 250_000_000
        response.anchor_utc = "2026-07-22T14:00:00.000000Z"
        return response

    def reporting_ready(_request, response):
        response.schema_version = 1
        response.evidence_store_writable = True
        response.report_generator_ready = True
        response.time_mapping_ready = True
        return response

    source.create_service(
        QueryRunTimeMapping, "/reporting/query_run_time_mapping", query_mapping
    )
    source.create_service(GetReportingReadiness, "/reporting/readiness", reporting_ready)

    try:
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not all(state.ready_dependencies.values()):
            context_pub.publish(_run_context())
            mission_pub.publish(_mission())
            twin_pub.publish(_twin())
            risk_pub.publish(_risk())
            executor.spin_once(timeout_sec=0.05)
        assert all(state.ready_dependencies.values()), state.ready_dependencies
        assert state.run_id == RUN_ID
        assert state.assets[0]["risk"]["score_0_100"] == 48.2
        assert state.mission["mission_id"] == MISSION_ID
    finally:
        executor.remove_node(gateway)
        executor.remove_node(source)
        gateway.destroy_node()
        source.destroy_node()
        executor.shutdown()
        context.shutdown()
