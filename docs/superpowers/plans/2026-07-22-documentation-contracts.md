# Documentation and Contract Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the project-plan phase-0 documentation gate and freeze the first ROS/Web contracts before any functional implementation.

**Architecture:** Treat the root project plan as the scope authority, ADRs as immutable architecture decisions, focused specification documents as implementation contracts, and status/handoff files as current-state recovery aids. Standard ROS 2 types are preferred; project-specific state and commands use a small custom interface set, while all browser traffic crosses the FastAPI ROS Web Gateway.

**Tech Stack:** Markdown, Git, ROS 2 Jazzy interface definitions, Gazebo Harmonic, Nav2, FastAPI/OpenAPI, WebSocket JSON envelopes, Next.js/TypeScript, SQLite.

## Global Constraints

- Ubuntu 24.04 LTS, ROS 2 Jazzy, Gazebo Harmonic `gz-sim 8.x`, OGRE2/EGL headless rendering.
- No Ubuntu desktop, Xorg, display manager, NoMachine, Xvfb, VirtualGL, ROS 1, Gazebo Classic, or alternate ROS distribution.
- Windows is a browser/SSH client only; all project services and evidence remain on the Ubuntu server.
- Browsers never connect directly to ROS DDS; commands and state cross the FastAPI ROS Web Gateway.
- Safety detection, equipment detection, fault classification, and gauge reading remain separate modules.
- Gauge training data is generated only by this project's Gazebo scenes.
- Versions are changed only through a new ADR plus synchronized plan, lockfile, and acceptance updates.
- No feature is complete without an actual verification command and saved evidence.

---

### Task 1: Repository execution rules and human entry point

**Files:**
- Create: `AGENTS.md`
- Create: `README.md`

**Interfaces:**
- Consumes: root project plan sections 2, 3, 7, 14, 15, and 19.
- Produces: automatic Codex repository rules and the human-readable documentation index used by every later task.

- [x] **Step 1: Write `AGENTS.md` with the twelve immutable constraints**

Include the exact authority order, allowed/disallowed actions, canonical build and verification command categories, completion definition, and mandatory updates to `docs/PROJECT_STATUS.md` and `docs/HANDOFF.md`.

- [x] **Step 2: Write `README.md` as a concise project entry point**

Include the closed-loop objective, server/browser deployment, architecture flow, planned directory map, document links, phase status, and non-executable quick validation commands that only inspect repository and host state.

- [x] **Step 3: Verify navigation and forbidden-stack wording**

Run:

```bash
rg -n '项目计划|ARCHITECTURE|INTERFACES|TEST_ACCEPTANCE|VERSION_MATRIX|PROJECT_STATUS|HANDOFF' AGENTS.md README.md
rg -n 'ROS 1|Gazebo Classic|Xorg|NoMachine|Xvfb|VirtualGL' AGENTS.md
```

Expected: both files link to the authority documents; `AGENTS.md` explicitly forbids every incompatible stack item.

- [x] **Step 4: Commit**

```bash
git add AGENTS.md README.md
git commit -m "docs: add repository rules and project entry point"
```

### Task 2: Architecture, deployment, and accepted decisions

**Files:**
- Create: `docs/ARCHITECTURE.md`
- Create: `docs/DEPLOYMENT.md`
- Create: `docs/adr/0001-headless-gazebo.md`
- Create: `docs/adr/0002-server-web-deployment.md`
- Create: `docs/adr/0003-multimodel-perception.md`

**Interfaces:**
- Consumes: the authority model from Task 1 and project-plan sections 3, 6, 7, 9, 12, and 17.
- Produces: stable component/process boundaries and three accepted architecture decisions referenced by all later implementation plans.

- [x] **Step 1: Define component boundaries and state ownership**

Document the Gazebo, description, perception, digital-twin, risk, mission, reporting, Gateway, frontend, Nginx, Foxglove, and evidence-store responsibilities; include dependency direction, process placement, main data flow, and degraded modes.

