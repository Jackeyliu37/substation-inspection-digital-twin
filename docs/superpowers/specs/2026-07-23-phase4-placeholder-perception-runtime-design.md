# Phase 4 Placeholder Perception Runtime Design

**Date:** 2026-07-23

**Scope:** Build the reusable YOLO11 inference and ROS image pipeline now, using the locked official `yolo11n.pt` only as a development placeholder. Production model import, production Topic activation, model evaluation, and Phase 4 completion remain blocked until the user publishes four trained artifacts.

## 1. Outcome

Create a new `substation_perception` ROS 2 Python package that can:

- verify an immutable weight file before loading it;
- run Ultralytics YOLO inference on `rgb8` ROS images through CUDA;
- convert bounded detections into `vision_msgs/Detection2DArray` while preserving the source header;
- publish an annotated `rgb8` image and structured diagnostics;
- prove the live Gazebo-camera-to-YOLO path without publishing unvalidated COCO classes on production perception Topics.

The official base weight identity is fixed to SHA-256 `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`, size `5613764` bytes, at `/var/lib/substation/models/base/0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1/yolo11n.pt`. Runtime code must not download weights.

## 2. Chosen Architecture

Three approaches were considered:

1. **Reusable runtime with an explicit placeholder mode (chosen).** A pure model-identity layer, a lazy Ultralytics backend, detection/message conversion, and a ROS node remain separate. Placeholder results use the development-only prefix `placeholder/coco/` and development-only Topics.
2. **Publish COCO output through production safety/equipment Topics.** Rejected because COCO class semantics do not satisfy the locked project mappings and downstream consumers could treat unvalidated output as production evidence.
3. **Wait for all four trained artifacts.** Rejected because model loading, CUDA execution, ROS conversion, diagnostics, launch, and failure handling can be completed independently now.

The package contains focused units:

- `model_identity.py` validates runtime mode, logical model, file type, byte size, and SHA-256 before any backend load.
- `yolo_backend.py` lazily imports Ultralytics, loads one immutable weight file, and returns framework-neutral detections. Tests inject a fake model and do not require network access.
- `detection_contract.py` validates finite scores and pixel bounds, assigns deterministic per-frame development IDs, and creates standard ROS detection messages.
- `placeholder_node.py` subscribes to `/camera/image_raw`, performs one-frame-at-a-time inference with latest-frame backpressure, and publishes only `/perception/development/detections`, `/perception/development/annotated_image`, and `/diagnostics`.
- `placeholder_perception.launch.py` wires the locked base weight and expected digest without starting Gazebo itself.

## 3. Runtime and Topic Rules

Placeholder mode has these non-negotiable properties:

- `runtime_mode=development_placeholder` and `production_ready=false` are present in diagnostics.
- The only accepted logical model is `yolo11n_base`; production logical names are rejected in this mode.
- Class IDs are `placeholder/coco/<normalized-class>` and can never be `safety/*`, `equipment/*`, `defect/*`, or `meter/*`.
- Detection IDs are development correlation IDs, not run-scoped production evidence IDs.
- The node never subscribes to `/simulation/scenario_truth` and never reads synthetic label metadata at runtime.
- A missing file, digest mismatch, unsupported encoding, malformed output, non-finite value, or CUDA/backend failure produces an explicit diagnostic error and no detection output for that frame.

The node keeps only one pending image while inference is active. This bounds memory and latency when Gazebo publishes faster than inference. Source header stamp and `camera_optical_frame` are copied unchanged to detections and the annotated image.

## 4. Production Replacement Boundary

The reusable identity, backend, and detection layers are production-oriented, but this checkpoint does not create production aliases or claim model acceptance. When the user artifacts arrive:

- `scripts/import_model_release.py` and `scripts/verify_data_and_models.py` will verify the immutable GitHub identity, manifests, metrics, class order, size, and SHA-256;
- safety, equipment, fault, and meter nodes will each load only their manifest-selected artifact;
- fault remains a classification pipeline, and meter remains a locator followed by independent OpenCV reading;
- production Topics become ready only after the corresponding artifact passes its module gate;
- the 300-second, 640-pixel, 15 FPS complete ROS pipeline test remains a final model acceptance requirement.

No code path aliases the official base weight to `yolo11n_safety.pt`, `yolo11n_equipment.pt`, `yolo11n_fault.pt`, or `yolo11n_meter.pt`.

## 5. Testing and Evidence

Automated tests cover:

- accepted official placeholder identity and rejected digest/path/mode combinations;
- lazy backend loading, normalized names, filtering, finite coordinates, and empty results;
- exact ROS header preservation, bounding-box conversion, class prefix, score range, and stable IDs;
- launch parameters, development-only Topics, and absence of production Topic names;
- node behavior for `rgb8`, unsupported encodings, inference failure, and latest-frame backpressure using an injected backend.

A bounded live smoke starts the existing headless Gazebo world and the placeholder node under a unique `GZ_PARTITION`, captures model identity, GPU/backend readiness, input/output frame counts, latency, and process cleanup, and seals evidence outside Git. It proves the development path only; it cannot satisfy the production model or Phase 4 final acceptance gates.

## 6. Completion Boundary

This subproject is complete when the new package builds, all unit and launch-contract tests pass, the official weight is verified and loaded without network access, a bounded live camera inference smoke succeeds, and documentation records the exact tested commit and evidence path. Phase 4 itself remains `in_progress / model artifacts blocked` until the four user-trained artifacts and their simplified handoff records are imported and accepted.
