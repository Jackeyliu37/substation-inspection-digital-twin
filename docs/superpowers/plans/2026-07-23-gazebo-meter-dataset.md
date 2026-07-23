# Gazebo Meter Locator Dataset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce and seal an AutoDL-ready ZIP containing exactly 2,000 Gazebo-derived, single-class YOLO meter-locator images with deterministic split isolation, rich ground truth, and immutable provenance.

**Architecture:** Pure planning, projection, validation, and packaging logic lives in ROS-free Python modules under `substation_gazebo`; a dedicated Gazebo Harmonic world supplies actual RGB frames, movable pressure/oil meter models, controllable needle joints, backgrounds, and occlusion. A bounded shell harness owns the unique Gazebo partition and process group, runs a live smoke gate, then generates the full dataset outside Git and seals it only after checksums and package validation pass.

**Tech Stack:** Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic `gz-sim 8.x`, OGRE2/EGL, Python 3.12, `rclpy`, `ros_gz_bridge`, `ros_gz_image`, OpenCV 4.11, PyYAML, NumPy 1.26, pytest, Bash, SHA-256, deterministic ZIP.

## Global Constraints

- Use the already locked Phase 1 environment; do not install or upgrade system, pip, ROS, Gazebo, CUDA, Node, or model dependencies.
- Every Gazebo command removes `DISPLAY`, uses OGRE2/EGL server-only mode, `ROS_LOCALHOST_ONLY=1`, a unique `GZ_PARTITION`, and PID/PGID-scoped cleanup.
- Instrument data is generated only by the project Gazebo chain. Do not download, include, composite from, or train against external meter images.
- The YOLO class set is exactly `{0: meter}`. Meter type, range, and unit come from `configs/devices.yaml`, not from the model class.
- The final dataset is exactly 2,000 640×480 images: pressure 1,000, oil 1,000; train 1,600, val 200, test 200.
- A scene group belongs to exactly one split. No image, source frame, scene group, view/light/background family tuple, or derived duplicate may cross split boundaries.
- Runtime data, generated images/labels/metadata, build/install/log trees, evidence, and ZIP files stay outside Git. Git contains only source, authored configuration, tests, manifests/checksums, design/plan, and status documents.
- Work directly on `main` as authorized by the user. Push the clean generator implementation before the full generation run, then generate against that immutable commit and push a later status/identity-only commit.

---

## Exact File Map

### Create

```text
configs/meter_dataset_generation.yaml
ros2_ws/src/substation_gazebo/config/meter_dataset_bridge.yaml
ros2_ws/src/substation_gazebo/launch/meter_dataset.launch.py
ros2_ws/src/substation_gazebo/models/synthetic_meter/model.config
ros2_ws/src/substation_gazebo/models/synthetic_meter/model.sdf
ros2_ws/src/substation_gazebo/worlds/meter_dataset_world.sdf
ros2_ws/src/substation_gazebo/substation_gazebo/meter_dataset_plan.py
ros2_ws/src/substation_gazebo/substation_gazebo/meter_dataset_projection.py
ros2_ws/src/substation_gazebo/substation_gazebo/meter_dataset_generator.py
ros2_ws/src/substation_gazebo/substation_gazebo/meter_dataset_package.py
ros2_ws/src/substation_gazebo/test/test_meter_dataset_plan.py
ros2_ws/src/substation_gazebo/test/test_meter_dataset_projection.py
ros2_ws/src/substation_gazebo/test/test_meter_dataset_package.py
tests/synthetic/test_meter_dataset_contract.py
tests/synthetic/run_meter_dataset_generation.sh
datasets/README.md
datasets/manifest.yaml
```

### Modify

```text
ros2_ws/src/substation_gazebo/package.xml
ros2_ws/src/substation_gazebo/setup.py
docs/PROJECT_STATUS.md
docs/HANDOFF.md
```

## Task 1: Deterministic sample plan, split contract, and projection math

