# Phase 2 Gazebo Substation World Design

**Status:** Approved for implementation under the user's solo fast-track instruction to use the recommended design without repeated confirmation.

**Phase goal:** Build a deterministic, repository-owned substation world that starts on Gazebo Harmonic in OGRE2/EGL headless mode and publishes the Phase 2 ROS sensor, environment, scenario, odometry, and TF contracts without any Fuel or runtime network dependency.

## Scope and phase boundary

Phase 2 creates only `substation_description` and `substation_gazebo`, their configuration, tests, launch files, and phase evidence tooling. It supplies the geometry and raw simulation interfaces required by later SLAM, perception, digital-twin, risk, mission, and Web phases; it does not implement those later consumers.

The completed phase must provide:

- a fenced substation yard with walls, two inspection lanes, a marked exclusion zone, static obstacles, movable scenario props, and at least eight canonical equipment categories;
- stable asset metadata and `map -> asset/<asset_id>` static transforms;
- one TurtleBot3 Waffle Pi-sized differential-drive robot with RGB camera, 2D GPU LiDAR, odometry, and the contract TF frames;
- `/clock`, RGB, CameraInfo, LiDAR, odometry, TF, raw temperature/smoke/gas, battery, scenario truth, and scenario state;
- the eight fixed scenario identifiers and an atomic standard ROS parameter service at `/scenario_manager/set_parameters_atomically`;
- repeatable static, unit, ROS integration, and live no-`DISPLAY` Gazebo checks.

Nav2 maps and navigation behavior belong to Phase 3. Visual inference, synthetic dataset export, and model integration belong to Phase 4. RunContext ownership and Gateway-only operator scenario control are integrated in Phases 6 and 7. The Phase 2 standalone launch therefore runs raw infrastructure continuously and uses an explicit launch-scoped acceptance `run_id`; the normal launch default is an empty readiness `run_id`. It does not invent a mission lifecycle owner.

## Considered approaches

### A. Repository-owned primitive assets and robot model — selected

Build the world and inspection robot from SDF boxes, cylinders, spheres, and locally installed TurtleBot3 mesh resources. This keeps the world small, reviewable, offline, deterministic, and compatible with the already locked ROS/Gazebo installation. Semantic fidelity comes from stable IDs, recognizable silhouettes, colors, collision geometry, and metadata rather than photorealistic meshes.

### B. Download detailed models from Gazebo Fuel

This improves appearance but adds network availability, licensing, version drift, cache identity, and mesh-performance risks. It is rejected for the Phase 2 baseline. Detailed replacements may be considered later only if they preserve collision geometry, IDs, frames, and reproducibility.

### C. Extend the upstream TurtleBot3 launch and world directly

This minimizes initial source, but the installed Waffle Pi publishes `base_scan` and `camera_rgb_frame`, while the project contract fixes `laser_frame` and `camera_optical_frame`. Hiding that mismatch behind later adapters would create duplicate frame ownership and semantic ambiguity. Upstream dimensions and installed meshes remain reference inputs, but project-owned SDF and Xacro define the actual contract.

## Component boundaries and file map

### `substation_description`

- `config/devices.yaml` is the only authored asset registry. It contains schema version, stable IDs, canonical categories, report names, map poses, inspection poses, and thresholds.
- `substation_description/asset_registry.py` parses and validates the registry without ROS side effects.
- `substation_description/asset_tf_broadcaster.py` publishes exactly one static `map -> asset/<asset_id>` transform per registry entry.
- `urdf/inspection_robot.urdf.xacro` defines the contract robot TF tree and TurtleBot3 Waffle Pi geometry references for `robot_state_publisher`.

The package owns authored geometry semantics and static transforms only. It never publishes runtime sensor, scenario, observation, or risk state.

### `substation_gazebo`

