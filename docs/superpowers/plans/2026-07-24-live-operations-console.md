# Live Operations Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the real ROS/Gazebo-backed Phase 7/8 operations console for manual acceptance.

**Architecture:** Extend the existing Gateway projection rather than adding another backend. Decode and render authoritative snapshots in the existing Next.js client, and keep Gazebo headless.

**Tech Stack:** ROS 2 Jazzy, rclpy, FastAPI/Starlette, Next.js 16, React 19, Three.js/react-three-fiber, Canvas/SVG.

## Global Constraints

- Browser traffic stays on `/api/v1` and `/ws`; no DDS or rosbridge access.
- Gazebo stays OGRE2/EGL headless.
- Production models remain immutable under `/var/lib/substation/models/production`.
- User performs final manual browser acceptance; no Playwright acceptance.

### Task 1: Gateway production contracts

**Files:**
- Modify: `tests/gateway/test_gateway_contract.py`
- Modify: `tests/gateway/test_ros_adapter.py`
- Modify: `ros2_ws/src/substation_web_gateway/substation_web_gateway/app.py`
- Modify: `ros2_ws/src/substation_web_gateway/substation_web_gateway/ros_adapter.py`

- [ ] Add failing tests for all-assets projection, production model discovery, scenario command dispatch, framed camera streaming, and ended-run mapping recovery.
- [ ] Run focused tests and confirm they fail for the missing behavior.
- [ ] Implement the smallest Gateway changes that satisfy those contracts.
- [ ] Run focused and complete Gateway tests.

### Task 2: Real console rendering

**Files:**
- Create: `web/frontend/app/map-utils.mjs`
- Modify: `web/frontend/app/page.js`
- Modify: `web/frontend/app/globals.css`
- Modify: `web/frontend/scripts/test-contract.mjs`

- [ ] Add failing Node contract tests for occupancy decoding, real asset fields/poses, robot/route rendering, model snapshots, and valid scenario payloads.
- [ ] Run the frontend contract test and confirm it fails for the placeholder implementation.
- [ ] Implement the map, substation twin, robot trail, model panel, video metadata, scenario controls, and stable refresh state.
- [ ] Run frontend tests and production build.

### Task 3: Integration and release

**Files:**
- Modify only if a regression is exposed by verification.

- [ ] Run Gateway, frontend, integration, and deployment contract suites.
- [ ] Commit and push the verified Phase 7/8 correction.
- [ ] Build the immutable release candidate.
- [ ] Install/activate with the existing one-command deployment script and verify REST, camera WebSocket, scenario route, assets, models, and readiness.
