from __future__ import annotations

import asyncio
import base64
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).parents[2] / "ros2_ws/src/substation_web_gateway"))

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from nav_msgs.msg import OccupancyGrid
from nav_msgs.msg import Odometry
import rclpy
from rclpy.context import Context
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import BatteryState, Image
from std_msgs.msg import String
import pytest
from geometry_msgs.msg import TransformStamped
from tf2_ros import TransformBroadcaster
from substation_interfaces.msg import (
    AssetRisk,
    AssetRiskArray,
    InspectionTask,
    InspectionTaskArray,
    ManualVelocityStatus,
    RunContext,
)
from substation_interfaces.srv import (
    GetReportingReadiness,
    ManageMission,
    QueryRunTimeMapping,
    RecordRunTimeMapping,
)

from substation_web_gateway.app import CommandStore, GatewayState, create_app
from substation_web_gateway.ros_adapter import RosGatewayAdapter, RosGatewayNode, RosStateProjector


RUN_ID = "f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f"
MISSION_ID = "0c5efce1-655b-413d-9847-da203fb5ca5e"


def test_projector_encodes_real_annotated_rgb_frame_as_jpeg() -> None:
    state = GatewayState()
    projector = RosStateProjector(state)
    message = Image()
    message.header.frame_id = "camera_optical_frame"
    message.header.stamp.sec = 12
    message.height = 2
    message.width = 2
    message.encoding = "rgb8"
    message.step = 6
    message.data = bytes([255, 0, 0] * 4)

    projector.on_annotated_image(message)

    assert state.camera_jpeg is not None
    assert state.camera_jpeg.startswith(b"\xff\xd8")
    assert state.camera_jpeg.endswith(b"\xff\xd9")
    assert state.camera_metadata == {
        "source_topic": "/perception/annotated_image",
        "source_frame_id": "camera_optical_frame",
        "source_ros_time": {"sec": 12, "nanosec": 0},
        "width": 2,
        "height": 2,
        "encoding": "jpeg",
    }


def test_projector_accepts_jazzy_byte_diagnostic_levels() -> None:
    state = GatewayState()
    projector = RosStateProjector(state)
    message = DiagnosticArray()
    message.header.stamp.sec = 12
    message.header.stamp.nanosec = 500_000_000
    message.status = [
        DiagnosticStatus(
            level=DiagnosticStatus.OK,
            name="perception",
            message="ready",
        ),
        DiagnosticStatus(
            level=DiagnosticStatus.ERROR,
            name="risk",
            message="fault",
        ),
    ]

    projector.on_diagnostics(message)

    assert [item["status"] for item in state.system["components"]] == [
        "ok",
        "error",
    ]


def _http_get(app, path: str):
    async def invoke():
        sent = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            sent.append(message)

        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "client": ("test", 1234),
            "server": ("test", 80),
            "scheme": "http",
        }
        await app(scope, receive, send)
        start = next(item for item in sent if item["type"] == "http.response.start")
        body = b"".join(item.get("body", b"") for item in sent if item["type"] == "http.response.body")
        return start["status"], json.loads(body)

    return asyncio.run(invoke())


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


class _CompletedFuture:
    def __init__(self, response) -> None:
        self._response = response

    def result(self):
        return self._response

    def add_done_callback(self, callback) -> None:
        callback(self)


class _ReadyServiceClient:
    def __init__(self, response) -> None:
        self.response = response
        self.requests = []

    def service_is_ready(self) -> bool:
        return True

    def call_async(self, request):
        self.requests.append(request)
        return _CompletedFuture(self.response)


def _missing_mapping_response() -> QueryRunTimeMapping.Response:
    response = QueryRunTimeMapping.Response()
    response.schema_version = 1
    response.found = False
    response.error_code = "TIME_MAPPING_UNAVAILABLE"
    response.error_message = response.error_code
    return response