- [x] **Step 2: Define target server layout and lifecycle**

Document target directories under `/opt/substation`, mutable state under `/var/lib/substation`, logs under `/var/log/substation`, source checkout under the operator account, loopback-only Gateway/frontend bindings, Nginx exposure, service startup order, backup inputs, upgrade sequence, rollback source, and recovery checks.

- [x] **Step 3: Record three accepted ADRs**

Each ADR contains status `Accepted`, context, at least two considered alternatives, decision, consequences, and explicit conditions that justify a superseding ADR.

- [x] **Step 4: Verify consistency**

Run:

```bash
rg -n 'Accepted|Supersed' docs/adr/*.md
rg -n 'OGRE2|EGL|headless|FastAPI|Next.js|SQLite' docs/ARCHITECTURE.md docs/DEPLOYMENT.md docs/adr/*.md
rg -n 'Xorg|NoMachine|Xvfb|VirtualGL' docs/DEPLOYMENT.md docs/adr/0001-headless-gazebo.md
```

Expected: all ADRs are accepted, the selected stack is consistent, and desktop/virtual-display software appears only as prohibited alternatives.

- [x] **Step 5: Commit**

```bash
git add docs/ARCHITECTURE.md docs/DEPLOYMENT.md docs/adr
git commit -m "docs: define architecture deployment and ADRs"
```

### Task 3: ROS, TF, REST, and WebSocket contracts

**Files:**
- Create: `docs/INTERFACES.md`

**Interfaces:**
- Consumes: component ownership from Task 2 and project-plan sections 8, 10, 11, and 12.4-12.5.
- Produces: exact ROS standard/custom types, custom field schemas, QoS, TF frames, REST payloads, WebSocket envelopes, command lifecycle, idempotency, and error codes.

- [x] **Step 1: Freeze naming, units, identifiers, time, and versioning rules**

Use UUID strings for `run_id`, `mission_id`, `task_id`, `command_id`, `alert_id`, and `evidence_id`; stable configuration strings for `asset_id`; ROS time inside ROS; RFC 3339 UTC on Web; SI units except Celsius, ppm, percentages, and the documented 0-1/0-100 normalized ranges.

- [x] **Step 2: Define all ROS topics and custom interfaces**

Specify publisher, subscribers, exact type, rate, and QoS for raw sensors, perception, environment, digital twin, risk, mission, navigation, and diagnostics. Provide compilable field lists for each custom `.msg`, `.srv`, and `.action` planned under `substation_interfaces`.

- [x] **Step 3: Define TF tree and frame ownership**

Freeze `map -> odom -> base_footprint -> base_link`, sensor child frames, static `asset/<asset_id>` frames, timestamp tolerance, and the rule that asset poses are authored in `map`.

- [x] **Step 4: Define REST and WebSocket schemas**

For every project-plan endpoint, specify method, request, success status/body, validation rules, and stable failure codes. Add `/api/v1/robot/emergency-stop/reset`, command lookup, report download, health/readiness, snapshot revision, WebSocket envelope, heartbeat, sequence-gap recovery, camera binary framing, and connection timeout behavior.

- [x] **Step 5: Verify contract coverage**

Run:

```bash
rg -n '/camera/image_raw|/perception/detections|/digital_twin/assets|/risk/assets|/mission/inspection_tasks|NavigateToPose' docs/INTERFACES.md
rg -n 'QoS|map|odom|base_footprint|base_link|command_id|Idempotency-Key|RFC 7807|schema_version|sequence' docs/INTERFACES.md
rg -n 'emergency-stop/reset|WS /ws/telemetry|WS /ws/events|WS /ws/camera' docs/INTERFACES.md
```

Expected: every required ROS/Web interface and cross-cutting protocol rule is present.

- [x] **Step 6: Commit**

