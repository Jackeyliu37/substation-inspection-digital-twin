from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping
from uuid import UUID

import yaml


Pose = tuple[float, float, float, float, float, float]
Scalar = str | int | float | bool
ACTIONS = frozenset({"start", "trigger", "reset"})
EXPECTED_SCENARIOS = frozenset(
    {
        "normal",
        "ppe",
        "fire-smoke",
        "temperature-high",
        "gas-high",
        "meter-limit",
        "unreachable",
        "combined-risk-obstacle",
    }
)


class ScenarioError(ValueError):
    """Stable scenario command or catalog failure."""


def _fail(code: str, detail: str) -> None:
    raise ScenarioError(f"{code}: {detail}")


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise ScenarioError(f"SCENARIO_PARAMETERS_INVALID: {error}") from error


def _is_scalar(value: object) -> bool:
    return isinstance(value, (str, int, float, bool)) and not (
        isinstance(value, float) and not math.isfinite(value)
    )


@dataclass(frozen=True)
class Command:
    command_id: str
    scenario_id: str
    action: str
    parameters: Mapping[str, Scalar]
    canonical_payload: str

    @classmethod
    def from_parameters(
        cls,
        command_id: str,
        scenario_id: str,
        action: str,
        parameters_json: str,
    ) -> "Command":
        try:
            parsed_uuid = UUID(command_id)
        except (ValueError, AttributeError) as error:
            raise ScenarioError(f"COMMAND_ID_INVALID: {command_id!r}") from error
        if str(parsed_uuid) != command_id:
            _fail("COMMAND_ID_INVALID", repr(command_id))
        if action not in ACTIONS:
            _fail("SCENARIO_ACTION_INVALID", repr(action))
        try:
            parameters = json.loads(parameters_json)
        except (json.JSONDecodeError, TypeError) as error:
            raise ScenarioError(f"SCENARIO_PARAMETERS_INVALID: {error}") from error
        if not isinstance(parameters, dict) or any(
            not isinstance(key, str) or not _is_scalar(value)
            for key, value in parameters.items()
        ):
            _fail("SCENARIO_PARAMETERS_INVALID", "parameters must be a scalar object")
        canonical_parameters = _canonical_json(parameters)
        if parameters_json != canonical_parameters:
            _fail("SCENARIO_PARAMETERS_INVALID", "JSON is not canonical")
        payload = _canonical_json(
            {
                "command_id": command_id,
                "scenario_id": scenario_id,
                "action": action,
                "parameters": parameters,
            }
        )
        return cls(
            command_id=command_id,
            scenario_id=scenario_id,
            action=action,
            parameters=MappingProxyType(dict(parameters)),
            canonical_payload=payload,
        )


@dataclass(frozen=True)
class ParameterRule:
    kind: str
    required: bool
    minimum: float | None
    maximum: float | None


