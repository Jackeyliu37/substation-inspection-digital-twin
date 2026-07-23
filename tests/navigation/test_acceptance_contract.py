from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys


ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "tests/navigation/run_phase3_acceptance.sh"
PROBE = ROOT / "tests/navigation/probe_phase3_navigation.py"


def load_probe_module():
    gazebo_package = ROOT / "ros2_ws/src/substation_gazebo"
    description_package = ROOT / "ros2_ws/src/substation_description"
    sys.path.insert(0, str(gazebo_package))
    sys.path.insert(0, str(description_package))
    spec = importlib.util.spec_from_file_location("phase3_navigation_probe", PROBE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_acceptance_harness_owns_runtime_and_finalizes_evidence() -> None:
    assert HARNESS.is_file(), "run_phase3_acceptance.sh must exist"
    source = HARNESS.read_text(encoding="utf-8")
    assert "set -euo pipefail" in source
    assert 'partition="phase3-$run_id"' in source
    assert "setsid env -u DISPLAY ROS_LOCALHOST_ONLY=1" in source
    assert 'kill -TERM -- "-$launch_pid"' in source
    assert source.count('kill -0 -- "-$launch_pid"') >= 3
    assert 'launch_group="$launch_pid"' in source
    assert 'kill -0 -- "-$launch_group"' in source
    assert "trap cleanup EXIT INT TERM" in source
    assert "timeout 300s python3 tests/navigation/probe_phase3_navigation.py" in source
    assert '03-navigation.staging' in source
    assert 'sha256sum -c SHA256SUMS' in source
    assert 'mv -- "$evidence_dir" "$final_dir"' in source


def test_probe_uses_nav2_action_tf_and_dynamic_local_costmap() -> None:
    assert PROBE.is_file(), "probe_phase3_navigation.py must exist"
    source = PROBE.read_text(encoding="utf-8")
    ast.parse(source, filename=str(PROBE))
    for token in (
        "NavigateToPose",
        'ActionClient(self, NavigateToPose, "/navigate_to_pose")',
        'Buffer(cache_time=Duration(seconds=30.0))',
        '"map", "odom"',
        'Costmap, "/local_costmap/costmap_raw"',
        "math.isclose(",
        "self.map_message.info.resolution, 0.05",
        '"baseline_state"',
        '"potential-transformer-01"',
        '"current-transformer-01"',
        '"combined-risk-obstacle"',
        '"scenario_dynamic_obstacle"',
        "GoalStatus.STATUS_SUCCEEDED",
        '"/bt_navigator/get_state"',
        "State.PRIMARY_STATE_ACTIVE",
        '"navigation-feedback"',
        '"phase3-navigation-probe: PASS"',
    ):
        assert token in source


def test_probe_finds_lethal_surface_cell_away_from_obstacle_center() -> None:
    module = load_probe_module()
    probe = module.Phase3NavigationProbe.__new__(module.Phase3NavigationProbe)
    transform = SimpleNamespace(
        transform=SimpleNamespace(
            translation=SimpleNamespace(x=0.0, y=0.0),
            rotation=SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0),
        )
    )
    probe.tf_buffer = SimpleNamespace(
        lookup_transform=lambda target, source, stamp: transform
    )
    metadata = SimpleNamespace(
        origin=SimpleNamespace(position=SimpleNamespace(x=0.5, y=-1.0)),
        resolution=0.05,
        size_x=40,
        size_y=40,
    )
    data = [0] * (metadata.size_x * metadata.size_y)
    obstacle_center_column = 20
    obstacle_center_row = 20
    obstacle_surface_row = obstacle_center_row + 8
    data[obstacle_surface_row * metadata.size_x + obstacle_center_column] = 254
    message = SimpleNamespace(
        header=SimpleNamespace(frame_id="odom"), metadata=metadata, data=data
    )

    assert probe.obstacle_cell_is_lethal(message)
