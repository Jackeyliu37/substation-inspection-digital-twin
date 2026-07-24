"""Contract tests for the FastAPI-only Gateway adapter.

The test harness invokes the ASGI application directly so the locked Gateway
environment does not need an optional HTTP client dependency.
"""

import asyncio
import hashlib
import json
import struct
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "ros2_ws/src/substation_web_gateway"))
from substation_interfaces.msg import ManualVelocityStatus
import substation_web_gateway.app as gateway_app
import substation_web_gateway.__main__ as gateway_main
from substation_web_gateway.app import CommandStore, GatewayState, create_app


def _http(app, method, path, *, headers=(), body=b"", decode_json=True):
    async def invoke():
        request = {"type": "http.request", "body": body, "more_body": False}
        sent = []

        async def receive():
            return request

        async def send(message):
            sent.append(message)

        route_path, separator, query = path.partition("?")
        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "path": route_path,
            "raw_path": route_path.encode(),
            "query_string": query.encode() if separator else b"",
            "headers": [(key.lower().encode(), value.encode()) for key, value in headers],
            "client": ("test", 1234),
            "server": ("test", 80),
            "scheme": "http",
        }
        await app(scope, receive, send)
        start = next(message for message in sent if message["type"] == "http.response.start")
        payload = b"".join(
            message.get("body", b"") for message in sent if message["type"] == "http.response.body"
        )
        response_headers = {key.decode().lower(): value.decode() for key, value in start["headers"]}
        decoded = json.loads(payload) if payload and decode_json else payload if payload else None
        return start["status"], response_headers, decoded

    return asyncio.run(invoke())


def _websocket_first_message(app, *, subprotocols=("substation.v1",)):
    async def invoke():
        incoming = asyncio.Queue()
        outgoing = []

        async def receive():
            return await incoming.get()

        async def send(message):
            outgoing.append(message)

        scope = {
            "type": "websocket",
            "path": "/ws/telemetry",
            "raw_path": b"/ws/telemetry",
            "query_string": b"",
            "headers": [],
            "subprotocols": list(subprotocols),
            "client": ("test", 1234),
            "server": ("test", 80),
            "scheme": "ws",
        }
        await incoming.put({"type": "websocket.connect"})
        task = asyncio.create_task(app(scope, receive, send))
        for _ in range(100):
            if outgoing:
                break
            await asyncio.sleep(0)
        assert outgoing, "Gateway did not complete the WebSocket handshake"
        await incoming.put({"type": "websocket.disconnect", "code": 1000})
        await task
        return outgoing

    return asyncio.run(invoke())


def _websocket_rejection(app):
    async def invoke():
        incoming = asyncio.Queue()
        outgoing = []

        async def receive():
            return await incoming.get()

        async def send(message):
            outgoing.append(message)

        scope = {
            "type": "websocket",
            "path": "/ws/telemetry",
            "raw_path": b"/ws/telemetry",
            "query_string": b"",
            "headers": [],
            "subprotocols": [],
            "extensions": {"websocket.http.response": {}},
            "client": ("test", 1234),
            "server": ("test", 80),
            "scheme": "ws",
        }
        await incoming.put({"type": "websocket.connect"})
        await app(scope, receive, send)
        return outgoing

    return asyncio.run(invoke())


def _websocket_open(app, path, *, subprotocols=("substation.v1",)):
    async def invoke():
        incoming = asyncio.Queue()
        outgoing = []

        async def receive():
            return await incoming.get()

        async def send(message):
            outgoing.append(message)

        scope = {
            "type": "websocket",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "subprotocols": list(subprotocols),
            "client": ("test", 1234),
            "server": ("test", 80),
            "scheme": "ws",
        }
        await incoming.put({"type": "websocket.connect"})
        task = asyncio.create_task(app(scope, receive, send))
        for _ in range(100):
            if outgoing:
                break
            await asyncio.sleep(0)
        assert outgoing
        await incoming.put({"type": "websocket.disconnect", "code": 1000})
        await task
        return outgoing

    return asyncio.run(invoke())


def _lifespan(app):
    async def invoke():
        incoming = asyncio.Queue()
        outgoing = []

        async def receive():
            return await incoming.get()

        async def send(message):
            outgoing.append(message)

        await incoming.put({"type": "lifespan.startup"})
        task = asyncio.create_task(app({"type": "lifespan", "state": {}}, receive, send))
        for _ in range(100):
            if any(item["type"] == "lifespan.startup.complete" for item in outgoing):
                break
            await asyncio.sleep(0)
        await incoming.put({"type": "lifespan.shutdown"})
        await task
        return outgoing

    return asyncio.run(invoke())


def test_health_and_readiness_are_distinct():
    app = create_app()
    status, _, body = _http(app, "GET", "/healthz")
    assert status == 200
    assert body["schema_version"] == "1.0"
    assert body["status"] == "alive"

    status, _, body = _http(app, "GET", "/readyz")
    assert status == 503
    assert body["code"] == "NOT_READY"

    not_ready = create_app(state=GatewayState(ready_dependencies={"ros": False}))
    status, headers, body = _http(not_ready, "GET", "/readyz")
    assert status == 503
    assert headers["content-type"].startswith("application/problem+json")
    assert body["code"] == "NOT_READY"
    assert body["violations"] == [{"field": "ros", "reason": "unavailable"}]

    ready = create_app(state=GatewayState(ready_dependencies={"ros": True, "run_context": True}))
    status, _, body = _http(ready, "GET", "/readyz")
    assert status == 200
    assert body["status"] == "ready"