**Files:**
- Create: `configs/meter_dataset_generation.yaml`
- Create: `ros2_ws/src/substation_gazebo/substation_gazebo/meter_dataset_plan.py`
- Create: `ros2_ws/src/substation_gazebo/substation_gazebo/meter_dataset_projection.py`
- Create: `ros2_ws/src/substation_gazebo/test/test_meter_dataset_plan.py`
- Create: `ros2_ws/src/substation_gazebo/test/test_meter_dataset_projection.py`

**Interfaces:**
- Consumes: `configs/devices.yaml`, authored generation configuration, and camera intrinsics.
- Produces: immutable `GenerationConfig`, `MeterContract`, `SamplePlan`, `CameraIntrinsics`, `Pose3D`, and `BoundingBox` values; `load_generation_config`, `build_sample_plan`, `project_dial`, and `validate_projection` used by Tasks 2–4.

- [ ] **Step 1: Write failing deterministic planning tests**

Create tests that assert two independent loads/builds are equal and that the full plan has the exact contract:

```python
def test_full_plan_is_balanced_group_isolated_and_deterministic():
    config = load_generation_config(CONFIG, DEVICES)
    first = build_sample_plan(config)
    second = build_sample_plan(config)
    assert first == second
    assert len(first) == 2000
    assert Counter(item.asset_id for item in first) == {
        "meter-pressure-01": 1000,
        "meter-oil-01": 1000,
    }
    assert Counter(item.split for item in first) == {
        "train": 1600, "val": 200, "test": 200,
    }
    ownership = defaultdict(set)
    for item in first:
        ownership[item.scene_group_id].add(item.split)
    assert len(ownership) == 100
    assert all(len(splits) == 1 for splits in ownership.values())
```

Also test that ranges/units are read from the registry, IDs and seeds are unique, readings remain within each configured range, paths are stable POSIX relative paths, the only class ID is zero, and non-finite/out-of-range/unknown config values fail with stable `MeterDatasetError` codes.

- [ ] **Step 2: Run the planning tests and record RED**

```bash
set +u
source /opt/ros/jazzy/setup.bash
set -u
PYTHONPATH=ros2_ws/src/substation_gazebo \
  python3 -m pytest -q \
  ros2_ws/src/substation_gazebo/test/test_meter_dataset_plan.py
```

Expected: nonzero exit because `meter_dataset_plan` and the authored config do not exist.

- [ ] **Step 3: Author the generation configuration**

Use schema 1 with these exact top-level values:

```yaml
schema_version: 1
dataset_id: gazebo-meter-locator-v1
scenario_id: gazebo-meter-locator
global_seed: 42
image: {width: 640, height: 480, format: rgb8}
class_names: {0: meter}
frames_per_group: 20
groups_per_meter: {train: 40, val: 5, test: 5}
meter_asset_ids: [meter-oil-01, meter-pressure-01]
minimum_bbox_pixels: 32
maximum_retries_per_sample: 8
fresh_frames_after_command: 3
view_families:
  distances_m: [0.65, 0.85, 1.05, 1.25, 1.45]
  yaw_degrees: [-28, -14, 0, 14, 28]
  pitch_degrees: [-18, -9, 0, 9, 18]
  roll_degrees: [-12, -6, 0, 6, 12]
light_families: [bright, nominal, low, warm, cool]
background_families: [industrial_light, industrial_dark, concrete]
occlusion_regimes: [none, edge_left, edge_right, partial_bottom]
postprocess:
  brightness_scales: [0.75, 0.9, 1.0, 1.1, 1.25]
  blur_sigmas: [0.0, 0.4, 0.8, 1.2]
```

Only asset IDs are authored here. Ranges, units, sensor IDs, and normal bounds must be loaded from `configs/devices.yaml`.

- [ ] **Step 4: Implement immutable planning types and validation**

Required public API:

