# Operator Console Usability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a Chinese-first, readable operator console with one-action autonomous inspection recovery and an interactive occupancy map.

**Architecture:** Keep ROS/Gateway contracts unchanged. Add pure frontend modules for Chinese presentation mapping, viewport math, and command-state helpers; compose them in the existing Next.js client page. Transform the occupancy raster and SVG overlay as one layer so all map content stays aligned.

**Tech Stack:** Next.js 16, React 19, JavaScript ES modules, CSS, existing FastAPI REST command API, Node contract tests.

## Global Constraints

- Do not add npm or Python dependencies.
- Preserve emergency-stop safety barriers and the existing idempotency contract.
- Keep `http://ros-server/` as the only operator entry point.
- Keep raw identifiers available as secondary diagnostic text while making primary labels Chinese.
- Use TDD: every behavior module starts with a failing Node assertion.

---

### Task 1: Chinese presentation mapping

**Files:**
- Create: `web/frontend/app/ui-labels.mjs`
- Modify: `web/frontend/scripts/test-contract.mjs`
- Modify: `web/frontend/app/page.js`

**Interfaces:**
- Produces: `assetLabel(id)`, `categoryLabel(value)`, `riskLabel(value)`, `missionStateLabel(value)`, `robotModeLabel(value)`, `scenarioLabel(value)`, `modelLabel(value)`, `eventLabel(value)`, `commandErrorLabel(value)`.

- [ ] Add Node assertions for every production asset/category plus unknown fallback and the motion-safety error.
- [ ] Run `npm --prefix web/frontend run test:contract` and confirm it fails because `ui-labels.mjs` does not exist.
- [ ] Implement the mapping module with deterministic fallbacks.
- [ ] Replace visible engineering enums and English headings in `page.js` with the mapping functions and Chinese copy.
- [ ] Run the contract test and confirm PASS.

### Task 2: Interactive occupancy viewport

**Files:**
- Create: `web/frontend/app/map-viewport.mjs`
- Modify: `web/frontend/scripts/test-contract.mjs`
- Modify: `web/frontend/app/page.js`
- Modify: `web/frontend/app/globals.css`

**Interfaces:**
- Produces: `DEFAULT_VIEWPORT`, `zoomViewport(viewport, factor)`, `panViewport(viewport, dx, dy)`, `rotateViewport(viewport, degrees)`, and `viewportTransform(viewport)`.

- [ ] Add Node assertions for zoom clamping, pan accumulation, 15° rotation and reset state.
- [ ] Run the contract test and confirm it fails because `map-viewport.mjs` does not exist.
- [ ] Implement the pure viewport helpers.
- [ ] Wrap canvas and SVG in one transformed layer and add wheel, pointer-drag, rotate, zoom and reset controls.
- [ ] Add current zoom/rotation status and Chinese interaction guidance.
- [ ] Run contract tests and the production build.

### Task 3: Safe one-action autonomous inspection

**Files:**
- Create: `web/frontend/app/command-flow.mjs`
- Modify: `web/frontend/scripts/test-contract.mjs`
- Modify: `web/frontend/app/page.js`

**Interfaces:**
- Produces: `needsMissionStop(robot, mission)`, `needsMissionStart(mission)`, `needsAutonomousMode(robot)`, and `recoverySteps(robot, mission)` for deterministic flow planning.
- `page.js` executes returned steps using the existing REST endpoints and fresh snapshot revisions.

- [ ] Add Node assertions for latched/running, unlatched/stopped, manual/running, and autonomous/running states.
- [ ] Run the contract test and confirm it fails because `command-flow.mjs` does not exist.
- [ ] Implement the pure flow planner.
- [ ] Add command polling, bounded motion-barrier retry, snapshot waiting and the “恢复并开始自动巡检” action.
- [ ] Translate terminal command errors through `commandErrorLabel` and display a Chinese safety banner.
- [ ] Verify the live API flow reaches `robot.mode=autonomous` and robot displacement exceeds 0.2 m in 10 seconds.

### Task 4: Readability, release and live verification

**Files:**
- Modify: `web/frontend/app/globals.css`

- [ ] Raise base, secondary, button, panel and navigation font sizes while retaining the existing responsive breakpoints.
- [ ] Run `npm --prefix web/frontend run test:contract` and `npm --prefix web/frontend run build`.
- [ ] Run Gateway and integration regression suites.
- [ ] Commit and push the implementation.
- [ ] Build an immutable release with `bash scripts/deployment/build_release.sh`.
- [ ] Activate it with `sudo bash scripts/deployment/activate_latest_release.sh`.
- [ ] Verify Chinese labels, map interactions, autonomous motion, four installed models, ten assets, camera frames and scenario trigger/reset.