def test_gateway_starts_and_stops_injected_ros_adapter_with_asgi_lifespan():
    calls = []

    class Adapter:
        def start(self):
            calls.append("start")

        def stop(self):
            calls.append("stop")

    messages = _lifespan(create_app(adapter=Adapter()))
    assert calls == ["start", "stop"]
    assert [message["type"] for message in messages] == [
        "lifespan.startup.complete",
        "lifespan.shutdown.complete",
    ]


def test_snapshot_uses_weak_etag_and_returns_304_without_body():
    app = create_app()
    status, headers, body = _http(app, "GET", "/api/v1/assets")
    assert status == 200
    assert headers["etag"] == 'W/"none:1"'
    assert body["schema_version"] == "1.0"
    assert body["run_id"] is None
    assert body["snapshot_revision"] == "1"
    assert isinstance(body["data"]["items"], list)

    status, headers, body = _http(
        app,
        "GET",
        "/api/v1/assets",
        headers=(("If-None-Match", 'W/"none:1"'),),
    )
    assert status == 304
    assert headers["etag"] == 'W/"none:1"'
    assert body is None


def test_system_and_idle_mission_are_snapshots_not_gateway_owned_state():
    app = create_app()

    status, system_headers, system = _http(app, "GET", "/api/v1/system/status")
    assert status == 200
    assert system_headers["etag"] == 'W/"none:1"'
    assert system["data"]["overall"] == "unavailable"
    assert system["data"]["run_context"] is None

    status, mission_headers, mission = _http(app, "GET", "/api/v1/missions/current")
    assert status == 200
    assert mission_headers["etag"] == 'W/"none:1"'
    assert mission["data"]["mission_id"] is None
    assert mission["data"]["state"] == "idle"
    assert mission["data"]["queue_revision"] == "0"
    assert mission["data"]["tasks"] == []


def test_production_state_endpoints_fail_closed_before_authoritative_ros_snapshots():
    state = GatewayState(authoritative_required=True)
    app = create_app(state=state)

    status, _, system = _http(app, "GET", "/api/v1/system/status")
    assert status == 503
    assert system["code"] == "DEPENDENCY_UNAVAILABLE"

    status, _, assets = _http(app, "GET", "/api/v1/assets")
    assert status == 503
    assert assets["code"] == "DEPENDENCY_UNAVAILABLE"

    status, _, mission = _http(app, "GET", "/api/v1/missions/current")
    assert status == 503
    assert mission["code"] == "MISSION_STATE_UNAVAILABLE"


def test_map_reports_and_diagnostics_are_read_only_snapshots():
    app = create_app()
    status, _, body = _http(app, "GET", "/api/v1/robot/state")
    assert status == 503
    assert body["code"] == "ROBOT_STATE_UNAVAILABLE"
    status, _, body = _http(app, "GET", "/api/v1/map")
    assert status == 503
    assert body["code"] == "MAP_UNAVAILABLE"

    state = GatewayState(
        robot={
            "frame_id": "map",
            "pose": {"x_m": 1.0, "y_m": 2.0, "z_m": 0.0, "qx": 0.0, "qy": 0.0, "qz": 0.0, "qw": 1.0},
            "twist": {"linear_x_m_s": 0.0, "linear_y_m_s": 0.0, "angular_z_rad_s": 0.0},
            "battery_percent": 87.0,
            "mode": "autonomous",
            "stale": False,
            "emergency_stop": {"latched": False, "latch_revision": "12"},
            "current_mission_id": None,
            "current_task_id": None,
            "source_ros_time": {"sec": 123, "nanosec": 0},
        },
        map_snapshot={
            "frame_id": "map",
            "map_revision": "3",
            "resolution_m": 0.05,
            "width_cells": 2,
            "height_cells": 1,
            "origin": {"x_m": 0.0, "y_m": 0.0, "yaw_rad": 0.0},
            "encoding": "int8-row-major",
            "data_base64": "AP8=",
        },
        reports=[{"report_id": "report-1", "status": "published"}],
        diagnostics={"items": [{"name": "gateway", "status": "ok"}]},
    )
    app = create_app(state=state)
    status, _, body = _http(app, "GET", "/api/v1/robot/state")
    assert status == 200
    assert body["data"]["battery_percent"] == 87.0
    status, _, body = _http(app, "GET", "/api/v1/map")
    assert status == 200
    assert body["data"]["map_revision"] == "3"
    status, _, body = _http(app, "GET", "/api/v1/reports")
    assert status == 200
    assert body["data"]["items"][0]["report_id"] == "report-1"
    assert body["data"]["generation"]["status"] == "ready"
    status, _, body = _http(app, "GET", "/api/v1/diagnostics")
    assert status == 200
    assert body["data"]["items"][0]["name"] == "gateway"