@dataclass(frozen=True)
class ScenarioDefinition:
    parameters: Mapping[str, ParameterRule]
    defaults: Mapping[str, Scalar]
    values: Mapping[str, float]
    props: Mapping[str, Pose]


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("CATALOG_INVALID", f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        _fail("CATALOG_INVALID", f"{field} must be finite")
    return result


def _pose(value: Any, field: str) -> Pose:
    if not isinstance(value, list) or len(value) != 6:
        _fail("CATALOG_INVALID", f"{field} must have six values")
    return tuple(_finite_number(item, field) for item in value)  # type: ignore[return-value]


class ScenarioCatalog:
    def __init__(
        self,
        nominal_values: Mapping[str, float],
        hidden_pose: Pose,
        known_props: tuple[str, ...],
        definitions: Mapping[str, ScenarioDefinition],
        allowed_asset_ids: frozenset[str],
    ) -> None:
        self.nominal_values = MappingProxyType(dict(nominal_values))
        self.hidden_pose = hidden_pose
        self.known_props = known_props
        self.definitions = MappingProxyType(dict(definitions))
        self.allowed_asset_ids = allowed_asset_ids

    @property
    def scenario_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.definitions))

    @classmethod
    def load(
        cls, path: Path, allowed_asset_ids: set[str] | frozenset[str]
    ) -> "ScenarioCatalog":
        try:
            raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            raise ScenarioError(f"CATALOG_READ_FAILED: {path}: {error}") from error
        if not isinstance(raw, dict) or set(raw) != {
            "schema_version",
            "nominal_values",
            "hidden_pose",
            "known_props",
            "scenarios",
        }:
            _fail("CATALOG_INVALID", "top-level keys")
        if raw["schema_version"] != 1:
            _fail("CATALOG_INVALID", "schema_version")
        nominal_raw = raw["nominal_values"]
        if not isinstance(nominal_raw, dict) or set(nominal_raw) != {
            "temperature_celsius",
            "smoke_0_1",
            "gas_ppm",
            "meter_reading",
            "battery_percentage",
        }:
            _fail("CATALOG_INVALID", "nominal_values")
        nominal = {key: _finite_number(value, key) for key, value in nominal_raw.items()}
        known_props_raw = raw["known_props"]
        if (
            not isinstance(known_props_raw, list)
            or not all(isinstance(item, str) for item in known_props_raw)
            or len(known_props_raw) != len(set(known_props_raw))
        ):
            _fail("CATALOG_INVALID", "known_props")
        scenarios_raw = raw["scenarios"]
        if not isinstance(scenarios_raw, dict) or set(scenarios_raw) != EXPECTED_SCENARIOS:
            _fail("CATALOG_INVALID", "scenario IDs")
        definitions: dict[str, ScenarioDefinition] = {}
        for scenario_id, definition_raw in scenarios_raw.items():
            if not isinstance(definition_raw, dict) or set(definition_raw) != {
                "parameters",
                "defaults",
                "values",
                "props",
            }:
                _fail("CATALOG_INVALID", f"{scenario_id} fields")
            rules: dict[str, ParameterRule] = {}
            if not isinstance(definition_raw["parameters"], dict):
                _fail("CATALOG_INVALID", f"{scenario_id}.parameters")
            for name, rule_raw in definition_raw["parameters"].items():
                if not isinstance(rule_raw, dict) or rule_raw.get("type") not in {"number", "asset_id"}:
                    _fail("CATALOG_INVALID", f"{scenario_id}.{name} rule")
                allowed_rule_keys = {"type", "required"}
                if rule_raw["type"] == "number":
                    allowed_rule_keys |= {"minimum", "maximum"}
                if set(rule_raw) != allowed_rule_keys:
                    _fail("CATALOG_INVALID", f"{scenario_id}.{name} rule keys")
                minimum = maximum = None
                if rule_raw["type"] == "number":
                    minimum = _finite_number(rule_raw["minimum"], f"{scenario_id}.{name}.minimum")
                    maximum = _finite_number(rule_raw["maximum"], f"{scenario_id}.{name}.maximum")
                    if minimum > maximum:
                        _fail("CATALOG_INVALID", f"{scenario_id}.{name} range")
                rules[name] = ParameterRule(
                    kind=rule_raw["type"],
                    required=rule_raw["required"] is True,
                    minimum=minimum,
                    maximum=maximum,
                )
            defaults = definition_raw["defaults"]
            if not isinstance(defaults, dict) or set(defaults) != set(rules):
                _fail("CATALOG_INVALID", f"{scenario_id}.defaults")
            if not all(_is_scalar(value) for value in defaults.values()):
                _fail("CATALOG_INVALID", f"{scenario_id}.defaults scalar")
            values = definition_raw["values"]
            if not isinstance(values, dict) or not set(values).issubset(nominal):
                _fail("CATALOG_INVALID", f"{scenario_id}.values")
            parsed_values = {
                name: _finite_number(value, f"{scenario_id}.values.{name}")
                for name, value in values.items()
            }
            props = definition_raw["props"]
            if not isinstance(props, dict) or not set(props).issubset(known_props_raw):
                _fail("CATALOG_INVALID", f"{scenario_id}.props")
            definitions[scenario_id] = ScenarioDefinition(
                parameters=MappingProxyType(rules),
                defaults=MappingProxyType(dict(defaults)),
                values=MappingProxyType(parsed_values),
                props=MappingProxyType(
                    {
                        name: _pose(value, f"{scenario_id}.props.{name}")
                        for name, value in props.items()
                    }
                ),
            )
        catalog = cls(
            nominal_values=nominal,
            hidden_pose=_pose(raw["hidden_pose"], "hidden_pose"),
            known_props=tuple(sorted(known_props_raw)),
            definitions=definitions,
            allowed_asset_ids=frozenset(allowed_asset_ids),
        )
        for scenario_id, definition in catalog.definitions.items():
            catalog.validate(
                Command.from_parameters(
                    "00000000-0000-4000-8000-000000000001",
                    scenario_id,
                    "trigger",
                    _canonical_json(dict(definition.defaults)),
                )
            )
        return catalog

    def validate(self, command: Command) -> None:
        if command.scenario_id not in self.definitions:
            _fail("SCENARIO_NOT_FOUND", command.scenario_id)
        definition = self.definitions[command.scenario_id]
        if command.action == "reset":
            if command.parameters:
                _fail("SCENARIO_PARAMETER_NOT_ALLOWED", "reset requires empty parameters")
            return
        unknown = set(command.parameters) - set(definition.parameters)
        if unknown:
            _fail("SCENARIO_PARAMETER_NOT_ALLOWED", repr(sorted(unknown)))
        effective = dict(definition.defaults)
        effective.update(command.parameters)
        missing = {
            name
            for name, rule in definition.parameters.items()
            if rule.required and name not in effective
        }
        if missing:
            _fail("SCENARIO_PARAMETERS_INVALID", repr(sorted(missing)))
        for name, value in effective.items():
            rule = definition.parameters[name]
            if rule.kind == "asset_id":
                if not isinstance(value, str) or value not in self.allowed_asset_ids:
                    _fail("SCENARIO_PARAMETER_OUT_OF_RANGE", name)
            else:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    _fail("SCENARIO_PARAMETERS_INVALID", name)
                numeric = float(value)
                if (
                    not math.isfinite(numeric)
                    or numeric < rule.minimum  # type: ignore[operator]
                    or numeric > rule.maximum  # type: ignore[operator]
                ):
                    _fail("SCENARIO_PARAMETER_OUT_OF_RANGE", name)


