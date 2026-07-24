#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import uuid
import zipfile


REQUIRED = {
    "SHA256SUMS",
    "manifest.json",
    "report.html",
    "report.pdf",
    "rosbag2/metadata.yaml",
    "snapshots/alerts.json",
    "snapshots/mission.json",
    "snapshots/model-manifest.yaml",
    "snapshots/trajectory.json",
}


def _safe_name(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts


def verify(bundle: Path, run_id: str) -> None:
    if str(uuid.UUID(run_id)) != run_id:
        raise ValueError("RUN_ID_INVALID")
    with zipfile.ZipFile(bundle) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != REQUIRED:
            raise ValueError("BUNDLE_MEMBERS_INVALID")
        if not all(_safe_name(name) for name in names):
            raise ValueError("BUNDLE_PATH_INVALID")
        bad_member = archive.testzip()
        if bad_member is not None:
            raise ValueError(f"BUNDLE_CRC_INVALID:{bad_member}")

        lines = archive.read("SHA256SUMS").decode("ascii").splitlines()
        expected_names = sorted(REQUIRED - {"SHA256SUMS"})
        if len(lines) != len(expected_names):
            raise ValueError("CHECKSUM_COUNT_INVALID")
        observed_names = []
        for line in lines:
            digest, separator, name = line.partition("  ")
            if separator != "  " or len(digest) != 64:
                raise ValueError("CHECKSUM_FORMAT_INVALID")
            observed_names.append(name)
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError(f"CHECKSUM_MISMATCH:{name}")
        if observed_names != expected_names:
            raise ValueError("CHECKSUM_ORDER_INVALID")

        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("run_id") != run_id:
            raise ValueError("RUN_ID_MISMATCH")
        if manifest.get("bundle_entries") != sorted(
            REQUIRED - {"SHA256SUMS", "manifest.json"}
        ):
            raise ValueError("BUNDLE_INDEX_INVALID")
        if not isinstance(json.loads(archive.read("snapshots/alerts.json")), list):
            raise ValueError("ALERT_SNAPSHOT_INVALID")
        if not isinstance(json.loads(archive.read("snapshots/trajectory.json")), list):
            raise ValueError("TRAJECTORY_SNAPSHOT_INVALID")
        mission = json.loads(archive.read("snapshots/mission.json"))
        if not isinstance(mission, dict) or not mission.get("mission_id"):
            raise ValueError("MISSION_SNAPSHOT_INVALID")
        if b"schema_version:" not in archive.read("snapshots/model-manifest.yaml"):
            raise ValueError("MODEL_MANIFEST_INVALID")
        if b"rosbag2_bagfile_information:" not in archive.read("rosbag2/metadata.yaml"):
            raise ValueError("ROSBAG_METADATA_INVALID")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    try:
        verify(args.bundle.resolve(), args.run_id)
    except Exception as exc:
        print(f"report-bundle: FAIL: {exc}", file=sys.stderr)
        return 1
    print("report-bundle: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
