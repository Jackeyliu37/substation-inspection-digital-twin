# Inspection Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the per-asset inspection, risk, reporting, event, and operator-telemetry loop.

**Architecture:** Keep schema 1 interfaces stable and use task transitions as the inspection boundary. Risk and reporting consume authoritative ROS snapshots; the Gateway and frontend only project and explain those snapshots.

**Tech Stack:** ROS 2 Jazzy, rclpy, Nav2, FastAPI, Next.js/React, Node contract tests, pytest.

## Global Constraints

- Do not fabricate frontend-only risk scores or sensor readings.
- Keep the existing ROS message and service schemas compatible.
- Show all ten registered assets and use Chinese operator-facing event text.
- Do not use Playwright; the user performs browser acceptance.

---

### Task 1: Per-asset mission settlement

**Files:** `ros2_ws/src/substation_mission/substation_mission/mission_node.py`, `inspection_executor.py`, and their tests.

- [ ] Add failing tests for one-active-task invariants and incremental completion.
- [ ] Mark the previous active task succeeded when feedback advances and settle the final task.
- [ ] Bound unreachable navigation duration and preserve skipped results.
- [ ] Run mission tests.

### Task 2: Risk and report triggers

**Files:** risk/reporting nodes and their tests.

- [ ] Add failing tests for inspection-triggered risk and one report per succeeded mission.
- [ ] Cache real observations for all assets and evaluate completed tasks.
- [ ] Generate a report idempotently from the terminal mission snapshot.
- [ ] Run risk and reporting tests.

### Task 3: Gateway semantics and frontend completeness

**Files:** Gateway projection/tests and frontend page/CSS/contract.

- [ ] Add failing contracts for sensor fields, semantic events, formula display, and ten-asset rendering.
- [ ] Project existing ROS telemetry and semantic state transitions.
- [ ] Add the sensor/risk panels, full asset list, and readable Chinese events.
- [ ] Run Gateway and frontend tests/build.

### Task 4: Scenario and release verification

**Files:** scenario/Gateway command tests and deployment scripts if the reproduction identifies a defect.

- [ ] Reproduce a scenario command through the live API and capture its terminal mismatch.
- [ ] Add a failing regression test and fix the identified boundary.
- [ ] Run the full affected test suites and production build.
- [ ] Commit, push, and build a release for one-command activation.