def test_report_snapshot_explains_progress_before_automatic_generation():
    state = GatewayState(
        mission={
            "state": "running",
            "completed_tasks": 3,
            "total_tasks": 10,
            "tasks": [],
        },
        ready_dependencies={"reporting": True},
    )
    app = create_app(state=state)

    status, _, body = _http(app, "GET", "/api/v1/reports")

    assert status == 200
    assert body["data"]["generation"] == {
        "status": "waiting_for_mission",
        "message": "巡检进行中，完成全部设备后自动生成报告。",
        "completed_tasks": 3,
        "total_tasks": 10,
    }


def test_reporting_index_groups_artifacts_and_downloads_through_adapter():
    report_id = "74727656-b320-4fe8-9a14-6de3c0094f08"
    report_run_id = "f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f"
    content = b"report-pdf"
    digest = hashlib.sha256(content).hexdigest()

    class Adapter:
        def list_reporting_artifacts(self, *, run_id=None, artifact_group_id=None, format_name=None):
            return {
                "available": True,
                "entries": [{
                    "evidence_id": "d0c4a7c6-6cf5-4f57-a31d-4c4f71cfed74",
                    "run_id": report_run_id,
                    "context_revision": "3",
                    "evidence_revision": "4",
                    "media_type": "application/pdf",
                    "content_sha256": digest,
                    "size_bytes": str(len(content)),
                    "metadata": {
                        "artifact_group_id": report_id,
                        "format": "pdf",
                        "mission_id": "0c5efce1-655b-413d-9847-da203fb5ca5e",
                        "created_at": "2026-07-24T03:04:05.000000Z",
                    },
                }],
                "error_code": "",
                "error_message": "",
            }

        def read_evidence_range(self, evidence_id, offset, length):
            assert evidence_id == "d0c4a7c6-6cf5-4f57-a31d-4c4f71cfed74"
            return content[offset:offset + length]

    app = create_app(adapter=Adapter())
    status, _, body = _http(app, "GET", "/api/v1/reports")
    assert status == 200
    assert body["data"]["items"][0]["report_id"] == report_id
    assert body["data"]["items"][0]["formats"] == ["pdf"]
    status, headers, payload = _http(
        app,
        "GET",
        f"/api/v1/reports/{report_id}/download?format=pdf",
        headers=(("Range", "bytes=0-5"),),
        decode_json=False,
    )
    assert status == 206
    assert payload == content[:6]
    assert headers["content-range"] == f"bytes 0-5/{len(content)}"
    status, _, body = _http(
        app,
        "GET",
        f"/api/v1/reports/{report_id}/download?format=html",
    )
    assert status == 404
    assert body["code"] == "REPORT_FORMAT_NOT_FOUND"


def test_events_and_camera_open_without_fabricating_frames():
    app = create_app()
    events = _websocket_open(app, "/ws/events")
    event_open = json.loads(next(item["text"] for item in events if item["type"] == "websocket.send"))
    assert event_open["stream"] == "events"
    app = create_app()
    camera = _websocket_open(app, "/ws/camera")
    camera_open = json.loads(next(item["text"] for item in camera if item["type"] == "websocket.send"))
    assert camera_open["stream"] == "camera"
    assert camera_open["payload"]["camera_available"] is False
    assert not any(item.get("bytes") for item in camera if item["type"] == "websocket.send")


def test_camera_frame_uses_locked_binary_header_and_metadata_contract():
    state = GatewayState(
        run_id="f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f",
        snapshot_revision=77,
        camera_jpeg=b"\xff\xd8camera\xff\xd9",
        camera_metadata={
            "source_frame_id": "camera_optical_frame",
            "source_ros_time": {"sec": 12, "nanosec": 34},
            "width": 640,
            "height": 480,
            "captured_at": "2026-07-24T11:00:00.000000Z",
        },
    )
    connection_id = "57d8cf69-ff22-4c0e-bc47-24d1b9eaf539"

    frame = gateway_app.pack_camera_frame(state, connection_id=connection_id)

    assert frame[:4] == b"SSCF"
    assert frame[4:8] == b"\x01\x01\x00\x40"
    sequence, revision, metadata_length, jpeg_length, width, height = struct.unpack(
        "!QQIIII", frame[8:40]
    )
    assert sequence == 1
    assert revision == 77
    assert (width, height) == (640, 480)
    assert jpeg_length == len(state.camera_jpeg)
    assert uuid.UUID(bytes=frame[40:56]) == uuid.UUID(state.stream_epoch)
    assert frame[56:64] == b"\0" * 8
    metadata = json.loads(frame[64:64 + metadata_length])
    assert metadata["connection_id"] == connection_id
    assert metadata["run_id"] == state.run_id
    assert metadata["ros_frame_id"] == "camera_optical_frame"
    assert metadata["annotated"] is True
    assert frame[-jpeg_length:] == state.camera_jpeg


def test_model_snapshot_discovers_all_imported_weights_and_metrics(tmp_path):
    manifest = tmp_path / "manifest.yaml"
    production = tmp_path / "production"
    digest = "a" * 64
    target = production / digest / "yolo11n_safety.pt"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"weights")
    manifest.write_text(
        """schema_version: 1
artifacts:
  - logical_model: yolo11n_safety
    module: safety
    filename: source.pt
    sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    class_names: [person, smoke]
    metric_name: metrics/mAP50(B)
    best_metric: 0.69297
    acceptance_status: passed
    threshold_waived: true
deployment_filenames:
  yolo11n_safety: yolo11n_safety.pt
""",
        encoding="utf-8",
    )

    models = gateway_app.load_production_models(manifest, production)

    assert models == [{
        "logical_model": "yolo11n_safety",
        "module": "safety",
        "filename": "yolo11n_safety.pt",
        "sha256": digest,
        "classes": ["person", "smoke"],
        "metric_name": "metrics/mAP50(B)",
        "best_metric": 0.69297,
        "acceptance_status": "passed",
        "threshold_waived": True,
        "installed": True,
        "size_bytes": 7,
    }]


