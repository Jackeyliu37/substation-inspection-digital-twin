from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum
import math
from pathlib import Path
from typing import Mapping

import yaml


class RiskLevel(IntEnum):
    NORMAL = 0
    ATTENTION = 1
    ALERT = 2
    EMERGENCY = 3


class AlertEvent(IntEnum):
    OPENED = 0
    LEVEL_CHANGED = 1
    CLEARED = 2


@dataclass(frozen=True)
class RiskPolicy:
    visual_weight: float
    temperature_weight: float
    smoke_weight: float
    gas_weight: float
    context_weight: float
    confirmation_frames: int
    recovery_frames: int
    moving_average_window: int

    def __post_init__(self) -> None:
        weights = (self.visual_weight, self.temperature_weight, self.smoke_weight,
                   self.gas_weight, self.context_weight)
        if not all(math.isfinite(value) and value >= 0.0 for value in weights):
            raise ValueError("RISK_WEIGHT_INVALID")
        if not math.isclose(sum(weights), 1.0, abs_tol=1e-9):
            raise ValueError("RISK_WEIGHT_SUM_INVALID")
        if min(self.confirmation_frames, self.recovery_frames, self.moving_average_window) < 1:
            raise ValueError("RISK_FRAME_POLICY_INVALID")


@dataclass
class _AssetRiskState:
    scores: deque[float]
    confirmation_frames: int = 0
    recovery_frames: int = 0
    level: RiskLevel = RiskLevel.NORMAL
    alert_open: bool = False


@dataclass(frozen=True)
class RiskObservation:
    asset_id: str
    score_0_100: float
    level: RiskLevel
    confirmation_frames: int
    alert_event: AlertEvent | None
    stamp_ns: int


def load_risk_policy(path: Path) -> RiskPolicy:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("RISK_POLICY_SCHEMA_INVALID")
    weights = data.get("weights")
    if not isinstance(weights, dict) or set(weights) != {"visual", "temperature", "smoke", "gas", "context"}:
        raise ValueError("RISK_POLICY_WEIGHTS_INVALID")
    return RiskPolicy(
        visual_weight=float(weights["visual"]), temperature_weight=float(weights["temperature"]),
        smoke_weight=float(weights["smoke"]), gas_weight=float(weights["gas"]),
        context_weight=float(weights["context"]), confirmation_frames=int(data["confirmation_frames"]),
        recovery_frames=int(data["recovery_frames"]), moving_average_window=int(data["moving_average_window"]),
    )


def _level(score_0_100: float) -> RiskLevel:
    if score_0_100 < 30.0:
        return RiskLevel.NORMAL
    if score_0_100 < 60.0:
        return RiskLevel.ATTENTION
    if score_0_100 < 80.0:
        return RiskLevel.ALERT
    return RiskLevel.EMERGENCY


class RiskEngine:
    """Confirmation, average and hysteresis owner; it has no scenario-truth input."""

    def __init__(self, policy: RiskPolicy) -> None:
        self._policy = policy
        self._states: dict[str, _AssetRiskState] = {}

    def observe(self, asset_id: str, components: Mapping[str, float], *, stamp_ns: int) -> RiskObservation:
        if not asset_id or stamp_ns < 0:
            raise ValueError("RISK_OBSERVATION_INVALID")
        if set(components) != {"visual", "temperature", "smoke", "gas", "context"}:
            raise ValueError("RISK_COMPONENTS_INVALID")
        values = {name: float(value) for name, value in components.items()}
        if not all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in values.values()):
            raise ValueError("RISK_COMPONENT_RANGE_INVALID")
        score = 100.0 * (
            self._policy.visual_weight * values["visual"] +
            self._policy.temperature_weight * values["temperature"] +
            self._policy.smoke_weight * values["smoke"] +
            self._policy.gas_weight * values["gas"] +
            self._policy.context_weight * values["context"]
        )
        state = self._states.setdefault(asset_id, _AssetRiskState(deque(maxlen=self._policy.moving_average_window)))
        state.scores.append(score)
        average = sum(state.scores) / len(state.scores)
        raw_level = _level(average)
        event = None
        if raw_level >= RiskLevel.ALERT:
            state.confirmation_frames += 1
            state.recovery_frames = 0
            if state.confirmation_frames >= self._policy.confirmation_frames:
                if not state.alert_open:
                    state.alert_open = True
                    state.level = raw_level
                    event = AlertEvent.OPENED
                elif raw_level != state.level:
                    state.level = raw_level
                    event = AlertEvent.LEVEL_CHANGED
        else:
            state.confirmation_frames = 0
            if state.alert_open:
                state.recovery_frames += 1
                if state.recovery_frames >= self._policy.recovery_frames:
                    state.alert_open = False
                    state.level = raw_level
                    event = AlertEvent.CLEARED
            else:
                state.level = raw_level
        return RiskObservation(asset_id, average, state.level, state.confirmation_frames, event, stamp_ns)