```python
class MeterDatasetError(ValueError):
    pass

@dataclass(frozen=True)
class MeterContract:
    asset_id: str
    sensor_id: str
    minimum: float
    maximum: float
    unit: str

@dataclass(frozen=True)
class SamplePlan:
    sample_id: str
    split: str
    scene_group_id: str
    sample_index: int
    seed: int
    asset_id: str
    reading: float
    normalized_reading: float
    needle_angle_radians: float
    distance_m: float
    yaw_radians: float
    pitch_radians: float
    roll_radians: float
    light_family: str
    background_family: str
    occlusion_regime: str
    brightness_scale: float
    blur_sigma: float
    image_path: str
    label_path: str

@dataclass(frozen=True)
class GenerationConfig:
    schema_version: int
    dataset_id: str
    scenario_id: str
    global_seed: int
    width: int
    height: int
    class_names: Mapping[int, str]
    meters: Mapping[str, MeterContract]
    samples: tuple[SamplePlan, ...]

def load_generation_config(config_path: Path, registry_path: Path) -> GenerationConfig: ...
def build_sample_plan(config: GenerationConfig) -> tuple[SamplePlan, ...]: ...
```

Derive each per-sample RNG from SHA-256 of `global_seed`, `scene_group_id`, and frame index; do not depend on Python hash randomization. Map normalized readings onto a configurable needle sweep fixed at `[-2.35619449019, 2.35619449019]` radians.

- [ ] **Step 5: Write projection RED tests**

Use known pinhole intrinsics and fronto-parallel/tilted dial poses. Assert a centered 0.18 m radius dial at 1.0 m projects inside 640×480, increasing distance reduces the box, tilt changes corner geometry, a box below 32×32 is rejected, and any point behind the camera fails with `PROJECTION_BEHIND_CAMERA`.

- [ ] **Step 6: Implement projection and label validation**

Required public API:

```python
@dataclass(frozen=True)
class CameraIntrinsics:
    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float

@dataclass(frozen=True)
class Pose3D:
    x: float; y: float; z: float
    roll: float; pitch: float; yaw: float

@dataclass(frozen=True)
class BoundingBox:
    x_min: float; y_min: float; x_max: float; y_max: float

@dataclass(frozen=True)
class Projection:
    bbox_pixels: BoundingBox
    bbox_yolo: tuple[float, float, float, float]
    dial_corners_pixels: tuple[tuple[float, float], ...]

def project_dial(intrinsics: CameraIntrinsics, pose_camera: Pose3D,
                 radius_m: float, boundary_points: int = 64) -> Projection: ...
def validate_projection(projection: Projection, minimum_bbox_pixels: int) -> None: ...
```

Sample 64 points on the known face circle, transform them into the optical frame, project with CameraInfo, clamp nothing silently, and reject boxes outside the image or below the minimum size.

- [ ] **Step 7: Run Task 1 GREEN tests and commit**

```bash
PYTHONPATH=ros2_ws/src/substation_gazebo \
  python3 -m pytest -q \
  ros2_ws/src/substation_gazebo/test/test_meter_dataset_plan.py \
  ros2_ws/src/substation_gazebo/test/test_meter_dataset_projection.py
git diff --check
git add configs/meter_dataset_generation.yaml \
  ros2_ws/src/substation_gazebo/substation_gazebo/meter_dataset_plan.py \
  ros2_ws/src/substation_gazebo/substation_gazebo/meter_dataset_projection.py \
  ros2_ws/src/substation_gazebo/test/test_meter_dataset_plan.py \
  ros2_ws/src/substation_gazebo/test/test_meter_dataset_projection.py
git commit -m "feat: add deterministic meter dataset planning"
```

## Task 2: Dedicated Gazebo world and live capture generator

**Files:**
- Create: `ros2_ws/src/substation_gazebo/models/synthetic_meter/model.config`
- Create: `ros2_ws/src/substation_gazebo/models/synthetic_meter/model.sdf`
- Create: `ros2_ws/src/substation_gazebo/worlds/meter_dataset_world.sdf`
- Create: `ros2_ws/src/substation_gazebo/config/meter_dataset_bridge.yaml`
- Create: `ros2_ws/src/substation_gazebo/launch/meter_dataset.launch.py`
- Create: `ros2_ws/src/substation_gazebo/substation_gazebo/meter_dataset_generator.py`
- Create: `tests/synthetic/test_meter_dataset_contract.py`
- Modify: `ros2_ws/src/substation_gazebo/package.xml`
- Modify: `ros2_ws/src/substation_gazebo/setup.py`

