# Phase 2 Gazebo Substation World Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a deterministic Gazebo Harmonic substation world with stable asset semantics, a contract-compliant inspection robot, reproducible scenarios, and no-`DISPLAY` ROS topic evidence.

**Architecture:** `substation_description` owns authored asset/robot semantics and static TF; `substation_gazebo` owns SDF physics/sensors, ROS–Gazebo bridges, raw environment/scenario state, and the one headless launch entry. Repository-owned primitive geometry and installed TurtleBot3 meshes avoid runtime downloads, while ROS-free parsers and state machines keep most behavior unit-testable before the live Gazebo gate.

**Tech Stack:** Ubuntu 24.04, ROS 2 Jazzy, Python 3.12, `ament_python`, `rclpy`, `tf2_ros`, Xacro, Gazebo Harmonic `gz-sim 8.x`, SDFormat 1.10, `ros_gz_bridge`, `ros_gz_image`, PyYAML, pytest, Bash, SHA-256.

## Global Constraints

- Use only Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic `gz-sim 8.x`, and the exact Phase 1 environment lock. Do not add or upgrade system or pip dependencies.
- Gazebo rendering is OGRE2/EGL server-only. Every product/live test command removes `DISPLAY`; never use `-g`, X11, Xvfb, VirtualGL, a desktop session, or a remote display.
- Set `ROS_LOCALHOST_ONLY=1`; tests use a unique `GZ_PARTITION=phase2-<run_id>` and PID-scoped cleanup.
- No Fuel lookup, external model download, public dataset download, third-party production model search, or untracked runtime cache is part of this phase.
- `substation_description` owns static asset/robot definitions. `substation_gazebo` owns raw simulated streams and scenario truth. Scenario truth never becomes a perception input.
- Required frames are `map -> odom -> base_footprint -> base_link -> camera_link -> camera_optical_frame`, `base_link -> laser_frame`, and `map -> asset/<asset_id>`. A child frame has one owner.
- Camera output is 640 × 480, `rgb8`, 15 Hz, frame `camera_optical_frame`; LiDAR is 360 samples, 10 Hz, frame `laser_frame`; odometry is 30 Hz with `odom` / `base_footprint`.
- The eight scenario IDs and DiagnosticArray key sets are copied exactly from `docs/INTERFACES.md` and the approved design spec.
- Runtime logs, frames, build/install/log trees, rosbag2, and acceptance payloads are not committed. Only source, configuration, tests, manifests, checksums, and status documents enter Git.
- The user's solo fast-track merges fine-grained plan tasks into two implementation checkpoints plus final evidence. Hard boundaries, hashes, process identity, tests, and phase completion evidence remain mandatory.

---

## Exact File Map

### Create

```text
configs/devices.yaml
ros2_ws/src/substation_description/package.xml
ros2_ws/src/substation_description/setup.cfg
ros2_ws/src/substation_description/setup.py
ros2_ws/src/substation_description/resource/substation_description
ros2_ws/src/substation_description/substation_description/__init__.py
ros2_ws/src/substation_description/substation_description/asset_registry.py
ros2_ws/src/substation_description/substation_description/asset_tf_broadcaster.py
ros2_ws/src/substation_description/urdf/inspection_robot.urdf.xacro
ros2_ws/src/substation_description/test/test_asset_registry.py
ros2_ws/src/substation_gazebo/package.xml
ros2_ws/src/substation_gazebo/setup.cfg
ros2_ws/src/substation_gazebo/setup.py
ros2_ws/src/substation_gazebo/resource/substation_gazebo
ros2_ws/src/substation_gazebo/substation_gazebo/__init__.py
ros2_ws/src/substation_gazebo/substation_gazebo/scenario_catalog.py
ros2_ws/src/substation_gazebo/substation_gazebo/scenario_manager.py
ros2_ws/src/substation_gazebo/config/bridge.yaml
ros2_ws/src/substation_gazebo/config/scenarios.yaml
ros2_ws/src/substation_gazebo/launch/substation_world.launch.py
ros2_ws/src/substation_gazebo/models/inspection_robot/model.config
ros2_ws/src/substation_gazebo/models/inspection_robot/model.sdf
ros2_ws/src/substation_gazebo/worlds/substation_world.sdf
ros2_ws/src/substation_gazebo/test/test_scenario_catalog.py
ros2_ws/src/substation_gazebo/test/test_scenario_engine.py
tests/world/test_world_contract.py
tests/world/probe_phase2_topics.py
tests/world/run_phase2_acceptance.sh
```

