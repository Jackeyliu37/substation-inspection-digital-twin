from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import math
from pathlib import Path, PurePosixPath
import random
from types import MappingProxyType
from typing import Mapping

import yaml

from substation_description.asset_registry import load_asset_registry


NEEDLE_MIN = -2.35619449019
NEEDLE_MAX = 2.35619449019
SPLITS = ("train", "val", "test")


class MeterDatasetError(ValueError):
    pass


def _fail(code: str, detail: str) -> None:
    raise MeterDatasetError(f"{code}: {detail}")


def _finite(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("NUMBER_INVALID", field)
    result = float(value)
    if not math.isfinite(result):
        _fail("NUMBER_NOT_FINITE", field)
    return result


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        _fail("INTEGER_INVALID", field)
    return value


def _string_list(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        _fail("LIST_INVALID", field)
    return tuple(value)


def _number_list(value: object, field: str) -> tuple[float, ...]:
    if not isinstance(value, list) or not value:
        _fail("LIST_INVALID", field)
    return tuple(_finite(item, field) for item in value)


@dataclass(frozen=True)
class MeterContract:
    asset_id: str
    sensor_id: str
    minimum: float
    maximum: float
    unit: str


@dataclass(frozen=True)
class SamplePlan:
    sample_id: str
    split: str
    scene_group_id: str
    sample_index: int
    seed: int
    asset_id: str
    reading: float
    normalized_reading: float
    needle_angle_radians: float
    distance_m: float
    yaw_radians: float
    pitch_radians: float
    roll_radians: float
    light_family: str
    background_family: str
    occlusion_regime: str
    brightness_scale: float
    blur_sigma: float
    image_path: str
    label_path: str


@dataclass(frozen=True)
class GenerationConfig:
    schema_version: int
    dataset_id: str
    scenario_id: str
    global_seed: int
    width: int
    height: int
    image_format: str
    class_names: Mapping[int, str]
    frames_per_group: int
    groups_per_meter: Mapping[str, int]
    meter_asset_ids: tuple[str, ...]
    meters: Mapping[str, MeterContract]
    minimum_bbox_pixels: int
    maximum_retries_per_sample: int
    fresh_frames_after_command: int
    distances_m: tuple[float, ...]
    yaw_radians: tuple[float, ...]
    pitch_radians: tuple[float, ...]
    roll_radians: tuple[float, ...]
    light_families: tuple[str, ...]
    background_families: tuple[str, ...]
    occlusion_regimes: tuple[str, ...]
    brightness_scales: tuple[float, ...]
    blur_sigmas: tuple[float, ...]
    samples: tuple[SamplePlan, ...] = ()


def load_generation_config(config_path: Path, registry_path: Path) -> GenerationConfig:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        _fail("CONFIG_SCHEMA_INVALID", str(config_path))
    image = raw.get("image")
    groups = raw.get("groups_per_meter")
    views = raw.get("view_families")
    postprocess = raw.get("postprocess")
    if not all(isinstance(item, dict) for item in (image, groups, views, postprocess)):
        _fail("CONFIG_SECTION_INVALID", str(config_path))
    class_names_raw = raw.get("class_names")
    if class_names_raw != {0: "meter"}:
        _fail("CLASS_NAMES_INVALID", repr(class_names_raw))

    registry = load_asset_registry(registry_path)
    registered = {asset.asset_id: asset for asset in registry.assets}
    meter_asset_ids = _string_list(raw.get("meter_asset_ids"), "meter_asset_ids")
    meters: dict[str, MeterContract] = {}
    for asset_id in meter_asset_ids:
        asset = registered.get(asset_id)
        if asset is None or asset.category != "analog_meter" or asset.meter is None:
            _fail("METER_ASSET_UNKNOWN", asset_id)
        meter = asset.meter
        meters[asset_id] = MeterContract(
            asset_id=asset_id,
            sensor_id=str(meter["sensor_id"]),
            minimum=_finite(meter["minimum"], f"{asset_id}.minimum"),
            maximum=_finite(meter["maximum"], f"{asset_id}.maximum"),
            unit=str(meter["unit"]),
        )
        if meters[asset_id].maximum <= meters[asset_id].minimum:
            _fail("METER_RANGE_INVALID", asset_id)

    groups_parsed = {split: _positive_int(groups.get(split), f"groups_per_meter.{split}") for split in SPLITS}
    config = GenerationConfig(
        schema_version=1,
        dataset_id=str(raw.get("dataset_id")),
        scenario_id=str(raw.get("scenario_id")),
        global_seed=int(raw.get("global_seed")),
        width=_positive_int(image.get("width"), "image.width"),
        height=_positive_int(image.get("height"), "image.height"),
        image_format=str(image.get("format")),
        class_names=MappingProxyType({0: "meter"}),
        frames_per_group=_positive_int(raw.get("frames_per_group"), "frames_per_group"),
        groups_per_meter=MappingProxyType(groups_parsed),
        meter_asset_ids=meter_asset_ids,
        meters=MappingProxyType(meters),
        minimum_bbox_pixels=_positive_int(raw.get("minimum_bbox_pixels"), "minimum_bbox_pixels"),
        maximum_retries_per_sample=_positive_int(raw.get("maximum_retries_per_sample"), "maximum_retries_per_sample"),
        fresh_frames_after_command=_positive_int(raw.get("fresh_frames_after_command"), "fresh_frames_after_command"),
        distances_m=_number_list(views.get("distances_m"), "view_families.distances_m"),
        yaw_radians=tuple(math.radians(value) for value in _number_list(views.get("yaw_degrees"), "view_families.yaw_degrees")),
        pitch_radians=tuple(math.radians(value) for value in _number_list(views.get("pitch_degrees"), "view_families.pitch_degrees")),
        roll_radians=tuple(math.radians(value) for value in _number_list(views.get("roll_degrees"), "view_families.roll_degrees")),
        light_families=_string_list(raw.get("light_families"), "light_families"),
        background_families=_string_list(raw.get("background_families"), "background_families"),
        occlusion_regimes=_string_list(raw.get("occlusion_regimes"), "occlusion_regimes"),
        brightness_scales=_number_list(postprocess.get("brightness_scales"), "postprocess.brightness_scales"),
        blur_sigmas=_number_list(postprocess.get("blur_sigmas"), "postprocess.blur_sigmas"),
    )
    samples = build_sample_plan(config)
    return replace(config, samples=samples)


def _choice(values: tuple, index: int, stride: int = 1):
    return values[(index * stride) % len(values)]


def _seed(global_seed: int, group_id: str, frame_index: int) -> int:
    payload = f"{global_seed}:{group_id}:{frame_index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _safe_relative(path: str) -> None:
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or ".." in parsed.parts or "\\" in path or "//" in path:
        _fail("PATH_UNSAFE", path)


def build_sample_plan(config: GenerationConfig) -> tuple[SamplePlan, ...]:
    for collection_name, values in (
        ("distances_m", config.distances_m),
        ("yaw_radians", config.yaw_radians),
        ("pitch_radians", config.pitch_radians),
        ("roll_radians", config.roll_radians),
        ("brightness_scales", config.brightness_scales),
        ("blur_sigmas", config.blur_sigmas),
    ):
        if not values:
            _fail("LIST_INVALID", collection_name)
        for value in values:
            _finite(value, collection_name)
    for asset_id in config.meter_asset_ids:
        if asset_id not in config.meters:
            _fail("METER_ASSET_UNKNOWN", asset_id)

    result: list[SamplePlan] = []
    used_seeds: set[int] = set()
    sample_index = 0
    split_offsets = {"train": 0, "val": 1000, "test": 2000}
    for split in SPLITS:
        groups_for_split = config.groups_per_meter[split]
        for asset_position, asset_id in enumerate(config.meter_asset_ids):
            meter = config.meters[asset_id]
            for group_index in range(groups_for_split):
                family_index = split_offsets[split] + asset_position * 200 + group_index
                group_id = f"{asset_id}-{split}-g{group_index:02d}"
                base_distance = _choice(config.distances_m, family_index, 1)
                base_yaw = _choice(config.yaw_radians, family_index, 2)
                base_pitch = _choice(config.pitch_radians, family_index, 3)
                base_roll = _choice(config.roll_radians, family_index, 4)
                light = _choice(config.light_families, family_index, 2)
                background = _choice(config.background_families, family_index, 2)
                occlusion = _choice(config.occlusion_regimes, family_index, 3)
                for frame_index in range(config.frames_per_group):
                    seed = _seed(config.global_seed, group_id, frame_index)
                    if seed in used_seeds:
                        _fail("SEED_DUPLICATE", str(seed))
                    used_seeds.add(seed)
                    rng = random.Random(seed)
                    normalized = frame_index / (config.frames_per_group - 1)
                    reading = meter.minimum + normalized * (meter.maximum - meter.minimum)
                    sample_id = f"{asset_id}-{split}-g{group_index:02d}-f{frame_index:02d}"
                    image_path = f"images/{split}/{sample_id}.png"
                    label_path = f"labels/{split}/{sample_id}.txt"
                    _safe_relative(image_path)
                    _safe_relative(label_path)
                    result.append(
                        SamplePlan(
                            sample_id=sample_id,
                            split=split,
                            scene_group_id=group_id,
                            sample_index=sample_index,
                            seed=seed,
                            asset_id=asset_id,
                            reading=reading,
                            normalized_reading=normalized,
                            needle_angle_radians=NEEDLE_MIN + normalized * (NEEDLE_MAX - NEEDLE_MIN),
                            distance_m=base_distance + rng.uniform(-0.025, 0.025),
                            yaw_radians=base_yaw + rng.uniform(-0.02, 0.02),
                            pitch_radians=base_pitch + rng.uniform(-0.02, 0.02),
                            roll_radians=base_roll + rng.uniform(-0.015, 0.015),
                            light_family=light,
                            background_family=background,
                            occlusion_regime=occlusion,
                            brightness_scale=_choice(config.brightness_scales, frame_index + family_index, 1),
                            blur_sigma=_choice(config.blur_sigmas, frame_index + family_index, 3),
                            image_path=image_path,
                            label_path=label_path,
                        )
                    )
                    sample_index += 1
    return tuple(result)
