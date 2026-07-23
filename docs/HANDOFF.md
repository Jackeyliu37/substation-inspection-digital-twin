# 工作交接与恢复入口

## 当前恢复快照

- Repository: `/home/jackeyliu37/substation-inspection-digital-twin`
- Branch: `main`
- Phase 0 contract snapshot commit: `d0fb12dbe794221f88abb777f31760bdee655783`
- Phase 0 contract snapshot subject: `docs: complete phase zero contracts`
- Status-record commit: resolve with `git log -1 --format=%H -- README.md docs/PROJECT_STATUS.md docs/HANDOFF.md`. This record intentionally does not embed its own commit hash.
- Phase 1 execution: Task 1 implementation commit exists, but live acceptance-run initialization is blocked by the current non-interactive `sudo` channel. No dependency installation, ROS package creation, resource or model download, server configuration change, or Gazebo/Nav2/Web launch has occurred.
- Phase 1 Task 1 implementation commit: `d049f62bd39b910c2e5fe41ace80b778f14da509` (`feat: add phase one documentation gate`).
- Phase 1 runtime artifacts: none. `.phase1-run.env`, `/var/lib/substation`, `/var/lib/substation/evidence/acceptance`, `/opt/substation`, and `/opt/substation/toolchains` were confirmed absent after the failed initialization attempt.
- Current blocker: `scripts/init_phase1_run.sh` needs to run `sudo install` for planned storage roots, but this execution channel cannot answer the password prompt. `sudo -n true` returns `sudo: a password is required`.
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

## Operator action required

Run this from an interactive shell where you can enter the sudo password:

```bash
cd /home/jackeyliu37/substation-inspection-digital-twin
gate_log="$(mktemp --tmpdir=/tmp)"
bash scripts/verify_documentation_gate.sh | tee "$gate_log"
bash scripts/init_phase1_run.sh --gate-log "$gate_log"
unlink -- "$gate_log"
```

Expected result: `.phase1-run.env` exists, `PHASE1_EVIDENCE_ROOT` ends in `/01-environment.staging`, `PHASE1_EVIDENCE_FINAL` ends in `/01-environment`, and the staging directory contains `acceptance_run_id.txt`, `git_commit.txt`, `documentation-gate.log`, and `storage-paths-before.tsv`. Do not run package installation, resource download, ROS, Gazebo, Nginx, or frontend commands as part of this operator action.

## First resume command after operator action

Run exactly:

```bash
cd /home/jackeyliu37/substation-inspection-digital-twin && source .phase1-run.env && test -d "$PHASE1_EVIDENCE_ROOT" && git log -1 --oneline
```

Then continue Task 1 Step 6 by writing `test-documentation-gate.log`, verifying `git_commit.txt` equals `d049f62bd39b910c2e5fe41ace80b778f14da509`, and updating status/handoff. Do not install, download, or start services before Task 2 preflight and later planned gates allow it.

## Recovery checks

```bash
cd /home/jackeyliu37/substation-inspection-digital-twin
git branch --show-current
git log -6 --oneline --decorate
git status --short --untracked-files=all
```

Expected branch is `main`; status output should be empty except for ignored `.superpowers/sdd/` reports when inspected with ignored-file flags.

## Next implementation action

Complete Phase 1 Task 1 live initialization after the operator action above. Preserve Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic OGRE2/EGL headless rendering and the FastAPI-only product browser boundary.
