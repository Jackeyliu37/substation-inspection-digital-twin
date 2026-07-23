from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping

import yaml


ASSET_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CANONICAL_CATEGORIES = frozenset(
    {
        "open_blade_disconnect_switch",
        "closed_blade_disconnect_switch",
        "open_tandem_disconnect_switch",
        "closed_tandem_disconnect_switch",
        "breaker",
        "fuse_disconnect_switch",
        "glass_disc_insulator",
        "porcelain_pin_insulator",
        "muffle",
        "lightning_arrester",
        "recloser",
        "power_transformer",
        "current_transformer",
        "potential_transformer",
        "tripolar_disconnect_switch",
        "analog_meter",
    }
)
THRESHOLD_NAMES = ("temperature_celsius", "smoke_0_1", "gas_ppm")


class RegistryError(ValueError):
    """Asset registry schema or semantic validation failure."""


@dataclass(frozen=True)
class Pose:
    x: float
    y: float
    z: float
    roll: float
    pitch: float
    yaw: float


@dataclass(frozen=True)
class Asset:
    asset_id: str
    category: str
    report_name: str
    pose: Pose
    inspection_x: float
    inspection_y: float
    inspection_yaw: float
    thresholds: Mapping[str, Mapping[str, float]]
    meter: Mapping[str, object] | None


@dataclass(frozen=True)
class AssetRegistry:
    schema_version: int
    assets: tuple[Asset, ...]


def _fail(reason: str, detail: str) -> None:
    raise RegistryError(f"{reason}: {detail}")


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        _fail("FIELD_TYPE_INVALID", field)
    return value


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("FIELD_TYPE_INVALID", field)
    result = float(value)
    if not math.isfinite(result):
        _fail("NUMBER_NOT_FINITE", field)
    return result


def _exact_keys(value: Mapping[str, Any], expected: set[str], field: str) -> None:
    if set(value) != expected:
        _fail("FIELD_KEYS_INVALID", field)


def _parse_pose(value: Any, field: str) -> Pose:
    data = _mapping(value, field)
    _exact_keys(data, {"x", "y", "z", "roll", "pitch", "yaw"}, field)
    return Pose(**{name: _finite(data[name], f"{field}.{name}") for name in data})


def _parse_thresholds(value: Any, asset_id: str) -> Mapping[str, Mapping[str, float]]:
    data = _mapping(value, f"{asset_id}.thresholds")
    _exact_keys(data, set(THRESHOLD_NAMES), f"{asset_id}.thresholds")
    result: dict[str, Mapping[str, float]] = {}
    for name in THRESHOLD_NAMES:
        pair = _mapping(data[name], f"{asset_id}.thresholds.{name}")
        _exact_keys(pair, {"warning", "critical"}, f"{asset_id}.thresholds.{name}")
        warning = _finite(pair["warning"], f"{asset_id}.{name}.warning")
        critical = _finite(pair["critical"], f"{asset_id}.{name}.critical")
        if warning >= critical:
            _fail("THRESHOLD_ORDER_INVALID", f"{asset_id}.{name}")
        result[name] = MappingProxyType({"warning": warning, "critical": critical})
    return MappingProxyType(result)


def _parse_meter(value: Any, asset_id: str) -> Mapping[str, object]:
    data = _mapping(value, f"{asset_id}.meter")
    _exact_keys(
        data,
        {"sensor_id", "minimum", "maximum", "unit", "normal_minimum", "normal_maximum"},
        f"{asset_id}.meter",
    )
    sensor_id = data["sensor_id"]
    unit = data["unit"]
    if not isinstance(sensor_id, str) or not ASSET_ID_PATTERN.fullmatch(sensor_id):
        _fail("METER_SENSOR_ID_INVALID", asset_id)
    if not isinstance(unit, str) or not unit or len(unit) > 16:
        _fail("METER_UNIT_INVALID", asset_id)
    minimum = _finite(data["minimum"], f"{asset_id}.meter.minimum")
    maximum = _finite(data["maximum"], f"{asset_id}.meter.maximum")
    normal_minimum = _finite(data["normal_minimum"], f"{asset_id}.meter.normal_minimum")
    normal_maximum = _finite(data["normal_maximum"], f"{asset_id}.meter.normal_maximum")
    if not minimum < normal_minimum < normal_maximum < maximum:
        _fail("METER_RANGE_INVALID", asset_id)
    return MappingProxyType(
        {
            "sensor_id": sensor_id,
            "minimum": minimum,
            "maximum": maximum,
            "unit": unit,
            "normal_minimum": normal_minimum,
            "normal_maximum": normal_maximum,
        }
    )