```bash
git add docs/INTERFACES.md
git commit -m "docs: freeze ROS and web interface contracts"
```

### Task 4: Version, data/model, and acceptance contracts

**Files:**
- Create: `docs/VERSION_MATRIX.md`
- Create: `docs/DATA_AND_MODELS.md`
- Create: `docs/TEST_ACCEPTANCE.md`

**Interfaces:**
- Consumes: root project-plan sections 4, 5, 15, 16, and 17 plus Task 3 contract names.
- Produces: dependency locks, reproducible data/model rules, and the single verification entry point for every later phase.

- [x] **Step 1: Transcribe the complete locked version matrix**

Include acquisition source, lock level, verification command, and upgrade rule for OS, driver, ROS/Gazebo/navigation/TurtleBot3, Python/AI packages, Node/frontend packages, FastAPI stack, SQLite, Nginx, datasets, and model weights.

- [x] **Step 2: Define data and model governance**

Document dataset purpose, license, revision, class mapping, split rules, synthetic data generation, directory/manifest schema, training baseline, required metrics, artifact naming, SHA-256 recording, permitted use, and the separation of four perception modules.

- [x] **Step 3: Define test layers, commands, thresholds, and evidence**

Cover phase-0 static checks, phase-1 host/environment checks, unit, ROS integration, Gazebo scenario, navigation/risk loop, model evaluation, Gateway contract, Playwright E2E, performance, report traceability, and final acceptance. For checks that depend on future files, name the exact future command and expected artifact rather than claiming it is currently runnable.

- [x] **Step 4: Verify exact project baselines**

Run:

```bash
rg -n 'Ubuntu 24.04|ROS 2 Jazzy|Gazebo Harmonic|2.12.1|8.4.104|24.18.0|16.2.11|0.139.2' docs/VERSION_MATRIX.md
rg -n 'c63ed3c7f5ea33ac8e9024c467a70a62b849b2ad|4bf9c31b18fadcd44d5f0b6d66f82bc56fa5e328|CC BY-NC 3.0|2,000|500' docs/DATA_AND_MODELS.md
rg -n '15 FPS|0.75|20|90%|2 seconds|500 ms|1 second|5 seconds' docs/TEST_ACCEPTANCE.md
```

Expected: versions, dataset revisions, sample requirements, and acceptance thresholds match the root project plan.

- [x] **Step 5: Commit**

```bash
git add docs/VERSION_MATRIX.md docs/DATA_AND_MODELS.md docs/TEST_ACCEPTANCE.md
git commit -m "docs: define version data and acceptance baselines"
```

### Task 5: Phase-1 executable environment plan

**Files:**
- Create: `docs/plans/PHASE-01-ENVIRONMENT.md`

**Interfaces:**
- Consumes: Tasks 1-4, especially exact versions, deployment boundaries, and acceptance commands.
- Produces: the zero-context implementation plan for environment detection, repository scaffolding, repeatable host installation, Python/GPU environment, Web environment, and evidence capture.

- [x] **Step 1: Map the exact phase-1 file structure**

Name each script, lock file, test, manifest, configuration file, and evidence output that phase 1 will create; assign one responsibility to each file.

- [x] **Step 2: Break phase 1 into test-first tasks**

Use tasks for documentation-gate test, read-only host audit, apt repository/ROS/Gazebo installer, ROS workspace baseline, AI virtual environment, Gateway virtual environment, Node frontend baseline, headless EGL smoke test, consolidated verifier, and phase status/handoff update.

- [x] **Step 3: Give exact commands, expected output, rollback, and commit boundaries**

Each task has a failing test or precondition, the minimal implementation, a passing command, evidence location, safe rollback for files/packages it owns, and a focused commit message.

- [x] **Step 4: Self-review task dependencies and type/path consistency**

Run:

