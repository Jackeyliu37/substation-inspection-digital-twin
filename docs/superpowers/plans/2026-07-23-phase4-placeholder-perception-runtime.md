# Phase 4 Placeholder Perception Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a tested headless ROS 2 YOLO11 development pipeline using only the locked official base weight, with no path for placeholder output to enter production perception Topics.

**Architecture:** `substation_perception` separates immutable model verification, lazy Ultralytics inference, ROS message conversion, and the image node. The node emits only two development Topics and diagnostics. A bounded smoke reuses the existing Gazebo camera and seals evidence outside Git.

**Tech Stack:** Ubuntu 24.04, ROS 2 Jazzy, Python 3.12, rclpy, cv_bridge, vision_msgs, diagnostic_msgs, NumPy, OpenCV, Ultralytics, pytest, colcon.

## Global Constraints

- Use Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic and OGRE2/EGL headless operation only.
- Keep `ROS_LOCALHOST_ONLY=1`; production consumers must not subscribe to development output.
- Weight path is `/var/lib/substation/models/base/0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1/yolo11n.pt`, SHA-256 is `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`, and size is `5613764` bytes.
- Accept only `runtime_mode=development_placeholder`, `production_ready=false`, and logical model `yolo11n_base`; runtime code never downloads weights.
- Use only `placeholder/coco/<normalized-class>`, `/perception/development/detections`, `/perception/development/annotated_image`, and `/diagnostics`.
- Never read `/simulation/scenario_truth` or create production model aliases.
- Start every behavior with a failing test and commit each independently testable task.
- Phase 4 completion and production acceptance remain blocked on the four user-trained artifacts.

## File Structure

- `ros2_ws/src/substation_perception/substation_perception/model_identity.py`: immutable placeholder identity gate.
- `ros2_ws/src/substation_perception/substation_perception/yolo_backend.py`: lazy injectable Ultralytics adapter.
- `ros2_ws/src/substation_perception/substation_perception/detection_contract.py`: bounded ROS detection conversion.
- `ros2_ws/src/substation_perception/substation_perception/placeholder_node.py`: latest-frame worker and diagnostics.
- `ros2_ws/src/substation_perception/launch/placeholder_perception.launch.py`: locked headless launch.
- `ros2_ws/src/substation_perception/test/`: package unit and launch-contract tests.
- `tests/perception/`: bounded live probe and evidence-producing smoke.

---

### Task 1: Package and Immutable Model Identity

**Files:**
- Create: `ros2_ws/src/substation_perception/package.xml`
- Create: `ros2_ws/src/substation_perception/setup.py`
- Create: `ros2_ws/src/substation_perception/setup.cfg`
- Create: `ros2_ws/src/substation_perception/resource/substation_perception`
- Create: `ros2_ws/src/substation_perception/substation_perception/__init__.py`
- Create: `ros2_ws/src/substation_perception/substation_perception/model_identity.py`
- Test: `ros2_ws/src/substation_perception/test/test_model_identity.py`

**Interfaces:**
- Produces `VerifiedModel(path: Path, sha256: str, size_bytes: int)` and `verify_development_placeholder(path, expected_path, expected_sha256, expected_size_bytes, runtime_mode, logical_model, production_ready) -> VerifiedModel`.
- Raises `ModelIdentityError` with stable codes `PLACEHOLDER_IDENTITY_INVALID`, `MODEL_PATH_INVALID`, `MODEL_SIZE_MISMATCH`, and `MODEL_SHA256_MISMATCH`.

- [ ] **Step 1: Write failing identity tests**

```python
def test_accepts_exact_identity(tmp_path):
    weights = tmp_path / "yolo11n.pt"
    weights.write_bytes(b"locked")
    result = verify_development_placeholder(
        weights, weights, hashlib.sha256(b"locked").hexdigest(), 6,
        "development_placeholder", "yolo11n_base", False,
    )
    assert result.path == weights.resolve()

def test_rejects_production_mode(tmp_path):
    weights = tmp_path / "yolo11n.pt"
    weights.write_bytes(b"locked")
    with pytest.raises(ModelIdentityError, match="PLACEHOLDER_IDENTITY_INVALID"):
        verify_development_placeholder(
            weights, weights, hashlib.sha256(b"locked").hexdigest(), 6,
            "production", "yolo11n_base", False,
        )
```

