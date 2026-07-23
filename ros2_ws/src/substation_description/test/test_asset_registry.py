from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[4]
MODULE_PATH = (
    ROOT
    / "ros2_ws/src/substation_description/substation_description/asset_registry.py"
)
REGISTRY_PATH = ROOT / "configs/devices.yaml"


def load_module():
    assert MODULE_PATH.is_file(), "asset_registry.py must exist"
    spec = importlib.util.spec_from_file_location("asset_registry_under_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def valid_asset(asset_id: str = "transformer-01") -> dict:
    return {
        "asset_id": asset_id,
        "category": "power_transformer",
        "report_name": "Main Transformer T1",
        "pose": {"x": 5.0, "y": 3.0, "z": 0.0, "roll": 0.0, "pitch": 0.0, "yaw": 0.0},
        "inspection_pose": {"x": 2.8, "y": 3.0, "yaw": 0.0},
        "thresholds": {
            "temperature_celsius": {"warning": 70.0, "critical": 85.0},
            "smoke_0_1": {"warning": 0.25, "critical": 0.6},
            "gas_ppm": {"warning": 100.0, "critical": 200.0},
        },
    }


def write_registry(path: Path, assets: list[dict]) -> None:
    path.write_text(
        yaml.safe_dump({"schema_version": 1, "assets": assets}, sort_keys=False),
        encoding="utf-8",
    )


def test_project_registry_has_required_assets() -> None:
    module = load_module()
    registry = module.load_asset_registry(REGISTRY_PATH)
    assert len(registry.assets) == 10
    assert len({asset.category for asset in registry.assets if asset.category != "analog_meter"}) >= 8
    assert sum(asset.category == "analog_meter" for asset in registry.assets) == 2
    assert [asset.asset_id for asset in registry.assets] == sorted(
        asset.asset_id for asset in registry.assets
    )


@pytest.mark.parametrize(
    ("mutator", "reason"),
    [
        (lambda assets: assets.append(dict(assets[0])), "ASSET_ID_DUPLICATE"),
        (lambda assets: assets[0].update(asset_id="Transformer_01"), "ASSET_ID_INVALID"),
        (
            lambda assets: assets[0]["thresholds"]["gas_ppm"].update(
                warning=math.inf
            ),
            "NUMBER_NOT_FINITE",
        ),
        (
            lambda assets: assets[0]["thresholds"]["gas_ppm"].update(
                warning=250.0, critical=200.0
            ),
            "THRESHOLD_ORDER_INVALID",
        ),
    ],
)
def test_invalid_registry_is_rejected(tmp_path: Path, mutator, reason: str) -> None:
    module = load_module()
    assets = [valid_asset()]
    mutator(assets)
    path = tmp_path / "devices.yaml"
    write_registry(path, assets)
    with pytest.raises(module.RegistryError, match=reason):
        module.load_asset_registry(path)


def test_analog_meter_requires_meter_contract(tmp_path: Path) -> None:
    module = load_module()
    asset = valid_asset("meter-pressure-01")
    asset["category"] = "analog_meter"
    path = tmp_path / "devices.yaml"
    write_registry(path, [asset])
    with pytest.raises(module.RegistryError, match="METER_CONTRACT_REQUIRED"):
        module.load_asset_registry(path)
