import ast
from pathlib import Path


LAUNCH = Path(__file__).resolve().parents[1] / "launch/substation_core.launch.py"


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