```python
@pytest.mark.parametrize("field,value,code", [
    ("logical_model", "yolo11n_safety", "PLACEHOLDER_IDENTITY_INVALID"),
    ("production_ready", True, "PLACEHOLDER_IDENTITY_INVALID"),
    ("expected_size_bytes", 7, "MODEL_SIZE_MISMATCH"),
    ("expected_sha256", "0" * 64, "MODEL_SHA256_MISMATCH"),
])
def test_rejects_changed_identity_field(tmp_path, field, value, code):
    weights = tmp_path / "yolo11n.pt"
    weights.write_bytes(b"locked")
    values = dict(expected_size_bytes=6,
                  expected_sha256=hashlib.sha256(b"locked").hexdigest(),
                  logical_model="yolo11n_base", production_ready=False)
    values[field] = value
    with pytest.raises(ModelIdentityError, match=code):
        verify_development_placeholder(
            weights, weights, values["expected_sha256"],
            values["expected_size_bytes"], "development_placeholder",
            values["logical_model"], values["production_ready"],
        )
```

Use dedicated assertions for a missing file, a different resolved path, and a non-`.pt` suffix because those enter path validation before bytes are read.

- [ ] **Step 2: Verify red**

Run: `source /opt/ros/jazzy/setup.bash && PYTHONPATH=$PWD/ros2_ws/src/substation_perception python3 -m pytest -q ros2_ws/src/substation_perception/test/test_model_identity.py`

Expected: collection fails because `model_identity` does not exist.

- [ ] **Step 3: Implement the minimum identity gate and ament package metadata**

```python
@dataclass(frozen=True)
class VerifiedModel:
    path: Path
    sha256: str
    size_bytes: int

def verify_development_placeholder(path, expected_path, expected_sha256,
                                   expected_size_bytes, runtime_mode,
                                   logical_model, production_ready):
    if (runtime_mode, logical_model, production_ready) != (
        "development_placeholder", "yolo11n_base", False
    ):
        raise ModelIdentityError("PLACEHOLDER_IDENTITY_INVALID")
    resolved = Path(path).resolve(strict=True)
    if resolved != Path(expected_path).resolve(strict=True) or resolved.suffix != ".pt":
        raise ModelIdentityError("MODEL_PATH_INVALID")
    if resolved.stat().st_size != expected_size_bytes:
        raise ModelIdentityError("MODEL_SIZE_MISMATCH")
    with resolved.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != expected_sha256:
        raise ModelIdentityError("MODEL_SHA256_MISMATCH")
    return VerifiedModel(resolved, digest, expected_size_bytes)
```

Declare ROS message/runtime dependencies and `ament_pytest`; do not declare Ultralytics as an apt dependency.

- [ ] **Step 4: Verify green and commit**

Run the Step 2 command; expect all identity tests to pass.

```bash
git add ros2_ws/src/substation_perception
git commit -m "feat: add placeholder model identity gate"
```

### Task 2: Lazy Injectable YOLO Adapter

**Files:**
- Create: `ros2_ws/src/substation_perception/substation_perception/yolo_backend.py`
- Test: `ros2_ws/src/substation_perception/test/test_yolo_backend.py`

**Interfaces:**
- Consumes Task 1 `VerifiedModel` and an RGB `numpy.ndarray`.
- Produces `RawDetection(class_id: int, class_name: str, score: float, xyxy: tuple[float, float, float, float])` and `YoloBackend.infer(image_rgb) -> list[RawDetection]`.

- [ ] **Step 1: Write failing adapter tests**

```python
def test_loads_once_and_returns_framework_neutral_boxes(verified_model):
    created = []
    backend = YoloBackend(verified_model, model_factory=fake_factory(created))
    image = np.zeros((32, 48, 3), dtype=np.uint8)
    assert backend.infer(image)[0].class_name == "fire extinguisher"
    assert backend.infer(image)[0].score == 0.75
    assert len(created) == 1

def test_rejects_non_rgb_input(verified_model):
    backend = YoloBackend(verified_model, model_factory=fake_factory([]))
    with pytest.raises(BackendError, match="IMAGE_RGB_INVALID"):
        backend.infer(np.zeros((10, 10), dtype=np.uint8))
```

Fake results expose `names`, `boxes.cls`, `boxes.conf`, and `boxes.xyxy`. Cover strict result handling with:

```python
@pytest.mark.parametrize("results", [[], [FakeResult(), FakeResult()]])
def test_requires_exactly_one_result(verified_model, results):
    backend = YoloBackend(verified_model, model_factory=factory_returning(results))
    with pytest.raises(BackendError, match="YOLO_OUTPUT_INVALID"):
        backend.infer(np.zeros((10, 10, 3), dtype=np.uint8))

def test_empty_boxes_are_valid(verified_model):
    backend = YoloBackend(verified_model, model_factory=empty_factory())
    assert backend.infer(np.zeros((10, 10, 3), dtype=np.uint8)) == []
```

