# Production Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the production perception, meter reading, safety barriers, evidence/reporting, immutable release deployment, and live acceptance work explicitly assigned by the operator.

**Architecture:** Keep the four trained models as independently identified runtime modules, preserve the ROS topic contracts, and integrate them through a production perception launch. Add explicit release staging/install scripts and record live evidence under run-scoped immutable directories. Browser acceptance remains manual and is not part of this implementation plan.

**Tech Stack:** ROS 2 Jazzy, rclpy, vision_msgs, diagnostic_msgs, PyTorch/Ultralytics CUDA, OpenCV, Gazebo Harmonic, FastAPI, Next.js, systemd, Nginx, rosbag2.

## Global Constraints

- Use the four SHA-256 identities in `models/manifest.yaml`; safety metric waiver is accepted and must remain visible.
- Production perception publishes only during an ACTIVE `RunContext`; development placeholder topics never enter production aggregation.
- `ROS_LOCALHOST_ONLY=1`; Gateway and frontend bind loopback; Nginx is the only LAN product listener.
- Runtime evidence goes below `/var/lib/substation`, not Git. Screenshots and demo video are not required.
- Every new behavior follows red-green TDD and every live acceptance uses a new run ID.

---

### Task 1: Normal README and accepted scope

**Files:**
- Modify: `README.md`
- Modify: `docs/PLAN_GAP_ANALYSIS.md`
- Modify: `docs/PROJECT_STATUS.md`
- Modify: `docs/HANDOFF.md`

- [ ] Remove project-progress and metric-report sections from README; retain overview, capabilities, architecture, stack, repository structure, setup, startup, tests, documentation, and project boundaries.
- [ ] Record the operator decisions: safety waiver accepted, browser acceptance manual, no screenshots/video deliverable.
- [ ] Run `bash scripts/verify_documentation_gate.sh` and require `documentation-gate: PASS`.

### Task 2: Production perception and real Gateway camera

**Files:**
- Create: `ros2_ws/src/substation_perception/substation_perception/production_identity.py`
- Create: `ros2_ws/src/substation_perception/substation_perception/production_nodes.py`
- Create: `ros2_ws/src/substation_perception/substation_perception/detection_aggregator.py`
- Create: `ros2_ws/src/substation_perception/launch/production_perception.launch.py`
- Modify: `ros2_ws/src/substation_perception/setup.py`
- Modify: `ros2_ws/src/substation_web_gateway/substation_web_gateway/ros_adapter.py`
- Test: `ros2_ws/src/substation_perception/test/test_production_perception.py`
- Test: `tests/gateway/test_ros_adapter.py`

- [ ] Write failing tests for manifest identity verification, ACTIVE RunContext gating, module-prefixed detections, aggregation without ID rewriting, and RGB-to-JPEG camera state updates.
- [ ] Run the focused tests and confirm failures are caused by missing production classes/callbacks.
- [ ] Implement separate safety/equipment detector processes, equipment-crop defect classification, meter locator input, same-stamp aggregation/annotation, and Gateway JPEG encoding.
- [ ] Run focused tests, package build/test, and Gateway regression.

### Task 3: Meter OpenCV reading and frozen test evaluation

**Files:**
- Create: `ros2_ws/src/substation_perception/substation_perception/meter_reader.py`
- Create: `scripts/evaluate_meter_reader.py`
- Modify: `configs/meter_reader.yaml`
- Test: `ros2_ws/src/substation_perception/test/test_meter_reader.py`
- Test: `tests/perception/test_meter_evaluation_contract.py`

- [ ] Write failing tests for needle-angle normalization, calibrated reading conversion, DiagnosticArray fields, invalid crop rejection, and deterministic evaluation JSON.
- [ ] Run tests and confirm expected failures.
- [ ] Implement perspective-normalized dial crop processing, center-to-needle line extraction, configured range/unit conversion, evidence UUID creation, and grouped test-set evaluation.
- [ ] Evaluate the frozen 200-image test split and store a run-scoped report outside Git.

### Task 4: Mission cold-start and emergency reset barriers

**Files:**
- Modify: `ros2_ws/src/substation_mission/substation_mission/mission_node.py`
- Modify: `ros2_ws/src/substation_mission/substation_mission/velocity_arbiter.py`
- Test: `ros2_ws/src/substation_mission/test/test_mission_node.py`
- Test: `ros2_ws/src/substation_mission/test/test_velocity_arbiter.py`

- [ ] Write failing tests proving IDLE→STARTING→ACTIVE persistence, no goal dispatch before ACTIVE, reset rejection while a goal exists, and 0.5-second confirmed zero velocity before reset/mode transition.
- [ ] Run focused tests and confirm expected failures.
- [ ] Implement monotonic zero barrier state and lifecycle transitions without weakening latch revision CAS.
- [ ] Run mission package tests and a real rclpy integration smoke.

### Task 5: Rosbag2, complete snapshot, and report closure

**Files:**
- Create: `scripts/reporting/run_evidence_capture.sh`
- Create: `scripts/reporting/verify_report_bundle.py`
- Modify: `ros2_ws/src/substation_reporting/substation_reporting/report_generator.py`
- Modify: `ros2_ws/src/substation_reporting/substation_reporting/report_generator_node.py`
- Test: `ros2_ws/src/substation_reporting/test/test_report_generator.py`
- Test: `tests/phase5_6/test_report_traceability.py`

- [ ] Write failing tests requiring alert, trajectory, mission, model manifest, rosbag2 metadata, and SHA-256 entries in the terminal bundle.
- [ ] Run focused tests and confirm expected failures.
- [ ] Implement run-scoped rosbag2 capture, snapshot indexing, HTML/PDF/evidence ZIP generation, and independent bundle verification.
- [ ] Run reporting tests and generate one complete report/evidence bundle during live acceptance.

### Task 6: Immutable release and service deployment

**Files:**
- Create: `scripts/deployment/build_release.sh`
- Create: `scripts/deployment/install_release.sh`
- Create: `deploy/systemd/substation-gazebo.service`
- Create: `deploy/systemd/substation-core.service`
- Modify: `deploy/systemd/substation-web-gateway.service`
- Modify: `deploy/systemd/substation-web-frontend.service`
- Test: `tests/integration/test_deployment_contract.py`

- [ ] Write failing deployment tests for a clean commit release manifest, SHA-256 inventory, five service units, loopback boundaries, and atomic `/opt/substation/current` switching.
- [ ] Run tests and confirm expected failures.
- [ ] Implement reproducible release staging plus root-only installation, permissions, unit installation, daemon reload, Nginx validation, and rollback-safe current link switch.
- [ ] Build the candidate as the operator, then run the minimal root install command after sudo authority is available.

### Task 7: 300-second live production acceptance

**Files:**
- Create: `tests/perception/run_production_acceptance.sh`
- Create: `tests/perception/probe_production_pipeline.py`
- Modify: `docs/PROJECT_STATUS.md`
- Modify: `docs/HANDOFF.md`

- [ ] Write contract tests for new run IDs, 300-second duration, 15 FPS threshold, four artifact hashes, meter metrics, real camera frames, mission safety barriers, rosbag2, reports, process cleanup, and immutable SHA256SUMS.
- [ ] Run the contract tests and confirm expected failures.
- [ ] Implement the acceptance runner and probe, then execute it with a new UUID under `/var/lib/substation/evidence/acceptance/<run-id>/09-production-integration.staging`.
- [ ] Verify the sealed evidence, confirm no residual project process, update status/handoff, run full regression, commit, and push.