def _parse_asset(value: Any) -> Asset:
    data = _mapping(value, "asset")
    common = {"asset_id", "category", "report_name", "pose", "inspection_pose", "thresholds"}
    if not common.issubset(data) or set(data) - common - {"meter"}:
        _fail("ASSET_FIELDS_INVALID", repr(sorted(data)))
    asset_id = data["asset_id"]
    if not isinstance(asset_id, str) or not ASSET_ID_PATTERN.fullmatch(asset_id):
        _fail("ASSET_ID_INVALID", repr(asset_id))
    category = data["category"]
    if category not in CANONICAL_CATEGORIES:
        _fail("ASSET_CATEGORY_INVALID", f"{asset_id}:{category}")
    report_name = data["report_name"]
    if not isinstance(report_name, str) or not report_name.strip():
        _fail("REPORT_NAME_INVALID", asset_id)
    pose = _parse_pose(data["pose"], f"{asset_id}.pose")
    inspection = _mapping(data["inspection_pose"], f"{asset_id}.inspection_pose")
    _exact_keys(inspection, {"x", "y", "yaw"}, f"{asset_id}.inspection_pose")
    inspection_x = _finite(inspection["x"], f"{asset_id}.inspection_pose.x")
    inspection_y = _finite(inspection["y"], f"{asset_id}.inspection_pose.y")
    inspection_yaw = _finite(inspection["yaw"], f"{asset_id}.inspection_pose.yaw")
    if not (-7.7 <= inspection_x <= 7.7 and -5.7 <= inspection_y <= 5.7):
        _fail("INSPECTION_POSE_OUTSIDE_YARD", asset_id)
    if 3.8 <= inspection_x <= 6.2 and 1.8 <= inspection_y <= 4.2:
        _fail("INSPECTION_POSE_IN_EXCLUSION_ZONE", asset_id)
    meter = None
    if category == "analog_meter":
        if "meter" not in data:
            _fail("METER_CONTRACT_REQUIRED", asset_id)
        meter = _parse_meter(data["meter"], asset_id)
    elif "meter" in data:
        _fail("METER_CONTRACT_UNEXPECTED", asset_id)
    return Asset(
        asset_id=asset_id,
        category=category,
        report_name=report_name.strip(),
        pose=pose,
        inspection_x=inspection_x,
        inspection_y=inspection_y,
        inspection_yaw=inspection_yaw,
        thresholds=_parse_thresholds(data["thresholds"], asset_id),
        meter=meter,
    )


def load_asset_registry(path: Path) -> AssetRegistry:
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise RegistryError(f"REGISTRY_READ_FAILED: {path}: {error}") from error
    data = _mapping(raw, "registry")
    _exact_keys(data, {"schema_version", "assets"}, "registry")
    if data["schema_version"] != 1:
        _fail("SCHEMA_VERSION_UNSUPPORTED", repr(data["schema_version"]))
    if not isinstance(data["assets"], list) or not data["assets"]:
        _fail("ASSETS_INVALID", "assets must be a non-empty list")
    assets = tuple(sorted((_parse_asset(value) for value in data["assets"]), key=lambda asset: asset.asset_id))
    ids = [asset.asset_id for asset in assets]
    if len(ids) != len(set(ids)):
        _fail("ASSET_ID_DUPLICATE", repr(ids))
    return AssetRegistry(schema_version=1, assets=assets)

