from __future__ import annotations

import io
import hashlib
import json
import zipfile

from substation_reporting.report_generator import ReportGenerator


def test_report_contains_traceability_and_risk_driven_task_change() -> None:
    snapshot = {
        "run_id": "4bdc2f5a-3a77-4a0e-ae28-bcd54063055a",
        "generated_at": "2026-07-23T19:10:00.000000Z",
        "git_commit": "a" * 40,
        "model_versions": {"safety": "development-placeholder"},
        "dataset_versions": {"meter": "a1532e097446"},
        "assets": [{"asset_id": "transformer-01", "risk": 82.5, "level": "emergency"}],
        "alerts": [{"asset_id": "transformer-01", "code": "HIGH_TEMPERATURE"}],
        "tasks": [{"asset_id": "transformer-01", "reason": "risk_replan", "priority": 92.0}],
        "trajectory": [{"x_m": 1.0, "y_m": 2.0}],
        "mission": {
            "mission_id": "0dad1253-4d5d-4930-a47f-251963527980",
            "state": "succeeded",
        },
        "model_manifest_yaml": "schema_version: 1\nrequired_logical_models: [safety]\n",
        "rosbag_metadata_yaml": "rosbag2_bagfile_information:\n  version: 9\n  duration:\n    nanoseconds: 300000000000\n",
        "evidence_ids": ["e0456194-f3bc-4a9a-87c3-a33b3d8a50d2"],
    }

    artifacts = ReportGenerator().generate(snapshot)

    html = artifacts.html.decode("utf-8")
    assert "transformer-01" in html
    assert "risk_replan" in html
    assert "development-placeholder" in html
    assert artifacts.pdf.startswith(b"%PDF-1.4")
    with zipfile.ZipFile(io.BytesIO(artifacts.evidence_zip)) as archive:
        assert sorted(archive.namelist()) == [
            "SHA256SUMS",
            "manifest.json",
            "report.html",
            "report.pdf",
            "rosbag2/metadata.yaml",
            "snapshots/alerts.json",
            "snapshots/mission.json",
            "snapshots/model-manifest.yaml",
            "snapshots/trajectory.json",
        ]
        manifest = json.loads(archive.read("manifest.json"))
        checksum_lines = archive.read("SHA256SUMS").decode("ascii").splitlines()
        assert len(checksum_lines) == 8
        for line in checksum_lines:
            digest, name = line.split("  ", 1)
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest
    assert manifest["run_id"] == snapshot["run_id"]
    assert manifest["evidence_ids"] == snapshot["evidence_ids"]
    assert manifest["bundle_entries"] == [
        "report.html",
        "report.pdf",
        "rosbag2/metadata.yaml",
        "snapshots/alerts.json",
        "snapshots/mission.json",
        "snapshots/model-manifest.yaml",
        "snapshots/trajectory.json",
    ]


def test_report_rejects_missing_traceability_fields() -> None:
    generator = ReportGenerator()
    try:
        generator.generate({"run_id": "missing-fields"})
    except ValueError as exc:
        assert str(exc) == "REPORT_INPUT_INVALID"
    else:
        raise AssertionError("invalid report input was accepted")
