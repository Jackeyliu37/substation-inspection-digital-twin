# 工作交接与恢复入口

## 当前恢复快照

- Repository: `/home/jackeyliu37/substation-inspection-digital-twin`
- Branch: `main`
- Phase 0 contract snapshot commit: `d0fb12dbe794221f88abb777f31760bdee655783`
- Phase 0 contract snapshot subject: `docs: complete phase zero contracts`
- Status-record commit: resolve with `git log -1 --format=%H -- README.md docs/PROJECT_STATUS.md docs/HANDOFF.md`. This record intentionally does not embed its own commit hash.
- Phase 1 execution: Task 1 documentation gate and acceptance-run initialization are complete. No dependency installation, ROS package creation, resource or model download, server configuration change, or Gazebo/Nav2/Web launch has occurred.
- Phase 1 Task 1 implementation commit: `d049f62bd39b910c2e5fe41ace80b778f14da509` (`feat: add phase one documentation gate`).
- Phase 1 run id: `a9ab99ee-a85e-4c6f-a9bd-65b421efc8ca`.
- Phase 1 evidence staging: `/var/lib/substation/evidence/acceptance/a9ab99ee-a85e-4c6f-a9bd-65b421efc8ca/01-environment.staging`.
- Phase 1 evidence final target: `/var/lib/substation/evidence/acceptance/a9ab99ee-a85e-4c6f-a9bd-65b421efc8ca/01-environment`.
- Acceptance identity commit in `git_commit.txt`: `99a2709f5a0f4d51eb7af99d3c440b06f5e28ad9`.
- Current blocker: none.
- Phase 0 final verification output: `.superpowers/sdd/final-phase0-fix-report.md` after the status-record commit. The file is ignored because it records post-commit evidence without changing the verified Git snapshot.

## Fixed contract decisions to preserve

- Browser clients use only Nginx plus FastAPI REST/WebSocket; they never connect directly to ROS DDS.
- All Web-visible ROS `uint64` values and Gateway revisions are decimal strings; binary camera headers remain network-order `uint64`.
- Evidence store is the single writer for run time mappings and evidence object identity; standard ROS messages need explicit immutable source metadata for run attribution.
- Mission ordering uses `configs/mission_ordering.yaml` defaults, active-task hold, normal cooldown and emergency bypass exactly as specified in `docs/INTERFACES.md`.
- Phase 1 keeps the current authorized operator checkout valid for development; the `substation` account is a later service runtime account.
- NVIDIA `595.71.05` may be retained if Phase 1 audit proves it compliant. The plan does not invoke automatic driver installation; driver noncompliance stops at `DRIVER_TRANSACTION_REQUIRED`.
- Ubuntu official NVIDIA inert X dependencies are allowed only as package dependencies with no active graphics stack, session, display manager, virtual display or remote desktop service.
- Phase 1 capacity means per-operation residual free space of at least `20 GiB`; full dataset capacity is a later expected-size gate.

## Fast-track execution note

The user clarified on 2026-07-23 that this is a personal project and requested a simplified path. Treat “Task” as a Phase 1 checkpoint. Use the solo fast-track overlay in `docs/plans/PHASE-01-ENVIRONMENT.md`: lightweight host preflight, then Node.js and YOLO11n downloads with hashes. Do not run heavyweight fake-host security matrices unless a concrete failure requires them.

## First resume command after operator action

Run exactly:

```bash
cd /home/jackeyliu37/substation-inspection-digital-twin && source .phase1-run.env && test -d "$PHASE1_EVIDENCE_ROOT" && sed -n '1,120p' docs/plans/PHASE-01-ENVIRONMENT.md
```

Then continue with lightweight host preflight. Do not install packages or start services before the preflight passes.

## Recovery checks

```bash
cd /home/jackeyliu37/substation-inspection-digital-twin
git branch --show-current
git log -6 --oneline --decorate
git status --short --untracked-files=all
```

Expected branch is `main`; status output should be empty except for ignored `.superpowers/sdd/` reports when inspected with ignored-file flags.

## Next implementation action

Implement the fast-track lightweight preflight, then prepare/download only Node.js 24.18.0 and `yolo11n.pt` with SHA-256 evidence. Preserve Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic OGRE2/EGL headless rendering and the FastAPI-only product browser boundary.
