from __future__ import annotations

from pathlib import Path

import pytest

from substation_mission.mission_store import MissionSnapshotConflict, MissionSnapshotStore


def snapshot(revision: int, *, latched: bool = False) -> dict[str, object]:
    return {
        "schema_version": 1,
        "run_id": "run-1",
        "mission_id": "mission-1",
        "state_revision": revision,
        "queue_revision": 2,
        "robot_mode": 2 if latched else 0,
        "emergency_stop_latched": latched,
        "emergency_stop_latch_revision": 4 if latched else 0,
        "tasks": [{"task_id": "task-1", "asset_id": "transformer-01"}],
    }


def test_snapshot_survives_reopen_and_duplicate_write_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "mission.sqlite3"
    store = MissionSnapshotStore(path)

    first = store.save(snapshot(7, latched=True))
    duplicate = store.save(snapshot(7, latched=True))
    restored = MissionSnapshotStore(path).load_latest()

    assert first == duplicate
    assert restored == first
    assert restored["emergency_stop_latched"] is True
    assert restored["emergency_stop_latch_revision"] == 4


def test_snapshot_rejects_revision_rollback_and_conflicting_replay(tmp_path: Path) -> None:
    store = MissionSnapshotStore(tmp_path / "mission.sqlite3")
    store.save(snapshot(7))

    with pytest.raises(MissionSnapshotConflict, match="STATE_REVISION_ROLLBACK"):
        store.save(snapshot(6))
    changed = snapshot(7)
    changed["queue_revision"] = 3
    with pytest.raises(MissionSnapshotConflict, match="STATE_REVISION_CONFLICT"):
        store.save(changed)