**Interfaces:**
- Consumes: Task 1 sample plans and projection API, `configs/devices.yaml`, CameraInfo/Image, `SetEntityPose`, two `std_msgs/Float64` needle command topics, and joint state feedback.
- Produces: installed `meter_dataset.launch.py`, console script `meter_dataset_generator`, per-sample images/labels/metadata, and `generation-result.json` in an absolute empty staging directory.

- [ ] **Step 1: Write failing SDF/launch/generator contract tests**

Parse XML/YAML/AST rather than relying on broad string search. Tests assert:

```python
assert world_name == "meter_dataset"
assert camera_width == "640" and camera_height == "480"
assert render_engine == "ogre2"
assert model_names >= {
    "synthetic_meter_pressure", "synthetic_meter_oil",
    "meter_occluder", "background_industrial_light",
    "background_industrial_dark", "background_concrete",
}
assert needle_bridge_topics == {
    "/meter_dataset/pressure/needle_cmd",
    "/meter_dataset/oil/needle_cmd",
}
```

The launch AST must contain `UnsetEnvironmentVariable("DISPLAY")`, `--headless-rendering`, localhost DDS, unique partition input, the topic/service/image bridges, and `meter_dataset_generator`. Package metadata must install the world/model/config/launch and declare `cv_bridge`, `std_msgs`, `sensor_msgs`, `ros_gz_interfaces`, and `substation_description` runtime dependencies.

- [ ] **Step 2: Run RED contracts**

```bash
python3 -m pytest -q tests/synthetic/test_meter_dataset_contract.py
```

Expected: nonzero exit because the dedicated world, model, launch, and generator do not exist.

- [ ] **Step 3: Implement the synthetic meter model and world**

Create two world-level meter instances from one repository-owned model. The model contains:

- a 0.18 m radius case, high-contrast face, tick primitives, center hub, and needle;
- a revolute `needle_joint` whose axis is normal to the dial face;
- `JointPositionController` using installed `gz-sim-joint-position-controller-system`; the reusable model leaves `<topic>` unset so Harmonic creates instance-scoped default command topics for `synthetic_meter_pressure` and `synthetic_meter_oil`;
- `JointStatePublisher` feedback on `/meter_dataset/joint_states`;
- no Fuel URI, external mesh, external texture, or runtime network lookup.

The world includes Physics, Sensors with `<render_engine>ogre2</render_engine>`, SceneBroadcaster, UserCommands, fixed camera rig, three repository-owned background panels, a movable occluder, ground, and fixed lights. Inactive meters/backgrounds/occluder begin below ground.

- [ ] **Step 4: Implement bridge and launch**

`meter_dataset_bridge.yaml` declares only clock, CameraInfo, joint-state feedback, and two ROS-to-Gazebo `std_msgs/msg/Float64 -> gz.msgs.Double` mappings. Their ROS names are `/meter_dataset/pressure/needle_cmd` and `/meter_dataset/oil/needle_cmd`; their Gazebo names are the instance-scoped `/model/synthetic_meter_pressure/joint/needle_joint/0/cmd_pos` and `/model/synthetic_meter_oil/joint/needle_joint/0/cmd_pos`. RGB uses `ros_gz_image`; pose uses:

```text
/world/meter_dataset/set_pose@ros_gz_interfaces/srv/SetEntityPose
```

The launch arguments are exactly `run_id`, `output_dir`, `generation_config`, `registry_path`, `expected_commit`, `sample_mode`, and `gz_partition`. `sample_mode` is `smoke|full`; normal product launch does not start this generator.

- [ ] **Step 5: Implement bounded live generation**

`MeterDatasetGenerator(Node)` must:

1. require a UUIDv4 `run_id`, absolute empty `.staging` output directory outside Git, clean `expected_commit`, and valid sample mode;
2. subscribe to Image, CameraInfo, and joint states with compatible QoS;
3. use `SetEntityPose` to show exactly one meter/background and place/hide the occluder;
4. publish the planned needle angle, wait until joint feedback is within 0.02 radians, then discard the configured number of fresh frames;
5. require a new non-uniform 640×480 `rgb8` frame, compute projection, apply deterministic brightness/blur, and revalidate decode/dimensions;
6. atomically write `.png`, one-line `0 x_center y_center width height` label, and canonical metadata;
7. print progress at frame 1 and every 100 accepted frames;
8. bound every service/frame/joint wait to 5 seconds, every sample to eight retries, and the full node run to 40 minutes;
9. write `generation-result.json` with accepted/rejected counts and stable rejection reasons, exiting nonzero on any incomplete count.

