"""Minimal HTTP/WebSocket adapter for the substation Web contract.

The domain nodes remain the owners of risk, mission, and digital-twin state.
This module only exposes protocol-shaped fixtures until the rclpy adapters are
wired to their authoritative topics and services.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse, Response


SCHEMA_VERSION = "1.0"
MAX_REQUEST_BYTES = 64 * 1024
_UUID_NIL = "00000000-0000-0000-0000-000000000000"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _strict_uuid(value: str) -> bool:
    try:
        return str(uuid.UUID(value)) == value
    except (ValueError, AttributeError, TypeError):
        return False


def _canonical_json(payload: Any) -> bytes:
    # The request model is JSON-compatible; sorting keys and using compact
    # separators gives stable idempotency for reordered object keys/whitespace.
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _problem(
    request: Request,
    status: int,
    code: str,
    detail: str,
    *,
    command_id: str | None = None,
    violations: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    body = {
        "type": f"http://ros-server/problems/{code.lower().replace('_', '-')}",
        "title": detail,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        "code": code,
        "trace_id": str(uuid.uuid4()),
        "command_id": command_id,
        "violations": violations or [],
    }
    return JSONResponse(body, status_code=status, media_type="application/problem+json", headers={"Cache-Control": "no-store"})


@dataclass
class GatewayState:
    """Authoritative-state adapter seam used by ROS subscribers later.

    The defaults are deliberately empty/no-run values rather than guessed
    operational state. Callers can replace these fields from ROS callbacks.
    """

    run_id: str | None = None
    snapshot_revision: int = 1
    assets: list[dict[str, Any]] = field(default_factory=list)
    map_snapshot: dict[str, Any] | None = None
    reports: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=lambda: {"items": []})
    events: list[dict[str, Any]] = field(default_factory=list)
    camera_jpeg: bytes | None = None
    camera_metadata: dict[str, Any] = field(default_factory=dict)
    mission: dict[str, Any] = field(default_factory=lambda: {
        "mission_id": None,
        "route_id": None,
        "state": "idle",
        "state_revision": "0",
        "queue_revision": "0",
        "transition_command_id": None,
        "transition_reason_code": "NO_ACTIVE_RUN",
        "transition_reason": "",
        "active_task_id": None,
        "completed_tasks": 0,
        "total_tasks": 0,
        "progress_0_1": 0.0,
        "tasks": [],
    })
    system: dict[str, Any] = field(default_factory=lambda: {
        "simulation_mode": True,
        "overall": "unavailable",
        "emergency_stop_latched": False,
        "run_context": None,
        "components": [],
        "gpu": None,
        "storage": None,
        "websocket": {"telemetry": "ok", "events": "ok", "camera": "ok"},
    })
    ready_dependencies: dict[str, bool] = field(default_factory=lambda: {
        "ros": False,
        "run_context": False,
        "gazebo": False,
        "nav2": False,
        "storage": False,
        "reporting": False,
        "time_mapping": False,
        "risk": False,
        "mission": False,
    })
    stream_epoch: str = field(default_factory=lambda: str(uuid.uuid4()))
    _sequence: int = 0

    def next_sequence(self) -> str:
        self._sequence += 1
        return str(self._sequence)

    def snapshot(self, data: Any) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "snapshot_revision": str(self.snapshot_revision),
            "generated_at": _utc_now(),
            "data": data,
        }


class CommandStore:
    """Single-writer SQLite store for idempotency and command records."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(str(path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA busy_timeout=5000")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS commands (
                command_id TEXT PRIMARY KEY,
                method TEXT NOT NULL,
                route TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                body_sha256 TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                run_id TEXT,
                created_at TEXT NOT NULL,
                accepted_at TEXT NOT NULL,
                response_status INTEGER NOT NULL,
                response_json TEXT NOT NULL,
                UNIQUE(method, route, idempotency_key)
            )
            """
        )
        self._connection.commit()

    def find_idempotency(self, method: str, route: str, key: str) -> sqlite3.Row | None:
        with self._lock:
            return self._connection.execute(
                "SELECT * FROM commands WHERE method=? AND route=? AND idempotency_key=?",
                (method, route, key),
            ).fetchone()

    def insert_accepted(
        self,
        *,
        command_id: str,
        method: str,
        route: str,
        key: str,
        body_sha256: str,
        kind: str,
        run_id: str | None,
        accepted_at: str,
        response: dict[str, Any],
    ) -> None:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO commands
                (command_id, method, route, idempotency_key, body_sha256, kind,
                 status, run_id, created_at, accepted_at, response_status, response_json)
                VALUES (?, ?, ?, ?, ?, ?, 'accepted', ?, ?, ?, 202, ?)
                """,
                (
                    command_id,
                    method,
                    route,
                    key,
                    body_sha256,
                    kind,
                    run_id,
                    accepted_at,
                    accepted_at,
                    json.dumps(response, ensure_ascii=False, separators=(",", ":")),
                ),
            )
            self._connection.commit()

    def get(self, command_id: str) -> sqlite3.Row | None:
        with self._lock:
            return self._connection.execute("SELECT * FROM commands WHERE command_id=?", (command_id,)).fetchone()