def test_production_startup_populates_model_state(tmp_path):
    manifest = tmp_path / "manifest.yaml"
    production = tmp_path / "production"
    digest = "b" * 64
    target = production / digest / "yolo11n_equipment.pt"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"production-weights")
    manifest.write_text(
        """schema_version: 1
artifacts:
  - logical_model: yolo11n_equipment
    module: equipment
    filename: source.pt
    sha256: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
    class_names: [breaker]
    metric_name: metrics/mAP50(B)
    best_metric: 0.84
    acceptance_status: passed
    threshold_waived: false
deployment_filenames:
  yolo11n_equipment: yolo11n_equipment.pt
""",
        encoding="utf-8",
    )

    state = gateway_main.build_runtime_state(manifest, production)

    assert [model["logical_model"] for model in state.models] == ["yolo11n_equipment"]
    assert state.models[0]["installed"] is True


def test_models_and_scenario_are_real_gateway_snapshots_and_commands():
    observed = []

    class Adapter:
        def dispatch_scenario(self, *, command_id, payload):
            observed.append((command_id, payload))
            return {"accepted": True, "scenario_revision": 8, "error_code": "", "error_message": ""}

    state = GatewayState(
        run_id="f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f",
        models=[{"logical_model": "yolo11n_safety", "installed": True}],
        scenario={"scenario_id": "normal", "status": "applied", "active": False, "scenario_revision": "7"},
    )
    state.system["simulation_mode"] = True
    state.system["run_context"] = {"lifecycle": "active"}
    app = create_app(state=state, adapter=Adapter())

    status, _, body = _http(app, "GET", "/api/v1/models")
    assert status == 200
    assert body["data"]["items"][0]["logical_model"] == "yolo11n_safety"
    status, _, body = _http(app, "GET", "/api/v1/simulation/scenario")
    assert status == 200
    assert body["data"]["scenario_revision"] == "7"

    payload = {
        "scenario_id": "gas-high",
        "action": "trigger",
        "parameters": {"asset_id": "transformer-01", "gas_ppm": 180.0},
        "reason": "operator web scenario trigger",
    }
    status, _, body = _http(
        app,
        "POST",
        "/api/v1/simulation/scenario",
        headers=(("Content-Type", "application/json"), ("Idempotency-Key", str(uuid.uuid4()))),
        body=json.dumps(payload).encode(),
    )
    assert status == 202
    assert body["status"] == "accepted"
    assert uuid.UUID(observed[0][0])
    assert observed[0][1] == payload


def test_matching_scenario_state_completes_the_gateway_command():
    store = CommandStore()
    command_id = str(uuid.uuid4())
    payload = {
        "scenario_id": "gas-high",
        "action": "trigger",
        "parameters": {"asset_id": "transformer-01", "gas_ppm": 180.0},
        "reason": "operator web scenario trigger",
    }
    store.insert_accepted(
        command_id=command_id,
        method="POST",
        route="/api/v1/simulation/scenario",
        key=str(uuid.uuid4()),
        body_sha256="0" * 64,
        kind="simulation.scenario",
        run_id="f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f",
        accepted_at="2026-07-24T11:00:00.000000Z",
        response={"status": "accepted"},
        expectation={"payload": payload, "service": {"scenario_revision": 7}},
    )
    scenario = {
        "scenario_id": "gas-high",
        "command_id": command_id,
        "action": "trigger",
        "status": "applied",
        "active": True,
        "scenario_revision": "8",
        "error_code": None,
    }

    assert store.complete_from_scenario(
        command_id,
        scenario,
        "f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f",
    ) is True
    row = store.get(command_id)
    assert row["status"] == "succeeded"
    assert json.loads(row["result_json"])["scenario_revision"] == "8"


def test_matching_failed_scenario_state_completes_without_revision_increment():
    store = CommandStore()
    command_id = str(uuid.uuid4())
    run_id = "f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f"
    payload = {
        "scenario_id": "fire-smoke",
        "action": "trigger",
        "parameters": {"asset_id": "transformer-01", "smoke_0_1": 0.8},
        "reason": "operator web scenario trigger",
    }
    store.insert_accepted(
        command_id=command_id,
        method="POST",
        route="/api/v1/simulation/scenario",
        key=str(uuid.uuid4()),
        body_sha256="0" * 64,
        kind="simulation.scenario",
        run_id=run_id,
        accepted_at="2026-07-24T11:00:00.000000Z",
        response={"status": "accepted"},
        expectation={"payload": payload, "service": {"scenario_revision": 7}},
    )
    scenario = {
        "scenario_id": "fire-smoke",
        "command_id": command_id,
        "action": "trigger",
        "status": "failed",
        "active": False,
        "scenario_revision": "7",
        "error_code": "GAZEBO_SET_POSE_FAILED",
    }

    assert store.complete_from_scenario(command_id, scenario, run_id) is True
    row = store.get(command_id)
    assert row["status"] == "failed"
    assert json.loads(row["error_json"])["code"] == "GAZEBO_SET_POSE_FAILED"


