# Gazebo Meter Locator Dataset Design

**Date:** 2026-07-23

**Scope:** Generate and package the project-owned synthetic dataset needed to fine-tune the independent YOLO11n `meter_locator` model on AutoDL. This is a Phase 4 preparation checkpoint brought forward by the user's explicit request; it does not implement perception runtime or claim Phase 3/4 completion.

## 1. Outcome

The deliverable is one AutoDL-ready ZIP containing exactly 2,000 Gazebo-derived 640×480 RGB images, YOLO detection labels, deterministic group-isolated splits, rich meter ground truth, provenance manifests, checksums, and a copy-paste training command.

The YOLO task has one canonical class:

```yaml
names:
  0: meter
```

The locator only finds the dial. Meter identity, range, and unit remain configuration-owned: `meter-pressure-01` is 0–2 MPa and `meter-oil-01` is 0–100 percent in `configs/devices.yaml`. The downstream OpenCV reader uses the detected dial plus the current inspection asset context to calculate a typed reading; the model never invents units or ranges.

## 2. Chosen Generation Approach

Use a dedicated Gazebo Harmonic server-only world with OGRE2/EGL rendering, a 640×480 camera, two controllable meter variants, a controllable needle joint, background geometry, lights, and a movable occluder. A deterministic ROS/Gazebo generator controls pose, reading, and scene variation, waits for a fresh image after every applied state, projects the known dial geometry through CameraInfo, validates the bounding box, and writes the image and YOLO label atomically.

Rejected alternatives:

- Reusing only the Phase 2 yard and robot camera gives insufficient view diversity and the existing static needle cannot cover readings efficiently.
- Pure OpenCV drawings are faster but violate the rule that instrument training and evaluation data come only from the project Gazebo generation chain.

Post-render brightness, Gaussian blur, and sensor noise transformations are allowed only as deterministic derivations of a captured Gazebo frame. Their parameters and the source-frame SHA-256 are recorded per sample. Occlusion is produced by Gazebo geometry, not painted over the target after rendering.

## 3. Dataset Composition and Split Isolation

The generator creates 100 immutable scene groups with 20 frames per group:

| Split | Pressure groups/images | Oil groups/images | Total images |
|---|---:|---:|---:|
| train | 40 / 800 | 40 / 800 | 1,600 |
| val | 5 / 100 | 5 / 100 | 200 |
| test | 5 / 100 | 5 / 100 | 200 |
| total | 50 / 1,000 | 50 / 1,000 | 2,000 |

A group fixes a meter type and a view/background/light/occlusion family. Frames within that group vary reading and bounded micro-jitter, but a `scene_group_id` appears in exactly one split. Test combinations of view family, light family, and background family do not appear in train. Split assignment is stable and independent of generation time or filesystem order.

Coverage includes:

- both configured meter assets and their complete numeric ranges;
- distance, yaw, pitch, and roll bins that keep the dial visible and useful;
- bright, nominal, low-light, warm, and cool illumination families;
- clean, industrial-light, and industrial-dark backgrounds;
- no, edge, and partial occlusion regimes, with the visible dial area kept sufficient for a valid label;
- deterministic brightness, blur, and camera-noise levels.

Every accepted dial box must lie inside the image, have positive normalized YOLO coordinates, and be at least 32×32 pixels. Samples failing projection, freshness, visibility, decode, or label validation are rejected without consuming an output index; bounded retry exhaustion fails the generation run.

## 4. Per-Sample Ground Truth

`metadata.jsonl` contains one canonical JSON object per image, sorted by `sample_id`, with at least:

```text
sample_id, split, scene_group_id, seed, scenario_id,
asset_id, sensor_id, meter_type, image_path, label_path,
image_sha256, source_frame_sha256, width, height,
bbox_xyxy_pixels, bbox_yolo, dial_corners_pixels,
meter_pose, camera_pose, camera_intrinsics,
minimum, maximum, unit, true_reading, normalized_reading, needle_angle_radians,
light_family, background_family, blur_sigma, brightness_scale,
occlusion_regime, visible_fraction,
generator_git_commit, world_sha256, generation_config_sha256,
gazebo_version, ros_distro
```