### Modify at each verified checkpoint

```text
docs/PROJECT_STATUS.md
docs/HANDOFF.md
```

## Task 1: Asset registry, robot description, and static Gazebo world

**Files:** Create `configs/devices.yaml`, all `substation_description` files, both SDF files, bridge configuration, `substation_gazebo` package metadata, and `tests/world/test_world_contract.py`; modify status/handoff after verification.

**Interfaces:**

- Produces `load_asset_registry(path: Path) -> AssetRegistry` with immutable `Asset` values.
- Produces `validate_asset_registry(registry: AssetRegistry) -> None`, raising `RegistryError` with a stable reason.
- Produces console script `asset_tf_broadcaster`, parameter `registry_path`, and static transforms `map -> asset/<asset_id>`.
- Produces installed `inspection_robot.urdf.xacro`, `inspection_robot/model.sdf`, `substation_world.sdf`, and `bridge.yaml` consumed by Task 2.

- [ ] **Step 1: Write failing registry and world contract tests**

Create tests that first fail because the packages and files do not exist. The registry tests must cover duplicate/invalid IDs, non-finite numbers, threshold order, missing meter metadata, and the approved 10-entry registry. The world test must parse XML/YAML rather than search unstructured text.

```python
# ros2_ws/src/substation_description/test/test_asset_registry.py
from pathlib import Path
import pytest
from substation_description.asset_registry import RegistryError, load_asset_registry

ROOT = Path(__file__).resolve().parents[4]

def test_project_registry_has_required_assets():
    registry = load_asset_registry(ROOT / "configs/devices.yaml")
    assert len(registry.assets) == 10
    assert len({a.category for a in registry.assets if a.category != "analog_meter"}) >= 8
    assert sum(a.category == "analog_meter" for a in registry.assets) == 2
    assert [a.asset_id for a in registry.assets] == sorted(a.asset_id for a in registry.assets)

def test_duplicate_asset_id_is_rejected(tmp_path):
    path = tmp_path / "devices.yaml"
    path.write_text("schema_version: 1\nassets:\n  - &a {asset_id: transformer-01}\n  - *a\n")
    with pytest.raises(RegistryError, match="ASSET_ID_DUPLICATE"):
        load_asset_registry(path)
```

```python
# tests/world/test_world_contract.py
from pathlib import Path
import xml.etree.ElementTree as ET
import yaml

ROOT = Path(__file__).resolve().parents[2]

def test_world_and_robot_sensor_contract():
    world = ET.parse(ROOT / "ros2_ws/src/substation_gazebo/worlds/substation_world.sdf")
    robot = ET.parse(ROOT / "ros2_ws/src/substation_gazebo/models/inspection_robot/model.sdf")
    names = {node.attrib["name"] for node in world.findall(".//model[@name]")}
    assets = yaml.safe_load((ROOT / "configs/devices.yaml").read_text())["assets"]
    assert {a["asset_id"] for a in assets}.issubset(names)
    assert robot.find(".//sensor[@type='camera']/topic").text == "camera/image_raw"
    assert robot.find(".//sensor[@type='camera']/gz_frame_id").text == "camera_optical_frame"
    assert robot.find(".//sensor[@type='gpu_lidar']/topic").text == "scan"
    assert robot.find(".//sensor[@type='gpu_lidar']/gz_frame_id").text == "laser_frame"

def test_bridge_contract_has_exact_directions():
    bridge = yaml.safe_load((ROOT / "ros2_ws/src/substation_gazebo/config/bridge.yaml").read_text())
    by_topic = {row["ros_topic_name"]: row for row in bridge}
    assert by_topic["clock"]["direction"] == "GZ_TO_ROS"
    assert by_topic["scan"]["ros_type_name"] == "sensor_msgs/msg/LaserScan"
    assert by_topic["cmd_vel"]["direction"] == "ROS_TO_GZ"
```

