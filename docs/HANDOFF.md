# 工作交接与恢复入口

## 当前恢复快照

- 当前阶段：Phase 1 Task 1–5 已完成，继续 Task 6 AI 虚拟环境；不要重新运行主机安装。
- 当前 acceptance run：`c2d99d10-058f-4033-aa33-89917bf74590`。
- 当前 evidence staging：`/var/lib/substation/evidence/acceptance/c2d99d10-058f-4033-aa33-89917bf74590/01-environment.staging`。
- 最近实现提交：`ae94eae feat: add ros workspace baseline`；最近状态同步提交应在该实现提交之后单独创建。
- Task 5 证据已通过：`rosdep-update.log`、`rosdep-check.log`、`colcon-build.log`、`colcon-test.log`、`colcon-test-result.log`、`setup-ros-workspace.log`。

- Repository: `/home/jackeyliu37/substation-inspection-digital-twin`
- Branch: `main`
- Phase 0 contract snapshot commit: `d0fb12dbe794221f88abb777f31760bdee655783`
- Phase 0 contract snapshot subject: `docs: complete phase zero contracts`
- Status-record commit: resolve with `git log -1 --format=%H -- README.md docs/PROJECT_STATUS.md docs/HANDOFF.md`. This record intentionally does not embed its own commit hash.
- Phase 1 execution: fast-track documentation gate, acceptance-run initialization, lightweight host preflight, early resource downloads, and model/data responsibility synchronization are complete. No dependency installation, ROS package creation, virtual environment creation, server configuration change, or Gazebo/Nav2/Web launch has occurred.
- Phase 1 Task 1 implementation commit: `d049f62bd39b910c2e5fe41ace80b778f14da509` (`feat: add phase one documentation gate`).
- Phase 1 fast-track simplification commit: `2f5b2e16c623e32746b42b7fc01626784aabf316` (`docs: simplify phase one fast track`).
- Phase 1 lightweight host preflight commit: `9edb7a2ccbe745e9a7123a5385b514c22f10715d` (`feat: add lightweight phase one host preflight`).
- Phase 1 resource download commit: `6e79e70274817710ddbd3b347c38bad648886549` (`feat: download phase one base resources`).
- Model/data responsibility contract commit: `21ea620c656030ec12c902de3cbd9d547b509a39` (`docs: externalize model training inputs`).
- Phase 1 run id: `a9ab99ee-a85e-4c6f-a9bd-65b421efc8ca`.
- Phase 1 evidence staging: `/var/lib/substation/evidence/acceptance/a9ab99ee-a85e-4c6f-a9bd-65b421efc8ca/01-environment.staging`.
- Phase 1 evidence final target: `/var/lib/substation/evidence/acceptance/a9ab99ee-a85e-4c6f-a9bd-65b421efc8ca/01-environment`.
- Acceptance identity commit in `git_commit.txt`: `99a2709f5a0f4d51eb7af99d3c440b06f5e28ad9`.
- Resource manifest: `artifacts/environment/resource-downloads.tsv`.
- Resource evidence: `/var/lib/substation/evidence/acceptance/a9ab99ee-a85e-4c6f-a9bd-65b421efc8ca/01-environment.staging/resource-downloads.tsv`.
- Download log: `/var/lib/substation/evidence/acceptance/a9ab99ee-a85e-4c6f-a9bd-65b421efc8ca/01-environment.staging/download-phase1-resources.log`.
- Locked resources:
  - Node.js 24.18.0 tarball: `/var/lib/substation/downloads/node/24.18.0/node-v24.18.0-linux-x64.tar.xz`, SHA-256 `55aa7153f9d88f28d765fcdad5ae6945b5c0f98a36881703817e4c450fa76742`, size `31511588`.
  - YOLO11n base weight: `/var/lib/substation/models/base/0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1/yolo11n.pt`, SHA-256 `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`, size `5613764`.
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
- Public training data download and all model fine-tuning are user-owned external work. The repository keeps official `yolo11n.pt` only as a non-production development base weight and later imports production models solely from a user-controlled immutable GitHub release or fixed commit with manifest, SHA-256, metrics, byte counts, and allowed-use metadata.

## Fast-track execution note

The user clarified on 2026-07-23 that this is a personal project and requested a simplified path. Treat “Task” as an internal Phase checkpoint only; user-facing execution should be phase-based. Use the solo fast-track overlay in `docs/plans/PHASE-01-ENVIRONMENT.md`. Do not run heavyweight fake-host security matrices unless a concrete failure requires them. Keep the hard boundaries: Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic OGRE2/EGL headless, no desktop/remote/virtual display stack, no unverified payload, no service start, no public dataset download, and no third-party production model search.

## First resume command after operator action

Run exactly:

```bash
cd /home/jackeyliu37/substation-inspection-digital-twin && source .phase1-run.env && test -d "$PHASE1_EVIDENCE_ROOT" && sed -n '1,120p' docs/plans/PHASE-01-ENVIRONMENT.md
```

Then continue with the environment installation/toolchain preparation checkpoint. Do not start Gazebo/Nav2/Web/Nginx services, download public training data, or search for third-party production models.

## Recovery checks

```bash
cd /home/jackeyliu37/substation-inspection-digital-twin
git branch --show-current
git log -6 --oneline --decorate
git status --short --untracked-files=all
```

Expected branch is `main`; status output should be empty except for ignored `.superpowers/sdd/` reports when inspected with ignored-file flags.

## Next implementation action

Proceed to Task 6: create and verify the CUDA-enabled AI virtual environment from the planned hash-locked requirements. Preserve Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic OGRE2/EGL headless rendering and the FastAPI-only product browser boundary.
