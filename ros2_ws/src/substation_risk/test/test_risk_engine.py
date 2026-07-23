from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
MODULE_PATH = ROOT / "ros2_ws/src/substation_risk/substation_risk/risk_engine.py"


def load_module():
    assert MODULE_PATH.is_file(), "risk_engine.py must exist"
    spec = importlib.util.spec_from_file_location("risk_engine_under_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_risk_requires_continuous_confirmation_before_opening_alert(tmp_path: Path) -> None:
    module = load_module()
    weights = tmp_path / "risk_weights.yaml"
    weights.write_text(
        """schema_version: 1
weights: {visual: 0.30, temperature: 0.25, smoke: 0.20, gas: 0.10, context: 0.15}
confirmation_frames: 3
recovery_frames: 2
moving_average_window: 1
""",
        encoding="utf-8",
    )
    engine = module.RiskEngine(module.load_risk_policy(weights))
    components = {"visual": 1.0, "temperature": 1.0, "smoke": 1.0, "gas": 1.0, "context": 1.0}

    first = engine.observe("transformer-01", components, stamp_ns=1)
    second = engine.observe("transformer-01", components, stamp_ns=2)
    third = engine.observe("transformer-01", components, stamp_ns=3)

    assert first.level == module.RiskLevel.NORMAL
    assert second.level == module.RiskLevel.NORMAL
    assert third.level == module.RiskLevel.EMERGENCY
    assert third.alert_event == module.AlertEvent.OPENED


def test_risk_hysteresis_requires_recovery_frames_before_clear(tmp_path: Path) -> None:
    module = load_module()
    policy = module.RiskPolicy(
        visual_weight=0.30, temperature_weight=0.25, smoke_weight=0.20,
        gas_weight=0.10, context_weight=0.15, confirmation_frames=1,
        recovery_frames=2, moving_average_window=1,
    )
    engine = module.RiskEngine(policy)
    high = {"visual": 1.0, "temperature": 1.0, "smoke": 1.0, "gas": 1.0, "context": 1.0}
    low = {"visual": 0.0, "temperature": 0.0, "smoke": 0.0, "gas": 0.0, "context": 0.0}
    assert engine.observe("transformer-01", high, stamp_ns=1).alert_event == module.AlertEvent.OPENED
    assert engine.observe("transformer-01", low, stamp_ns=2).alert_event is None
    cleared = engine.observe("transformer-01", low, stamp_ns=3)
    assert cleared.level == module.RiskLevel.NORMAL
    assert cleared.alert_event == module.AlertEvent.CLEARED
