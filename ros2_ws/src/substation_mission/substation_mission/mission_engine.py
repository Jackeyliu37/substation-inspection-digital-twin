from __future__ import annotations

from dataclasses import dataclass, replace
from enum import IntEnum
import math
from pathlib import Path

import yaml


class RobotMode(IntEnum):
    AUTONOMOUS = 0
    MANUAL = 1
    ESTOP = 2


class TaskState(IntEnum):
    QUEUED = 0
    ACTIVE = 1
    SUCCEEDED = 2
    SKIPPED = 3
    FAILED = 4
    CANCELLED = 5


@dataclass(frozen=True)
class MissionPolicy:
    risk_gain: float = 1.0
    distance_penalty: float = 0.25
    minimum_active_hold_s: float = 5.0
    normal_replan_cooldown_s: float = 10.0
    emergency_score_0_100: float = 80.0
    emergency_safety_standoff_m: float = 1.0


def load_mission_policy(path: Path) -> MissionPolicy:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    required = {
        "schema_version", "risk_gain", "distance_penalty", "minimum_active_hold_s",
        "normal_replan_cooldown_s", "emergency_score_0_100",
    }
    if not isinstance(data, dict) or set(data) != required or data["schema_version"] != 1:
        raise ValueError("MISSION_POLICY_SCHEMA_INVALID")
    values = {name: float(data[name]) for name in required - {"schema_version"}}
    if not all(math.isfinite(value) and value >= 0.0 for value in values.values()):
        raise ValueError("MISSION_POLICY_VALUE_INVALID")
    if not 0.0 <= values["emergency_score_0_100"] <= 100.0:
        raise ValueError("MISSION_POLICY_EMERGENCY_THRESHOLD_INVALID")
    return MissionPolicy(**values)


@dataclass(frozen=True)
class InspectionTask:
    task_id: str
    asset_id: str
    base_priority: int
    path_length_m: float
    risk_score_0_100: float = 0.0
    computed_priority: float = 0.0
    safety_standoff_m: float = 0.0
    emergency: bool = False
    state: TaskState = TaskState.QUEUED
    attempt: int = 0
    last_error_code: str = ""


@dataclass(frozen=True)
class StopResult:
    accepted: bool
    latched: bool
    latch_revision: int
    robot_mode: RobotMode


class MissionEngine:
    """Deterministic queue owner; Nav2 execution remains a separate adapter."""

    def __init__(self, policy: MissionPolicy) -> None:
        self.policy = policy
        self.run_id = ""
        self.mission_id = ""
        self.route_id = ""
        self.tasks: tuple[InspectionTask, ...] = ()
        self.robot_mode = RobotMode.AUTONOMOUS
        self.emergency_stop_latched = False
        self.latch_revision = 0
        self._last_normal_replan_s: float | None = None

    def start(self, *, run_id: str, mission_id: str, route_id: str) -> None:
        if not run_id or not mission_id or not route_id:
            raise ValueError("MISSION_IDENTITY_INVALID")
        self.run_id, self.mission_id, self.route_id = run_id, mission_id, route_id
        self.robot_mode = RobotMode.AUTONOMOUS

    def replace_tasks(self, tasks: tuple[InspectionTask, ...]) -> None:
        if not self.mission_id or self.emergency_stop_latched:
            raise ValueError("MISSION_NOT_MUTABLE")
        self.tasks = tuple(tasks)

    def apply_risk(self, scores: dict[str, float], *, monotonic_s: float) -> bool:
        if self.emergency_stop_latched or not self.mission_id:
            return False
        emergency_assets = sorted(asset_id for asset_id, score in scores.items() if score >= self.policy.emergency_score_0_100)
        if emergency_assets:
            self._insert_emergency(emergency_assets[0], scores[emergency_assets[0]])
            return True
        if self._last_normal_replan_s is not None and monotonic_s - self._last_normal_replan_s < self.policy.normal_replan_cooldown_s:
            return False
        mutable = tuple(task for task in self.tasks if task.state in (TaskState.QUEUED, TaskState.ACTIVE))
        terminal = tuple(task for task in self.tasks if task.state not in (TaskState.QUEUED, TaskState.ACTIVE))
        updated = tuple(
            replace(
                task,
                risk_score_0_100=scores.get(task.asset_id, task.risk_score_0_100),
                computed_priority=(
                    task.base_priority + self.policy.risk_gain * scores.get(task.asset_id, task.risk_score_0_100)
                    - self.policy.distance_penalty * task.path_length_m
                ),
            ) for task in mutable
        )
        ordered = tuple(sorted(updated, key=lambda task: (-task.computed_priority, task.task_id)))
        next_tasks = ordered + terminal
        if next_tasks == self.tasks:
            return False
        self.tasks = next_tasks
        self._last_normal_replan_s = monotonic_s
        return True

    def _insert_emergency(self, asset_id: str, score: float) -> None:
        existing = next((task for task in self.tasks if task.asset_id == asset_id and task.emergency), None)
        task = existing or InspectionTask(
            task_id=f"emergency-{asset_id}", asset_id=asset_id, base_priority=1000,
            path_length_m=0.0, safety_standoff_m=self.policy.emergency_safety_standoff_m, emergency=True,
        )
        task = replace(task, risk_score_0_100=score, computed_priority=task.base_priority + self.policy.risk_gain * score)
        remaining = tuple(item for item in self.tasks if item.task_id != task.task_id)
        self.tasks = (task,) + tuple(sorted(remaining, key=lambda item: (-item.computed_priority, item.task_id)))

    def emergency_stop(self, reason: str) -> StopResult:
        if not reason:
            return StopResult(False, self.emergency_stop_latched, self.latch_revision, self.robot_mode)
        if not self.emergency_stop_latched:
            self.emergency_stop_latched = True
            self.latch_revision += 1
        self.robot_mode = RobotMode.ESTOP
        return StopResult(True, True, self.latch_revision, self.robot_mode)

    def reset_emergency_stop(self, observed_latch_revision: int, *, confirm: bool) -> StopResult:
        if not self.emergency_stop_latched or not confirm or observed_latch_revision != self.latch_revision:
            return StopResult(False, self.emergency_stop_latched, self.latch_revision, self.robot_mode)
        self.emergency_stop_latched = False
        self.robot_mode = RobotMode.MANUAL
        return StopResult(True, False, self.latch_revision, self.robot_mode)