- `models/inspection_robot/model.sdf` is the physical differential-drive robot with camera and LiDAR sensors.
- `worlds/substation_world.sdf` owns the yard, assets, lanes, exclusion markings, collision bodies, fixed obstacles, hidden scenario props, light, physics, and Gazebo sensor systems.
- `config/bridge.yaml` declares only the Gazebo-to-ROS clock, CameraInfo, LiDAR, odometry, TF, and joint-state bridges plus ROS-to-Gazebo velocity input. RGB pixels use `ros_gz_image`.
- `config/scenarios.yaml` is the scenario catalog, allowed scalar parameters, value ranges, default raw sensor values, and prop poses.
- `substation_gazebo/scenario_catalog.py` is a ROS-free parser and validator.
- `substation_gazebo/scenario_manager.py` owns scenario command idempotency, scene prop movement, raw environment publishers, battery simulation, truth, and state.
- `launch/substation_world.launch.py` is the single supported Phase 2 launch entry. It removes `DISPLAY`, forces `ROS_LOCALHOST_ONLY=1`, sets a unique `GZ_PARTITION`, starts Gazebo server-only with `--headless-rendering`, the bridge, image bridge, robot state publisher, asset TF broadcaster, Gazebo set-pose service bridge, and scenario manager.

No process in either package downloads resources or starts a GUI.

## Asset registry and world layout

`devices.yaml` uses schema version 1. Every asset entry has exactly these common fields:

```yaml
asset_id: transformer-01
category: power_transformer
report_name: Main Transformer T1
pose: {x: 5.0, y: 3.0, z: 0.0, roll: 0.0, pitch: 0.0, yaw: 0.0}
inspection_pose: {x: 2.8, y: 3.0, yaw: 0.0}
thresholds:
  temperature_celsius: {warning: 70.0, critical: 85.0}
  smoke_0_1: {warning: 0.25, critical: 0.60}
  gas_ppm: {warning: 100.0, critical: 200.0}
```

IDs match `^[a-z0-9]+(?:-[a-z0-9]+)*$`, are unique, and become TF suffixes without rewriting. Categories use the canonical names from `docs/DATA_AND_MODELS.md` for detectable equipment. Analog meters use the explicit non-detector category `analog_meter` and add `meter: {sensor_id, minimum, maximum, unit, normal_minimum, normal_maximum}`. All numeric values must be finite; warning must be lower than critical; an inspection pose must remain inside the yard and outside the exclusion zone.

The initial registry contains:

| Asset ID | Category | Map position | Inspection position |
|---|---|---:|---:|
| `transformer-01` | `power_transformer` | `(5.0, 3.0)` | `(2.8, 3.0)` |
| `breaker-01` | `breaker` | `(0.5, 3.5)` | `(0.5, 1.8)` |
| `disconnect-switch-01` | `closed_blade_disconnect_switch` | `(-3.5, 3.5)` | `(-3.5, 1.8)` |
| `arrester-01` | `lightning_arrester` | `(5.5, -2.5)` | `(3.5, -2.5)` |
| `current-transformer-01` | `current_transformer` | `(1.5, -3.0)` | `(1.5, -1.4)` |
| `potential-transformer-01` | `potential_transformer` | `(-1.5, -3.0)` | `(-1.5, -1.4)` |
| `glass-insulator-01` | `glass_disc_insulator` | `(-5.0, -2.5)` | `(-3.3, -2.5)` |
| `porcelain-insulator-01` | `porcelain_pin_insulator` | `(-5.0, 0.5)` | `(-3.3, 0.5)` |
| `meter-pressure-01` | `analog_meter` | `(4.0, 3.0)` | `(2.8, 2.5)` |
| `meter-oil-01` | `analog_meter` | `(5.0, 2.0)` | `(3.0, 2.0)` |