- [ ] **Step 2: Run the focused tests and record the expected red state**

```bash
set +u
source /opt/ros/jazzy/setup.bash
set -u
python3 -m pytest -q \
  ros2_ws/src/substation_description/test/test_asset_registry.py \
  tests/world/test_world_contract.py
```

Expected: nonzero exit with missing `substation_description` and missing Phase 2 files; no package installation or network access occurs.

- [ ] **Step 3: Implement registry types and validation**

Use frozen dataclasses and one parser boundary. Required public signatures are:

```python
class RegistryError(ValueError):
    pass

@dataclass(frozen=True)
class Pose:
    x: float
    y: float
    z: float
    roll: float
    pitch: float
    yaw: float

@dataclass(frozen=True)
class Asset:
    asset_id: str
    category: str
    report_name: str
    pose: Pose
    inspection_x: float
    inspection_y: float
    inspection_yaw: float
    thresholds: Mapping[str, Mapping[str, float]]
    meter: Mapping[str, object] | None

@dataclass(frozen=True)
class AssetRegistry:
    schema_version: int
    assets: tuple[Asset, ...]

def load_asset_registry(path: Path) -> AssetRegistry:
    """Load schema 1, validate all fields, and return assets sorted by asset_id."""
```

`configs/devices.yaml` must contain the exact IDs, categories, map/inspection positions, and common threshold example from the design. Both meters define stable sensor IDs, finite ranges, units, and normal bounds.

- [ ] **Step 4: Implement asset TF broadcaster and robot Xacro**

The node constructs `TransformStamped` values with parent `map`, child `asset/<asset_id>`, registry translation, and a normalized quaternion from authored roll/pitch/yaw. It publishes once through `StaticTransformBroadcaster` and exits only on shutdown.

The Xacro must contain these exact fixed joints and no alternate parent for the child frames:

```xml
<joint name="base_joint" type="fixed">
  <parent link="base_footprint"/><child link="base_link"/>
  <origin xyz="0 0 0.01" rpy="0 0 0"/>
</joint>
<joint name="camera_joint" type="fixed">
  <parent link="base_link"/><child link="camera_link"/>
  <origin xyz="0.073 -0.011 0.094" rpy="0 0 0"/>
</joint>
<joint name="camera_optical_joint" type="fixed">
  <parent link="camera_link"/><child link="camera_optical_frame"/>
  <origin xyz="0 0 0" rpy="-1.57079632679 0 -1.57079632679"/>
</joint>
<joint name="laser_joint" type="fixed">
  <parent link="base_link"/><child link="laser_frame"/>
  <origin xyz="-0.064 0 0.121" rpy="0 0 0"/>
</joint>
```

- [ ] **Step 5: Implement SDF robot, world, and bridge configuration**

The robot uses a `base_footprint`, physical `base_link`, two revolute wheel joints, caster contacts, a 15 Hz 640 × 480 `R8G8B8` camera, a 10 Hz/360-sample GPU LiDAR, DiffDrive at 30 Hz, and JointStatePublisher. The world contains Harmonic Physics, Sensors with `<render_engine>ogre2</render_engine>`, SceneBroadcaster, and UserCommands systems.

Use named primitive models for all 10 registry assets and the required layout markers/obstacles. Names are contract data, not decorative labels:

```xml
<model name="transformer-01"><static>true</static><!-- primitive links --></model>
<model name="inspection_lane_ns"><static>true</static><!-- non-colliding marking --></model>
<model name="transformer_exclusion_zone"><static>true</static><!-- red marking --></model>
<model name="scenario_dynamic_obstacle"><pose>0 0 -10 0 0 0</pose><!-- movable box --></model>
<include><uri>model://inspection_robot</uri><name>inspection_robot</name></include>
```