Smoke mode selects exactly 12 deterministic samples spanning both meter types and all three splits; full mode uses all 2,000 plans.

- [ ] **Step 6: Build, test static contracts, and commit**

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
python3 -m pytest -q tests/synthetic/test_meter_dataset_contract.py
git diff --check
git add ros2_ws/src/substation_gazebo tests/synthetic/test_meter_dataset_contract.py
git commit -m "feat: add headless gazebo meter capture"
```

## Task 3: Dataset validation, deterministic packaging, and live smoke gate

**Files:**
- Create: `ros2_ws/src/substation_gazebo/substation_gazebo/meter_dataset_package.py`
- Create: `ros2_ws/src/substation_gazebo/test/test_meter_dataset_package.py`
- Create: `tests/synthetic/run_meter_dataset_generation.sh`
- Modify: `ros2_ws/src/substation_gazebo/setup.py`

**Interfaces:**
- Consumes: Task 2 output directory, generation result, full sample plan, clean Git commit, authored inputs, and runtime version evidence.
- Produces: console script `meter_dataset_package`, deterministic `file-manifest.tsv`, `dataset-manifest.yaml`, `SHA256SUMS`, `README-AutoDL.md`, ZIP, JUnit/result evidence, and a final directory renamed from staging only after all gates pass.

- [ ] **Step 1: Write failing validator/package tests**

Create tiny synthetic fixtures and assert rejection of missing/extra images, invalid PNGs, wrong dimensions, unknown class IDs, malformed/unsafe labels, label boxes outside `(0,1]`, duplicate image hashes, cross-split scene groups, metadata mismatch, non-finite readings, wrong meter range/unit, unsafe paths, unsorted manifests, bad SHA-256, nondeterministic ZIP timestamps, and incomplete result files.

The happy-path fixture must produce byte-identical ZIP SHA-256 values across two package runs.

- [ ] **Step 2: Run package tests and record RED**

```bash
PYTHONPATH=ros2_ws/src/substation_gazebo \
  python3 -m pytest -q \
  ros2_ws/src/substation_gazebo/test/test_meter_dataset_package.py
```

Expected: nonzero exit because `meter_dataset_package` is absent.

- [ ] **Step 3: Implement validation and packaging**

Required public API:

```python
@dataclass(frozen=True)
class DatasetSummary:
    total_images: int
    split_counts: Mapping[str, int]
    asset_counts: Mapping[str, int]
    file_manifest_sha256: str
    metadata_sha256: str
    zip_sha256: str
    zip_size_bytes: int

def validate_generated_dataset(root: Path, config: GenerationConfig,
                               sample_mode: str) -> DatasetSummary: ...
def write_file_manifest(root: Path, included_paths: Sequence[Path]) -> str: ...
def write_dataset_manifest(root: Path, summary: DatasetSummary,
                           provenance: Mapping[str, object]) -> Path: ...
def create_deterministic_zip(dataset_root: Path, output_path: Path) -> tuple[str, int]: ...
```

Use sorted POSIX paths, safe relative path checks, canonical JSONL, PNG decode, and exact label parsing. ZIP entries use fixed timestamp `1980-01-01T00:00:00`, fixed Unix modes, sorted paths, and Deflate level 6. The file manifest lists dataset payload files but excludes itself, `dataset-manifest.yaml`, and `SHA256SUMS` to avoid cycles; `SHA256SUMS` then covers every packaged file except itself.

Generate `README-AutoDL.md` with exact commands:

```bash
unzip gazebo-meter-locator-v1.zip
cd gazebo-meter-locator-v1
sha256sum -c SHA256SUMS
yolo detect train data=data.yaml model=yolo11n.pt imgsz=640 epochs=100 batch=8 device=0 workers=6 seed=42 patience=20
```

- [ ] **Step 4: Implement the shell harness**

CLI:

```text
bash tests/synthetic/run_meter_dataset_generation.sh \
  --mode smoke|full \
  --run-id UUID \
  --output-dir /var/lib/substation/datasets/synthetic/gazebo-meter/<generation-id>.staging
