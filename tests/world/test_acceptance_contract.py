from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys

from sensor_msgs.msg import LaserScan


ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "tests/world/run_phase2_acceptance.sh"
PROBE = ROOT / "tests/world/probe_phase2_topics.py"


def load_probe_module():
    spec = importlib.util.spec_from_file_location("phase2_probe_under_test", PROBE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_harness_is_bounded_headless_and_pid_scoped() -> None:
    assert HARNESS.is_file(), "run_phase2_acceptance.sh must exist"
    source = HARNESS.read_text(encoding="utf-8")
    assert "set -euo pipefail" in source
    assert "setsid env -u DISPLAY" in source
    assert "ROS_LOCALHOST_ONLY=1" in source
    assert "GZ_PARTITION" in source
    assert "timeout 120s" in source
    assert 'kill -TERM -- "-$launch_pid"' in source
    assert "trap cleanup EXIT INT TERM" in source
    assert "pkill" not in source
    assert "killall" not in source
    assert "SHA256SUMS" in source
    assert "02-gazebo-world.staging" in source


def test_probe_has_exact_required_topics_and_atomic_service() -> None:
    assert PROBE.is_file(), "probe_phase2_topics.py must exist"
    source = PROBE.read_text(encoding="utf-8")
    ast.parse(source, filename=str(PROBE))
    for topic in (
        "/clock",
        "/camera/image_raw",
        "/camera/camera_info",
        "/scan",
        "/odom",
        "/tf",
        "/tf_static",
        "/simulation/environment/temperature_raw",
        "/simulation/environment/smoke_raw",
        "/simulation/environment/gas_raw",
        "/simulation/scenario_truth",
        "/simulation/scenario_state",
        "/battery_state",
    ):
        assert topic in source
    assert "/scenario_manager/set_parameters_atomically" in source
    assert "camera_optical_frame" in source
    assert "laser_frame" in source
    assert "temperature-high" in source


def test_probe_accepts_float32_scan_contract_boundaries() -> None:
    module = load_probe_module()

    class ProbeState:
        counts = {"/scan": 0}
        scan_valid = False

    message = LaserScan()
    message.header.frame_id = "laser_frame"
    message.ranges = [1.0] * 360
    message.range_min = 0.11999999731779099
    message.range_max = 10.0

    state = ProbeState()
    module.Phase2Probe.on_scan(state, message)
    assert state.scan_valid