`bridge.yaml` defines clock, joint states, odom, TF, scan, CameraInfo, and command velocity with exact ROS/Gazebo types and directions. RGB is deliberately absent because `ros_gz_image image_bridge` owns it.

- [ ] **Step 6: Build and run the green static checkpoint**

```bash
set +u
source /opt/ros/jazzy/setup.bash
set -u
export ROS_LOCALHOST_ONLY=1
cd ros2_ws
rm -rf build/substation_description build/substation_gazebo \
  install/substation_description install/substation_gazebo
colcon build --symlink-install --packages-select substation_description substation_gazebo
source install/setup.bash
colcon test --packages-select substation_description substation_gazebo --event-handlers console_direct+
colcon test-result --verbose
cd ..
python3 -m pytest -q tests/world/test_world_contract.py
xacro ros2_ws/src/substation_description/urdf/inspection_robot.urdf.xacro >/tmp/phase2-inspection-robot.urdf
check_urdf /tmp/phase2-inspection-robot.urdf
```

Expected: both packages build, all tests pass, `colcon test-result` reports zero failures, world contract passes, and `check_urdf` reports a valid tree rooted at `base_footprint`.

- [ ] **Step 7: Record checkpoint truth, commit, and push**

Commit the source checkpoint first, then rerun its focused test against the exact commit:

```bash
git add configs ros2_ws/src/substation_description ros2_ws/src/substation_gazebo \
  tests/world/test_world_contract.py
git commit -m "feat: add phase two substation world foundation"
checkpoint_commit="$(git rev-parse HEAD)"
python3 -m pytest -q tests/world/test_world_contract.py
```

Update `PROJECT_STATUS.md` and `HANDOFF.md` with the literal `checkpoint_commit`, exact verification command/result, no running service, and Task 2 as next. Commit the status-only checkpoint and push both commits:

```bash
git add docs/PROJECT_STATUS.md docs/HANDOFF.md
git commit -m "docs: record phase two world foundation checkpoint"
git push origin main
```

## Task 2: Scenario engine, headless launch, and live topic acceptance

**Files:** Create scenario catalog/manager, launch, package tests, live probe/harness; modify package metadata/setup and status/handoff.

**Interfaces:**

- Consumes `configs/devices.yaml`, installed world/model/Xacro/bridge files, and the asset TF broadcaster from Task 1.
- Produces `ScenarioCatalog.load(path)`, `ScenarioEngine.apply(command, pose_setter)`, console script `scenario_manager`, `/scenario_manager/set_parameters_atomically`, environment/battery/truth/state topics, and the `substation_world.launch.py` entry.
- Produces `run_phase2_acceptance.sh --evidence-dir PATH [--run-id UUID]`, which is the Phase 2 executable acceptance entry.

- [ ] **Step 1: Write failing catalog and transactional state tests**

```python
# ros2_ws/src/substation_gazebo/test/test_scenario_engine.py
from pathlib import Path
from substation_gazebo.scenario_catalog import Command, ScenarioCatalog, ScenarioEngine

CATALOG = Path(__file__).resolve().parents[1] / "config/scenarios.yaml"

def test_apply_is_transactional_and_idempotent():
    engine = ScenarioEngine(ScenarioCatalog.load(CATALOG))
    moved = []
    command = Command(
        command_id="4ce58f68-1fcc-45e5-9834-1e3c674c57a8",
        scenario_id="temperature-high",
        action="trigger",
        parameters={"asset_id": "transformer-01", "temperature_celsius": 90.0},
    )
    first = engine.apply(command, lambda name, pose: moved.append((name, pose)) or True)
    replay = engine.apply(command, lambda name, pose: (_ for _ in ()).throw(AssertionError()))
    assert first.status == replay.status == "applied"
    assert first.revision == replay.revision == 1

def test_pose_failure_keeps_previous_complete_state():
    engine = ScenarioEngine(ScenarioCatalog.load(CATALOG))
    command = Command(
        command_id="e941fc04-d843-49e8-aa90-3ee0a20e8b59",
        scenario_id="fire-smoke",
        action="trigger",
        parameters={"asset_id": "transformer-01", "smoke_0_1": 0.8},
    )
    result = engine.apply(command, lambda name, pose: False)
    assert result.status == "failed"
    assert result.error_code == "GAZEBO_SET_POSE_FAILED"
    assert engine.revision == 0
    assert engine.active_scenario == "normal"
```

