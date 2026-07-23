from __future__ import annotations

from pathlib import Path

from substation_gazebo.meter_dataset_plan import load_generation_config
from substation_gazebo.meter_dataset_scene import SceneState, scene_commands


ROOT = Path(__file__).resolve().parents[4]
CONFIG = ROOT / "configs/meter_dataset_generation.yaml"
DEVICES = ROOT / "configs/devices.yaml"


def test_scene_commands_only_hide_previously_visible_models() -> None:
    config = load_generation_config(CONFIG, DEVICES)
    first = config.samples[0]
    first_commands, state = scene_commands(first, SceneState())
    assert [name for name, _pose in first_commands] == [
        "background_industrial_light",
        "synthetic_meter_oil",
    ]

    repeat_commands, repeat_state = scene_commands(config.samples[1], state)
    assert [name for name, _pose in repeat_commands] == [
        "background_industrial_light",
        "synthetic_meter_oil",
    ]
    assert repeat_state == state

    pressure = next(
        sample for sample in config.samples if sample.asset_id == "meter-pressure-01"
    )
    switched_commands, switched_state = scene_commands(pressure, repeat_state)
    names = [name for name, _pose in switched_commands]
    assert names[:2] == ["synthetic_meter_oil", "background_industrial_light"]
    assert names[-2:] == ["background_industrial_dark", "synthetic_meter_pressure"]
    assert switched_state.active_meter == "synthetic_meter_pressure"
