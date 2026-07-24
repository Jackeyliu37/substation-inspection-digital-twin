"""Contract tests for the FastAPI-only Gateway adapter.

The test harness invokes the ASGI application directly so the locked Gateway
environment does not need an optional HTTP client dependency.
"""

import asyncio
import hashlib
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "ros2_ws/src/substation_web_gateway"))
from substation_web_gateway.app import GatewayState, create_app


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
    status, _, body = _http(app, "GET", "/api/v1/diagnostics")
    assert status == 200
    assert body["data"]["items"][0]["name"] == "gateway"


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


def test_telemetry_rejects_missing_subprotocol_with_http_426():
    outgoing = _websocket_rejection(create_app())
    response_start = next(message for message in outgoing if message["type"] == "websocket.http.response.start")
    assert response_start["status"] == 426