def test_gateway_records_mapping_only_after_observing_starting_to_active_transition() -> None:
    context = Context()
    rclpy.init(context=context)
    gateway = RosGatewayNode(GatewayState(), context=context)
    query = _ReadyServiceClient(_missing_mapping_response())
    recorded = RecordRunTimeMapping.Response()
    recorded.schema_version = 1
    recorded.accepted = True
    record = _ReadyServiceClient(recorded)
    gateway._query_mapping = query
    gateway._record_mapping = record
    starting = _run_context()
    starting.lifecycle = RunContext.LIFECYCLE_STARTING
    starting.context_revision = 16
    active = _run_context()

    try:
        gateway._on_context(starting)
        gateway._on_context(active)

        assert len(query.requests) == 1
        assert len(record.requests) == 1
        assert record.requests[0].run_id == RUN_ID
        assert gateway.projector._time_mapping is not None
    finally:
        gateway.destroy_node()
        context.shutdown()


def test_gateway_restart_does_not_recreate_missing_active_run_mapping() -> None:
    context = Context()
    rclpy.init(context=context)
    gateway = RosGatewayNode(GatewayState(), context=context)
    query = _ReadyServiceClient(_missing_mapping_response())
    recorded = RecordRunTimeMapping.Response()
    recorded.schema_version = 1
    recorded.accepted = True
    record = _ReadyServiceClient(recorded)
    gateway._query_mapping = query
    gateway._record_mapping = record

    try:
        gateway._on_context(_run_context())

        assert len(query.requests) == 1
        assert record.requests == []
        assert gateway.projector._time_mapping is None
    finally:
        gateway.destroy_node()
        context.shutdown()


def test_gateway_restart_queries_existing_mapping_for_ended_run() -> None:
    context = Context()
    rclpy.init(context=context)
    gateway = RosGatewayNode(GatewayState(), context=context)
    response = QueryRunTimeMapping.Response()
    response.schema_version = 1
    response.found = True
    response.context_revision = 17
    response.anchor_ros_sec = 100
    response.anchor_ros_nanosec = 250_000_000
    response.anchor_utc = "2026-07-22T14:00:00.000000Z"
    query = _ReadyServiceClient(response)
    gateway._query_mapping = query
    ended = _run_context()
    ended.lifecycle = RunContext.LIFECYCLE_ENDED
    ended.ended_at.sec = 140

    try:
        gateway._on_context(ended)

        assert len(query.requests) == 1
        assert gateway.projector._time_mapping is not None
        assert gateway.projector.state.ready_dependencies["run_context"] is True
    finally:
        gateway.destroy_node()
        context.shutdown()


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


def test_all_twin_assets_are_exposed_even_before_each_has_a_risk_sample() -> None:
    state = GatewayState()
    projection = RosStateProjector(state)
    projection.on_run_context(_run_context())
    twin = _twin()
    breaker = copy.deepcopy(twin.status[0])
    breaker.name = "breaker-01"
    for value in breaker.values:
        if value.key == "category":
            value.value = "breaker"
        elif value.key == "pose_x_m":
            value.value = "0.5"
        elif value.key == "pose_y_m":
            value.value = "3.5"
    twin.status.append(breaker)

    assert projection.on_twin(twin) is True
    assert projection.on_risk(_risk()) is True

    assert [asset["asset_id"] for asset in state.assets] == ["breaker-01", "transformer-01"]
    assert state.assets[0]["risk"] == {
        "score_0_100": 0.0,
        "level": "unknown",
        "visual_0_1": 0.0,
        "temperature_0_1": 0.0,
        "smoke_0_1": 0.0,
        "gas_0_1": 0.0,
        "context_0_1": 0.0,
    }
    assert state.assets[1]["risk"]["level"] == "attention"