```bash
rg -n '^### Task|^\- \[ \] \*\*Step|^\*\*Files:|^\*\*Interfaces:' docs/plans/PHASE-01-ENVIRONMENT.md
rg -n 'scripts/verify_environment.sh|tests/environment|artifacts/environment|requirements.lock|package-lock.json' docs/plans/PHASE-01-ENVIRONMENT.md
```

Expected: every task is independently reviewable and later tasks consume only files/interfaces created earlier.

- [x] **Step 5: Commit**

```bash
git add docs/plans/PHASE-01-ENVIRONMENT.md
git commit -m "docs: plan phase one environment baseline"
```

### Task 6: Current status, handoff, and documentation-gate verification

**Files:**
- Create: `docs/PROJECT_STATUS.md`
- Create: `docs/HANDOFF.md`
- Modify: `docs/superpowers/plans/2026-07-22-documentation-contracts.md`

**Interfaces:**
- Consumes: all previous documentation outputs and the current Git commit/test evidence.
- Produces: a truthful current snapshot, a deterministic resume command, and checked completion boxes for this plan.

- [x] **Step 1: Synchronize the current phase in entry and acceptance documents**

Update `README.md` and `docs/TEST_ACCEPTANCE.md` to state that Phase 0 is complete and Phase 1 is active/next. Clarify that future acceptance commands become runnable only as their planned files are created; until then they remain contracts, not implemented claims.

- [x] **Step 2: Commit an exact reproducible Phase 0 gate**

The gate must enumerate every Phase 0 deliverable explicitly, keep concrete unresolved markers, and avoid treating the generic Chinese noun used in legitimate explanatory text as an unresolved marker.

- [ ] **Step 3: Run the exact committed Phase 0 gate**

Run this exact block from the committed plan without substitution:

```bash
set -euo pipefail
phase0_files=(
  AGENTS.md
  README.md
  基于数字孪生与多模态风险感知的变电站智能巡检系统_项目计划.md
  docs/ARCHITECTURE.md
  docs/DEPLOYMENT.md
  docs/INTERFACES.md
  docs/TEST_ACCEPTANCE.md
  docs/VERSION_MATRIX.md
  docs/DATA_AND_MODELS.md
  docs/PROJECT_STATUS.md
  docs/HANDOFF.md
  docs/plans/PHASE-01-ENVIRONMENT.md
  docs/adr/0001-headless-gazebo.md
  docs/adr/0002-server-web-deployment.md
  docs/adr/0003-multimodel-perception.md
)
for file in "${phase0_files[@]}"; do
  test -s "$file"
done
scan_pattern='T''BD|T''ODO|F''IXME|待''补充|待''确认|待''定|以后再''定'
if rg -n -i "$scan_pattern" "${phase0_files[@]}"; then
  exit 1
fi
git diff --check
printf '%s\n' 'phase0-documentation-gate: PASS'
```

Expected: literal stdout `phase0-documentation-gate: PASS`, no marker matches, and exit code 0.

- [ ] **Step 4: Record the verified snapshot in status and handoff**

After committing Step 1 and Step 2, run the exact Step 3 block at the clean commit. Record that commit as `verified_snapshot_commit`, the UTC verification time, the full exact commands, literal outputs, service state, clean status, blockers, next three actions, and this exact first resume command in `docs/PROJECT_STATUS.md` and `docs/HANDOFF.md`:

```bash
cd /home/jackeyliu37/substation-inspection-digital-twin && sed -n '1,240p' docs/plans/PHASE-01-ENVIRONMENT.md
```

- [ ] **Step 5: Commit bookkeeping and verify clean handoff**

Commit the status record separately from the verified snapshot. Explain that the later commit is bookkeeping and was not the commit tested by the recorded snapshot gate. Then run:

```bash
git diff --check
git status --short
git log -6 --oneline --decorate
```

Expected: `git diff --check` and `git status --short` have no output; the two latest commits are the status-record bookkeeping commit and its verified synchronized-document parent.