Parameterized fake box values cover an unknown class index, unequal tensor lengths and `NaN` coordinates; each must raise `YOLO_OUTPUT_INVALID`.

- [ ] **Step 2: Verify red**

Run: `source /opt/ros/jazzy/setup.bash && PYTHONPATH=$PWD/ros2_ws/src/substation_perception python3 -m pytest -q ros2_ws/src/substation_perception/test/test_yolo_backend.py`

Expected: import fails because `yolo_backend` does not exist.

- [ ] **Step 3: Implement lazy load and strict parsing**

```python
class YoloBackend:
    def __init__(self, identity: VerifiedModel, model_factory=None):
        self._identity = identity
        self._factory = model_factory
        self._loaded = None

    def _model(self):
        if self._loaded is None:
            factory = self._factory
            if factory is None:
                from ultralytics import YOLO
                factory = YOLO
            self._loaded = factory(str(self._identity.path))
        return self._loaded

    def infer(self, image_rgb):
        if image_rgb.dtype != np.uint8 or image_rgb.ndim != 3 or image_rgb.shape[2] != 3:
            raise BackendError("IMAGE_RGB_INVALID")
        results = self._model()(image_rgb, verbose=False)
        return _parse_single_result(results)
```

`_parse_single_result` requires exactly one result, uses `detach().cpu().tolist()` when available, validates equal list lengths and finite values, maps through `result.names`, and raises `YOLO_OUTPUT_INVALID` for malformed output. No import-time model load or network call is permitted.

- [ ] **Step 4: Verify green and commit**

Run the Step 2 command; expect all adapter tests to pass without importing Ultralytics.

```bash
git add ros2_ws/src/substation_perception
git commit -m "feat: add lazy placeholder yolo backend"
```

### Task 3: Development Detection Message Contract

**Files:**
- Create: `ros2_ws/src/substation_perception/substation_perception/detection_contract.py`
- Test: `ros2_ws/src/substation_perception/test/test_detection_contract.py`

**Interfaces:**
- Consumes a `std_msgs/msg/Header`, image dimensions, and Task 2 `RawDetection` values.
- Produces `to_development_detections(header, image_width, image_height, detections) -> Detection2DArray`.

- [ ] **Step 1: Write failing conversion tests**

```python
def test_preserves_header_clips_box_and_prefixes_class():
    header = Header(frame_id="camera_optical_frame")
    header.stamp.sec = 17
    output = to_development_detections(header, 100, 80, [
        RawDetection(4, "Fire Extinguisher", 0.75, (-5.0, 5.0, 120.0, 60.0)),
    ])
    item = output.detections[0]
    assert output.header == header
    assert item.id == "development-000000"
    assert item.results[0].hypothesis.class_id == "placeholder/coco/fire_extinguisher"
    assert item.bbox.center.position.x == 50.0
    assert item.bbox.size_x == 100.0
```

Add one test each for empty names, scores outside `[0,1]`, non-finite coordinates, reversed boxes, fully off-image boxes, and zero image dimensions; invalid candidates must not produce messages.

- [ ] **Step 2: Verify red**

Run: `source /opt/ros/jazzy/setup.bash && PYTHONPATH=$PWD/ros2_ws/src/substation_perception python3 -m pytest -q ros2_ws/src/substation_perception/test/test_detection_contract.py`

Expected: import fails because `detection_contract` does not exist.

- [ ] **Step 3: Implement bounded conversion**

```python
def to_development_detections(header, image_width, image_height, detections):
    output = Detection2DArray(header=header)
    for ordinal, candidate in enumerate(detections):
        normalized = normalize_class_name(candidate.class_name)
        bounded = clip_xyxy(candidate.xyxy, image_width, image_height)
        if not normalized or not valid_score(candidate.score) or bounded is None:
            continue
        x1, y1, x2, y2 = bounded
        item = Detection2D(id=f"development-{ordinal:06d}")
        item.bbox.center.position.x = (x1 + x2) / 2.0
        item.bbox.center.position.y = (y1 + y2) / 2.0
        item.bbox.size_x = x2 - x1
        item.bbox.size_y = y2 - y1
        result = ObjectHypothesisWithPose()
        result.hypothesis.class_id = f"placeholder/coco/{normalized}"
        result.hypothesis.score = candidate.score
        item.results.append(result)
        output.detections.append(item)
    return output
```