def test_matching_mission_transition_notifies_command_terminal_observer() -> None:
    observed = []
    state = GatewayState()
    projection = RosStateProjector(
        state,
        command_observer=lambda command_id, mission, run_id: observed.append(
            (command_id, mission, run_id)
        ),
    )
    projection.on_run_context(_run_context())
    mission = _mission()
    mission.mission_state = InspectionTaskArray.MISSION_PAUSED
    mission.transition_command_id = "8d0fa612-997d-430e-8dd0-9f35fc1e129b"

    assert projection.on_mission(mission) is True
    assert observed[0][0] == mission.transition_command_id
    assert observed[0][1]["state"] == "paused"
    assert observed[0][1]["robot_mode"] == "autonomous"
    assert observed[0][1]["emergency_stop_latched"] is False
    assert observed[0][1]["emergency_stop_latch_revision"] == "12"
    assert observed[0][2] == RUN_ID


def test_odom_requires_map_transform_and_battery_is_exposed_as_percent() -> None:
    state = GatewayState()
    projection = RosStateProjector(state)
    odom = Odometry()
    odom.header.frame_id = "odom"
    odom.child_frame_id = "base_footprint"
    odom.header.stamp.sec = 123
    odom.pose.pose.position.x = 1.0
    odom.pose.pose.position.y = 2.0
    odom.pose.pose.orientation.w = 1.0
    transform = type("Transform", (), {})()
    transform.transform = type("Stamped", (), {})()
    transform.transform.translation = type("Translation", (), {"x": 10.0, "y": -1.0, "z": 0.0})()
    transform.transform.rotation = type("Rotation", (), {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0})()

    assert projection.on_odom(odom, transform) is True
    battery = BatteryState()
    battery.header.frame_id = "base_link"
    battery.percentage = 0.87
    assert projection.on_battery(battery) is True
    assert state.robot["frame_id"] == "map"
    assert state.robot["pose"]["x_m"] == 11.0
    assert state.robot["pose"]["y_m"] == 1.0
    assert state.robot["battery_percent"] == 87.0

    invalid = Odometry()
    invalid.header.frame_id = "base_link"
    invalid.child_frame_id = "base_footprint"
    assert projection.on_odom(invalid, transform) is False

    invalid_battery = BatteryState()
    invalid_battery.header.frame_id = "odom"
    invalid_battery.percentage = 0.5
    assert projection.on_battery(invalid_battery) is False


def test_odom_pose_is_rotated_and_composed_with_exact_map_transform() -> None:
    state = GatewayState()
    projection = RosStateProjector(state)
    odom = Odometry()
    odom.header.frame_id = "odom"
    odom.child_frame_id = "base_footprint"
    odom.header.stamp.sec = 123
    odom.header.stamp.nanosec = 450_000_000
    odom.pose.pose.position.x = 1.0
    odom.pose.pose.orientation.w = 1.0
    transform = type("Transform", (), {})()
    transform.transform = type("Stamped", (), {})()
    transform.transform.translation = type(
        "Translation", (), {"x": 10.0, "y": -1.0, "z": 0.0}
    )()
    transform.transform.rotation = type(
        "Rotation", (), {"x": 0.0, "y": 0.0, "z": 2**-0.5, "w": 2**-0.5}
    )()

    assert projection.on_odom(odom, transform) is True
    assert state.robot is not None
    assert state.robot["pose"]["x_m"] == pytest.approx(10.0)
    assert state.robot["pose"]["y_m"] == pytest.approx(0.0)
    assert state.robot["pose"]["qz"] == pytest.approx(2**-0.5)
    assert state.robot["pose"]["qw"] == pytest.approx(2**-0.5)
    assert state.robot["source_ros_time"] == {"sec": 123, "nanosec": 450_000_000}

    revision = state.snapshot_revision
    assert projection.update_robot_staleness(123, 950_000_001) is True
    assert state.robot["stale"] is True
    assert state.snapshot_revision == revision + 1
    assert projection.update_robot_staleness(123, 960_000_000) is True
    assert state.snapshot_revision == revision + 1


