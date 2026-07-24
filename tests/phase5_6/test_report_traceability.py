from __future__ import annotations

from pathlib import Path
import subprocess

from substation_reporting.report_generator import ReportGenerator


ROOT = Path(__file__).resolve().parents[2]


def test_capture_script_records_required_run_scoped_topics() -> None:
    source = (ROOT / "scripts/reporting/run_evidence_capture.sh").read_text(
        encoding="utf-8"
    )
    for required in (
        "ros2 bag record",
        "--topics",
        "/system/run_context",
        "/risk/alerts",
        "/mission/inspection_tasks",
        "/odom",
        "/perception/detections",
        "metadata.yaml",
        '"$output_dir/metadata.yaml"',
    ):
        assert required in source


def test_bundle_verifier_rejects_a_non_zip_payload(tmp_path: Path) -> None:
    payload = tmp_path / "evidence.zip"
    payload.write_bytes(b"not a zip")

    completed = subprocess.run(
        [
            "python3",
            str(ROOT / "scripts/reporting/verify_report_bundle.py"),
            "--bundle",
            str(payload),
            "--run-id",
            "4bdc2f5a-3a77-4a0e-ae28-bcd54063055a",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "report-bundle: FAIL" in completed.stderr


def test_bundle_verifier_accepts_complete_terminal_bundle(tmp_path: Path) -> None:
    run_id = "4bdc2f5a-3a77-4a0e-ae28-bcd54063055a"
    bundle = tmp_path / "evidence.zip"
    bundle.write_bytes(ReportGenerator().generate({
        "run_id": run_id,
        "generated_at": "2026-07-24T00:00:00.000000Z",
        "git_commit": "a" * 40,
        "model_versions": {"safety": "sha256"},
        "dataset_versions": {"meter": "synthetic-v1"},
        "assets": [],
        "alerts": [],
        "tasks": [],
        "trajectory": [],
        "mission": {"mission_id": "mission-1", "state": "succeeded"},
        "model_manifest_yaml": "schema_version: 1\n",
        "rosbag_metadata_yaml": (
            "rosbag2_bagfile_information:\n  version: 9\n"
        ),
        "evidence_ids": [],
    }).evidence_zip)

    completed = subprocess.run(
        [
            "python3",
            str(ROOT / "scripts/reporting/verify_report_bundle.py"),
            "--bundle",
            str(bundle),
            "--run-id",
            run_id,
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "report-bundle: PASS"