Normalization lowercases ASCII, replaces every non-alphanumeric run with one underscore, and strips edge underscores. Preserve the source header exactly.

- [ ] **Step 4: Verify green and commit**

Run the Step 2 command; expect all conversion tests to pass.

```bash
git add ros2_ws/src/substation_perception
git commit -m "feat: add development detection contract"
```

### Task 4: Latest-Frame ROS Placeholder Node

**Files:**
- Create: `ros2_ws/src/substation_perception/substation_perception/placeholder_node.py`
- Modify: `ros2_ws/src/substation_perception/setup.py`
- Test: `ros2_ws/src/substation_perception/test/test_placeholder_node.py`

**Interfaces:**
- Consumes `/camera/image_raw` with `Q_IMAGE` and the Task 1-3 APIs.
- Produces `/perception/development/detections` with `Q_STREAM`, `/perception/development/annotated_image` with `Q_IMAGE`, and `/diagnostics` with `Q_DIAGNOSTIC`.
- Exposes pure `LatestFrameBuffer.offer(message) -> bool` and `take() -> Image | None` for deterministic backpressure tests.

- [ ] **Step 1: Write failing node-boundary tests**

```python
def test_latest_frame_replaces_pending_message():
    buffer = LatestFrameBuffer()
    assert buffer.offer(make_image(1)) is False
    assert buffer.offer(make_image(2)) is True
    assert buffer.take().header.stamp.sec == 2
    assert buffer.take() is None

def test_processor_rejects_non_rgb_without_output(processor):
    outcome = processor.process(make_image(3, encoding="bgr8"))
    assert outcome.detections is None
    assert outcome.annotated_image is None
    assert outcome.error_code == "IMAGE_ENCODING_UNSUPPORTED"

def test_processor_preserves_source_headers(processor):
    source = make_image(4, encoding="rgb8")
    outcome = processor.process(source)
    assert outcome.detections.header == source.header
    assert outcome.annotated_image.header == source.header
```

```python
@pytest.mark.parametrize("failure,code", [
    ("bridge", "IMAGE_DECODE_FAILED"),
    ("backend", "INFERENCE_FAILED"),
    ("output", "OUTPUT_INVALID"),
])
def test_frame_failure_suppresses_both_outputs(processor_factory, failure, code):
    outcome = processor_factory(failure).process(make_image(5, encoding="rgb8"))
    assert (outcome.detections, outcome.annotated_image, outcome.error_code) == (None, None, code)

def test_module_has_no_production_or_truth_topics():
    source = MODULE.read_text(encoding="utf-8")
    for forbidden in ("/perception/safety", "/perception/equipment",
                      "/perception/defects", "/perception/meters",
                      "/perception/detections", "/perception/annotated_image",
                      "/simulation/scenario_truth"):
        assert forbidden not in source
```

The success test supplies one detection below and one above the confidence threshold, then asserts one output detection and diagnostic values for all eight required identity/counter keys.

- [ ] **Step 2: Verify red**

Run: `source /opt/ros/jazzy/setup.bash && PYTHONPATH=$PWD/ros2_ws/src/substation_perception python3 -m pytest -q ros2_ws/src/substation_perception/test/test_placeholder_node.py`

Expected: import fails because `placeholder_node` does not exist.

- [ ] **Step 3: Implement processor, buffer, worker, QoS and diagnostics**

```python
class LatestFrameBuffer:
    def __init__(self):
        self._condition = Condition()
        self._pending = None

    def offer(self, message):
        with self._condition:
            replaced = self._pending is not None
            self._pending = message
            self._condition.notify()
            return replaced

    def take(self):
        with self._condition:
            message, self._pending = self._pending, None
            return message
```

`FrameProcessor.process` checks `encoding == "rgb8"`, converts through `CvBridge`, runs Task 2, filters by the configured score, calls Task 3, draws accepted boxes on a copy, and returns an `rgb8` ROS image with the original header. `PlaceholderPerceptionNode` validates identity before backend construction; one worker processes one image at a time while callbacks retain only the newest pending image. Publish one-Hz diagnostics with `runtime_mode`, `production_ready`, `logical_model`, verified digest, `frames_received`, `frames_processed`, `frames_replaced`, `frames_failed`, and `last_error_code`. Any frame error publishes an ERROR diagnostic and no frame output.

- [ ] **Step 4: Verify green and commit**