def test_mission_snapshot_updates_robot_mode_latch_and_active_task_atomically() -> None:
    state = GatewayState()
    projection = RosStateProjector(state)
    odom = Odometry()
    odom.header.frame_id = "odom"
    odom.child_frame_id = "base_footprint"
    odom.pose.pose.orientation.w = 1.0
    transform = type("Transform", (), {})()
    transform.transform = type("Stamped", (), {})()
    transform.transform.translation = type("Translation", (), {"x": 0.0, "y": 0.0, "z": 0.0})()
    transform.transform.rotation = type("Rotation", (), {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0})()
    assert projection.on_odom(odom, transform) is True
    projection.on_run_context(_run_context())
    mission = _mission()
    mission.robot_mode = InspectionTaskArray.MODE_ESTOP
    mission.emergency_stop_latched = True
    mission.emergency_stop_latch_revision = 19

    assert projection.on_mission(mission) is True
    assert state.robot is not None
    assert state.robot["mode"] == "estop"
    assert state.robot["emergency_stop"] == {"latched": True, "latch_revision": "19"}
    assert state.robot["current_mission_id"] == MISSION_ID
    assert state.robot["current_task_id"] == mission.active_task_id


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


def test_ros_manual_velocity_rechecks_fresh_pose_at_publish_boundary() -> None:
    context = Context()
    rclpy.init(context=context)
    state = GatewayState(robot={"stale": True})
    gateway = RosGatewayNode(state, context=context)
    gateway.projector.on_run_context(_run_context())
    mission = _mission()
    mission.robot_mode = InspectionTaskArray.MODE_MANUAL
    gateway.projector.on_mission(mission)
    try:
        result = gateway.dispatch_manual_velocity(
            command_id="8d0fa612-997d-430e-8dd0-9f35fc1e129b",
            payload={"linear_x_m_s": 0.1, "angular_z_rad_s": 0.0, "duration_s": 0.15},
        )
        assert result["accepted"] is False
        assert result["error_code"] == "ROBOT_STATE_UNAVAILABLE"
    finally:
        gateway.destroy_node()
        context.shutdown()


def test_manual_velocity_status_callback_uses_dispatch_context_and_ros_time_mapping() -> None:
    context = Context()
    rclpy.init(context=context)
    observed = []
    state = GatewayState()
    gateway = RosGatewayNode(
        state,
        context=context,
        manual_command_observer=lambda message, run_id, revision, applied_at: observed.append(
            (message.command_id, message.state, run_id, revision, applied_at)
        ),
    )
    gateway.projector.on_run_context(_run_context())
    gateway.projector.set_time_mapping(
        run_id=RUN_ID,
        context_revision=17,
        anchor_ros_sec=100,
        anchor_ros_nanosec=250_000_000,
        anchor_utc="2026-07-22T14:00:00.000000Z",
    )
    command_id = "8d0fa612-997d-430e-8dd0-9f35fc1e129b"
    gateway._manual_command_context[command_id] = (RUN_ID, 17)
    status = ManualVelocityStatus()
    status.schema_version = 1
    status.header.frame_id = "base_link"
    status.header.stamp.sec = 100
    status.header.stamp.nanosec = 350_000_000
    status.command_id = command_id
    status.state = ManualVelocityStatus.STATE_APPLIED
    try:
        gateway._on_manual_velocity_status(status)
        assert observed == [
            (command_id, ManualVelocityStatus.STATE_APPLIED, RUN_ID, 17, "2026-07-22T14:00:00.100000Z")
        ]
    finally:
        gateway.destroy_node()
        context.shutdown()