@dataclass(frozen=True)
class ApplyResult:
    status: str
    revision: int
    active: bool
    scenario_id: str
    error_code: str


class ScenarioEngine:
    def __init__(self, catalog: ScenarioCatalog) -> None:
        self.catalog = catalog
        self.revision = 0
        self.active_scenario = "normal"
        self.active = False
        self.values: Mapping[str, float] = catalog.nominal_values
        self._poses: dict[str, Pose] = {
            name: catalog.hidden_pose for name in catalog.known_props
        }
        self._results: dict[str, tuple[str, ApplyResult]] = {}

    def _failed(self, command: Command, code: str) -> ApplyResult:
        return ApplyResult(
            status="failed",
            revision=self.revision,
            active=self.active,
            scenario_id=command.scenario_id,
            error_code=code,
        )

    def apply(
        self, command: Command, pose_setter: Callable[[str, Pose], bool]
    ) -> ApplyResult:
        previous = self._results.get(command.command_id)
        if previous is not None:
            payload, result = previous
            if payload == command.canonical_payload:
                return result
            return self._failed(command, "COMMAND_ID_CONFLICT")
        try:
            self.catalog.validate(command)
        except ScenarioError as error:
            return self._failed(command, str(error).split(":", 1)[0])
        if command.action == "reset":
            target_scenario = "normal"
            target_active = False
            effective: dict[str, Scalar] = {}
        else:
            target_scenario = command.scenario_id
            target_active = True
            effective = dict(self.catalog.definitions[target_scenario].defaults)
            effective.update(command.parameters)
        definition = self.catalog.definitions[target_scenario]
        target_values = dict(self.catalog.nominal_values)
        target_values.update(definition.values)
        for name in target_values:
            if name in effective:
                target_values[name] = float(effective[name])
        target_poses = {
            name: self.catalog.hidden_pose for name in self.catalog.known_props
        }
        target_poses.update(definition.props)
        changed = [
            name for name in sorted(target_poses) if target_poses[name] != self._poses[name]
        ]
        applied: list[str] = []
        for name in changed:
            if pose_setter(name, target_poses[name]):
                applied.append(name)
                continue
            rollback_ok = all(
                pose_setter(applied_name, self._poses[applied_name])
                for applied_name in reversed(applied)
            )
            code = "GAZEBO_SET_POSE_FAILED" if rollback_ok else "GAZEBO_SET_POSE_ROLLBACK_FAILED"
            result = self._failed(command, code)
            self._results[command.command_id] = (command.canonical_payload, result)
            return result
        self.revision += 1
        self.active_scenario = target_scenario
        self.active = target_active
        self.values = MappingProxyType(target_values)
        self._poses = target_poses
        result = ApplyResult(
            status="applied",
            revision=self.revision,
            active=self.active,
            scenario_id=command.scenario_id,
            error_code="",
        )
        self._results[command.command_id] = (command.canonical_payload, result)
        return result