Also test exact eight IDs, parameter allowlists/ranges, unknown/nested/array rejection, invalid/reused UUIDs, `start|trigger|reset`, and exact DiagnosticArray value keys.

- [ ] **Step 2: Run tests and prove the red state**

```bash
set +u
source /opt/ros/jazzy/setup.bash
set -u
PYTHONPATH=ros2_ws/src/substation_gazebo \
  python3 -m pytest -q ros2_ws/src/substation_gazebo/test
```

Expected: nonzero exit because `scenario_catalog` and `scenario_manager` are not implemented.

- [ ] **Step 3: Implement catalog, command validation, and transaction engine**

Required pure interfaces:

```python
@dataclass(frozen=True)
class Command:
    command_id: str
    scenario_id: str
    action: str
    parameters: Mapping[str, str | int | float | bool]

@dataclass(frozen=True)
class ApplyResult:
    status: str
    revision: int
    active: bool
    scenario_id: str
    error_code: str

class ScenarioCatalog:
    @classmethod
    def load(cls, path: Path) -> "ScenarioCatalog": ...
    def validate(self, command: Command) -> None: ...

class ScenarioEngine:
    def apply(self, command: Command,
              pose_setter: Callable[[str, Pose], bool]) -> ApplyResult: ...
```

The engine caches `command_id -> canonical payload + result`, stages all value/pose changes before mutation, and increments revision only after every pose operation succeeds. `reset` returns all props below ground and restores catalog nominal values.

- [ ] **Step 4: Implement the ROS scenario manager**

The node uses explicit QoS profiles corresponding to `Q_SENSOR`, `Q_STATE`, `Q_EVENT`, and `Q_STREAM`. It declares the exact four command parameters and rejects partial updates in its atomic callback. Its publishers and rate are:

```python
self.temperature_pub = self.create_publisher(DiagnosticArray,
    "/simulation/environment/temperature_raw", q_sensor)
self.smoke_pub = self.create_publisher(DiagnosticArray,
    "/simulation/environment/smoke_raw", q_sensor)
self.gas_pub = self.create_publisher(DiagnosticArray,
    "/simulation/environment/gas_raw", q_sensor)
self.truth_pub = self.create_publisher(DiagnosticArray,
    "/simulation/scenario_truth", q_event)
self.state_pub = self.create_publisher(DiagnosticArray,
    "/simulation/scenario_state", q_state)
self.battery_pub = self.create_publisher(BatteryState, "/battery_state", q_stream)
self.create_timer(0.5, self.publish_environment)
self.create_timer(1.0, self.publish_truth_state_and_battery)
```

The Gazebo pose client is `ros_gz_interfaces/srv/SetEntityPose` at `/world/substation/set_pose`; every call has a bounded 2 s timeout. Diagnostics use exactly the field sets in `docs/INTERFACES.md`, stable quality level/message, and source ROS timestamps.

- [ ] **Step 5: Implement the headless launch entry**

The launch file declares `world`, `run_id`, and `gz_partition`, removes `DISPLAY`, forces localhost DDS, appends installed model paths to `GZ_SIM_RESOURCE_PATH`, and starts only these actions:

