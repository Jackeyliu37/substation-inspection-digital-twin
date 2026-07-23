from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any
import uuid


class EvidenceConflict(RuntimeError):
    """Raised when an idempotent evidence or time-mapping write disagrees."""


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    run_id: str
    context_revision: int
    evidence_revision: int
    media_type: str
    size_bytes: int
    content_sha256: str
    metadata_json: str


class EvidenceStore:
    """Single-writer SQLite metadata store with content-addressed objects."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._objects = self._root / "objects"
        self._root.mkdir(parents=True, exist_ok=True)
        self._objects.mkdir(parents=True, exist_ok=True)
        self._db_path = self._root / "evidence.sqlite3"
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS run_time_mappings (
                    run_id TEXT PRIMARY KEY,
                    context_revision INTEGER NOT NULL,
                    anchor_ros_sec INTEGER NOT NULL,
                    anchor_ros_nanosec INTEGER NOT NULL,
                    anchor_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evidence (
                    evidence_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    context_revision INTEGER NOT NULL,
                    evidence_revision INTEGER NOT NULL,
                    media_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    UNIQUE(run_id, evidence_revision)
                );
                """
            )

    @staticmethod
    def _validate_uuid(value: str, code: str) -> str:
        try:
            parsed = uuid.UUID(value)
        except (ValueError, AttributeError, TypeError) as exc:
            raise ValueError(code) from exc
        if str(parsed) != value:
            raise ValueError(code)
        return value

    @staticmethod
    def _metadata_json(metadata: dict[str, Any]) -> str:
        return json.dumps(metadata, ensure_ascii=True, sort_keys=True, separators=(",", ":"))

    def record_run_time_mapping(
        self,
        run_id: str,
        context_revision: int,
        anchor_ros_sec: int,
        anchor_ros_nanosec: int,
        anchor_utc: datetime,
    ) -> dict[str, Any]:
        self._validate_uuid(run_id, "RUN_ID_INVALID")
        if context_revision < 0 or anchor_ros_nanosec not in range(1_000_000_000):
            raise ValueError("TIME_MAPPING_INVALID")
        if anchor_utc.tzinfo is None:
            raise ValueError("TIME_MAPPING_INVALID")
        canonical_utc = (
            anchor_utc.astimezone(timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
        value = {
            "run_id": run_id,
            "context_revision": context_revision,
            "anchor_ros_sec": anchor_ros_sec,
            "anchor_ros_nanosec": anchor_ros_nanosec,
            "anchor_utc": canonical_utc,
        }
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM run_time_mappings WHERE run_id = ?", (run_id,)
            ).fetchone()
            if row is not None:
                existing = dict(row)
                if existing != value:
                    raise EvidenceConflict("TIME_MAPPING_CONFLICT")
                return value
            connection.execute(
                "INSERT INTO run_time_mappings VALUES (?, ?, ?, ?, ?)",
                tuple(value[field] for field in (
                    "run_id", "context_revision", "anchor_ros_sec",
                    "anchor_ros_nanosec", "anchor_utc"
                )),
            )
        return value

    def query_run_time_mapping(self, run_id: str) -> dict[str, Any] | None:
        self._validate_uuid(run_id, "RUN_ID_INVALID")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM run_time_mappings WHERE run_id = ?", (run_id,)
            ).fetchone()
        return dict(row) if row is not None else None

    def store_bytes(
        self,
        run_id: str,
        context_revision: int,
        media_type: str,
        payload: bytes,
        metadata: dict[str, Any],
        evidence_id: str | None = None,
    ) -> EvidenceRecord:
        self._validate_uuid(run_id, "RUN_ID_INVALID")
        evidence_id = evidence_id or str(uuid.uuid4())
        self._validate_uuid(evidence_id, "EVIDENCE_ID_INVALID")
        if not media_type or not isinstance(payload, bytes):
            raise ValueError("EVIDENCE_INPUT_INVALID")
        digest = hashlib.sha256(payload).hexdigest()
        metadata_json = self._metadata_json(metadata)
        object_path = self._objects / digest[:2] / digest
        object_path.parent.mkdir(parents=True, exist_ok=True)
        if object_path.exists():
            if object_path.read_bytes() != payload:
                raise EvidenceConflict("CONTENT_HASH_CONFLICT")
        else:
            object_path.write_bytes(payload)

        with self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM evidence WHERE evidence_id = ?", (evidence_id,)
            ).fetchone()
            if existing is not None:
                row = dict(existing)
                if any(row[key] != value for key, value in {
                    "run_id": run_id,
                    "context_revision": context_revision,
                    "media_type": media_type,
                    "size_bytes": len(payload),
                    "content_sha256": digest,
                    "metadata_json": metadata_json,
                }.items()):
                    raise EvidenceConflict("EVIDENCE_ID_CONFLICT")
                return EvidenceRecord(**row)
            next_revision = connection.execute(
                "SELECT COALESCE(MAX(evidence_revision), 0) + 1 FROM evidence WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (evidence_id, run_id, context_revision, next_revision, media_type,
                 len(payload), digest, metadata_json),
            )
            return EvidenceRecord(
                evidence_id, run_id, context_revision, next_revision, media_type,
                len(payload), digest, metadata_json,
            )

    def query_evidence(self, evidence_id: str) -> EvidenceRecord | None:
        self._validate_uuid(evidence_id, "EVIDENCE_ID_INVALID")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM evidence WHERE evidence_id = ?", (evidence_id,)
            ).fetchone()
        return EvidenceRecord(**dict(row)) if row is not None else None

    def read_evidence_chunk(self, evidence_id: str, start: int, end: int) -> bytes:
        record = self.query_evidence(evidence_id)
        if record is None:
            raise KeyError("EVIDENCE_NOT_FOUND")
        if start < 0 or end < start or end > record.size_bytes:
            raise ValueError("INVALID_RANGE")
        object_path = self._objects / record.content_sha256[:2] / record.content_sha256
        with object_path.open("rb") as stream:
            stream.seek(start)
            return stream.read(end - start)
