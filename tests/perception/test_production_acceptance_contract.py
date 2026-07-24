from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tests/perception/run_production_acceptance.sh"
PROBE = ROOT / "tests/perception/probe_production_pipeline.py"
CAPTURE = ROOT / "scripts/reporting/run_evidence_capture.sh"


def test_runner_locks_duration_fps_evidence_and_manual_web_boundary() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    for required in (
        "duration_s=300",
        "fps_threshold=15",
        "09-production-integration.staging",
        "models/manifest.yaml",
        "scripts/reporting/run_evidence_capture.sh",
        "scripts/reporting/verify_report_bundle.py",
        "meter-evaluation.json",
        "release-SHA256SUMS",
        "systemctl is-active",
        "SHA256SUMS",
        "mv --",
    ):
        assert required in source
    assert "playwright" not in source.lower()
    assert "screenshot" not in source.lower()


def test_runner_requires_all_four_models_and_cleans_owned_processes() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    for model in (
        "yolo11n_safety",
        "yolo11n_equipment",
        "yolo11n_fault",
        "meter_locator",
    ):
        assert model in source
    assert "trap cleanup" in source
    assert "kill -TERM" in source
    assert "residual" in source


def test_runner_validates_the_live_active_run_not_bootstrap_environment() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert "SUBSTATION_RUN_ID" not in source
    assert "/api/v1/system/status" in source
    assert 'lifecycle != "active"' in source


def test_runner_reports_the_exact_preflight_failure_instead_of_exiting_silently() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert "production-acceptance: FAIL:" in source
    assert "evidence staging directory is not empty" in source
    assert "meter evaluation source is missing" in source
    assert "rosbag target already exists" in source


def test_probe_contract_covers_real_frames_modules_and_safety_barriers() -> None:
    source = PROBE.read_text(encoding="utf-8")

    for required in (
        "/camera/image_raw",
        "/perception/annotated_image",
        "/perception/safety/detections",
        "/perception/equipment/detections",
        "/perception/defects/detections",
        "/perception/meters/readings",
        "/mission/emergency_stop",
        "/mission/emergency_stop_reset",
        "MOTION_SAFETY_BARRIER_PENDING",
        "camera_frame_sha256",
        "zero_velocity_duration_s",
    ):
        assert required in source


def test_rosbag_capture_bootstraps_ros_before_invoking_ros2() -> None:
    source = CAPTURE.read_text(encoding="utf-8")

    assert "source /opt/ros/jazzy/setup.bash" in source
    assert source.index("source /opt/ros/jazzy/setup.bash") < source.index("ros2 bag record")


def _probe_module():
    spec = importlib.util.spec_from_file_location("production_probe", PROBE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_fps_gate_uses_measured_duration_and_rejects_below_threshold() -> None:
    module = _probe_module()

    assert module.measured_fps(4500, 300.0) == 15.0
    module.require_fps(4500, 300.0, 15.0)
    with pytest.raises(RuntimeError, match="PRODUCTION_FPS_BELOW_THRESHOLD"):
        module.require_fps(4499, 300.0, 15.0)


def test_production_probe_does_not_overwrite_rclpy_node_context_property() -> None:
    module = _probe_module()
    module.rclpy.init()
    node = None
    try:
        node = module.ProductionProbe("1c8b12d5-bc53-441d-9e90-006fb1754676")
        assert node.run_context is None
    finally:
        if node is not None:
            node.destroy_node()
        module.rclpy.shutdown()
