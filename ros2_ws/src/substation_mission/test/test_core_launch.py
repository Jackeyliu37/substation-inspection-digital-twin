import ast
from pathlib import Path


LAUNCH = Path(__file__).resolve().parents[1] / "launch/substation_core.launch.py"
PACKAGE = LAUNCH.parents[1]
EXECUTOR_LAUNCH = PACKAGE / "launch/inspection_executor.launch.py"


def test_core_launch_wires_environment_twin_risk_and_mission() -> None:
    source = LAUNCH.read_text(encoding="utf-8")
    ast.parse(source)
    for package, executable in (
        ("substation_mission", "task_manager"),
        ("substation_perception", "environment_normalizer"),
        ("substation_digital_twin", "digital_twin"),
        ("substation_risk", "risk"),
    ):
        assert f'package="{package}"' in source
        assert f'executable="{executable}"' in source
    assert '"use_sim_time": True' in source
    assert '"run_id": run_id' in source
    assert "/simulation/scenario_truth" not in source
    assert "/perception/development/" not in source


def test_navigation_executor_has_an_explicit_nav2_launch_boundary() -> None:
    assert EXECUTOR_LAUNCH.is_file()
    source = EXECUTOR_LAUNCH.read_text(encoding="utf-8")
    ast.parse(source)
    assert 'package="substation_mission"' in source
    assert 'executable="inspection_executor"' in source
    assert 'SetEnvironmentVariable("ROS_LOCALHOST_ONLY", "1")' in source

    setup = (PACKAGE / "setup.py").read_text(encoding="utf-8")
    manifest = (PACKAGE / "package.xml").read_text(encoding="utf-8")
    assert "inspection_executor = substation_mission.inspection_executor:main" in setup
    assert '"launch/inspection_executor.launch.py"' in setup
    assert "<exec_depend>action_msgs</exec_depend>" in manifest
    assert "<exec_depend>nav2_msgs</exec_depend>" in manifest
