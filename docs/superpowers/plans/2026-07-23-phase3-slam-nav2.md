# Phase 3 SLAM and Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver headless SLAM mapping, deterministic AMCL/Nav2 navigation, and validated inspection poses for the locked Phase 2 substation world.

**Architecture:** Mapping and navigation have separate launch modes.  Mapping runs `slam_toolbox` as the single `map -> odom` owner; normal operation loads the committed map and runs `map_server + AMCL + Nav2`, leaving dynamic scenario objects to the local LiDAR costmap.

**Tech Stack:** ROS 2 Jazzy, Gazebo Harmonic, `slam_toolbox`, Navigation2, Python `rclpy`, PyYAML, pytest, bash.

## Global Constraints

- Do not install or upgrade dependencies, and do not download external assets.
- Keep all runtime maps, logs, builds, installs, and evidence outside Git.
- Preserve the existing Phase 2 `/scan`, `/odom`, `/tf`, and `/cmd_vel` interfaces.
- Mapping and AMCL never run together; exactly one node owns `map -> odom`.
- Every Gazebo execution unsets `DISPLAY`, sets `ROS_LOCALHOST_ONLY=1`, uses a unique `GZ_PARTITION`, and kills only its own process group.
- Dynamic scenario objects are runtime local-costmap obstacles, never static-map input.

---

### Task 1: Map Metadata and Inspection-Pose Contract

**Files:**
- Create: `ros2_ws/src/substation_gazebo/config/nav2_params.yaml`
- Create: `ros2_ws/src/substation_gazebo/config/slam_toolbox.yaml`
- Create: `ros2_ws/src/substation_gazebo/maps/substation.yaml`
- Create: `ros2_ws/src/substation_gazebo/maps/substation.pgm`
- Create: `ros2_ws/src/substation_gazebo/substation_gazebo/inspection_poses.py`
- Create: `ros2_ws/src/substation_gazebo/test/test_inspection_poses.py`
- Modify: `ros2_ws/src/substation_gazebo/setup.py`

**Interfaces:**
- Consumes: `configs/devices.yaml` schema-1 assets and their `inspection_pose` values.
- Produces: `load_inspection_poses(path: Path) -> dict[str, InspectionPose]` and `pose_stamped(asset_id: str, poses: Mapping[str, InspectionPose], stamp: Time) -> PoseStamped`.

- [ ] **Step 1: Write failing tests** for unknown asset rejection, map-frame `PoseStamped`, normalized yaw quaternion, static map metadata, and only one `map -> odom` owner per launch mode.
- [ ] **Step 2: Run the focused test** with `pytest -q ros2_ws/src/substation_gazebo/test/test_inspection_poses.py` and verify failure is caused by the missing module/configuration.
- [ ] **Step 3: Add the minimal pose helper, map pair, SLAM configuration, Nav2 configuration, and package data-file entries.**
- [ ] **Step 4: Rerun focused tests** and `python3 -m compileall -q ros2_ws/src/substation_gazebo/substation_gazebo`; both must pass.
- [ ] **Step 5: Commit** with `feat: add phase three map and pose contract`.

### Task 2: Mapping and Navigation Launches

**Files:**
- Create: `ros2_ws/src/substation_gazebo/launch/substation_mapping.launch.py`
- Create: `ros2_ws/src/substation_gazebo/launch/substation_navigation.launch.py`
- Create: `ros2_ws/src/substation_gazebo/test/test_navigation_launch.py`
- Modify: `ros2_ws/src/substation_gazebo/setup.py`

**Interfaces:**
- Consumes: Task 1 map/config files and existing `substation_world.launch.py` world interface.
- Produces: mapping launch exposing `/map`; navigation launch exposing `/navigate_to_pose` and `/initialpose`.

- [ ] **Step 1: Write failing launch-contract tests** checking headless/local partition inheritance, separate map-transform ownership, map-server path, AMCL, Nav2 navigation launch, and no direct scenario modification.
- [ ] **Step 2: Run the focused launch tests** and confirm the missing launch files fail the assertions.
- [ ] **Step 3: Implement minimal launch files** with `IncludeLaunchDescription` for the Phase 2 world and installed SLAM/Nav2 launch files; pass `use_sim_time:=True` and committed paths explicitly.
- [ ] **Step 4: Rerun launch tests and import checks** with `pytest -q ros2_ws/src/substation_gazebo/test/test_navigation_launch.py` and `python3 -m py_compile` for both launch files.
- [ ] **Step 5: Commit** with `feat: add phase three navigation launches`.

### Task 3: Headless Navigation Acceptance

**Files:**
- Create: `tests/navigation/probe_phase3_navigation.py`
- Create: `tests/navigation/run_phase3_acceptance.sh`
- Create: `tests/navigation/test_acceptance_contract.py`

**Interfaces:**
- Consumes: Task 2 normal navigation launch, `/navigate_to_pose`, `/tf`, `/local_costmap/costmap_raw`, and the `dynamic-obstacle` scenario command.
- Produces: evidence `result.json`, launch/probe logs, JUnit XML, checksums, and a final evidence directory only after validation.

- [ ] **Step 1: Write failing static tests** for unique process-group cleanup, bounded timeouts, unique partition, evidence finalization, navigation-goal success, and dynamic local-costmap observation.
- [ ] **Step 2: Run the focused contract test** using `pytest -q tests/navigation/test_acceptance_contract.py` and verify failure because the harness and probe do not exist.
- [ ] **Step 3: Implement the probe and harness**: start the navigation launch in a new session, wait for lifecycle/action readiness, publish an AMCL initial pose, send a registered inspection pose, then activate the dynamic obstacle and assert an alternate reachable pose succeeds while the committed map hash is unchanged.
- [ ] **Step 4: Run static tests, then live acceptance** with a fresh UUID and evidence staging directory.  Verify JUnit, `result.json.status == "passed"`, checksum manifest, action success, `map -> odom`, dynamic local-costmap data, and no remaining process group.
- [ ] **Step 5: Commit** with `test: add phase three navigation acceptance`.

### Task 4: Seal Phase 3 and Push

**Files:**
- Modify: `docs/PROJECT_STATUS.md`
- Modify: `docs/HANDOFF.md`

**Interfaces:**
- Consumes: verified Task 3 final evidence.
- Produces: a truthful Phase 4 resume point with the tested commit and evidence identity.

- [ ] **Step 1: Extract and checksum final evidence.**
- [ ] **Step 2: Update the two status records** with the exact tested commit, UTC completion time, evidence path, verification command, and later-phase boundary.
- [ ] **Step 3: Run `bash scripts/verify_documentation_gate.sh`, `git diff --check`, focused/full tests, and `git status --short --branch`.**
- [ ] **Step 4: Commit and push** with `docs: record phase three navigation completion`; local and `origin/main` must resolve to the same commit.

## Plan Self-Review

Each contract requirement in the Phase 3 design is covered: Task 1 fixes map and pose semantics, Task 2 separates transform ownership and startup modes, Task 3 proves static navigation plus dynamic-obstacle local avoidance, and Task 4 records only verified runtime facts.  No task requires an external download, writes runtime artifacts to Git, or expands into mission/risk/perception scope.  The plan contains no placeholders and all produced names match their stated interfaces.