Run the Step 2 command; expect node-boundary tests to pass.

```bash
git add ros2_ws/src/substation_perception
git commit -m "feat: add placeholder perception node"
```

### Task 5: Launch Contract, Build and Headless Live Smoke

**Files:**
- Create: `ros2_ws/src/substation_perception/launch/placeholder_perception.launch.py`
- Create: `ros2_ws/src/substation_perception/test/test_placeholder_launch.py`
- Create: `tests/perception/probe_placeholder_pipeline.py`
- Create: `tests/perception/run_placeholder_smoke.sh`
- Modify: `docs/PROJECT_STATUS.md`
- Modify: `docs/HANDOFF.md`

**Interfaces:**
- Launches only `substation_perception/placeholder_detector` with the exact locked model parameters.
- The smoke consumes the existing headless Gazebo camera and publishes evidence to `/var/lib/substation/evidence/acceptance/<uuid>/04-perception-placeholder`.

- [ ] **Step 1: Write failing launch tests**

```python
def test_launch_locks_development_identity():
    source = LAUNCH.read_text(encoding="utf-8")
    assert '"development_placeholder"' in source
    assert '"yolo11n_base"' in source
    assert '"0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1"' in source
    assert "5613764" in source
    for forbidden in ("yolo11n_safety", "yolo11n_equipment", "yolo11n_fault", "meter_locator"):
        assert forbidden not in source

def test_launch_is_headless_and_localhost_only():
    source = LAUNCH.read_text(encoding="utf-8")
    assert 'UnsetEnvironmentVariable("DISPLAY")' in source
    assert 'SetEnvironmentVariable("ROS_LOCALHOST_ONLY", "1")' in source
```

```python
def test_launch_syntax_executable_and_package_dependencies():
    source = LAUNCH.read_text(encoding="utf-8")
    ast.parse(source, filename=str(LAUNCH))
    assert 'package="substation_perception"' in source
    assert 'executable="placeholder_detector"' in source
    dependencies = {item.text for item in ET.parse(PACKAGE_XML).findall("exec_depend")}
    assert {"cv_bridge", "diagnostic_msgs", "rclpy", "sensor_msgs", "vision_msgs"} <= dependencies
```

- [ ] **Step 2: Verify red**

Run: `source /opt/ros/jazzy/setup.bash && PYTHONPATH=$PWD/ros2_ws/src/substation_perception python3 -m pytest -q ros2_ws/src/substation_perception/test/test_placeholder_launch.py`

Expected: failure because the launch file does not exist.

- [ ] **Step 3: Implement launch and bounded evidence smoke**

The launch unsets `DISPLAY`, sets `ROS_LOCALHOST_ONLY=1`, and starts only the placeholder executable with the locked path, digest, size and development identity. `run_placeholder_smoke.sh` requires `--expected-commit`, a clean tracked worktree, a UUIDv4 run ID and an empty staging evidence directory. It starts the existing `substation_world.launch.py` and placeholder launch under one unique `GZ_PARTITION`, runs the Python probe with a 90-second deadline, records input/output counts, latency, identity, diagnostics and `nvidia-smi`, kills the process group in an EXIT trap, verifies no owned process survives, then atomically renames the staging directory. The probe requires at least one camera input, one detection message, one annotated image, matching headers, CUDA/backend readiness, and development-only class prefixes.

- [ ] **Step 4: Verify package and smoke**

```bash
source /opt/ros/jazzy/setup.bash
colcon build --base-paths ros2_ws/src --packages-select substation_perception --event-handlers console_direct+
source install/setup.bash
colcon test --base-paths ros2_ws/src --packages-select substation_perception --event-handlers console_direct+ --return-code-on-test-failure
colcon test-result --test-result-base build --all --verbose
python3 -m pytest -q tests/perception
bash tests/perception/run_placeholder_smoke.sh --expected-commit "$(git rev-parse HEAD)"
```

Expected: all tests pass; evidence contains the locked identity, live GPU/backend readiness, matching source/output headers and cleanup proof. This does not claim production throughput or Phase 4 completion.

- [ ] **Step 5: Record checkpoint, commit and push**

Record the exact tested commit, commands, evidence directory, development limitation, and user-model blocker in both status documents.

```bash
git add ros2_ws/src/substation_perception tests/perception docs/PROJECT_STATUS.md docs/HANDOFF.md
git commit -m "feat: verify placeholder perception pipeline"
git push origin main
```

Expected: source, tests and small documentation are pushed; weights, logs, datasets and evidence remain outside Git.
