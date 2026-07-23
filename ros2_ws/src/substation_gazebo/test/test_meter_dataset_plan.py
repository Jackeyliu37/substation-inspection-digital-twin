from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import replace
import math
from pathlib import Path

import pytest

from substation_gazebo.meter_dataset_plan import (
    MeterDatasetError,
    build_sample_plan,
    load_generation_config,
)


ROOT = Path(__file__).resolve().parents[4]
CONFIG = ROOT / "configs/meter_dataset_generation.yaml"
DEVICES = ROOT / "configs/devices.yaml"


def test_full_plan_is_balanced_group_isolated_and_deterministic() -> None:
    config = load_generation_config(CONFIG, DEVICES)
    first = build_sample_plan(config)
    second = build_sample_plan(config)

    assert first == second
    assert len(first) == 2000
    assert Counter(item.asset_id for item in first) == {
        "meter-pressure-01": 1000,
        "meter-oil-01": 1000,
    }
    assert Counter(item.split for item in first) == {
        "train": 1600,
        "val": 200,
        "test": 200,
    }
    ownership: dict[str, set[str]] = defaultdict(set)
    for item in first:
        ownership[item.scene_group_id].add(item.split)
    assert len(ownership) == 100
    assert all(len(splits) == 1 for splits in ownership.values())


def test_registry_owns_meter_ranges_units_and_sensor_ids() -> None:
    config = load_generation_config(CONFIG, DEVICES)
    assert config.fresh_frames_after_command == 1
    pressure = config.meters["meter-pressure-01"]
    oil = config.meters["meter-oil-01"]
    assert (pressure.minimum, pressure.maximum, pressure.unit) == (0.0, 2.0, "MPa")
    assert pressure.sensor_id == "meter-pressure-sensor-01"
    assert (oil.minimum, oil.maximum, oil.unit) == (0.0, 100.0, "percent")
    assert oil.sensor_id == "meter-oil-sensor-01"


def test_sample_ids_seeds_paths_readings_and_class_are_valid() -> None:
    config = load_generation_config(CONFIG, DEVICES)
    plan = build_sample_plan(config)
    assert config.class_names == {0: "meter"}
    assert len({item.sample_id for item in plan}) == len(plan)
    assert len({item.seed for item in plan}) == len(plan)
    for item in plan:
        meter = config.meters[item.asset_id]
        assert meter.minimum <= item.reading <= meter.maximum
        assert 0.0 <= item.normalized_reading <= 1.0
        assert math.isfinite(item.needle_angle_radians)
        assert item.image_path == f"images/{item.split}/{item.sample_id}.png"
        assert item.label_path == f"labels/{item.split}/{item.sample_id}.txt"
        assert ".." not in item.image_path and "\\" not in item.image_path


def test_unknown_meter_asset_is_rejected() -> None:
    config = load_generation_config(CONFIG, DEVICES)
    invalid = replace(config, meter_asset_ids=("meter-missing-01",))
    with pytest.raises(MeterDatasetError, match="METER_ASSET_UNKNOWN"):
        build_sample_plan(invalid)


def test_nonfinite_view_configuration_is_rejected() -> None:
    config = load_generation_config(CONFIG, DEVICES)
    invalid = replace(config, distances_m=(math.nan,))
    with pytest.raises(MeterDatasetError, match="NUMBER_NOT_FINITE"):
        build_sample_plan(invalid)