```python
UnsetEnvironmentVariable("DISPLAY")
SetEnvironmentVariable("ROS_LOCALHOST_ONLY", "1")
SetEnvironmentVariable("GZ_PARTITION", LaunchConfiguration("gz_partition"))
IncludeLaunchDescription(gz_sim, launch_arguments={
    "gz_args": ["-r -s -v 3 --headless-rendering ", world],
}.items())
Node(package="ros_gz_bridge", executable="parameter_bridge",
     parameters=[{"config_file": bridge_path}])
Node(package="ros_gz_bridge", executable="parameter_bridge",
     arguments=["/world/substation/set_pose@ros_gz_interfaces/srv/SetEntityPose"])
Node(package="ros_gz_image", executable="image_bridge", arguments=["/camera/image_raw"])
Node(package="robot_state_publisher", executable="robot_state_publisher",
     parameters=[{"use_sim_time": True, "robot_description": robot_description}])
Node(package="substation_description", executable="asset_tf_broadcaster",
     parameters=[{"registry_path": devices_path, "use_sim_time": True}])
Node(package="substation_gazebo", executable="scenario_manager",
     parameters=[{"catalog_path": scenarios_path, "registry_path": devices_path,
                  "run_id": LaunchConfiguration("run_id"), "use_sim_time": True}])
```

No GUI action or fallback display path exists.

- [ ] **Step 6: Implement the bounded live probe and acceptance harness**

`probe_phase2_topics.py` subscribes with contract-compatible QoS, collects at least two samples per required topic, validates messages/TF/scenario action, writes JSON atomically, and exits nonzero on a 90 s global timeout. It sets parameters atomically through the standard service, never publishes truth or raw sensor topics.

`run_phase2_acceptance.sh` must:

1. require an absolute, empty evidence directory outside Git;
2. record run ID, commit, dirty state, UTC time, free space, environment lock identity, and input SHA-256 values;
3. source ROS/workspace, set `ROS_LOCALHOST_ONLY=1`, unset `DISPLAY`, set a unique partition, and launch in a new process group;
4. run the probe with `timeout 120s` and capture all stdout/stderr;
5. record `/proc/<gz_pid>/environ` proof that `DISPLAY` is absent and command proof of `--headless-rendering`;
6. terminate only its recorded process group, wait, and fail if a matching process remains;
7. write JUnit, `result.json`, and `SHA256SUMS` only after all checks pass.

Core shell safety and cleanup shape:

```bash
set -euo pipefail
cleanup() {
  if [[ -n "${launch_pid:-}" ]] && kill -0 "$launch_pid" 2>/dev/null; then
    kill -- -"$launch_pid" 2>/dev/null || true
    wait "$launch_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM
setsid env -u DISPLAY ROS_LOCALHOST_ONLY=1 GZ_PARTITION="$partition" \
  ros2 launch substation_gazebo substation_world.launch.py \
  run_id:="$run_id" gz_partition:="$partition" >"$evidence/launch.log" 2>&1 &
launch_pid=$!
timeout 120s python3 tests/world/probe_phase2_topics.py --output "$evidence/topic-probe.json"
```

- [ ] **Step 7: Run unit/package/static tests and commit the implementation**

```bash
set +u
source /opt/ros/jazzy/setup.bash
set -u
export ROS_LOCALHOST_ONLY=1
cd ros2_ws
colcon build --symlink-install --packages-select substation_description substation_gazebo
source install/setup.bash
colcon test --packages-select substation_description substation_gazebo --event-handlers console_direct+
colcon test-result --verbose
cd ..
python3 -m pytest -q tests/world/test_world_contract.py
git diff --check
git add ros2_ws/src/substation_gazebo tests/world docs/PROJECT_STATUS.md docs/HANDOFF.md
git commit -m "feat: add headless phase two scenario runtime"
git push origin main
```

Expected: all non-live checks pass and the implementation commit is pushed before immutable live evidence is gathered.

- [ ] **Step 8: Run live acceptance against the clean implementation commit**

