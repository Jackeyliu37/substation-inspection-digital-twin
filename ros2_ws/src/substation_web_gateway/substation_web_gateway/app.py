"""HTTP/WebSocket adapter for the production substation ROS graph."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
import math
import re
import sqlite3
import struct
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
_RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")
_UINT64 = re.compile(r"^(0|[1-9][0-9]{0,19})$")


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


def load_production_models(
    manifest_path: str | Path,
    production_root: str | Path,
) -> list[dict[str, Any]]:
    """Project the locked model manifest and installed immutable weights."""
    import yaml

    manifest = yaml.safe_load(Path(manifest_path).read_text(encoding="utf-8"))
    artifacts = manifest.get("artifacts", []) if isinstance(manifest, dict) else []
    deployment_names = manifest.get("deployment_filenames", {}) if isinstance(manifest, dict) else {}
    if not isinstance(artifacts, list) or not isinstance(deployment_names, dict):
        raise ValueError("MODEL_MANIFEST_INVALID")
    root = Path(production_root)
    models: list[dict[str, Any]] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise ValueError("MODEL_MANIFEST_INVALID")
        logical_model = str(artifact["logical_model"])
        digest = str(artifact["sha256"])
        filename = str(deployment_names[logical_model])
        weight = root / digest / filename
        models.append({
            "logical_model": logical_model,
            "module": str(artifact["module"]),
            "filename": filename,
            "sha256": digest,
            "classes": list(artifact.get("class_names", [])),
            "metric_name": artifact.get("metric_name"),
            "best_metric": artifact.get("best_metric"),
            "acceptance_status": artifact.get("acceptance_status"),
            "threshold_waived": bool(artifact.get("threshold_waived", False)),
            "installed": weight.is_file() and weight.stat().st_size > 0,
            "size_bytes": weight.stat().st_size if weight.is_file() else 0,
        })
    return models


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

    authoritative_required: bool = False
    run_id: str | None = None
    snapshot_revision: int = 1
    assets: list[dict[str, Any]] = field(default_factory=list)
    robot: dict[str, Any] | None = None
    map_snapshot: dict[str, Any] | None = None
    models: list[dict[str, Any]] = field(default_factory=list)
    scenario: dict[str, Any] = field(default_factory=lambda: {
        "scenario_id": "normal",
        "action": "reset",
        "status": "unknown",
        "active": False,
        "scenario_revision": "0",
        "error_code": None,
    })
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


def pack_camera_frame(state: GatewayState, *, connection_id: str) -> bytes:
    """Pack the newest camera JPEG using the locked SSCF v1 framing."""
    jpeg = state.camera_jpeg
    if jpeg is None or not jpeg.startswith(b"\xff\xd8") or not jpeg.endswith(b"\xff\xd9"):
        raise ValueError("CAMERA_FRAME_INVALID")
    metadata_source = state.camera_metadata
    width = int(metadata_source["width"])
    height = int(metadata_source["height"])
    sequence = int(state.next_sequence())
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "connection_id": connection_id,
        "run_id": state.run_id,
        "captured_at": metadata_source.get("captured_at") or _utc_now(),
        "source_ros_time": metadata_source["source_ros_time"],
        "ros_frame_id": metadata_source["source_frame_id"],
        "encoding": "jpeg",
        "annotated": True,
        "detections_sequence": str(sequence),
        "evidence_id": metadata_source.get("evidence_id"),
    }
    encoded_metadata = _canonical_json(metadata)
    if not 1 <= len(encoded_metadata) <= 16_384 or not 1 <= len(jpeg) <= 2_097_152:
        raise ValueError("CAMERA_FRAME_INVALID")
    header = struct.pack(
        "!4sBBHQQIIII16s8s",
        b"SSCF",
        1,
        1,
        64,
        sequence,
        int(state.snapshot_revision),
        len(encoded_metadata),
        len(jpeg),
        width,
        height,
        uuid.UUID(state.stream_epoch).bytes,
        b"\0" * 8,
    )
    return header + encoded_metadata + jpeg


def _report_generation(state: GatewayState, *, has_reports: bool) -> dict[str, Any]:
    mission = state.mission if isinstance(state.mission, dict) else {}
    try:
        completed_tasks = int(mission.get("completed_tasks", 0))
        total_tasks = int(mission.get("total_tasks", 0))
    except (TypeError, ValueError):
        completed_tasks = total_tasks = 0
    status = str(mission.get("state", "idle"))
    if has_reports:
        generation_status = "ready"
        message = "报告已生成，可下载网页、PDF 和证据包。"
    elif not bool(state.ready_dependencies.get("reporting")):
        generation_status = "unavailable"
        message = "报告生成服务不可用，请查看系统状态。"
    elif status == "succeeded":
        generation_status = "generating"
        message = "巡检已完成，报告生成中。"
    elif status in {"ready", "running", "paused", "stopping"}:
        generation_status = "waiting_for_mission"
        message = "巡检进行中，完成全部设备后自动生成报告。"
    else:
        generation_status = "idle"
        message = "开始并完成一次巡检后将自动生成报告。"
    return {
        "status": generation_status,
        "message": message,
        "completed_tasks": completed_tasks,
        "total_tasks": total_tasks,
    }


class CommandStore:
    """Single-writer SQLite store for idempotency and command records."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self._lock = threading.Lock()
        self._transition_observer = None
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
                started_at TEXT,
                completed_at TEXT,
                result_json TEXT,
                error_json TEXT,
                expectation_json TEXT,
                response_status INTEGER NOT NULL,
                response_json TEXT NOT NULL,
                UNIQUE(method, route, idempotency_key)
            )
            """
        )
        columns = {
            row["name"] for row in self._connection.execute("PRAGMA table_info(commands)")
        }
        for name in (
            "started_at", "completed_at", "result_json", "error_json", "expectation_json"
        ):
            if name not in columns:
                self._connection.execute(f"ALTER TABLE commands ADD COLUMN {name} TEXT")
        self._connection.commit()

    def set_transition_observer(self, observer) -> None:
        self._transition_observer = observer

    def _notify_transition(
        self,
        *,
        command_id: str,
        kind: str,
        status: str,
        run_id: str | None,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> None:
        if self._transition_observer is not None:
            self._transition_observer({
                "type": "command.status",
                "command_id": command_id,
                "kind": kind,
                "status": status,
                "run_id": run_id,
                "result": result,
                "error": error,
            })

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
        expectation: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO commands
                (command_id, method, route, idempotency_key, body_sha256, kind,
                 status, run_id, created_at, accepted_at, expectation_json,
                 response_status, response_json)
                VALUES (?, ?, ?, ?, ?, ?, 'accepted', ?, ?, ?, ?, 202, ?)
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
                    json.dumps(
                        expectation or {}, ensure_ascii=False, separators=(",", ":")
                    ),
                    json.dumps(response, ensure_ascii=False, separators=(",", ":")),
                ),
            )
            self._connection.commit()
        self._notify_transition(
            command_id=command_id,
            kind=kind,
            status="accepted",
            run_id=run_id,
        )

    def get(self, command_id: str) -> sqlite3.Row | None:
        with self._lock:
            return self._connection.execute("SELECT * FROM commands WHERE command_id=?", (command_id,)).fetchone()

    def expire_due(
        self, *, command_id: str | None = None, now_utc: str | None = None
    ) -> int:
        timeouts = {
            "mission.start": 30.0,
            "mission.pause": 10.0,
            "mission.resume": 10.0,
            "mission.stop": 10.0,
            "mission.return_home": 300.0,
            "robot.mode": 10.0,
            "robot.manual_velocity": 1.0,
            "robot.emergency_stop": 2.0,
            "robot.emergency_stop_reset": 5.0,
            "simulation.scenario": 30.0,
        }
        now_text = now_utc or _utc_now()
        try:
            now = datetime.fromisoformat(now_text.replace("Z", "+00:00"))
        except ValueError:
            return 0
        with self._lock:
            query = "SELECT * FROM commands WHERE status IN ('accepted', 'executing')"
            parameters: tuple[Any, ...] = ()
            if command_id is not None:
                query += " AND command_id=?"
                parameters = (command_id,)
            rows = self._connection.execute(query, parameters).fetchall()
            expired = 0
            expired_events: list[tuple[str, str, str | None, dict[str, Any]]] = []
            error = json.dumps(
                {
                    "code": "COMMAND_TIMED_OUT",
                    "message": "No matching authoritative terminal state arrived before the deadline.",
                    "retryable": True,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            for row in rows:
                timeout_s = timeouts.get(row["kind"])
                if timeout_s is None:
                    continue
                try:
                    accepted = datetime.fromisoformat(
                        str(row["accepted_at"]).replace("Z", "+00:00")
                    )
                except ValueError:
                    continue
                if (now - accepted).total_seconds() < timeout_s:
                    continue
                cursor = self._connection.execute(
                    """
                    UPDATE commands
                    SET status='timed_out', started_at=COALESCE(started_at, accepted_at),
                        completed_at=?, error_json=?
                    WHERE command_id=? AND status IN ('accepted', 'executing')
                    """,
                    (now_text, error, row["command_id"]),
                )
                expired += cursor.rowcount
                if cursor.rowcount:
                    expired_events.append(
                        (row["command_id"], row["kind"], row["run_id"], json.loads(error))
                    )
            self._connection.commit()
            for expired_command_id, kind, run_id, expired_error in expired_events:
                self._notify_transition(
                    command_id=expired_command_id,
                    kind=kind,
                    status="timed_out",
                    run_id=run_id,
                    error=expired_error,
                )
            return expired

    def complete_from_mission(
        self, command_id: str, mission: dict[str, Any], run_id: str | None
    ) -> bool:
        expected_states = {
            "mission.start": "running",
            "mission.pause": "paused",
            "mission.resume": "running",
            "mission.stop": "stopped",
        }
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM commands WHERE command_id=?", (command_id,)
            ).fetchone()
            if row is None or row["status"] not in {"accepted", "executing"}:
                return False
            if mission.get("transition_command_id") != command_id:
                return False
            kind = row["kind"]
            expected = expected_states.get(kind)
            expectation = json.loads(row["expectation_json"] or "{}")
            service = expectation.get("service") or {}
            payload = expectation.get("payload") or {}
            try:
                state_revision = int(mission.get("state_revision", 0))
                latch_revision = int(mission.get("emergency_stop_latch_revision", 0))
                if state_revision < int(service.get("state_revision", 0)):
                    return False
                if kind.startswith("robot.") and latch_revision < int(
                    service.get("latch_revision", 0)
                ):
                    return False
            except (TypeError, ValueError):
                return False
            result = {
                "run_id": run_id,
                "state_revision": str(state_revision),
            }
            if expected is not None:
                if mission.get("state") != expected:
                    return False
                result.update(
                    mission_id=mission.get("mission_id"),
                    queue_revision=str(mission.get("queue_revision", "0")),
                )
            elif kind == "robot.mode":
                target_mode = payload.get("target_mode")
                if (
                    target_mode not in {"manual", "autonomous"}
                    or mission.get("robot_mode") != target_mode
                    or bool(mission.get("emergency_stop_latched"))
                ):
                    return False
                result.update(mode=target_mode, latch_revision=str(latch_revision))
            elif kind == "robot.emergency_stop":
                if (
                    mission.get("robot_mode") != "estop"
                    or not bool(mission.get("emergency_stop_latched"))
                ):
                    return False
                result.update(latch_revision=str(latch_revision))
            elif kind == "robot.emergency_stop_reset":
                if (
                    mission.get("robot_mode") != "manual"
                    or bool(mission.get("emergency_stop_latched"))
                ):
                    return False
                result.update(mode="manual", latch_revision=str(latch_revision))
            else:
                return False
            completed_at = _utc_now()
            self._connection.execute(
                """
                UPDATE commands
                SET status='succeeded', started_at=accepted_at, completed_at=?, result_json=?
                WHERE command_id=? AND status IN ('accepted', 'executing')
                """,
                (
                    completed_at,
                    json.dumps(result, ensure_ascii=False, separators=(",", ":")),
                    command_id,
                ),
            )
            self._connection.commit()
            self._notify_transition(
                command_id=command_id,
                kind=kind,
                status="succeeded",
                run_id=run_id,
                result=result,
            )
            return True

    def complete_from_manual_velocity(
        self,
        message,
        *,
        run_id: str | None,
        context_revision: int,
        applied_at: str | None,
    ) -> bool:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM commands WHERE command_id=?", (message.command_id,)
            ).fetchone()
            if (
                row is None
                or row["kind"] != "robot.manual_velocity"
                or row["status"] not in {"accepted", "executing"}
                or row["run_id"] != run_id
            ):
                return False
            state = int(message.state)
            if state == 0:
                self._connection.execute(
                    """
                    UPDATE commands
                    SET status='executing', started_at=COALESCE(started_at, accepted_at)
                    WHERE command_id=? AND status='accepted'
                    """,
                    (message.command_id,),
                )
                self._connection.commit()
                self._notify_transition(
                    command_id=message.command_id,
                    kind=row["kind"],
                    status="executing",
                    run_id=run_id,
                )
                return True
            terminal_states = {1: "succeeded", 2: "failed", 3: "timed_out", 4: "cancelled"}
            command_state = terminal_states.get(state)
            if command_state is None:
                return False
            expectation = json.loads(row["expectation_json"] or "{}")
            payload = expectation.get("payload") or {}
            result_json = None
            error_json = None
            if command_state == "succeeded":
                if applied_at is None:
                    return False
                result_json = json.dumps(
                    {
                        "run_id": run_id,
                        "context_revision": str(context_revision),
                        "applied_at": applied_at,
                        "duration_s": payload.get("duration_s"),
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            else:
                defaults = {
                    "failed": "MANUAL_VELOCITY_REJECTED",
                    "timed_out": "MANUAL_VELOCITY_EXPIRED",
                    "cancelled": "MANUAL_VELOCITY_CANCELLED",
                }
                error_json = json.dumps(
                    {
                        "code": message.error_code or defaults[command_state],
                        "message": message.error_message or defaults[command_state],
                        "retryable": command_state == "timed_out",
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            self._connection.execute(
                """
                UPDATE commands
                SET status=?, started_at=COALESCE(started_at, accepted_at),
                    completed_at=?, result_json=?, error_json=?
                WHERE command_id=? AND status IN ('accepted', 'executing')
                """,
                (
                    command_state,
                    _utc_now(),
                    result_json,
                    error_json,
                    message.command_id,
                ),
            )
            self._connection.commit()
            self._notify_transition(
                command_id=message.command_id,
                kind=row["kind"],
                status=command_state,
                run_id=run_id,
                result=json.loads(result_json) if result_json else None,
                error=json.loads(error_json) if error_json else None,
            )
            return True

    def complete_from_scenario(
        self,
        command_id: str,
        scenario: dict[str, Any],
        run_id: str | None,
    ) -> bool:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM commands WHERE command_id=?", (command_id,)
            ).fetchone()
            if (
                row is None
                or row["kind"] != "simulation.scenario"
                or row["status"] not in {"accepted", "executing"}
                or row["run_id"] != run_id
            ):
                return False
            expectation = json.loads(row["expectation_json"] or "{}")
            payload = expectation.get("payload") or {}
            service = expectation.get("service") or {}
            if (
                scenario.get("command_id") != command_id
                or scenario.get("scenario_id") != payload.get("scenario_id")
                or scenario.get("action") != payload.get("action")
                or scenario.get("status") not in {"applied", "failed"}
            ):
                return False
            try:
                revision = int(scenario.get("scenario_revision", -1))
                baseline_revision = int(service.get("scenario_revision", -1))
                if (
                    scenario["status"] == "applied"
                    and revision <= baseline_revision
                ) or (
                    scenario["status"] == "failed"
                    and revision < baseline_revision
                ):
                    return False
            except (TypeError, ValueError):
                return False
            succeeded = scenario["status"] == "applied"
            completed_at = _utc_now()
            result = {
                "run_id": run_id,
                "scenario_id": scenario["scenario_id"],
                "action": scenario["action"],
                "scenario_revision": str(revision),
                "active": bool(scenario.get("active")),
            } if succeeded else None
            error = None if succeeded else {
                "code": scenario.get("error_code") or "SCENARIO_APPLY_FAILED",
                "message": scenario.get("error_code") or "Gazebo rejected the scenario command.",
                "retryable": True,
            }
            self._connection.execute(
                """
                UPDATE commands
                SET status=?, started_at=accepted_at, completed_at=?, result_json=?, error_json=?
                WHERE command_id=? AND status IN ('accepted', 'executing')
                """,
                (
                    "succeeded" if succeeded else "failed",
                    completed_at,
                    json.dumps(result, ensure_ascii=False, separators=(",", ":")) if result else None,
                    json.dumps(error, ensure_ascii=False, separators=(",", ":")) if error else None,
                    command_id,
                ),
            )
            self._connection.commit()
            self._notify_transition(
                command_id=command_id,
                kind=row["kind"],
                status="succeeded" if succeeded else "failed",
                run_id=run_id,
                result=result,
                error=error,
            )
            return True


def create_app(
    *,
    state: GatewayState | None = None,
    db_path: str | Path = ":memory:",
    adapter: Any | None = None,
) -> FastAPI:
    state = state or GatewayState()
    store = CommandStore(db_path)
    store.set_transition_observer(state.events.append)
    if adapter is not None and hasattr(adapter, "attach_command_store"):
        adapter.attach_command_store(store)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        async def expire_commands() -> None:
            while True:
                await asyncio.sleep(0.25)
                store.expire_due()

        expiry_task = asyncio.create_task(expire_commands())
        if adapter is not None:
            adapter.start()
        try:
            yield
        finally:
            expiry_task.cancel()
            try:
                await expiry_task
            except asyncio.CancelledError:
                pass
            if adapter is not None:
                adapter.stop()

    app = FastAPI(title="Substation Web Gateway", version=SCHEMA_VERSION, lifespan=lifespan)
    app.state.gateway = state
    app.state.commands = store

    def snapshot_response(data: Any, request: Request) -> Response:
        envelope = state.snapshot(data)
        etag = f'W/"{state.run_id or "none"}:{state.snapshot_revision}"'
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers={"ETag": etag})
        return JSONResponse(envelope, headers={"ETag": etag})

    async def query_evidence_record(evidence_id: str, request: Request):
        if not _strict_uuid(evidence_id):
            return None, _problem(
                request, 422, "VALIDATION_FAILED", "evidence_id must be a canonical UUID."
            )
        if adapter is None or not hasattr(adapter, "query_evidence"):
            return None, _problem(
                request, 503, "EVIDENCE_STORAGE_UNAVAILABLE", "Evidence storage is unavailable."
            )
        try:
            record = await asyncio.to_thread(adapter.query_evidence, evidence_id)
        except Exception:
            return None, _problem(
                request, 503, "EVIDENCE_STORAGE_UNAVAILABLE", "Evidence query failed."
            )
        if not record.get("found", False):
            if record.get("error_code"):
                return None, _problem(
                    request,
                    503,
                    "EVIDENCE_STORAGE_UNAVAILABLE",
                    record.get("error_message") or "Evidence query failed.",
                )
            return None, _problem(request, 404, "EVIDENCE_NOT_FOUND", "Evidence was not found.")
        return record, None

    def parse_range(value: str | None, total: int) -> tuple[int, int] | str | None:
        if value is None:
            return None
        match = _RANGE.fullmatch(value)
        if match is None or "," in value:
            return "invalid"
        start_text, end_text = match.groups()
        if not start_text and not end_text:
            return "invalid"
        if not start_text:
            suffix = int(end_text)
            if suffix == 0:
                return "unsatisfiable"
            return max(0, total - suffix), total - 1
        start = int(start_text)
        if start >= total:
            return "unsatisfiable"
        end = total - 1 if not end_text else int(end_text)
        if end < start:
            return "invalid"
        return start, min(end, total - 1)

    async def reporting_index(request: Request):
        if adapter is None or not hasattr(adapter, "list_reporting_artifacts"):
            return None, _problem(
                request,
                503,
                "REPORT_INDEX_UNAVAILABLE",
                "The reporting artifact index is unavailable.",
            )
        try:
            result = await asyncio.to_thread(
                adapter.list_reporting_artifacts,
                run_id=state.run_id,
            )
        except Exception:
            return None, _problem(
                request, 503, "REPORT_INDEX_UNAVAILABLE", "Reporting index query failed."
            )
        if not result.get("available", False):
            return None, _problem(
                request,
                503,
                result.get("error_code") or "REPORT_INDEX_UNAVAILABLE",
                result.get("error_message") or "The reporting artifact index is unavailable.",
            )
        entries = result.get("entries")
        if not isinstance(entries, list):
            return None, _problem(
                request, 503, "REPORT_INDEX_UNAVAILABLE", "Reporting index returned invalid data."
            )
        return entries, None

    async def download_evidence_record(
        record: dict[str, Any],
        request: Request,
        *,
        filename: str,
        storage_code: str = "EVIDENCE_STORAGE_UNAVAILABLE",
    ) -> Response:
        if adapter is None or not hasattr(adapter, "read_evidence_range"):
            return _problem(request, 503, storage_code, "Evidence storage is unavailable.")
        try:
            digest = str(record["content_sha256"])
            total = int(record["size_bytes"])
            evidence_id = str(record["evidence_id"])
            media_type = str(record["media_type"])
            if not re.fullmatch(r"[0-9a-f]{64}", digest) or total < 0:
                raise ValueError("invalid record")
        except (KeyError, TypeError, ValueError):
            return _problem(request, 503, storage_code, "Evidence metadata is invalid.")
        etag = f'"sha256:{digest}"'
        requested_range = request.headers.get("range")
        if requested_range is None and request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers={"ETag": etag, "Accept-Ranges": "bytes"})
        if_range = request.headers.get("if-range")
        selected = None if requested_range is not None and if_range not in (None, etag) else parse_range(
            requested_range, total
        )
        if selected == "invalid":
            response = _problem(request, 400, "INVALID_RANGE", "Only one valid byte range is supported.")
            response.headers["Accept-Ranges"] = "bytes"
            return response
        if selected == "unsatisfiable" or total == 0:
            response = _problem(request, 416, "RANGE_NOT_SATISFIABLE", "The requested byte range is unavailable.")
            response.headers["Accept-Ranges"] = "bytes"
            response.headers["Content-Range"] = f"bytes */{total}"
            return response
        start, end = (0, total - 1) if selected is None else selected
        try:
            content = await asyncio.to_thread(
                adapter.read_evidence_range, evidence_id, start, end - start + 1
            )
        except Exception:
            return _problem(request, 503, storage_code, "Evidence read failed.")
        if len(content) != end - start + 1:
            return _problem(request, 503, storage_code, "Evidence read was incomplete.")
        if selected is None and hashlib.sha256(content).hexdigest() != digest:
            return _problem(request, 503, storage_code, "Evidence digest verification failed.")
        if media_type not in {"image/jpeg", "application/json", "application/pdf", "application/zip", "text/html"}:
            return _problem(request, 503, storage_code, "Evidence media type is unsupported.")
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'attachment; filename="{filename}"',
            "ETag": etag,
            "X-Content-SHA256": digest,
        }
        if selected is not None:
            headers["Content-Range"] = f"bytes {start}-{end}/{total}"
        return Response(
            content,
            status_code=206 if selected is not None else 200,
            media_type=media_type,
            headers=headers,
        )

    async def dispatch_json_service_command(
        request: Request,
        *,
        kind: str,
        adapter_method: str,
        unavailable_code: str,
        allowed_fields: set[str],
        require_fresh_robot: bool = False,
    ) -> Response:
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
        if not isinstance(payload, dict) or set(payload) != allowed_fields:
            return _problem(request, 422, "VALIDATION_FAILED", "Request fields do not match the schema.")
        route = request.url.path
        digest = hashlib.sha256(_canonical_json(payload)).hexdigest()
        existing = store.find_idempotency("POST", route, key)
        if existing is not None:
            if existing["body_sha256"] != digest:
                return _problem(request, 409, "IDEMPOTENCY_KEY_REUSED", "Idempotency-Key was reused with a different request.")
            return JSONResponse(
                json.loads(existing["response_json"]),
                status_code=existing["response_status"],
                headers={"Idempotent-Replayed": "true", "Cache-Control": "no-store"},
            )
        if require_fresh_robot and (
            state.robot is None or bool(state.robot.get("stale", True))
        ):
            return _problem(
                request,
                503,
                "ROBOT_STATE_UNAVAILABLE",
                "A fresh validated robot pose is required.",
            )
        if adapter is None or not hasattr(adapter, adapter_method):
            return _problem(request, 503, unavailable_code, "The required ROS Service is unavailable.")
        command_id = str(uuid.uuid4())
        try:
            service_result = await asyncio.to_thread(
                getattr(adapter, adapter_method), command_id=command_id, payload=payload
            )
        except Exception:
            return _problem(request, 503, unavailable_code, "The ROS Service call failed.")
        if not service_result.get("accepted", False):
            code = str(service_result.get("error_code") or unavailable_code).split(":", 1)[0]
            status = 503 if code in {
                unavailable_code, "NAVIGATION_UNAVAILABLE", "AUDIT_STORAGE_UNAVAILABLE"
            } else 404 if code in {"MISSION_NOT_FOUND", "SCENARIO_NOT_FOUND"} else 422 if code in {
                "VALIDATION_FAILED", "MODE_INVALID", "RESET_CONFIRMATION_REQUIRED",
                "SCENARIO_ACTION_INVALID", "SCENARIO_PARAMETER_INVALID",
            } else 409
            return _problem(
                request,
                status,
                code,
                service_result.get("error_message") or "The command was rejected.",
            )
        accepted_at = _utc_now()
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
            expectation={"payload": payload, "service": service_result},
        )
        if hasattr(adapter, "replay_terminal"):
            adapter.replay_terminal(command_id)
        return JSONResponse(response, status_code=202, headers={"Cache-Control": "no-store"})

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
        if state.authoritative_required and not state.ready_dependencies["run_context"]:
            return _problem(
                request, 503, "DEPENDENCY_UNAVAILABLE", "RunContext is unavailable."
            )
        return snapshot_response(state.system, request)

    @app.get("/api/v1/assets")
    async def assets(request: Request) -> Response:
        if state.authoritative_required and not state.ready_dependencies["risk"]:
            return _problem(
                request, 503, "DEPENDENCY_UNAVAILABLE", "Authoritative asset state is unavailable."
            )
        items = sorted(state.assets, key=lambda item: item.get("asset_id", ""))
        return snapshot_response({"items": items, "next_cursor": None}, request)

    @app.get("/api/v1/missions/current")
    async def current_mission(request: Request) -> Response:
        if state.authoritative_required and not state.ready_dependencies["mission"]:
            return _problem(
                request, 503, "MISSION_STATE_UNAVAILABLE", "A consistent mission snapshot is unavailable."
            )
        return snapshot_response(state.mission, request)

    @app.get("/api/v1/robot/state")
    async def robot_state(request: Request) -> Response:
        if state.robot is None:
            return _problem(
                request, 503, "ROBOT_STATE_UNAVAILABLE", "A validated robot pose is unavailable."
            )
        return snapshot_response(state.robot, request)

    @app.get("/api/v1/map")
    async def map_snapshot(request: Request) -> Response:
        if state.map_snapshot is None:
            return _problem(request, 503, "MAP_UNAVAILABLE", "A validated map snapshot is not available.")
        return snapshot_response(state.map_snapshot, request)

    @app.get("/api/v1/models")
    async def models(request: Request) -> Response:
        return snapshot_response({"items": state.models}, request)

    @app.get("/api/v1/simulation/scenario")
    async def scenario_snapshot(request: Request) -> Response:
        return snapshot_response(state.scenario, request)

    @app.get("/api/v1/evidence/{evidence_id}")
    async def evidence_metadata(evidence_id: str, request: Request) -> Response:
        record, error = await query_evidence_record(evidence_id, request)
        if error is not None:
            return error
        assert record is not None
        try:
            metadata = json.loads(record["metadata_canonical_json"])
            if not isinstance(metadata, dict):
                raise ValueError("metadata must be an object")
        except (KeyError, ValueError, json.JSONDecodeError):
            return _problem(
                request, 503, "EVIDENCE_STORAGE_UNAVAILABLE", "Evidence metadata is invalid."
            )
        return snapshot_response({
            "evidence_id": evidence_id,
            "run_id": record["run_id"],
            "context_revision": str(record["context_revision"]),
            "evidence_revision": str(record["evidence_revision"]),
            "media_type": record["media_type"],
            "size_bytes": str(record["size_bytes"]),
            "content_sha256": record["content_sha256"],
            "metadata": metadata,
            "download_url": f"/api/v1/evidence/{evidence_id}/download",
        }, request)

    @app.get("/api/v1/evidence/{evidence_id}/download")
    async def evidence_download(evidence_id: str, request: Request) -> Response:
        record, error = await query_evidence_record(evidence_id, request)
        if error is not None:
            return error
        assert record is not None
        record = dict(record)
        record["evidence_id"] = evidence_id
        extension = {
            "image/jpeg": "jpg",
            "application/json": "json",
            "application/pdf": "pdf",
            "application/zip": "zip",
            "text/html": "html",
        }.get(str(record["media_type"]))
        if extension is None:
            return _problem(request, 503, "EVIDENCE_STORAGE_UNAVAILABLE", "Evidence media type is unsupported.")
        return await download_evidence_record(
            record,
            request,
            filename=f"evidence-{evidence_id}.{extension}",
        )

    @app.get("/api/v1/reports")
    async def reports(request: Request) -> Response:
        if adapter is not None:
            entries, error = await reporting_index(request)
            if error is not None:
                return error
            groups: dict[str, dict[str, Any]] = {}
            assert entries is not None
            for entry in entries:
                metadata = entry.get("metadata") if isinstance(entry, dict) else None
                if not isinstance(metadata, dict) or metadata.get("format") == "diagnostic":
                    continue
                report_id = metadata.get("artifact_group_id")
                format_name = metadata.get("format")
                if not isinstance(report_id, str) or not _strict_uuid(report_id):
                    continue
                if format_name not in {"html", "pdf", "evidence"}:
                    continue
                item = groups.setdefault(report_id, {
                    "report_id": report_id,
                    "run_id": entry.get("run_id"),
                    "mission_id": metadata.get("mission_id"),
                    "status": "ready",
                    "formats": [],
                    "download_urls": {},
                    "sha256": {},
                    "size_bytes": {},
                    "created_at": metadata.get("created_at"),
                })
                if format_name not in item["formats"]:
                    item["formats"].append(format_name)
                item["download_urls"][format_name] = (
                    f"/api/v1/reports/{report_id}/download?format={format_name}"
                )
                item["sha256"][format_name] = entry.get("content_sha256")
                item["size_bytes"][format_name] = str(entry.get("size_bytes"))
                if str(metadata.get("created_at", "")) > str(item.get("created_at", "")):
                    item["created_at"] = metadata.get("created_at")
            for item in groups.values():
                item["formats"].sort()
            report_items = sorted(
                groups.values(), key=lambda item: str(item["report_id"])
            )
            return snapshot_response({
                "items": report_items,
                "next_cursor": None,
                "generation": _report_generation(
                    state, has_reports=bool(report_items)
                ),
            }, request)
        items = sorted(state.reports, key=lambda item: str(item.get("report_id", "")))
        return snapshot_response({
            "items": items,
            "next_cursor": None,
            "generation": _report_generation(state, has_reports=bool(items)),
        }, request)

    @app.get("/api/v1/diagnostics")
    async def diagnostics(request: Request) -> Response:
        if adapter is not None:
            entries, error = await reporting_index(request)
            if error is not None:
                return error
            items: dict[str, dict[str, Any]] = {}
            assert entries is not None
            for entry in entries:
                metadata = entry.get("metadata") if isinstance(entry, dict) else None
                if not isinstance(metadata, dict) or metadata.get("format") != "diagnostic":
                    continue
                diagnostic_id = metadata.get("artifact_group_id")
                if not isinstance(diagnostic_id, str) or not _strict_uuid(diagnostic_id):
                    continue
                items[diagnostic_id] = {
                    "diagnostic_id": diagnostic_id,
                    "run_id": entry.get("run_id"),
                    "status": "ready",
                    "created_at": metadata.get("created_at"),
                    "download_url": f"/api/v1/diagnostics/{diagnostic_id}/download",
                    "sha256": entry.get("content_sha256"),
                    "size_bytes": str(entry.get("size_bytes")),
                }
            return snapshot_response({
                "items": sorted(items.values(), key=lambda item: item["diagnostic_id"])
            }, request)
        return snapshot_response(state.diagnostics, request)

    @app.get("/api/v1/reports/{report_id}/download")
    async def report_download(report_id: str, request: Request) -> Response:
        if not _strict_uuid(report_id):
            return _problem(request, 422, "VALIDATION_FAILED", "report_id must be a canonical UUID.")
        format_name = request.query_params.get("format")
        if format_name not in {"html", "pdf", "evidence"}:
            return _problem(request, 422, "VALIDATION_FAILED", "format must be html, pdf, or evidence.")
        entries, error = await reporting_index(request)
        if error is not None:
            if error.status_code == 503:
                return _problem(
                    request,
                    503,
                    "REPORT_STORAGE_UNAVAILABLE",
                    "Report storage is unavailable.",
                )
            return error
        assert entries is not None
        record = None
        for entry in entries:
            metadata = entry.get("metadata") if isinstance(entry, dict) else None
            if (
                isinstance(metadata, dict)
                and metadata.get("artifact_group_id") == report_id
                and metadata.get("format") == format_name
            ):
                record = entry
                break
        if record is None:
            found_group = any(
                isinstance(entry.get("metadata"), dict)
                and entry["metadata"].get("artifact_group_id") == report_id
                for entry in entries if isinstance(entry, dict)
            )
            return _problem(
                request,
                404,
                "REPORT_FORMAT_NOT_FOUND" if found_group else "REPORT_NOT_FOUND",
                "The requested report artifact was not found.",
            )
        extension = "zip" if format_name == "evidence" else format_name
        return await download_evidence_record(
            record,
            request,
            filename=f"inspection-{report_id}.{extension}",
            storage_code="REPORT_STORAGE_UNAVAILABLE",
        )

    @app.get("/api/v1/diagnostics/{diagnostic_id}/download")
    async def diagnostic_download(diagnostic_id: str, request: Request) -> Response:
        if not _strict_uuid(diagnostic_id):
            return _problem(request, 422, "VALIDATION_FAILED", "diagnostic_id must be a canonical UUID.")
        entries, error = await reporting_index(request)
        if error is not None:
            if error.status_code == 503:
                return _problem(
                    request,
                    503,
                    "EVIDENCE_STORAGE_UNAVAILABLE",
                    "Evidence storage is unavailable.",
                )
            return error
        assert entries is not None
        record = next((
            entry for entry in entries
            if isinstance(entry, dict)
            and isinstance(entry.get("metadata"), dict)
            and entry["metadata"].get("artifact_group_id") == diagnostic_id
            and entry["metadata"].get("format") == "diagnostic"
        ), None)
        if record is None:
            return _problem(request, 404, "DIAGNOSTIC_NOT_FOUND", "The diagnostic bundle was not found.")
        return await download_evidence_record(
            record,
            request,
            filename=f"diagnostic-{diagnostic_id}.zip",
            storage_code="EVIDENCE_STORAGE_UNAVAILABLE",
        )

    @app.get("/api/v1/commands/{command_id}")
    async def command_lookup(command_id: str, request: Request) -> Response:
        if not _strict_uuid(command_id):
            return _problem(request, 422, "VALIDATION_FAILED", "command_id must be a canonical UUID.")
        store.expire_due(command_id=command_id)
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
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "result": json.loads(row["result_json"]) if row["result_json"] else None,
            "error": json.loads(row["error_json"]) if row["error_json"] else None,
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
        if kind == "unknown":
            return _problem(request, 400, "INVALID_ACTION", "Mission action is not supported.")
        if adapter is None or not hasattr(adapter, "dispatch_mission"):
            return _problem(
                request,
                503,
                "DEPENDENCY_UNAVAILABLE",
                "The authoritative mission ROS Service is unavailable.",
            )
        try:
            service_result = await asyncio.to_thread(
                adapter.dispatch_mission,
                command_id=command_id,
                action=action,
                payload=payload,
            )
        except Exception:
            return _problem(
                request,
                503,
                "DEPENDENCY_UNAVAILABLE",
                "The authoritative mission ROS Service call failed.",
            )
        if not service_result.get("accepted", False):
            error_code = service_result.get("error_code") or "DEPENDENCY_UNAVAILABLE"
            status = 503 if error_code in {
                "DEPENDENCY_UNAVAILABLE", "NAVIGATION_UNAVAILABLE", "AUDIT_STORAGE_UNAVAILABLE"
            } else 404 if error_code in {"MISSION_NOT_FOUND", "ROUTE_NOT_FOUND"} else (
                422 if error_code == "VALIDATION_FAILED" else 409
            )
            return _problem(
                request,
                status,
                error_code,
                service_result.get("error_message") or "The mission command was rejected.",
            )
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
            expectation={"payload": payload, "service": service_result},
        )
        store.complete_from_mission(command_id, state.mission, state.run_id)
        if hasattr(adapter, "replay_terminal"):
            adapter.replay_terminal(command_id)
        return JSONResponse(response, status_code=202, headers={"Cache-Control": "no-store"})

    @app.post("/api/v1/robot/emergency-stop")
    async def emergency_stop(request: Request) -> Response:
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
        if not isinstance(payload, dict) or set(payload) != {"reason"} or not isinstance(payload["reason"], str) or not payload["reason"].strip():
            return _problem(request, 422, "VALIDATION_FAILED", "A non-empty reason is required.")
        route = request.url.path
        digest = hashlib.sha256(_canonical_json(payload)).hexdigest()
        existing = store.find_idempotency("POST", route, key)
        if existing is not None:
            if existing["body_sha256"] != digest:
                return _problem(request, 409, "IDEMPOTENCY_KEY_REUSED", "Idempotency-Key was reused with a different request.")
            return JSONResponse(
                json.loads(existing["response_json"]),
                status_code=existing["response_status"],
                headers={"Idempotent-Replayed": "true", "Cache-Control": "no-store"},
            )
        if adapter is None or not hasattr(adapter, "dispatch_emergency_stop"):
            return _problem(
                request, 503, "EMERGENCY_STOP_PATH_UNAVAILABLE", "Emergency-stop ROS Service is unavailable."
            )
        command_id = str(uuid.uuid4())
        try:
            service_result = await asyncio.to_thread(
                adapter.dispatch_emergency_stop,
                command_id=command_id,
                payload=payload,
            )
        except Exception:
            return _problem(
                request, 503, "EMERGENCY_STOP_PATH_UNAVAILABLE", "Emergency-stop ROS Service call failed."
            )
        if not service_result.get("accepted", False):
            code = service_result.get("error_code") or "EMERGENCY_STOP_PATH_UNAVAILABLE"
            return _problem(
                request,
                422 if code == "VALIDATION_FAILED" else 503,
                code,
                service_result.get("error_message") or "Emergency stop was rejected.",
            )
        accepted_at = _utc_now()
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
            kind="robot.emergency_stop",
            run_id=state.run_id,
            accepted_at=accepted_at,
            response=response,
            expectation={"payload": payload, "service": service_result},
        )
        if hasattr(adapter, "replay_terminal"):
            adapter.replay_terminal(command_id)
        return JSONResponse(response, status_code=202, headers={"Cache-Control": "no-store"})

    @app.post("/api/v1/robot/mode")
    async def robot_mode(request: Request) -> Response:
        try:
            payload = json.loads(await request.body())
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict):
            if payload.get("target_mode") not in {"manual", "autonomous"}:
                return _problem(request, 422, "MODE_INVALID", "target_mode is invalid.")
            for field in ("observed_state_revision", "observed_latch_revision"):
                value = payload.get(field)
                if not isinstance(value, str) or _UINT64.fullmatch(value) is None or int(value) > 18446744073709551615:
                    return _problem(request, 422, "VALIDATION_FAILED", f"{field} is invalid.")
        return await dispatch_json_service_command(
            request,
            kind="robot.mode",
            adapter_method="dispatch_robot_mode",
            unavailable_code="ROBOT_STATE_UNAVAILABLE",
            allowed_fields={
                "mission_id", "target_mode", "observed_state_revision",
                "observed_latch_revision", "reason",
            },
        )

    @app.post("/api/v1/robot/emergency-stop/reset")
    async def emergency_stop_reset(request: Request) -> Response:
        try:
            payload = json.loads(await request.body())
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict):
            revision = payload.get("observed_latch_revision")
            if not isinstance(revision, str) or _UINT64.fullmatch(revision) is None or int(revision) > 18446744073709551615:
                return _problem(request, 422, "VALIDATION_FAILED", "observed_latch_revision is invalid.")
            if payload.get("confirm") is not True:
                return _problem(request, 422, "RESET_CONFIRMATION_REQUIRED", "confirm must be true.")
        return await dispatch_json_service_command(
            request,
            kind="robot.emergency_stop_reset",
            adapter_method="dispatch_emergency_reset",
            unavailable_code="EMERGENCY_STOP_PATH_UNAVAILABLE",
            allowed_fields={"observed_latch_revision", "confirm", "reason"},
        )

    @app.post("/api/v1/robot/manual-velocity")
    async def manual_velocity(request: Request) -> Response:
        try:
            payload = json.loads(await request.body())
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict):
            try:
                linear = float(payload.get("linear_x_m_s"))
                angular = float(payload.get("angular_z_rad_s"))
                duration = float(payload.get("duration_s"))
            except (TypeError, ValueError):
                return _problem(request, 422, "VALIDATION_FAILED", "Velocity fields must be numbers.")
            if not all(math.isfinite(value) for value in (linear, angular, duration)):
                return _problem(request, 422, "VALIDATION_FAILED", "Velocity fields must be finite.")
            if abs(linear) > 0.4 or abs(angular) > 0.8:
                return _problem(request, 422, "VELOCITY_LIMIT_EXCEEDED", "Velocity exceeds the safety limit.")
            if not 0.05 <= duration <= 0.25:
                return _problem(request, 422, "VALIDATION_FAILED", "duration_s is out of range.")
            if (linear != 0.0 or angular != 0.0) and payload.get("deadman") is not True:
                return _problem(request, 422, "DEADMAN_REQUIRED", "Non-zero velocity requires deadman=true.")
        return await dispatch_json_service_command(
            request,
            kind="robot.manual_velocity",
            adapter_method="dispatch_manual_velocity",
            unavailable_code="ROBOT_STATE_UNAVAILABLE",
            allowed_fields={"linear_x_m_s", "angular_z_rad_s", "deadman", "duration_s"},
            require_fresh_robot=True,
        )

    @app.post("/api/v1/simulation/scenario")
    async def simulation_scenario(request: Request) -> Response:
        if not bool(state.system.get("simulation_mode")):
            return _problem(
                request, 403, "SIMULATION_MODE_REQUIRED", "Simulation mode is required."
            )
        run_context = state.system.get("run_context")
        if not isinstance(run_context, dict) or run_context.get("lifecycle") != "active":
            return _problem(
                request, 409, "RUN_CONTEXT_MISMATCH", "An ACTIVE RunContext is required."
            )
        return await dispatch_json_service_command(
            request,
            kind="simulation.scenario",
            adapter_method="dispatch_scenario",
            unavailable_code="GAZEBO_UNAVAILABLE",
            allowed_fields={"scenario_id", "action", "parameters", "reason"},
        )

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
        last_frame_key = None
        heartbeat_at = asyncio.get_running_loop().time()
        while True:
            metadata = state.camera_metadata
            source_time = metadata.get("source_ros_time") if isinstance(metadata, dict) else None
            frame_key = (
                source_time.get("sec") if isinstance(source_time, dict) else None,
                source_time.get("nanosec") if isinstance(source_time, dict) else None,
                len(state.camera_jpeg) if state.camera_jpeg is not None else 0,
            )
            if state.camera_jpeg is not None and frame_key != last_frame_key:
                try:
                    await websocket.send_bytes(
                        pack_camera_frame(state, connection_id=connection_id)
                    )
                    last_frame_key = frame_key
                except ValueError:
                    last_frame_key = frame_key
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=0.05)
            except asyncio.TimeoutError:
                now = asyncio.get_running_loop().time()
                if now - heartbeat_at >= 1.0:
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
                    heartbeat_at = now
                continue
            if message.get("type") == "websocket.disconnect":
                return

    return app


app = create_app()


def main() -> None:
    """Run the loopback-only development server when invoked by ROS tooling."""
    import uvicorn

    from .ros_adapter import RosGatewayAdapter

    manifest = Path.cwd() / "models" / "manifest.yaml"
    production_root = Path("/var/lib/substation/models/production")
    state = GatewayState(
        models=load_production_models(manifest, production_root)
        if manifest.is_file()
        else []
    )
    uvicorn.run(
        create_app(
            state=state,
            db_path="/var/lib/substation/sqlite/gateway.sqlite3",
            adapter=RosGatewayAdapter(state),
        ),
        host="127.0.0.1",
        port=8000,
    )