Values for `asset_id`, `sensor_id`, range, and unit are loaded from `configs/devices.yaml`; they are not duplicated as independent authored constants. Non-finite values, missing fields, unknown IDs, or inconsistent reading/angle mappings fail validation.

## 5. Package Layout

The uncompressed generation directory and final ZIP live outside Git under:

```text
/var/lib/substation/datasets/synthetic/gazebo-meter/<generation_id>/
```

The ZIP root is:

```text
gazebo-meter-locator-v1/
├── images/
│   ├── train/
│   ├── val/
│   └── test/
├── labels/
│   ├── train/
│   ├── val/
│   └── test/
├── data.yaml
├── metadata.jsonl
├── dataset-manifest.yaml
├── file-manifest.tsv
├── generation-config.yaml
├── README-AutoDL.md
└── SHA256SUMS
```

`file-manifest.tsv` is sorted by relative path and uses `sha256<TAB>size_bytes<TAB>relative_path`. `SHA256SUMS` covers every packaged file except itself and is verified before the ZIP is published. `generation_id` is the SHA-256 identity of the clean generator commit, generation configuration, authored world/model inputs, Gazebo version, and complete seed list.

`README-AutoDL.md` gives upload, extraction, integrity verification, environment check, and the canonical command:

```bash
yolo detect train data=gazebo-meter-locator-v1/data.yaml model=yolo11n.pt imgsz=640 epochs=100 batch=8 device=0 workers=6 seed=42 patience=20
```

If AutoDL records a CUDA out-of-memory failure, the user may rerun with `batch=4`; image size remains 640.

## 6. Generator Boundaries and Failure Handling

- Every live command unsets `DISPLAY`, sets `ROS_LOCALHOST_ONLY=1`, uses a unique `GZ_PARTITION`, and launches Gazebo in a dedicated process group.
- The generator records the exact clean Git commit, input SHA-256 values, `gz sim` command, Gazebo environment, versions, seed plan, start/end UTC times, counts, rejection reasons, and process identity.
- Only the recorded process group is terminated. No generic `pkill` or `killall` is allowed.
- Output is written to a `.staging` generation directory. A failed or interrupted run remains failed evidence and is never renamed or reused.
- The final directory and ZIP appear only after image/label validation, split isolation, manifests, byte counts, and all checksums pass.
- Runtime network access, Fuel downloads, public datasets, external meter images, and Gazebo scenario truth as a perception input are forbidden.

## 7. Verification and Acceptance

Automated tests cover deterministic sample planning, exact 1000/1000 meter balance, exact 1600/200/200 split counts, group isolation, reading-to-angle mapping, projection and normalized label bounds, canonical metadata, path safety, checksum construction, and failure cleanup.

A small live smoke generation validates OGRE2/EGL content, non-uniform RGB payloads, controlled needle changes, projected boxes, and zero residual processes before the full run. The full dataset is accepted only when:

- exactly 2,000 decodable 640×480 images and 2,000 one-line YOLO labels exist;
- every label is class `0` and matches the projected dial bounds;
- pressure and oil counts are exactly 1,000 each;
- train/val/test counts are exactly 1,600/200/200 with no group crossing;
- every required metadata field is present and finite where numeric;
- all relative paths are safe and every recorded SHA-256 and byte count matches;
- the ZIP extracts cleanly, `data.yaml` resolves all three splits, and the AutoDL README command parses;
- no Gazebo or generator process remains.

Repository commits contain only generator source, configuration, tests, design/plan, and the final dataset identity/checksum record. Images, labels, generated metadata payloads, logs, and ZIP files remain outside Git.