def test_adapter_replays_terminal_snapshot_that_arrived_before_http_record() -> None:
    state = GatewayState(run_id=RUN_ID)
    adapter = RosGatewayAdapter(state)
    store = CommandStore()
    adapter.attach_command_store(store)
    command_id = "8d0fa612-997d-430e-8dd0-9f35fc1e129b"
    observation = {
        "transition_command_id": command_id,
        "state_revision": "64",
        "emergency_stop_latch_revision": "12",
        "robot_mode": "manual",
        "emergency_stop_latched": False,
    }

    adapter._observe_mission_command(command_id, observation, RUN_ID)
    store.insert_accepted(
        command_id=command_id,
        method="POST",
        route="/api/v1/robot/mode",
        key="b2adb26d-4f79-4a76-b858-a5dfd8f73670",
        body_sha256="0" * 64,
        kind="robot.mode",
        run_id=RUN_ID,
        accepted_at="2026-07-24T10:00:00.000000Z",
        response={"status": "accepted"},
        expectation={
            "payload": {"target_mode": "manual"},
            "service": {"state_revision": 64, "latch_revision": 12},
        },
    )
    adapter.replay_terminal(command_id)
    assert store.get(command_id)["status"] == "succeeded"


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

    def manage_mission(request, response):
        response.schema_version = 1
        response.accepted = request.action == ManageMission.Request.ACTION_PAUSE
        response.run_id = RUN_ID
        response.mission_id = MISSION_ID
        response.run_context_revision = 17
        response.state_revision = 64
        response.queue_revision = 42
        return response

    source.create_service(ManageMission, "/mission/manage", manage_mission)

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

        result = {}
        worker = threading.Thread(
            target=lambda: result.update(gateway.dispatch_mission(
                command_id="8d0fa612-997d-430e-8dd0-9f35fc1e129b",
                action="pause",
                payload={"mission_id": MISSION_ID, "reason": "operator pause"},
            ))
        )
        worker.start()
        deadline = time.monotonic() + 3.0
        while worker.is_alive() and time.monotonic() < deadline:
            executor.spin_once(timeout_sec=0.05)
        worker.join(timeout=0.1)
        assert result["accepted"] is True
        assert result["state_revision"] == 64
    finally:
        executor.remove_node(gateway)
        executor.remove_node(source)
        gateway.destroy_node()
        source.destroy_node()
        executor.shutdown()
        context.shutdown()


def test_live_odom_tf_and_battery_are_exposed_by_robot_state_endpoint() -> None:
    context = Context()
    rclpy.init(context=context)
    source = Node("robot_state_test_source", context=context)
    state = GatewayState()
    gateway = RosGatewayNode(state, context=context)
    executor = SingleThreadedExecutor(context=context)
    executor.add_node(source)
    executor.add_node(gateway)
    sensor_qos = QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=5,
        reliability=ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.VOLATILE,
    )
    stream_qos = QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=10,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.VOLATILE,
    )
    odom_pub = source.create_publisher(Odometry, "/odom", sensor_qos)
    battery_pub = source.create_publisher(BatteryState, "/battery_state", stream_qos)
    tf_broadcaster = TransformBroadcaster(source)
    stamp = rclpy.time.Time(seconds=123, nanoseconds=450_000_000).to_msg()
    transform = TransformStamped()
    transform.header.stamp = stamp
    transform.header.frame_id = "map"
    transform.child_frame_id = "odom"
    transform.transform.translation.x = 5.0
    transform.transform.translation.y = 6.0
    transform.transform.rotation.w = 1.0
    odom = Odometry()
    odom.header.stamp = stamp
    odom.header.frame_id = "odom"
    odom.child_frame_id = "base_footprint"
    odom.pose.pose.position.x = 1.0
    odom.pose.pose.position.y = 2.0
    odom.pose.pose.orientation.w = 1.0
    battery = BatteryState()
    battery.header.frame_id = "base_link"
    battery.percentage = 0.87

    try:
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline and (
            state.robot is None or state.robot.get("battery_percent") is None
        ):
            tf_broadcaster.sendTransform(transform)
            odom_pub.publish(odom)
            battery_pub.publish(battery)
            executor.spin_once(timeout_sec=0.05)
        assert state.robot is not None
        assert state.robot["pose"]["x_m"] == pytest.approx(6.0)
        assert state.robot["pose"]["y_m"] == pytest.approx(8.0)
        assert state.robot["battery_percent"] == 87.0
        status, body = _http_get(create_app(state=state), "/api/v1/robot/state")
        assert status == 200
        assert body["data"]["frame_id"] == "map"
        assert body["data"]["battery_percent"] == 87.0
    finally:
        executor.remove_node(gateway)
        executor.remove_node(source)
        gateway.destroy_node()
        source.destroy_node()
        executor.shutdown()
        context.shutdown()
