# Phase 3 SLAM and Navigation Design

## Goal

Make the locked Phase 2 Gazebo world navigable in headless mode.  The result
provides a reproducible static map, AMCL localization, Nav2 goal execution,
and validated inspection poses.  It does not implement mission scheduling,
risk priority, perception, or Web commands.

## Decision

Three viable approaches were considered:

1. Run SLAM continuously during every navigation session.  This adapts to
   world edits, but lets normal scenario obstacles change the global map and
   makes runs non-repeatable.
2. Use an analytic map only.  This is deterministic but does not exercise the
   required LiDAR SLAM path.
3. Use `slam_toolbox` in an explicit mapping launch, retain the generated map
   in source control, then use `map_server + AMCL + Nav2` in normal runs.

Option 3 is selected.  It proves the LiDAR mapping integration while keeping
normal navigation deterministic and prevents scenario-only objects from being
persisted into the map.

## Ownership and Interfaces

`substation_gazebo` owns all Phase 3 configuration and the two launch entry
points.  It consumes the existing `/scan`, `/odom`, `/tf`, and `/cmd_vel`
interfaces from Phase 2.  No Phase 3 node writes asset frames, risk, mission
state, or scenario truth.

Mapping mode starts `slam_toolbox` with `map_frame=map`, `odom_frame=odom`,
`base_frame=base_footprint`, and `/scan`.  It is the only publisher of
`map -> odom` in that mode.  Saving `/map` produces the version-controlled
`maps/substation.yaml` and `maps/substation.pgm` pair.

Navigation mode starts `map_server`, `amcl`, and the Nav2 lifecycle-managed
navigation stack with that map.  AMCL is the only publisher of `map -> odom`;
the Phase 2 differential-drive plugin remains the sole publisher of
`odom -> base_footprint`.  Nav2 receives goals only through the standard
`/navigate_to_pose` action.  It publishes velocity to `/cmd_vel`, whose
existing Gazebo bridge drives the robot.

## Map and Pose Contract

The map has `frame_id=map`, 0.05 m resolution, origin `[-8.0, -6.0, 0.0]`,
and represents the fixed Phase 2 walls and collision geometry only.  The
initial robot pose is `(-5.0, -4.2, 0.0)`.  The active dynamic-obstacle and
unreachable-blocker scenario models remain absent from the saved map and are
observed at runtime by the Nav2 local obstacle layer.

Inspection goals derive only from `configs/devices.yaml`.  A goal is accepted
only when its `asset_id` is registered, its pose uses `map`, its yaw is finite,
and it lies in known free space after the configured robot footprint and
inflation radius are considered.  The Phase 3 helper returns a standard
`geometry_msgs/msg/PoseStamped`; it does not decide task order or issue goals
on its own.

## Runtime Configuration

Robot footprint is a 0.30 m by 0.32 m polygon, with 0.25 m costmap inflation.
The global costmap uses the saved map plus a static layer; the local costmap
uses `/scan` as an obstacle layer and rolls with the robot.  Regulated Pure
Pursuit follows the global path at a conservative 0.22 m/s and rotates to the
path heading before translating.  Recovery behavior may clear costmaps and
rotate, but never changes scenarios or static-map files.

Every launch forces headless, localhost-only execution, takes a caller-supplied
unique `gz_partition`, and owns only its process group.  Acceptance cleanup
terminates that group and verifies no Phase 3 process remains.

## Verification

Unit tests prove map metadata, Nav2 parameter ownership, and deterministic
inspection-pose validation before runtime code is added.  The headless
acceptance harness starts the Phase 2 world and normal navigation launch,
sets the initial AMCL pose, waits for the Nav2 action server, sends a known
inspection pose, and requires a successful action result with a `map -> odom`
transform.  A second run activates `dynamic-obstacle`; it must observe local
costmap obstacle data and complete a reachable alternate inspection goal
without a static-map change.  Runtime logs and result JSON are written only
under the caller-provided Phase 3 evidence directory.

## Out of Scope

Mission orchestration, manual controls, risk-based reordering, emergency-stop
arbitration, visual perception, and UI exposure begin in later phases.  No
external package, model, or dataset download is part of this phase.
