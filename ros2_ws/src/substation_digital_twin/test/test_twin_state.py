from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
MODULE_PATH = ROOT / "ros2_ws/src/substation_digital_twin/substation_digital_twin/twin_state.py"


def load_module():
    assert MODULE_PATH.is_file(), "twin_state.py must exist"
    spec = importlib.util.spec_from_file_location("twin_state_under_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_twin_normalizes_observation_and_rejects_truth_source() -> None:
    module = load_module()
    twin = module.DigitalTwin(("transformer-01",))
    snapshot = twin.apply_observation(
        asset_id="transformer-01", source="environment_normalizer",
        temperature_0_1=0.9, smoke_0_1=0.2, gas_0_1=0.1, visual_0_1=0.0,
        context_0_1=0.5, stamp_ns=42,
    )
    assert snapshot.assets[0].temperature_0_1 == 0.9
    assert snapshot.revision == 1

    try:
        twin.apply_observation(
            asset_id="transformer-01", source="scenario_truth",
            temperature_0_1=1.0, smoke_0_1=1.0, gas_0_1=1.0, visual_0_1=1.0,
            context_0_1=1.0, stamp_ns=43,
        )
    except module.ObservationError as error:
        assert str(error) == "FORBIDDEN_OBSERVATION_SOURCE"
    else:
        raise AssertionError("scenario truth must never enter twin inference")
