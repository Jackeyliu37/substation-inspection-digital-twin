from __future__ import annotations

import importlib
from pathlib import Path
import sys

import pytest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PACKAGE_ROOT / "substation_gazebo/scenario_catalog.py"
CATALOG_PATH = PACKAGE_ROOT / "config/scenarios.yaml"
ASSET_IDS = {
    "transformer-01",
    "breaker-01",
    "disconnect-switch-01",
    "arrester-01",
    "current-transformer-01",
    "potential-transformer-01",
    "glass-insulator-01",
    "porcelain-insulator-01",
    "meter-pressure-01",
    "meter-oil-01",
}


def load_module():
    assert MODULE_PATH.is_file(), "scenario_catalog.py must exist"
    sys.path.insert(0, str(PACKAGE_ROOT))
    return importlib.import_module("substation_gazebo.scenario_catalog")


def load_catalog(module):
    assert CATALOG_PATH.is_file(), "scenarios.yaml must exist"
    return module.ScenarioCatalog.load(CATALOG_PATH, allowed_asset_ids=ASSET_IDS)


def test_catalog_has_exact_scenario_ids() -> None:
    module = load_module()
    catalog = load_catalog(module)
    assert set(catalog.scenario_ids) == {
        "normal",
        "ppe",
        "fire-smoke",
        "temperature-high",
        "gas-high",
        "meter-limit",
        "unreachable",
        "combined-risk-obstacle",
    }


def test_valid_temperature_command_is_canonicalized() -> None:
    module = load_module()
    catalog = load_catalog(module)
    command = module.Command.from_parameters(
        command_id="4ce58f68-1fcc-45e5-9834-1e3c674c57a8",
        scenario_id="temperature-high",
        action="trigger",
        parameters_json='{"asset_id":"transformer-01","temperature_celsius":90.0}',
    )
    catalog.validate(command)
    assert command.canonical_payload.endswith(
        '"parameters":{"asset_id":"transformer-01","temperature_celsius":90.0},'
        '"scenario_id":"temperature-high"}'
    )


@pytest.mark.parametrize(
    ("scenario_id", "parameters_json", "reason"),
    [
        ("unknown", "{}", "SCENARIO_NOT_FOUND"),
        ("temperature-high", '{"asset_id":"transformer-01","nested":{"x":1}}', "SCENARIO_PARAMETERS_INVALID"),
        ("temperature-high", '{"asset_id":"transformer-01","temperature_celsius":500.0}', "SCENARIO_PARAMETER_OUT_OF_RANGE"),
        ("temperature-high", '{"asset_id":"missing-01","temperature_celsius":90.0}', "SCENARIO_PARAMETER_OUT_OF_RANGE"),
        ("temperature-high", '{"asset_id":"transformer-01","gas_ppm":150.0}', "SCENARIO_PARAMETER_NOT_ALLOWED"),
    ],
)
def test_invalid_command_is_rejected(
    scenario_id: str, parameters_json: str, reason: str
) -> None:
    module = load_module()
    catalog = load_catalog(module)
    with pytest.raises(module.ScenarioError, match=reason):
        command = module.Command.from_parameters(
            command_id="4ce58f68-1fcc-45e5-9834-1e3c674c57a8",
            scenario_id=scenario_id,
            action="trigger",
            parameters_json=parameters_json,
        )
        catalog.validate(command)


def test_command_rejects_bad_uuid_action_and_noncanonical_json() -> None:
    module = load_module()
    with pytest.raises(module.ScenarioError, match="COMMAND_ID_INVALID"):
        module.Command.from_parameters("bad", "normal", "trigger", "{}")
    with pytest.raises(module.ScenarioError, match="SCENARIO_ACTION_INVALID"):
        module.Command.from_parameters(
            "4ce58f68-1fcc-45e5-9834-1e3c674c57a8", "normal", "enable", "{}"
        )
    with pytest.raises(module.ScenarioError, match="SCENARIO_PARAMETERS_INVALID"):
        module.Command.from_parameters(
            "4ce58f68-1fcc-45e5-9834-1e3c674c57a8",
            "normal",
            "trigger",
            '{"z":1, "a":2}',
        )