```bash
phase2_run_id="$(python3 -c 'import uuid; print(uuid.uuid4())')"
phase2_evidence="/var/lib/substation/evidence/acceptance/$phase2_run_id/02-gazebo-world.staging"
phase2_evidence_final="/var/lib/substation/evidence/acceptance/$phase2_run_id/02-gazebo-world"
sudo install -d -o "$(id -un)" -g "$(id -gn)" -m 0750 "$phase2_evidence"
bash tests/world/run_phase2_acceptance.sh \
  --run-id "$phase2_run_id" \
  --evidence-dir "$phase2_evidence"
test -d "$phase2_evidence_final"
phase2_evidence="$phase2_evidence_final"
```

Expected final lines: `phase2-topic-probe: PASS` and `phase2-acceptance: PASS`; `result.json.status` is `passed`, the tested commit equals `git rev-parse HEAD`, and no matching ROS/Gazebo process remains.

## Task 3: Seal Phase 2 status and hand off to Phase 3

**Files:** Modify only `docs/PROJECT_STATUS.md` and `docs/HANDOFF.md` after the verified implementation commit; the runtime evidence directory is renamed from staging to final by the acceptance harness only after checksum verification.

**Interfaces:** Consumes Task 2's immutable evidence; produces the truthful Phase 3 resume point.

- [ ] **Step 1: Verify evidence and extract literal identity values**

```bash
test -f "$phase2_evidence/result.json"
python3 - "$phase2_evidence/result.json" <<'PY'
import json, pathlib, sys
data = json.loads(pathlib.Path(sys.argv[1]).read_text())
assert data["status"] == "passed"
assert data["phase"] == "02-gazebo-world"
print(data["implementation_commit"])
print(data["completed_at"])
PY
(cd "$phase2_evidence" && sha256sum -c SHA256SUMS)
pgrep -af 'gz sim|ruby.*gz sim|substation_world|scenario_manager|parameter_bridge|image_bridge' && exit 1 || true
```

Expected: hashes pass and no Phase 2 process remains.

- [ ] **Step 2: Update current status and recovery entry**

Both documents record the same implementation commit, run ID, final evidence path, completed UTC time, exact final verification command, `passed` result, no running product services, and the distinction that the later documentation commit was not the implementation commit tested by Gazebo.

The next action is exactly: write and approve the Phase 3 SLAM/Nav2 design and plan using the locked Phase 2 world, then implement map generation, localization, inspection poses, and dynamic-obstacle navigation test-first. Do not claim Phase 3 behavior exists.

- [ ] **Step 3: Run documentation and repository consistency checks**

```bash
bash scripts/verify_documentation_gate.sh
git diff --check
git diff --name-only "$implementation_commit"..HEAD
rg -n 'Phase 2|02-gazebo-world|implementation commit|Phase 3|SLAM|Nav2' \
  docs/PROJECT_STATUS.md docs/HANDOFF.md
```

Expected: documentation gate passes; before the final commit, only the two status documents differ from the verified implementation commit.

- [ ] **Step 4: Commit and push the Phase 2 completion record**

```bash
git add docs/PROJECT_STATUS.md docs/HANDOFF.md
git commit -m "docs: record phase two gazebo world completion"
git push origin main
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
```

Expected: local and remote commit IDs match; the only tolerated unrelated local item is the pre-existing `.phase1-run.failed-*.env`; Phase 2 is complete and execution stops at the Phase 3 design boundary.

## Plan Self-Review

- The plan covers every requirement in the approved Phase 2 design: 10 stable assets, eight canonical equipment classes, two meters, yard/layout/hazards, robot geometry, camera/LiDAR/odom/TF, environment/battery, eight scenarios, atomic control, headless launch, QoS, idempotency, evidence, cleanup, status, and remote push.
- File ownership matches `docs/ARCHITECTURE.md`; raw truth remains isolated and no later-phase component is implemented.
- Public type names and signatures are consistent between Tasks 1 and 2.
- There are no runtime resource downloads, unbounded waits, generic process kills, or claims based only on static parsing.
- No unresolved placeholder remains; Phase 3 work is explicitly excluded rather than deferred inside Phase 2 code.
