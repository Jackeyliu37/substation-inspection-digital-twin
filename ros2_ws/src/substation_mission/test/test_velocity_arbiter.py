from __future__ import annotations

from substation_interfaces.msg import ManualVelocityCommand, ManualVelocityStatus

from substation_mission.velocity_arbiter import SafeVelocityArbiter


def command() -> ManualVelocityCommand:
    message = ManualVelocityCommand()
    message.schema_version = 1
    message.header.frame_id = "base_link"
    message.command_id = "3b514885-bb10-448b-92fd-ef9ec7ce9c74"
    message.run_id = "run-1"
    message.context_revision = 7
    message.twist.linear.x = 0.2
    message.twist.angular.z = -0.3
    message.duration_s = 0.15
    return message


def test_manual_command_is_applied_once_and_expires_on_monotonic_deadline() -> None:
    arbiter = SafeVelocityArbiter()
    arbiter.update_context(run_id="run-1", context_revision=7, active=True)
    arbiter.update_mission(robot_mode=1, emergency_stop_latched=False)

    decision = arbiter.accept_manual(command(), monotonic_s=10.0)
    assert decision.output == (0.2, 0.0, -0.3)
    assert [status.state for status in decision.statuses] == [
        ManualVelocityStatus.STATE_ACCEPTED,
        ManualVelocityStatus.STATE_APPLIED,
    ]
    assert arbiter.tick(monotonic_s=10.149) is None
    assert arbiter.tick(monotonic_s=10.15) == (0.0, 0.0, 0.0)
    assert arbiter.tick(monotonic_s=10.20) is None

    duplicate = arbiter.accept_manual(command(), monotonic_s=11.0)
    assert duplicate.output is None
    assert [status.state for status in duplicate.statuses] == [
        ManualVelocityStatus.STATE_APPLIED
    ]


def test_manual_command_rejects_context_mode_latch_frame_and_limits() -> None:
    arbiter = SafeVelocityArbiter()
    arbiter.update_context(run_id="run-1", context_revision=7, active=True)
    arbiter.update_mission(robot_mode=0, emergency_stop_latched=False)
    rejected = arbiter.accept_manual(command(), monotonic_s=1.0)
    assert rejected.statuses[0].error_code == "MANUAL_MODE_REQUIRED"

    arbiter.update_mission(robot_mode=1, emergency_stop_latched=True)
    other = command()
    other.command_id = "1bb5190d-72cc-45ab-aa76-9ece7b65787a"
    rejected = arbiter.accept_manual(other, monotonic_s=1.0)
    assert rejected.statuses[0].error_code == "EMERGENCY_STOP_LATCHED"

    arbiter.update_mission(robot_mode=1, emergency_stop_latched=False)
    other.command_id = "3d66fac1-9fd0-4594-a042-9f7ea33eaf83"
    other.context_revision = 8
    rejected = arbiter.accept_manual(other, monotonic_s=1.0)
    assert rejected.statuses[0].error_code == "RUN_CONTEXT_MISMATCH"

    other.command_id = "68ed27a8-f5d4-4fc8-adbe-4ecbf765b6b4"
    other.context_revision = 7
    other.header.frame_id = "map"
    rejected = arbiter.accept_manual(other, monotonic_s=1.0)
    assert rejected.statuses[0].error_code == "FRAME_ID_INVALID"

    other.command_id = "e3f51fd2-4ad6-4ac2-afd1-f5800391a237"
    other.header.frame_id = "base_link"
    other.twist.linear.x = 0.41
    rejected = arbiter.accept_manual(other, monotonic_s=1.0)
    assert rejected.statuses[0].error_code == "VELOCITY_LIMIT_EXCEEDED"


def test_nav_velocity_passes_only_in_active_autonomous_non_latched_state() -> None:
    arbiter = SafeVelocityArbiter()
    arbiter.update_context(run_id="run-1", context_revision=7, active=True)
    arbiter.update_mission(robot_mode=0, emergency_stop_latched=False)
    assert arbiter.accept_nav((0.3, 0.0, 0.4)) == (0.3, 0.0, 0.4)

    assert arbiter.update_mission(robot_mode=1, emergency_stop_latched=False) == (
        0.0, 0.0, 0.0
    )
    assert arbiter.accept_nav((0.3, 0.0, 0.4)) is None

    arbiter.update_mission(robot_mode=0, emergency_stop_latched=True)
    assert arbiter.accept_nav((0.3, 0.0, 0.4)) is None