```

The harness verifies an absolute empty non-symlink staging directory, at least 20 GiB residual free space, a clean tracked worktree, current commit identity, and the Phase 1 environment seal. It computes `generation-id` from the commit, input hashes, versions, and plan seed list; rejects a mismatched output basename; starts `ros2 launch ... meter_dataset.launch.py` using `setsid env -u DISPLAY`; enforces `timeout 45m`; records the exact process tree and Gazebo environment; runs the package validator; terminates only the recorded PGID even if the launch leader exits; checks zero residual matching processes; writes JUnit/result/SHA-256 evidence; then atomically renames `.staging` to final.

- [ ] **Step 5: Run unit/static gates**

```bash
set +u
source /opt/ros/jazzy/setup.bash
set -u
cd ros2_ws
colcon build --symlink-install --packages-select substation_description substation_gazebo
source install/setup.bash
colcon test --packages-select substation_description substation_gazebo --event-handlers console_direct+
colcon test-result --verbose
cd ..
python3 -m pytest -q tests/synthetic/test_meter_dataset_contract.py
git diff --check
```

- [ ] **Step 6: Run the live smoke gate**

```bash
smoke_run_id="$(python3 -c 'import uuid; print(uuid.uuid4())')"
smoke_generation_id="$(PYTHONPATH=ros2_ws/src/substation_gazebo python3 -m substation_gazebo.meter_dataset_package identity --config configs/meter_dataset_generation.yaml --mode smoke)"
smoke_dir="/var/lib/substation/datasets/synthetic/gazebo-meter/${smoke_generation_id}.staging"
install -d -m 0750 "$smoke_dir"
bash tests/synthetic/run_meter_dataset_generation.sh \
  --mode smoke --run-id "$smoke_run_id" --output-dir "$smoke_dir"
```

Expected final lines: `meter-dataset-smoke: PASS` and `meter-dataset-package: PASS`; 12 images/labels span both meters and all splits, non-uniform RGB and changing needle pixels are proven, hashes pass, and no process remains.

- [ ] **Step 7: Commit, update checkpoint status, and push clean generator source**

```bash
git add ros2_ws/src/substation_gazebo/substation_gazebo/meter_dataset_package.py \
  ros2_ws/src/substation_gazebo/test/test_meter_dataset_package.py \
  ros2_ws/src/substation_gazebo/setup.py \
  tests/synthetic/run_meter_dataset_generation.sh \
  docs/PROJECT_STATUS.md docs/HANDOFF.md
git commit -m "feat: add sealed meter dataset generation"
git push origin main
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
```

Status documents record the exact source commit, smoke run ID/path, test commands/results, zero services, and full generation as next. Failed smoke runs remain immutable staging evidence.

## Task 4: Generate, seal, and hand off the 2,000-image AutoDL ZIP

**Files:**
- Create: `datasets/README.md`
- Create: `datasets/manifest.yaml`
- Modify: `docs/PROJECT_STATUS.md`
- Modify: `docs/HANDOFF.md`

**Interfaces:**
- Consumes: the clean pushed Task 3 generator commit and locked environment.
- Produces: immutable full dataset directory and ZIP under `/var/lib/substation/datasets/synthetic/gazebo-meter/`, repository identity records, and an exact AutoDL handoff path/checksum.

- [ ] **Step 1: Create the full empty staging directory**

```bash
full_run_id="$(python3 -c 'import uuid; print(uuid.uuid4())')"
full_generation_id="$(PYTHONPATH=ros2_ws/src/substation_gazebo python3 -m substation_gazebo.meter_dataset_package identity --config configs/meter_dataset_generation.yaml --mode full)"
full_staging="/var/lib/substation/datasets/synthetic/gazebo-meter/${full_generation_id}.staging"
full_final="/var/lib/substation/datasets/synthetic/gazebo-meter/${full_generation_id}"
install -d -m 0750 "$full_staging"
```

- [ ] **Step 2: Run full bounded generation**

```bash
bash tests/synthetic/run_meter_dataset_generation.sh \
  --mode full --run-id "$full_run_id" --output-dir "$full_staging"
