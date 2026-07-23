from __future__ import annotations

from pathlib import Path

from test_scenario_catalog import ASSET_IDS, load_catalog, load_module


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def command(module, command_id: str, scenario_id: str, parameters_json: str):
    return module.Command.from_parameters(
        command_id=command_id,
        scenario_id=scenario_id,
        action="trigger",
        parameters_json=parameters_json,
    )


def test_apply_is_transactional_and_idempotent() -> None:
    module = load_module()
    engine = module.ScenarioEngine(load_catalog(module))
    moved: list[tuple[str, tuple[float, ...]]] = []
    requested = command(
        module,
        "4ce58f68-1fcc-45e5-9834-1e3c674c57a8",
        "temperature-high",
        '{"asset_id":"transformer-01","temperature_celsius":90.0}',
    )
    first = engine.apply(
        requested, lambda name, pose: moved.append((name, pose)) or True
    )
    replay = engine.apply(
        requested,
        lambda name, pose: (_ for _ in ()).throw(AssertionError("must not replay")),
    )
    assert first.status == replay.status == "applied"
    assert first.revision == replay.revision == 1
    assert engine.values["temperature_celsius"] == 90.0


def test_command_id_conflict_is_rejected() -> None:
    module = load_module()
    engine = module.ScenarioEngine(load_catalog(module))
    command_id = "4ce58f68-1fcc-45e5-9834-1e3c674c57a8"
    first = command(
        module,
        command_id,
        "temperature-high",
        '{"asset_id":"transformer-01","temperature_celsius":90.0}',
    )
    engine.apply(first, lambda name, pose: True)
    conflicting = command(
        module,
        command_id,
        "temperature-high",
        '{"asset_id":"transformer-01","temperature_celsius":95.0}',
    )
    result = engine.apply(conflicting, lambda name, pose: True)
    assert result.status == "failed"
    assert result.error_code == "COMMAND_ID_CONFLICT"
    assert engine.revision == 1
    assert engine.values["temperature_celsius"] == 90.0


def test_pose_failure_rolls_back_and_keeps_complete_state() -> None:
    module = load_module()
    engine = module.ScenarioEngine(load_catalog(module))
    requested = command(
        module,
        "e941fc04-d843-49e8-aa90-3ee0a20e8b59",
        "fire-smoke",
        '{"asset_id":"transformer-01","smoke_0_1":0.8}',
    )
    calls: list[str] = []

    def setter(name, pose):
        calls.append(name)
        return name != "scenario_smoke"

    result = engine.apply(requested, setter)
    assert result.status == "failed"
    assert result.error_code == "GAZEBO_SET_POSE_FAILED"
    assert engine.revision == 0
    assert engine.active_scenario == "normal"
    assert engine.values == engine.catalog.nominal_values
    assert calls == ["scenario_fire", "scenario_smoke", "scenario_fire"]


def test_reset_restores_nominal_values_and_hidden_poses() -> None:
    module = load_module()
    engine = module.ScenarioEngine(load_catalog(module))
    active = command(
        module,
        "a8a41620-21de-47f4-9d9d-9daf86eeafc2",
        "gas-high",
        '{"asset_id":"transformer-01","gas_ppm":180.0}',
    )
    engine.apply(active, lambda name, pose: True)
    reset = module.Command.from_parameters(
        "fd367b8b-efcc-4341-be36-b63f19993366", "gas-high", "reset", "{}"
    )
    result = engine.apply(reset, lambda name, pose: True)
    assert result.status == "applied"
    assert result.revision == 2
    assert not result.active
    assert engine.active_scenario == "normal"
    assert engine.values == engine.catalog.nominal_values
