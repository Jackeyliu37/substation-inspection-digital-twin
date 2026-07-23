from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import uuid

import pytest

from substation_reporting.evidence_store import EvidenceConflict, EvidenceStore


def test_time_mapping_is_idempotent_and_rejects_conflicts(tmp_path) -> None:
    store = EvidenceStore(tmp_path)
    run_id = str(uuid.uuid4())
    anchor_utc = datetime(2026, 7, 23, 19, 0, tzinfo=timezone.utc)

    first = store.record_run_time_mapping(run_id, 7, 123, 400_000_000, anchor_utc)
    second = store.record_run_time_mapping(run_id, 7, 123, 400_000_000, anchor_utc)

    assert first == second
    assert first["anchor_utc"] == "2026-07-23T19:00:00.000000Z"
    with pytest.raises(EvidenceConflict, match="TIME_MAPPING_CONFLICT"):
        store.record_run_time_mapping(run_id, 8, 124, 0, anchor_utc)


def test_evidence_is_content_addressed_queryable_and_range_readable(tmp_path) -> None:
    store = EvidenceStore(tmp_path)
    run_id = str(uuid.uuid4())
    payload = b"immutable-camera-frame"
    metadata = {"source_topic": "/perception/annotated_image", "sequence": "12"}

    record = store.store_bytes(run_id, 3, "image/jpeg", payload, metadata)
    replay = store.store_bytes(
        run_id,
        3,
        "image/jpeg",
        payload,
        metadata,
        evidence_id=record.evidence_id,
    )

    assert replay == record
    assert record.content_sha256 == hashlib.sha256(payload).hexdigest()
    assert store.query_evidence(record.evidence_id) == record
    assert store.read_evidence_chunk(record.evidence_id, 2, 11) == payload[2:11]
    assert json.loads(record.metadata_json) == metadata
    assert not hasattr(record, "object_path")


def test_existing_evidence_id_cannot_change_content(tmp_path) -> None:
    store = EvidenceStore(tmp_path)
    evidence_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    store.store_bytes(run_id, 1, "application/json", b"{}", {}, evidence_id)

    with pytest.raises(EvidenceConflict, match="EVIDENCE_ID_CONFLICT"):
        store.store_bytes(run_id, 1, "application/json", b'{"changed":true}', {}, evidence_id)