test -d "$full_final"
```

Expected final lines: `meter-dataset-full: PASS` and `meter-dataset-package: PASS`.

- [ ] **Step 3: Verify full content and package identity**

```bash
python3 - "$full_final/dataset/gazebo-meter-locator-v1/dataset-manifest.yaml" <<'PY'
from pathlib import Path
import sys, yaml
data = yaml.safe_load(Path(sys.argv[1]).read_text())
assert data["status"] == "accepted"
assert data["total_images"] == 2000
assert data["split_counts"] == {"train": 1600, "val": 200, "test": 200}
assert data["asset_counts"] == {"meter-oil-01": 1000, "meter-pressure-01": 1000}
print(data["generator_git_commit"])
print(data["zip_sha256"])
PY
(cd "$full_final/dataset/gazebo-meter-locator-v1" && sha256sum -c SHA256SUMS)
unzip -t "$full_final/gazebo-meter-locator-v1.zip"
```

Also confirm the manifest commit equals the current clean `HEAD`, the ZIP hash/size match, and no matching Gazebo/generator process exists.

- [ ] **Step 4: Record the accepted synthetic source in Git**

`datasets/manifest.yaml` records schema 1 source `gazebo-meter`, revision type `generated`, the literal generation ID, accepted status, project-owned permitted use, exact counts, file manifest SHA-256/path, split/content manifest hashes, generator commit, world/config/registry hashes, seed plan hash, ZIP SHA-256/size, and the absolute server handoff path. It does not copy images or absolute AutoDL paths into Git.

`datasets/README.md` states that the repository does not contain the ZIP and gives the server path, verification command, AutoDL extraction/training command, single class order, and the rule that range/unit come from asset configuration.

- [ ] **Step 5: Update status and run final gates**

Both status documents record the generator commit, full run ID, generation ID, final directory, ZIP path/hash/size, completion UTC time, exact verification command/result, zero running services, and the next action: the user uploads the ZIP to AutoDL and trains `meter_locator`; project execution then returns to Phase 3 SLAM/Nav2.

```bash
bash scripts/verify_documentation_gate.sh
git diff --check
python3 -m pytest -q \
  ros2_ws/src/substation_gazebo/test/test_meter_dataset_plan.py \
  ros2_ws/src/substation_gazebo/test/test_meter_dataset_projection.py \
  ros2_ws/src/substation_gazebo/test/test_meter_dataset_package.py \
  tests/synthetic/test_meter_dataset_contract.py
```

- [ ] **Step 6: Commit and push the handoff record**

```bash
git add datasets/README.md datasets/manifest.yaml \
  docs/PROJECT_STATUS.md docs/HANDOFF.md
git commit -m "docs: record gazebo meter dataset handoff"
git push origin main
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
git status --short --branch
```

The only tolerated unrelated local item remains the pre-existing `.phase1-run.failed-*.env`. Stop after reporting the final ZIP path, SHA-256, size, exact AutoDL command, generator commit, and remote status.

## Plan Self-Review

- The plan implements every approved design requirement: actual Gazebo rendering, one `meter` class, exact 2,000/1,000/1,000/1,600/200/200 counts, group isolation, rich metadata, checksums, deterministic ZIP, AutoDL instructions, no external meter data, and no runtime cache in Git.
- Range/unit ownership stays in `configs/devices.yaml`; training labels contain only class zero and normalized boxes.
- Pure planning/projection/packaging code is independently testable before live Gazebo, and live generation has bounded waits, retries, global timeout, unique partition, and PGID cleanup.
- The generator source is pushed before the full run, so every image and manifest refers to an immutable clean commit; the later Git commit only records the external artifact identity.
- No Phase 3 navigation or Phase 4 perception runtime is implemented or claimed.