The 16 m × 12 m yard is centered on `map`. A 0.2 m perimeter wall and fence collision prevent escape. Two 1.5 m-wide inspection lanes cross the yard through the center. The transformer exclusion zone is a red, non-colliding floor marking enclosing the transformer's collision body; later navigation configuration will use the same authored boundary. Pallets and bollards provide static obstacles. Scenario props start below the ground and are moved into named poses only by the scenario manager.

## Robot, rendering, and bridge contract

The SDF robot uses Waffle Pi dimensions and locally installed TurtleBot3 mesh URIs where practical, with primitive collision bodies for stable physics. The differential-drive plugin owns `odom -> base_footprint`, publishes odometry at 30 Hz, and consumes `/cmd_vel`. `robot_state_publisher` owns the fixed robot transforms:

```text
base_footprint -> base_link -> camera_link -> camera_optical_frame
                            -> laser_frame
```

The camera publishes 640 × 480 `R8G8B8` at 15 Hz. Its Gazebo sensor pose is rotated so the optical frame obeys REP-103: z forward, x right, y down. ROS output is `sensor_msgs/msg/Image` with `encoding=rgb8`, `header.frame_id=camera_optical_frame`; CameraInfo uses the same frame and stamp with nonzero calibration.

The 2D GPU LiDAR publishes 360 samples at 10 Hz over 0 to 2π, range 0.12–10.0 m, and `header.frame_id=laser_frame`. The SDF world uses the Harmonic physics, scene broadcaster, user commands, and rendering sensor systems. Rendering is OGRE2/EGL server-only. No launch path contains `-g`, X11, Xvfb, or VirtualGL.

The bridge preserves the project topics exactly:

| ROS topic | Direction | Type / source |
|---|---|---|
| `/clock` | Gazebo → ROS | `rosgraph_msgs/msg/Clock` |
| `/camera/image_raw` | Gazebo → ROS | `sensor_msgs/msg/Image` through `ros_gz_image` |
| `/camera/camera_info` | Gazebo → ROS | `sensor_msgs/msg/CameraInfo` |
| `/scan` | Gazebo → ROS | `sensor_msgs/msg/LaserScan` |
| `/odom` | Gazebo → ROS | `nav_msgs/msg/Odometry` |
| `/tf` | Gazebo → ROS | `tf2_msgs/msg/TFMessage` for odometry only |
| `/joint_states` | Gazebo → ROS | `sensor_msgs/msg/JointState` |
| `/cmd_vel` | ROS → Gazebo | `geometry_msgs/msg/Twist` |

Phase 2 may drive `/cmd_vel` only from its live smoke test. The final product's unique velocity owner remains the Phase 6 mission safety arbiter.

## Scenario catalog and state machine

The catalog contains exactly these stable identifiers:

- `normal`
- `ppe`
- `fire-smoke`
- `temperature-high`
- `gas-high`
- `meter-limit`
- `unreachable`
- `combined-risk-obstacle`

`normal` keeps all props hidden and publishes nominal measurements. Other scenarios change only catalog-authorized scalar fields and named prop poses. Examples include `asset_id`, `temperature_celsius`, `smoke_0_1`, `gas_ppm`, `meter_reading`, and `obstacle_progress_0_1`. File paths, ROS names, nested JSON, arrays, and code-like values are rejected.

The node declares the four interface parameters `command_id`, `scenario_id`, `scenario_action`, and `scenario_parameters_json`; this automatically exposes `/scenario_manager/set_parameters_atomically`. The callback accepts only a set containing all four fields, validates UUID/action/catalog/allowlist/ranges/canonical scalar JSON, and applies it as one transaction. `start` and `trigger` activate the scenario; `reset` restores `normal`. Replaying an identical `command_id` and payload returns success without changing revision or scene state. Reusing the ID with different content fails.

Application proceeds in this order:

1. publish `scenario_state` with `status=applying`;
2. call the bridged Gazebo `SetEntityPose` service for every affected prop;
3. atomically update active values and increment `scenario_revision` only if every pose succeeds;
4. publish `scenario_state` with `status=applied` and the corresponding `scenario_truth`;
5. on validation or pose failure, preserve the last complete state and publish `status=failed` with a stable code.

