from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping


class MissionSnapshotConflict(RuntimeError):
    """Raised when a snapshot would violate monotonic persistence."""


class MissionSnapshotStore:
    REQUIRED_FIELDS = {
        "schema_version",
        "run_id",
        "mission_id",
        "state_revision",
        "queue_revision",
        "mission_state",
        "context_lifecycle",
        "context_revision",
        "transition_command_id",
        "transition_reason_code",
        "transition_reason",
        "active_task_id",
        "completed_tasks",
        "progress_0_1",
        "robot_mode",
        "emergency_stop_latched",
        "emergency_stop_latch_revision",
        "tasks",
    }

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS mission_snapshots (
                    state_revision INTEGER PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    mission_id TEXT NOT NULL,
                    queue_revision INTEGER NOT NULL,
                    snapshot_json TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    @classmethod
    def _canonical(cls, snapshot: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
        value = dict(snapshot)
        if set(value) != cls.REQUIRED_FIELDS or value.get("schema_version") != 1:
            raise ValueError("MISSION_SNAPSHOT_SCHEMA_INVALID")
        for name in (
            "state_revision", "queue_revision", "mission_state", "context_lifecycle",
            "context_revision", "robot_mode", "emergency_stop_latch_revision",
            "completed_tasks",
        ):
            if isinstance(value[name], bool) or not isinstance(value[name], int) or value[name] < 0:
                raise ValueError("MISSION_SNAPSHOT_VALUE_INVALID")
        if value["state_revision"] < 1 or not isinstance(value["emergency_stop_latched"], bool):
            raise ValueError("MISSION_SNAPSHOT_VALUE_INVALID")
        if (
            isinstance(value["progress_0_1"], bool)
            or not isinstance(value["progress_0_1"], (int, float))
            or not 0.0 <= value["progress_0_1"] <= 1.0
        ):
            raise ValueError("MISSION_SNAPSHOT_VALUE_INVALID")
        if not isinstance(value["tasks"], list):
            raise ValueError("MISSION_SNAPSHOT_VALUE_INVALID")
        idle = value["context_lifecycle"] == 0 and value["mission_state"] == 0
        if idle:
            if value["run_id"] or value["mission_id"] or value["queue_revision"] != 0 or value["tasks"]:
                raise ValueError("MISSION_SNAPSHOT_VALUE_INVALID")
        elif not value["run_id"] or not value["mission_id"]:
            raise ValueError("MISSION_SNAPSHOT_VALUE_INVALID")
        encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        return json.loads(encoded), encoded

    def save(self, snapshot: Mapping[str, Any]) -> dict[str, Any]:
        value, encoded = self._canonical(snapshot)
        revision = value["state_revision"]
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            latest = connection.execute(
                "SELECT state_revision, snapshot_json FROM mission_snapshots ORDER BY state_revision DESC LIMIT 1"
            ).fetchone()
            if latest is not None and revision < latest["state_revision"]:
                raise MissionSnapshotConflict("STATE_REVISION_ROLLBACK")
            if latest is not None and revision == latest["state_revision"]:
                if encoded != latest["snapshot_json"]:
                    raise MissionSnapshotConflict("STATE_REVISION_CONFLICT")
                return json.loads(latest["snapshot_json"])
            connection.execute(
                "INSERT INTO mission_snapshots VALUES (?, ?, ?, ?, ?)",
                (revision, value["run_id"], value["mission_id"], value["queue_revision"], encoded),
            )
        return value

    def load_latest(self) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT snapshot_json FROM mission_snapshots ORDER BY state_revision DESC LIMIT 1"
            ).fetchone()
        return None if row is None else json.loads(row["snapshot_json"])
