# 工作交接与恢复入口

## 当前恢复快照

- Repository: `/home/jackeyliu37/substation-inspection-digital-twin`
- Branch: `main`
- Phase 0 contract snapshot commit: `d0fb12dbe794221f88abb777f31760bdee655783`
- Phase 0 contract snapshot subject: `docs: complete phase zero contracts`
- Status-record commit: resolve with `git log -1 --format=%H -- README.md docs/PROJECT_STATUS.md docs/HANDOFF.md`. This record intentionally does not embed its own commit hash.
- Phase 1 execution: not started; no host mutation, dependency installation, ROS package creation, resource or model download, server configuration change, acceptance-run initialization, or Gazebo/Nav2/Web launch has occurred.
- Phase 1 runtime artifacts: none. No `/var/lib/substation/evidence/acceptance/<run_id>/` directory has been initialized by this Phase 0 work.
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

## First resume command

Run exactly:

```bash
cd /home/jackeyliu37/substation-inspection-digital-twin && sed -n '1,240p' docs/plans/PHASE-01-ENVIRONMENT.md
```

Then, only if the user asks to enter Phase 1, start Task 1 Step 1. Do not install, download, start services or initialize a Phase 1 acceptance run before the planned documentation gate/bootstrap sequence reaches that point.

## Recovery checks

```bash
cd /home/jackeyliu37/substation-inspection-digital-twin
git branch --show-current
git log -6 --oneline --decorate
git status --short --untracked-files=all
```

Expected branch is `main`; status output should be empty except for ignored `.superpowers/sdd/` reports when inspected with ignored-file flags.

## Next implementation action

Start Phase 1 Task 1 from `docs/plans/PHASE-01-ENVIRONMENT.md`: create the failing documentation-gate test, then implement only the read-only validator, shared helpers and acceptance-run initialization defined there. Preserve Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic OGRE2/EGL headless rendering and the FastAPI-only product browser boundary.