The environment publishers run at 2 Hz and emit one `DiagnosticStatus` per affected asset using the exact key sets in `docs/INTERFACES.md`. Truth and state publish immediately on change and repeat at 1 Hz. State is reliable/transient-local; truth is reliable/volatile; raw sensors are best-effort/volatile. A normal readiness sample may carry empty `run_id`; a standalone scenario acceptance launch supplies a UUID explicitly.

Stable Phase 2 failure codes are `COMMAND_FIELDS_INCOMPLETE`, `COMMAND_ID_INVALID`, `COMMAND_ID_CONFLICT`, `SCENARIO_NOT_FOUND`, `SCENARIO_ACTION_INVALID`, `SCENARIO_PARAMETERS_INVALID`, `SCENARIO_PARAMETER_NOT_ALLOWED`, `SCENARIO_PARAMETER_OUT_OF_RANGE`, and `GAZEBO_SET_POSE_FAILED`.

## Testing and evidence

Development is test-first and split into independently reviewable checkpoints.

### Static and unit checks

- parse `devices.yaml`, prove schema/ID/category/pose/threshold validity, at least eight canonical equipment categories, two meters, and exact SDF model-name coverage;
- parse SDF/XML and assert the world systems, headless-compatible sensor definitions, lane/wall/exclusion/static/dynamic elements, robot plugins, topic names, rates, frame IDs, camera format, and LiDAR range;
- parse Xacro output and prove every required fixed frame and unique parent exists;
- parse bridge and launch files, reject GUI/display dependencies, and verify exact topic direction/type declarations;
- unit-test scenario catalog allowlists, range validation, canonical command parsing, idempotency, reset, and failure-without-partial-commit behavior;
- unit-test DiagnosticArray builders for exact field names, units, rates, and QoS constructors.

### ROS package and live checks

The workspace must pass package-selective build, package tests, and `colcon test-result`. A live harness launches the world with `env -u DISPLAY`, `ROS_LOCALHOST_ONLY=1`, and a unique `GZ_PARTITION`; it waits with explicit timeouts and records logs under a caller-provided evidence directory.

The live harness must prove:

- no `DISPLAY` exists in the Gazebo process environment and the launch uses `--headless-rendering`;
- each required topic has a publisher and at least two samples;
- camera is non-uniform `rgb8`, 640 × 480, frame `camera_optical_frame`; CameraInfo matches dimensions/frame and has a nonzero K matrix;
- LaserScan is finite enough to demonstrate a rendered yard, has 360 ranges, 10 Hz nominal behavior, and frame `laser_frame`;
- odometry frames are `odom` and `base_footprint`; required dynamic and static TF edges exist with unique owners;
- every configured `asset_id` has `map -> asset/<asset_id>`;
- raw environment, battery, truth, and state messages match exact key sets and bounds;
- a valid `temperature-high` atomic parameter command reaches `applied`, increments revision once, moves its prop, changes temperature output, and is idempotent on replay;
- reset returns nominal values and hides the prop;
- Gazebo, bridges, and ROS nodes are stopped by PID-scoped cleanup even after a failure.

Evidence contains launch logs, topic inventory, sampled messages, TF YAML, process-environment proof, scenario command/result, world/config SHA-256 values, JUnit, and a final JSON result. No rendered frames, logs, rosbag2, build trees, or evidence payloads are committed to Git.

## Completion conditions

Phase 2 is complete only when the implementation commit builds and passes all static, unit, package, and live no-`DISPLAY` tests on the locked Phase 1 host; the evidence identifies that exact commit and hashes every authored world/config input; `PROJECT_STATUS.md` and `HANDOFF.md` record the immutable result and Phase 3 as the next action; and the final phase commit is pushed to `origin/main`.