def test_idempotency_persists_command_and_replays_exact_response():
    class Adapter:
        def dispatch_mission(self, *, command_id, action, payload):
            assert uuid.UUID(command_id)
            assert action == "start"
            assert payload["route_id"] == "default-route"
            return {"accepted": True, "error_code": "", "error_message": ""}

    app = create_app(adapter=Adapter())
    key = str(uuid.uuid4())
    body = json.dumps({"route_id": "default-route", "reason": "operator start"}).encode()
    headers = (("Content-Type", "application/json"), ("Idempotency-Key", key))

    status, response_headers, accepted = _http(app, "POST", "/api/v1/missions/start", headers=headers, body=body)
    assert status == 202
    assert accepted["status"] == "accepted"
    command_id = accepted["command_id"]
    assert response_headers["cache-control"] == "no-store"

    replay_status, replay_headers, replay = _http(
        app, "POST", "/api/v1/missions/start", headers=headers, body=body
    )
    assert replay_status == status
    assert replay == accepted
    assert replay_headers["idempotent-replayed"] == "true"

    status, _, conflict = _http(
        app,
        "POST",
        "/api/v1/missions/start",
        headers=headers,
        body=json.dumps({"route_id": "other-route", "reason": "operator start"}).encode(),
    )
    assert status == 409
    assert conflict["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert conflict["command_id"] is None

    status, _, command = _http(app, "GET", f"/api/v1/commands/{command_id}")
    assert status == 200
    assert command["command_id"] == command_id
    assert command["status"] == "accepted"


def test_mission_command_fails_closed_without_a_ros_service_adapter():
    app = create_app()
    key = str(uuid.uuid4())
    body = json.dumps({"route_id": "default-route", "reason": "operator start"}).encode()
    headers = (("Content-Type", "application/json"), ("Idempotency-Key", key))

    status, _, problem = _http(
        app, "POST", "/api/v1/missions/start", headers=headers, body=body
    )
    assert status == 503
    assert problem["code"] == "DEPENDENCY_UNAVAILABLE"
    assert problem["command_id"] is None


def test_mission_command_becomes_succeeded_only_after_matching_authoritative_snapshot():
    state = GatewayState(run_id="f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f")

    class Adapter:
        def dispatch_mission(self, *, command_id, action, payload):
            assert action == "pause"
            state.mission.update(
                mission_id=payload["mission_id"],
                state="paused",
                state_revision="64",
                queue_revision="42",
                transition_command_id=command_id,
            )
            return {
                "accepted": True,
                "run_id": state.run_id,
                "mission_id": payload["mission_id"],
                "state_revision": 64,
                "queue_revision": 42,
                "error_code": "",
                "error_message": "",
            }

    app = create_app(state=state, adapter=Adapter())
    key = str(uuid.uuid4())
    mission_id = "0c5efce1-655b-413d-9847-da203fb5ca5e"
    status, _, accepted = _http(
        app,
        "POST",
        "/api/v1/missions/pause",
        headers=(("Content-Type", "application/json"), ("Idempotency-Key", key)),
        body=json.dumps({"mission_id": mission_id, "reason": "operator pause"}).encode(),
    )
    assert status == 202

    status, _, command = _http(
        app, "GET", f"/api/v1/commands/{accepted['command_id']}"
    )
    assert status == 200
    assert command["status"] == "succeeded"
    assert command["completed_at"] is not None
    assert command["result"] == {
        "run_id": state.run_id,
        "mission_id": mission_id,
        "state_revision": "64",
        "queue_revision": "42",
    }


@pytest.mark.parametrize(
    ("kind", "payload", "service", "observation", "expected_result"),
    [
        (
            "robot.mode",
            {"target_mode": "manual"},
            {"state_revision": 64, "latch_revision": 12},
            {"robot_mode": "manual", "emergency_stop_latched": False},
            {"mode": "manual"},
        ),
        (
            "robot.emergency_stop",
            {},
            {"state_revision": 65, "latch_revision": 13},
            {"robot_mode": "estop", "emergency_stop_latched": True},
            {},
        ),
        (
            "robot.emergency_stop_reset",
            {},
            {"state_revision": 66, "latch_revision": 14},
            {"robot_mode": "manual", "emergency_stop_latched": False},
            {"mode": "manual"},
        ),
    ],
)
def test_robot_commands_require_matching_authoritative_terminal_snapshot(
    kind, payload, service, observation, expected_result
) -> None:
    store = CommandStore()
    command_id = str(uuid.uuid4())
    store.insert_accepted(
        command_id=command_id,
        method="POST",
        route="/api/v1/robot/test",
        key=str(uuid.uuid4()),
        body_sha256="0" * 64,
        kind=kind,
        run_id="f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f",
        accepted_at="2026-07-24T10:00:00.000000Z",
        response={"status": "accepted"},
        expectation={"payload": payload, "service": service},
    )
    snapshot = {
        "transition_command_id": command_id,
        "state_revision": str(service["state_revision"] - 1),
        "emergency_stop_latch_revision": str(service["latch_revision"]),
        **observation,
    }
    assert store.complete_from_mission(command_id, snapshot, store.get(command_id)["run_id"]) is False
    snapshot["state_revision"] = str(service["state_revision"])
    assert store.complete_from_mission(command_id, snapshot, store.get(command_id)["run_id"]) is True
    row = store.get(command_id)
    assert row["status"] == "succeeded"
    result = json.loads(row["result_json"])
    assert result["state_revision"] == str(service["state_revision"])
    assert result["latch_revision"] == str(service["latch_revision"])
    for key, value in expected_result.items():
        assert result[key] == value


def test_manual_velocity_command_only_succeeds_after_applied_status() -> None:
    store = CommandStore()
    events = []
    store.set_transition_observer(events.append)
    command_id = str(uuid.uuid4())
    store.insert_accepted(
        command_id=command_id,
        method="POST",
        route="/api/v1/robot/manual-velocity",
        key=str(uuid.uuid4()),
        body_sha256="0" * 64,
        kind="robot.manual_velocity",
        run_id="f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f",
        accepted_at="2026-07-24T10:00:00.000000Z",
        response={"status": "accepted"},
        expectation={"payload": {"duration_s": 0.15}, "service": {}},
    )
    status = ManualVelocityStatus()
    status.schema_version = 1
    status.header.frame_id = "base_link"
    status.command_id = command_id
    status.state = ManualVelocityStatus.STATE_ACCEPTED
    assert store.complete_from_manual_velocity(
        status,
        run_id="f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f",
        context_revision=17,
        applied_at="2026-07-24T10:00:00.100000Z",
    ) is True
    assert store.get(command_id)["status"] == "executing"

    status.state = ManualVelocityStatus.STATE_APPLIED
    assert store.complete_from_manual_velocity(
        status,
        run_id="f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f",
        context_revision=17,
        applied_at="2026-07-24T10:00:00.120000Z",
    ) is True
    row = store.get(command_id)
    assert row["status"] == "succeeded"
    assert json.loads(row["result_json"]) == {
        "run_id": "f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f",
        "context_revision": "17",
        "applied_at": "2026-07-24T10:00:00.120000Z",
        "duration_s": 0.15,
    }
    assert [event["status"] for event in events] == ["accepted", "executing", "succeeded"]


@pytest.mark.parametrize(
    ("ros_state", "command_state"),
    [
        (ManualVelocityStatus.STATE_REJECTED, "failed"),
        (ManualVelocityStatus.STATE_EXPIRED, "timed_out"),
        (ManualVelocityStatus.STATE_CANCELLED, "cancelled"),
    ],
)
def test_manual_velocity_negative_terminal_status_is_persisted(ros_state, command_state) -> None:
    store = CommandStore()
    command_id = str(uuid.uuid4())
    store.insert_accepted(
        command_id=command_id,
        method="POST",
        route="/api/v1/robot/manual-velocity",
        key=str(uuid.uuid4()),
        body_sha256="0" * 64,
        kind="robot.manual_velocity",
        run_id=None,
        accepted_at="2026-07-24T10:00:00.000000Z",
        response={"status": "accepted"},
    )
    status = ManualVelocityStatus()
    status.schema_version = 1
    status.header.frame_id = "base_link"
    status.command_id = command_id
    status.state = ros_state
    status.error_code = "MANUAL_MODE_REQUIRED"
    status.error_message = "manual velocity command rejected"
    assert store.complete_from_manual_velocity(
        status, run_id=None, context_revision=0, applied_at=None
    ) is True
    row = store.get(command_id)
    assert row["status"] == command_state
    if command_state == "failed":
        assert json.loads(row["error_json"])["code"] == "MANUAL_MODE_REQUIRED"


def test_command_timeout_is_terminal_and_late_authoritative_result_is_ignored() -> None:
    store = CommandStore()
    command_id = str(uuid.uuid4())
    store.insert_accepted(
        command_id=command_id,
        method="POST",
        route="/api/v1/robot/mode",
        key=str(uuid.uuid4()),
        body_sha256="0" * 64,
        kind="robot.mode",
        run_id=None,
        accepted_at="2026-07-24T10:00:00.000000Z",
        response={"status": "accepted"},
        expectation={
            "payload": {"target_mode": "manual"},
            "service": {"state_revision": 2, "latch_revision": 1},
        },
    )

    assert store.expire_due(
        command_id=command_id, now_utc="2026-07-24T10:00:10.000001Z"
    ) == 1
    row = store.get(command_id)
    assert row["status"] == "timed_out"
    assert json.loads(row["error_json"])["code"] == "COMMAND_TIMED_OUT"
    assert store.complete_from_mission(
        command_id,
        {
            "transition_command_id": command_id,
            "state_revision": "2",
            "emergency_stop_latch_revision": "1",
            "robot_mode": "manual",
            "emergency_stop_latched": False,
        },
        None,
    ) is False


def test_evidence_metadata_and_single_range_download_use_reporting_adapter_only():
    evidence_id = "ea6992e2-4398-414d-a587-ce8b33932266"
    content = b"\xff\xd8gateway-evidence\xff\xd9"

    class Adapter:
        def query_evidence(self, requested_id):
            assert requested_id == evidence_id
            return {
                "found": True,
                "run_id": "f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f",
                "context_revision": 17,
                "evidence_revision": 41,
                "media_type": "image/jpeg",
                "content_sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
                "metadata_canonical_json": json.dumps({
                    "source_topic": "/perception/annotated_image",
                    "source_ros_time": {"sec": 123, "nanosec": 400_000_000},
                    "source_frame_id": "camera_optical_frame",
                }, sort_keys=True, separators=(",", ":")),
                "error_code": "",
                "error_message": "",
            }

        def read_evidence_range(self, requested_id, offset, length):
            assert requested_id == evidence_id
            return content[offset:offset + length]

    app = create_app(adapter=Adapter())
    status, _, metadata = _http(app, "GET", f"/api/v1/evidence/{evidence_id}")
    assert status == 200
    assert metadata["data"]["evidence_id"] == evidence_id
    assert metadata["data"]["size_bytes"] == str(len(content))
    assert metadata["data"]["metadata"]["source_topic"] == "/perception/annotated_image"

    status, headers, body = _http(
        app,
        "GET",
        f"/api/v1/evidence/{evidence_id}/download",
        headers=(("Range", "bytes=2-8"),),
        decode_json=False,
    )
    assert status == 206
    assert body == content[2:9]
    assert headers["accept-ranges"] == "bytes"
    assert headers["content-range"] == f"bytes 2-8/{len(content)}"
    assert headers["etag"] == f'"sha256:{hashlib.sha256(content).hexdigest()}"'
    assert headers["x-content-sha256"] == hashlib.sha256(content).hexdigest()
    assert headers["content-disposition"] == f'attachment; filename="evidence-{evidence_id}.jpg"'

    status, headers, problem = _http(
        app,
        "GET",
        f"/api/v1/evidence/{evidence_id}/download",
        headers=(("Range", f"bytes={len(content)}-"),),
    )
    assert status == 416
    assert problem["code"] == "RANGE_NOT_SATISFIABLE"
    assert headers["content-range"] == f"bytes */{len(content)}"


def test_emergency_stop_bypasses_readiness_but_requires_real_ros_service() -> None:
    calls = []

    class Adapter:
        def dispatch_emergency_stop(self, *, command_id, payload):
            calls.append((command_id, payload["reason"]))
            return {
                "accepted": True,
                "latched": True,
                "latch_revision": 3,
                "state_revision": 12,
                "error_code": "",
                "error_message": "",
            }

    app = create_app(adapter=Adapter())
    key = str(uuid.uuid4())
    headers = (("Content-Type", "application/json"), ("Idempotency-Key", key))
    status, _, accepted = _http(
        app,
        "POST",
        "/api/v1/robot/emergency-stop",
        headers=headers,
        body=json.dumps({"reason": "operator emergency stop"}).encode(),
    )
    assert status == 202
    assert accepted["status"] == "accepted"
    assert len(calls) == 1

    replay_status, replay_headers, replay = _http(
        app,
        "POST",
        "/api/v1/robot/emergency-stop",
        headers=headers,
        body=json.dumps({"reason": "operator emergency stop"}).encode(),
    )
    assert replay_status == 202
    assert replay == accepted
    assert replay_headers["idempotent-replayed"] == "true"
    assert len(calls) == 1

    unavailable = create_app()
    status, _, problem = _http(
        unavailable,
        "POST",
        "/api/v1/robot/emergency-stop",
        headers=(("Content-Type", "application/json"), ("Idempotency-Key", str(uuid.uuid4()))),
        body=json.dumps({"reason": "operator emergency stop"}).encode(),
    )
    assert status == 503
    assert problem["code"] == "EMERGENCY_STOP_PATH_UNAVAILABLE"


def test_robot_mode_and_emergency_reset_dispatch_only_to_ros_services() -> None:
    calls = []

    class Adapter:
        def dispatch_robot_mode(self, *, command_id, payload):
            calls.append(("mode", command_id, payload))
            return {
                "accepted": True,
                "robot_mode": 1,
                "state_revision": 64,
                "latch_revision": 12,
                "error_code": "",
                "error_message": "",
            }

        def dispatch_emergency_reset(self, *, command_id, payload):
            calls.append(("reset", command_id, payload))
            return {
                "accepted": True,
                "latched": False,
                "state_revision": 65,
                "latch_revision": 13,
                "error_code": "",
                "error_message": "",
            }

    state = GatewayState(
        run_id="f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f",
        robot={"stale": False},
    )
    app = create_app(state=state, adapter=Adapter())
    mission_id = "0c5efce1-655b-413d-9847-da203fb5ca5e"
    status, _, mode_accepted = _http(
        app,
        "POST",
        "/api/v1/robot/mode",
        headers=(("Content-Type", "application/json"), ("Idempotency-Key", str(uuid.uuid4()))),
        body=json.dumps({
            "mission_id": mission_id,
            "target_mode": "manual",
            "observed_state_revision": "63",
            "observed_latch_revision": "12",
            "reason": "operator handoff",
        }).encode(),
    )
    assert status == 202
    assert app.state.commands.complete_from_mission(
        mode_accepted["command_id"],
        {
            "transition_command_id": mode_accepted["command_id"],
            "state_revision": "64",
            "emergency_stop_latch_revision": "12",
            "robot_mode": "manual",
            "emergency_stop_latched": False,
        },
        state.run_id,
    ) is True

    status, _, reset_accepted = _http(
        app,
        "POST",
        "/api/v1/robot/emergency-stop/reset",
        headers=(("Content-Type", "application/json"), ("Idempotency-Key", str(uuid.uuid4()))),
        body=json.dumps({
            "observed_latch_revision": "12",
            "confirm": True,
            "reason": "area verified clear",
        }).encode(),
    )
    assert status == 202
    assert app.state.commands.complete_from_mission(
        reset_accepted["command_id"],
        {
            "transition_command_id": reset_accepted["command_id"],
            "state_revision": "65",
            "emergency_stop_latch_revision": "13",
            "robot_mode": "manual",
            "emergency_stop_latched": False,
        },
        state.run_id,
    ) is True
    assert [call[0] for call in calls] == ["mode", "reset"]


def test_manual_velocity_dispatches_bounded_request_to_ros_adapter() -> None:
    calls = []

    class Adapter:
        def dispatch_manual_velocity(self, *, command_id, payload):
            calls.append((command_id, payload))
            return {"accepted": True, "error_code": "", "error_message": ""}

    app = create_app(state=GatewayState(robot={"stale": False}), adapter=Adapter())
    status, _, accepted = _http(
        app,
        "POST",
        "/api/v1/robot/manual-velocity",
        headers=(("Content-Type", "application/json"), ("Idempotency-Key", str(uuid.uuid4()))),
        body=json.dumps({
            "linear_x_m_s": 0.2,
            "angular_z_rad_s": -0.3,
            "deadman": True,
            "duration_s": 0.15,
        }).encode(),
    )
    assert status == 202
    assert accepted["status"] == "accepted"
    assert calls[0][1]["deadman"] is True
    assert app.state.gateway.events[-1] == {
        "type": "command.status",
        "command_id": accepted["command_id"],
        "kind": "robot.manual_velocity",
        "status": "accepted",
        "run_id": None,
        "result": None,
        "error": None,
    }

    status, _, problem = _http(
        app,
        "POST",
        "/api/v1/robot/manual-velocity",
        headers=(("Content-Type", "application/json"), ("Idempotency-Key", str(uuid.uuid4()))),
        body=json.dumps({
            "linear_x_m_s": 0.41,
            "angular_z_rad_s": 0.0,
            "deadman": True,
            "duration_s": 0.15,
        }).encode(),
    )
    assert status == 422
    assert problem["code"] == "VELOCITY_LIMIT_EXCEEDED"


def test_manual_velocity_rejects_missing_or_stale_robot_pose_before_ros_dispatch() -> None:
    calls = []

    class Adapter:
        def dispatch_manual_velocity(self, *, command_id, payload):
            calls.append((command_id, payload))
            return {"accepted": True, "error_code": "", "error_message": ""}

    payload = json.dumps({
        "linear_x_m_s": 0.1,
        "angular_z_rad_s": 0.0,
        "deadman": True,
        "duration_s": 0.15,
    }).encode()
    for robot in (None, {"stale": True}):
        app = create_app(state=GatewayState(robot=robot), adapter=Adapter())
        status, _, problem = _http(
            app,
            "POST",
            "/api/v1/robot/manual-velocity",
            headers=(("Content-Type", "application/json"), ("Idempotency-Key", str(uuid.uuid4()))),
            body=payload,
        )
        assert status == 503
        assert problem["code"] == "ROBOT_STATE_UNAVAILABLE"
    assert calls == []


def test_telemetry_requires_substation_v1_and_emits_open_envelope():
    app = create_app()
    outgoing = _websocket_first_message(app)
    accepted = next(message for message in outgoing if message["type"] == "websocket.accept")
    assert accepted["subprotocol"] == "substation.v1"
    text = next(message["text"] for message in outgoing if message["type"] == "websocket.send")
    envelope = json.loads(text)
    assert envelope["schema_version"] == "1.0"
    assert envelope["stream"] == "telemetry"
    assert envelope["type"] == "stream.open"
    assert envelope["sequence"] == "0"
    assert envelope["payload"] == {
        "heartbeat_interval_s": 1.0,
        "connection_timeout_s": 5.0,
        "replay_available": False,
    }


def test_events_websocket_replays_persisted_command_status_events() -> None:
    state = GatewayState()
    state.events.append({
        "type": "command.status",
        "command_id": "8d0fa612-997d-430e-8dd0-9f35fc1e129b",
        "kind": "robot.mode",
        "status": "succeeded",
        "run_id": None,
        "result": {"mode": "manual"},
        "error": None,
    })
    outgoing = _websocket_open(create_app(state=state), "/ws/events")
    event = next(
        json.loads(item["text"])
        for item in outgoing
        if item.get("type") == "websocket.send"
        and json.loads(item["text"]).get("type") == "event"
    )
    assert event["payload"]["type"] == "command.status"
    assert event["payload"]["status"] == "succeeded"


def test_telemetry_rejects_missing_subprotocol_with_http_426():
    outgoing = _websocket_rejection(create_app())
    response_start = next(message for message in outgoing if message["type"] == "websocket.http.response.start")
    assert response_start["status"] == 426