def create_app(*, state: GatewayState | None = None, db_path: str | Path = ":memory:") -> FastAPI:
    state = state or GatewayState()
    store = CommandStore(db_path)
    app = FastAPI(title="Substation Web Gateway", version=SCHEMA_VERSION)
    app.state.gateway = state
    app.state.commands = store

    def snapshot_response(data: Any, request: Request) -> Response:
        envelope = state.snapshot(data)
        etag = f'W/"{state.run_id or "none"}:{state.snapshot_revision}"'
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers={"ETag": etag})
        return JSONResponse(envelope, headers={"ETag": etag})

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, "status": "alive", "checked_at": _utc_now()}

    @app.get("/readyz")
    async def readyz(request: Request) -> Response:
        dependencies = dict(state.ready_dependencies)
        if not all(dependencies.values()):
            violations = [
                {"field": name, "reason": "unavailable"}
                for name, available in sorted(dependencies.items())
                if not available
            ]
            return _problem(request, 503, "NOT_READY", "Gateway dependencies are unavailable.", violations=violations)
        return JSONResponse({
            "schema_version": SCHEMA_VERSION,
            "status": "ready",
            "checked_at": _utc_now(),
            "dependencies": dependencies,
        })

    @app.get("/api/v1/system/status")
    async def system_status(request: Request) -> Response:
        return snapshot_response(state.system, request)

    @app.get("/api/v1/assets")
    async def assets(request: Request) -> Response:
        items = sorted(state.assets, key=lambda item: item.get("asset_id", ""))
        return snapshot_response({"items": items, "next_cursor": None}, request)

    @app.get("/api/v1/missions/current")
    async def current_mission(request: Request) -> Response:
        return snapshot_response(state.mission, request)

    @app.get("/api/v1/map")
    async def map_snapshot(request: Request) -> Response:
        if state.map_snapshot is None:
            return _problem(request, 503, "MAP_UNAVAILABLE", "A validated map snapshot is not available.")
        return snapshot_response(state.map_snapshot, request)

    @app.get("/api/v1/reports")
    async def reports(request: Request) -> Response:
        items = sorted(state.reports, key=lambda item: str(item.get("report_id", "")))
        return snapshot_response({"items": items, "next_cursor": None}, request)

    @app.get("/api/v1/diagnostics")
    async def diagnostics(request: Request) -> Response:
        return snapshot_response(state.diagnostics, request)

    @app.get("/api/v1/commands/{command_id}")
    async def command_lookup(command_id: str, request: Request) -> Response:
        if not _strict_uuid(command_id):
            return _problem(request, 422, "VALIDATION_FAILED", "command_id must be a canonical UUID.")
        row = store.get(command_id)
        if row is None:
            return _problem(request, 404, "COMMAND_NOT_FOUND", "Command was not found.")
        return JSONResponse({
            "schema_version": SCHEMA_VERSION,
            "command_id": row["command_id"],
            "run_id": row["run_id"],
            "kind": row["kind"],
            "status": row["status"],
            "created_at": row["created_at"],
            "accepted_at": row["accepted_at"],
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
        })

    @app.post("/api/v1/missions/{action}")
    async def mission_command(action: str, request: Request) -> Response:
        if not request.headers.get("content-type", "").lower().startswith("application/json"):
            return _problem(request, 415, "UNSUPPORTED_MEDIA_TYPE", "Requests must use application/json.")
        body = await request.body()
        if len(body) > MAX_REQUEST_BYTES:
            return _problem(request, 413, "REQUEST_TOO_LARGE", "Request body exceeds 64 KiB.")
        key = request.headers.get("idempotency-key")
        if key is None:
            return _problem(request, 400, "IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key is required.")
        if not _strict_uuid(key):
            return _problem(request, 400, "INVALID_IDEMPOTENCY_KEY", "Idempotency-Key must be a canonical UUID.")
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return _problem(request, 400, "BAD_REQUEST", "Request body is not valid JSON.")
        if not isinstance(payload, dict):
            return _problem(request, 422, "VALIDATION_FAILED", "Request body must be a JSON object.")

        route = request.url.path
        digest = hashlib.sha256(_canonical_json(payload)).hexdigest()
        existing = store.find_idempotency("POST", route, key)
        if existing is not None:
            if existing["body_sha256"] != digest:
                return _problem(request, 409, "IDEMPOTENCY_KEY_REUSED", "Idempotency-Key was reused with a different request.")
            replay = json.loads(existing["response_json"])
            return JSONResponse(replay, status_code=existing["response_status"], headers={"Idempotent-Replayed": "true", "Cache-Control": "no-store"})

        accepted_at = _utc_now()
        command_id = str(uuid.uuid4())
        kind = f"mission.{action.replace('-', '_')}" if action in {"start", "pause", "resume", "stop", "return-home"} else "unknown"
        response = {
            "schema_version": SCHEMA_VERSION,
            "command_id": command_id,
            "status": "accepted",
            "accepted_at": accepted_at,
            "status_url": f"/api/v1/commands/{command_id}",
        }
        store.insert_accepted(
            command_id=command_id,
            method="POST",
            route=route,
            key=key,
            body_sha256=digest,
            kind=kind,
            run_id=state.run_id,
            accepted_at=accepted_at,
            response=response,
        )
        return JSONResponse(response, status_code=202, headers={"Cache-Control": "no-store"})

    @app.websocket("/ws/telemetry")
    async def telemetry(websocket: WebSocket) -> None:
        if "substation.v1" not in websocket.scope.get("subprotocols", []):
            denial = Response(status_code=426, headers={"Sec-WebSocket-Protocol": "substation.v1"})
            try:
                await websocket.send_denial_response(denial)
            except RuntimeError:
                # ASGI servers without the denial-response extension cannot
                # emit an HTTP response after a WebSocket scope is selected.
                await websocket.close(code=1002)
            return
        await websocket.accept(subprotocol="substation.v1")
        connection_id = str(uuid.uuid4())
        envelope = {
            "schema_version": SCHEMA_VERSION,
            "stream": "telemetry",
            "stream_epoch": state.stream_epoch,
            "connection_id": connection_id,
            "run_id": state.run_id,
            "sequence": "0",
            "snapshot_revision": str(state.snapshot_revision),
            "timestamp": _utc_now(),
            "type": "stream.open",
            "payload": {
                "heartbeat_interval_s": 1.0,
                "connection_timeout_s": 5.0,
                "replay_available": False,
            },
        }
        await websocket.send_json(envelope)
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=1.0)
            except asyncio.TimeoutError:
                heartbeat = {
                    "schema_version": SCHEMA_VERSION,
                    "stream": "telemetry",
                    "stream_epoch": state.stream_epoch,
                    "connection_id": connection_id,
                    "run_id": state.run_id,
                    "sequence": state.next_sequence(),
                    "snapshot_revision": str(state.snapshot_revision),
                    "timestamp": _utc_now(),
                    "type": "heartbeat",
                    "payload": {
                        "server_time": _utc_now(),
                        "latest_data_sequence": str(state._sequence),
                        "ready": all(state.ready_dependencies.values()),
                    },
                }
                await websocket.send_json(heartbeat)
                continue
            if message.get("type") == "websocket.disconnect":
                return

    async def _stream_open(websocket: WebSocket, stream: str, payload: dict[str, Any]) -> str | None:
        if "substation.v1" not in websocket.scope.get("subprotocols", []):
            denial = Response(status_code=426, headers={"Sec-WebSocket-Protocol": "substation.v1"})
            try:
                await websocket.send_denial_response(denial)
            except RuntimeError:
                await websocket.close(code=1002)
            return None
        await websocket.accept(subprotocol="substation.v1")
        connection_id = str(uuid.uuid4())
        await websocket.send_json({
            "schema_version": SCHEMA_VERSION,
            "stream": stream,
            "stream_epoch": state.stream_epoch,
            "connection_id": connection_id,
            "run_id": state.run_id,
            "sequence": "0",
            "snapshot_revision": str(state.snapshot_revision),
            "timestamp": _utc_now(),
            "type": "stream.open",
            "payload": payload,
        })
        return connection_id

    @app.websocket("/ws/events")
    async def events(websocket: WebSocket) -> None:
        connection_id = await _stream_open(websocket, "events", {
            "heartbeat_interval_s": 1.0,
            "connection_timeout_s": 5.0,
            "replay_available": False,
        })
        if connection_id is None:
            return
        for event in state.events:
            await websocket.send_json({
                "schema_version": SCHEMA_VERSION,
                "stream": "events",
                "stream_epoch": state.stream_epoch,
                "connection_id": connection_id,
                "run_id": state.run_id,
                "sequence": state.next_sequence(),
                "snapshot_revision": str(state.snapshot_revision),
                "timestamp": _utc_now(),
                "type": "event",
                "payload": event,
            })
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=1.0)
            except asyncio.TimeoutError:
                await websocket.send_json({
                    "schema_version": SCHEMA_VERSION,
                    "stream": "events",
                    "stream_epoch": state.stream_epoch,
                    "connection_id": connection_id,
                    "run_id": state.run_id,
                    "sequence": state.next_sequence(),
                    "snapshot_revision": str(state.snapshot_revision),
                    "timestamp": _utc_now(),
                    "type": "heartbeat",
                    "payload": {"server_time": _utc_now(), "ready": all(state.ready_dependencies.values())},
                })
                continue
            if message.get("type") == "websocket.disconnect":
                return

    @app.websocket("/ws/camera")
    async def camera(websocket: WebSocket) -> None:
        connection_id = await _stream_open(websocket, "camera", {
            "heartbeat_interval_s": 1.0,
            "connection_timeout_s": 5.0,
            "camera_available": state.camera_jpeg is not None,
            "media_type": "image/jpeg" if state.camera_jpeg is not None else None,
        })
        if connection_id is None:
            return
        if state.camera_jpeg is not None:
            await websocket.send({"type": "websocket.send", "bytes": state.camera_jpeg})
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=1.0)
            except asyncio.TimeoutError:
                await websocket.send_json({
                    "schema_version": SCHEMA_VERSION,
                    "stream": "camera",
                    "stream_epoch": state.stream_epoch,
                    "connection_id": connection_id,
                    "run_id": state.run_id,
                    "sequence": state.next_sequence(),
                    "snapshot_revision": str(state.snapshot_revision),
                    "timestamp": _utc_now(),
                    "type": "heartbeat",
                    "payload": {"server_time": _utc_now(), "camera_available": state.camera_jpeg is not None},
                })
                continue
            if message.get("type") == "websocket.disconnect":
                return

    return app


app = create_app()


def main() -> None:
    """Run the loopback-only development server when invoked by ROS tooling."""
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
