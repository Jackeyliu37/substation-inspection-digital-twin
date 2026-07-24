"""Pure safety policy for the task manager's single /cmd_vel publisher."""

from __future__ import annotations

from dataclasses import dataclass
import math

from substation_interfaces.msg import ManualVelocityCommand, ManualVelocityStatus


@dataclass(frozen=True)
class VelocityStatus:
    state: int
    error_code: str = ""
    error_message: str = ""


@dataclass(frozen=True)
class VelocityDecision:
    statuses: tuple[VelocityStatus, ...]
    output: tuple[float, float, float] | None


def _clean(value: float) -> float:
    return float(f"{float(value):.6g}")


class SafeVelocityArbiter:
    """Select Nav2 or bounded manual velocity using a monotonic deadline."""

    def __init__(self) -> None:
        self._run_id = ""
        self._context_revision = 0
        self._context_active = False
        self._robot_mode = 0
        self._latched = False
        self._manual_deadline: float | None = None
        self._output_active = False
        self._zero_since: float | None = None
        self._terminal: dict[str, VelocityStatus] = {}

    def record_published(
        self,
        velocity: tuple[float, float, float],
        *,
        monotonic_s: float,
    ) -> None:
        """Record the velocity actually published by the single writer."""
        if any(value != 0.0 for value in velocity):
            self._zero_since = None
        elif self._zero_since is None:
            self._zero_since = float(monotonic_s)

    def zero_barrier_satisfied(
        self,
        *,
        monotonic_s: float,
        minimum_s: float = 0.5,
    ) -> bool:
        return (
            self._zero_since is not None
            and float(monotonic_s) - self._zero_since >= minimum_s
        )

    def update_context(self, *, run_id: str, context_revision: int, active: bool) -> tuple[float, float, float] | None:
        changed = (
            run_id != self._run_id
            or context_revision != self._context_revision
            or active != self._context_active
        )
        self._run_id = run_id
        self._context_revision = context_revision
        self._context_active = active
        if changed and (not active or self._manual_deadline is not None):
            return self._stop()
        return None

    def update_mission(
        self, *, robot_mode: int, emergency_stop_latched: bool
    ) -> tuple[float, float, float] | None:
        unsafe_transition = (
            emergency_stop_latched
            or robot_mode != self._robot_mode
            or robot_mode == 2
        )
        self._robot_mode = int(robot_mode)
        self._latched = bool(emergency_stop_latched)
        if unsafe_transition:
            return self._stop()
        return None

    def accept_nav(
        self, velocity: tuple[float, float, float]
    ) -> tuple[float, float, float] | None:
        if not self._context_active or self._robot_mode != 0 or self._latched:
            return None
        output = tuple(_clean(value) for value in velocity)
        if not all(math.isfinite(value) for value in output):
            return None
        self._output_active = any(value != 0.0 for value in output)
        return output

    def accept_manual(
        self, message: ManualVelocityCommand, *, monotonic_s: float
    ) -> VelocityDecision:
        duplicate = self._terminal.get(message.command_id)
        if duplicate is not None:
            return VelocityDecision((duplicate,), None)
        error = self._validate_manual(message)
        if error:
            status = VelocityStatus(
                ManualVelocityStatus.STATE_REJECTED,
                error,
                "manual velocity command rejected",
            )
            self._terminal[message.command_id] = status
            return VelocityDecision((status,), None)
        output = (
            _clean(message.twist.linear.x),
            _clean(message.twist.linear.y),
            _clean(message.twist.angular.z),
        )
        self._manual_deadline = monotonic_s + float(message.duration_s)
        self._output_active = any(value != 0.0 for value in output)
        accepted = VelocityStatus(ManualVelocityStatus.STATE_ACCEPTED)
        applied = VelocityStatus(ManualVelocityStatus.STATE_APPLIED)
        self._terminal[message.command_id] = applied
        return VelocityDecision((accepted, applied), output)

    def _validate_manual(self, message: ManualVelocityCommand) -> str:
        if message.schema_version != ManualVelocityCommand.SCHEMA_VERSION:
            return "VALIDATION_FAILED"
        if message.header.frame_id != "base_link":
            return "FRAME_ID_INVALID"
        if (
            not self._context_active
            or message.run_id != self._run_id
            or int(message.context_revision) != self._context_revision
        ):
            return "RUN_CONTEXT_MISMATCH"
        if self._robot_mode != 1:
            return "MANUAL_MODE_REQUIRED"
        if self._latched:
            return "EMERGENCY_STOP_LATCHED"
        values = (
            message.twist.linear.x,
            message.twist.linear.y,
            message.twist.linear.z,
            message.twist.angular.x,
            message.twist.angular.y,
            message.twist.angular.z,
            message.duration_s,
        )
        if not all(math.isfinite(value) for value in values):
            return "VALIDATION_FAILED"
        if (
            abs(message.twist.linear.x) > 0.4
            or abs(message.twist.angular.z) > 0.8
            or any(value != 0.0 for value in (
                message.twist.linear.y,
                message.twist.linear.z,
                message.twist.angular.x,
                message.twist.angular.y,
            ))
        ):
            return "VELOCITY_LIMIT_EXCEEDED"
        if not 0.05 <= message.duration_s <= 0.25:
            return "VALIDATION_FAILED"
        return ""

    def tick(self, *, monotonic_s: float) -> tuple[float, float, float] | None:
        if self._manual_deadline is None or monotonic_s < self._manual_deadline:
            return None
        return self._stop()

    def _stop(self) -> tuple[float, float, float] | None:
        should_publish = self._output_active or self._manual_deadline is not None
        self._manual_deadline = None
        self._output_active = False
        return (0.0, 0.0, 0.0) if should_publish else None
