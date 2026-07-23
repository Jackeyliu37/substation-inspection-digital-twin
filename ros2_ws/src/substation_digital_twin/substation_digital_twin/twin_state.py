from __future__ import annotations

from dataclasses import dataclass
import math


FORBIDDEN_SOURCES = frozenset({"scenario_truth", "placeholder_perception"})


class ObservationError(ValueError):
    """Raised when an observation violates the digital-twin input boundary."""


@dataclass(frozen=True)
class AssetState:
    asset_id: str
    visual_0_1: float
    temperature_0_1: float
    smoke_0_1: float
    gas_0_1: float
    context_0_1: float
    stamp_ns: int
    source: str


@dataclass(frozen=True)
class TwinSnapshot:
    revision: int
    assets: tuple[AssetState, ...]


class DigitalTwin:
    """Owns semantic asset observations and rejects test-only truth channels."""

    def __init__(self, asset_ids: tuple[str, ...]) -> None:
        if len(asset_ids) != len(set(asset_ids)) or not asset_ids:
            raise ValueError("ASSET_REGISTRY_INVALID")
        self._asset_ids = frozenset(asset_ids)
        self._assets: dict[str, AssetState] = {}
        self._revision = 0

    def apply_observation(
        self,
        *,
        asset_id: str,
        source: str,
        visual_0_1: float,
        temperature_0_1: float,
        smoke_0_1: float,
        gas_0_1: float,
        context_0_1: float,
        stamp_ns: int,
    ) -> TwinSnapshot:
        if source in FORBIDDEN_SOURCES:
            raise ObservationError("FORBIDDEN_OBSERVATION_SOURCE")
        if asset_id not in self._asset_ids:
            raise ObservationError("ASSET_NOT_FOUND")
        values = (visual_0_1, temperature_0_1, smoke_0_1, gas_0_1, context_0_1)
        if not all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in values):
            raise ObservationError("OBSERVATION_RANGE_INVALID")
        if stamp_ns < 0:
            raise ObservationError("OBSERVATION_TIME_INVALID")
        previous = self._assets.get(asset_id)
        if previous is not None and stamp_ns < previous.stamp_ns:
            raise ObservationError("OBSERVATION_TIME_REGRESSION")
        self._assets[asset_id] = AssetState(
            asset_id, visual_0_1, temperature_0_1, smoke_0_1, gas_0_1,
            context_0_1, stamp_ns, source,
        )
        self._revision += 1
        return self.snapshot()

    def snapshot(self) -> TwinSnapshot:
        return TwinSnapshot(self._revision, tuple(
            self._assets[asset_id] for asset_id in sorted(self._assets)
        ))
