# Phase 1 Environment Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and prove a reproducible Ubuntu 24.04 environment for ROS 2 Jazzy, Gazebo Harmonic OGRE2/EGL headless rendering, CUDA-enabled YOLO11n development, the FastAPI ROS Gateway, and the locked Next.js frontend before Phase 2 world development begins.

**Architecture:** A documentation gate runs before the first host mutation. Small idempotent scripts then audit the host, install only the approved repositories and packages, acquire early external resources into `/var/lib/substation`, build an empty ROS workspace baseline, create isolated AI and Gateway virtual environments, create the frontend baseline, exercise Gazebo through EGL with `DISPLAY` removed, and consolidate every result into one checksummed acceptance directory. Git stores scripts, tests, lock files, manifests, source code, and checksums; large downloads, virtual environments, build trees, logs, model files, and acceptance payloads stay on the Ubuntu server.

**Tech Stack:** Ubuntu 24.04 LTS, Bash, Python 3.12, ROS 2 Jazzy Jalisco, `colcon`, Gazebo Harmonic `gz-sim 8.x`, OGRE2/EGL, NVIDIA driver `>=560.35.05`, PyTorch 2.12.1 CUDA 12.6, Ultralytics 8.4.104, FastAPI 0.139.2, Node.js 24.18.0, npm, Next.js 16.2.11, React 19.2.8, TypeScript 6.0.3, Git, SHA-256.

## Global Constraints

- The root project plan is the scope authority. This phase creates only the environment, repository baselines, early immutable resource downloads, tests, and evidence required by Phase 1 acceptance.
- Use Ubuntu 24.04 LTS, ROS 2 Jazzy Jalisco, Gazebo Harmonic `gz-sim 8.x`, and Python 3.12. Stop if the host or resolved upstream versions contradict `docs/VERSION_MATRIX.md`.
- Preserve the approved ROS upstream identities: `ros_gz 1.0.23-1`, Navigation2 `1.3.12-1`, SLAM Toolbox `2.8.5-1`, TurtleBot3 core `2.3.6-1`, and TurtleBot3 simulation `2.3.7-1`; full Noble package revisions enter the Debian manifest.
- Gazebo rendering is OGRE2/EGL headless only. Ubuntu desktop metapackages, GNOME/KDE shells, display managers, NoMachine, Xvfb, VirtualGL, active `Xorg`/`Xwayland`/Wayland sessions, graphical targets, and project-created X Server configuration are forbidden. Ubuntu official NVIDIA driver packages may retain inert X package dependencies only under ADR-0004 evidence.
- Do not introduce ROS 1, Gazebo Classic, another ROS distribution, Conda CUDA, Ubuntu `nvidia-cuda-toolkit`, a global `sudo pip`, or pip CUDA packages outside the approved PyTorch CUDA 12.6 wheel source.
- The AI environment is repository-root `.venv`; the Gateway environment is repository-root `.venv-web`; both use `python3 -m venv --system-site-packages` so ROS `rclpy` remains available.
- The product browser boundary is unchanged: normal users eventually access only `http://ros-server/`; browsers never connect to DDS; Gateway and frontend processes remain loopback-only; Foxglove remains a separate read-only diagnostic path.
- Development may run from the current authorized operator checkout, including `/home/jackeyliu37/substation-inspection-digital-twin`. The `substation` account is the later no-login systemd service user fixed by `docs/DEPLOYMENT.md`, not a Phase 1 development-checkout precondition. Deployment releases are built only from clean verified commits under `/opt/substation/releases/<git-commit>`.
- Safety detection, equipment detection, defect classification, and meter reading stay separate. The only Phase 1 model download is the immutable YOLO11n base weight; it is not a production model.
- Instrument data remains Gazebo-generated only. Phase 1 does not add, download, or describe an external meter dataset.
- Every manually acquired external payload in this phase, specifically the Node.js archive and `yolo11n.pt`, is written below `/var/lib/substation`, receives a SHA-256 and byte count, and is recorded in `artifacts/environment/resource-downloads.tsv`. Large payloads never enter Git.
- Dataset source downloads are not silently mixed into the environment phase, and the user explicitly removed dataset downloading and model fine-tuning from this agent's execution scope on 2026-07-23. `config/environment/resource-sources.tsv` records public dataset identities only as external user-training references; this repository does not download them unless the user gives a later explicit instruction.
- `InsPLAD` is not fetched from a floating branch. If it appears in a user-provided training manifest, that manifest must still name one complete 40-character revision as required by `docs/DATA_AND_MODELS.md`.
- The official `yolo11n.pt` is the Phase 1 placeholder/base weight. Production safety, equipment, defect, and meter locator weights are accepted later only from a user-published immutable GitHub release or commit with manifest metadata, SHA-256, metrics, and allowed-use fields.
- Do not modify original public data. Do not commit raw/derived datasets, weights, virtual environments, `node_modules`, ROS build/install/log trees, acceptance evidence, service logs, or rosbag2.
- Tests precede implementation in every task. A test is first run against the missing or incomplete implementation and must fail for the stated reason; after the minimal implementation it must pass.
- Initial host snapshots and source backups are write-once, and the complete evidence tree becomes immutable after its final recursive `SHA256SUMS` is published. Rollback preserves `/var/lib/substation/evidence`; it reverts tracked code or restores only explicitly recorded files/packages.
- Tasks 1-9 write only to the fresh unsealed sibling `01-environment.staging`. Task 10 refuses any staging or final target that already contains `SHA256SUMS`, writes the checksum as its last staging mutation, and atomically renames the directory to `01-environment`. A sealed directory is read-only forever; retries use a new acceptance run.
- Verification is read-only with respect to installed packages, apt sources, persistent resources, toolchains, and virtual environments. In particular, the consolidated verifier invokes the checksum-only resource verifier and never invokes a downloader, installer, lock compiler, `npm install`, or environment setup script.
- Existing storage parents, virtual environments, toolchains, symlinks, apt sources, service-suppression files, and content-addressed resource directories are foreign unless their exact metadata or task-owned provenance marker proves compatibility. Refuse incompatible state; never recursively change ownership or permissions on an existing directory.
- Never remove packages with automatic dependency cleanup. Package rollback may remove only package names recorded as newly installed by `scripts/install_host.sh`, using `apt-get remove --no-auto-remove` after human review.
- Do not overwrite existing virtual environments, toolchains, manifests, repository files, or apt source/key files. Refuse, back up to the active evidence directory, or move the exact owned path to a timestamped quarantine name.
- Any version mismatch, missing SHA-256, forbidden active graphics stack, disallowed package/source origin, physical memory below 15 GiB, insufficient Phase 1 working-space margin, failed CUDA check, failed colcon command, failed frontend build, or failed EGL probe is a hard failure.
- Phase 1 storage checks are scoped to the environment baseline. Before every payload download, toolchain extraction, build tree, environment install, and final seal, the script records expected additional bytes and proves the affected mount will retain at least 20 GiB free after the operation. Later dataset/model phases must run a separate gate of `expected download bytes + expected unpacked/derived bytes + 20 GiB remaining`; Phase 1 success never means the full data/training footprint is already provisioned.
- After `docs/PROJECT_STATUS.md` and `docs/HANDOFF.md` exist, every Phase 1 task updates them at the end of that task's verification, not only in Task 11. Each update records the task commit, exact commands, result, evidence path, blockers, and next action. Final documents distinguish the verified implementation commit from the later documentation-only synchronization commit.

---

## Solo Fast-Track Execution Overlay

The user authorized a faster solo-project execution path on 2026-07-23. In this overlay, “Task” means a Phase 1 implementation checkpoint, not the complete product task system. The detailed task list below remains a reference, but execution may combine low-risk checks when the combined checkpoint still records a fixed commit, exact commands, evidence paths, blockers, and the next action.

The fast-track path for the current resource-preparation push is:

1. Finish Task 1 run identity and documentation gate evidence.
2. Run a lightweight host preflight that checks the hard blockers only: Ubuntu 24.04, x86_64, memory and free-space floors, NVIDIA GPU/driver presence, forbidden desktop/remote-display/virtual-display packages, non-Jazzy ROS and Gazebo Classic packages, and absence of active project services.
3. Prepare and download only the Phase 1 early external payloads: Node.js 24.18.0 and official `yolo11n.pt`, with URL, byte count and SHA-256 evidence under the active acceptance staging directory and tracked manifests under `artifacts/environment/`.
4. Treat public training datasets and fine-tuned production weights as user-owned external training inputs. The environment phase must not download datasets or search for third-party production weights.

The overlay deliberately omits heavyweight fake-host security matrices and exhaustive apt-origin simulation for this personal project. It does not relax these hard boundaries: no desktop or remote/virtual display stack, no ROS 1 or non-Jazzy ROS, no Gazebo Classic, no unverified resource payload, no dataset download, no third-party production model search/download, no service start, no dependency installation outside the active checkpoint, and no claim of Phase 1 completion until the final environment verifier is implemented and passes.

---

## Exact Phase 1 File Map

### Tracked files created by this plan

| Path | Single responsibility |
|---|---|
| `.gitignore` | Exclude local virtual environments, Node/ROS build trees, local run state, large resource payloads, and runtime evidence while leaving manifests and checksums trackable. |
| `config/environment/apt-packages.txt` | Exact explicit Debian package request set for the Ubuntu, ROS 2, Gazebo, navigation, build, SQLite, Nginx, and diagnostic baseline. |
| `config/environment/forbidden-packages.regex` | Anchored installed-package name patterns that make headless acceptance fail. |
| `config/environment/resource-sources.tsv` | Source identity and phase sequence for Node.js, official YOLO11n, user-owned public training references, and Gazebo synthetic resources. |
| `scripts/lib/environment_common.sh` | Shared argument, repository-root, evidence-path, command, and SHA-256 helpers used by Phase 1 scripts. |
| `scripts/verify_documentation_gate.sh` | Re-run the Phase 0 document gate without changing the host. |
| `scripts/init_phase1_run.sh` | Create one acceptance run directory after the document gate passes and write ignored `.phase1-run.env`. |
| `scripts/audit_host.sh` | Read-only OS, architecture, GPU, driver, memory, disk, forbidden-package, and session audit. |
| `scripts/install_host.sh` | Add only official ROS/Gazebo apt sources, validate every requested and changed package candidate/origin, preserve write-once before/after evidence, install the approved non-driver package set, refuse NVIDIA driver changes with `DRIVER_TRANSACTION_REQUIRED`, and leave services stopped. |
| `scripts/rollback_host.sh` | Validate recorded backups/current state, simulate the exact package rollback transaction, then restore only recorded packages, apt sources, service state, and task-created files after explicit run-id confirmation. |
| `scripts/download_phase1_resources.sh` | Download and verify Node.js 24.18.0 and YOLO11n v8.4.0 into controlled server storage. |
| `scripts/verify_phase1_resources.sh` | Read-only checksum/metadata verification of the already locked Node and YOLO resources; it has no network or repair path. |
| `scripts/setup_ros_workspace.sh` | Source Jazzy and run the canonical colcon build/test/test-result baseline. |
| `scripts/compile_requirements.sh` | Resolve one Python input file to a fully hashed lock with a short-lived pinned `pip-tools` resolver environment. |
| `scripts/lib/venv_provenance.py` | Write or verify task-owned virtual-environment provenance against kind, Python/system-site state, and exact lock SHA before any environment mutation. |
| `scripts/setup_python_env.sh` | Create `.venv`, install the AI lock with `--require-hashes`, and prove the locked CUDA stack. |
| `scripts/setup_gateway_env.sh` | Create `.venv-web`, install the Gateway lock with `--require-hashes`, and prove `rclpy` plus locked Web packages. |
| `scripts/write_frontend_manifest.py` | Write the exact frontend dependency manifest while taking the npm version only from Node.js 24.18.0. |
| `scripts/setup_web_env.sh` | Install the verified Node toolchain under `/opt/substation/toolchains`, generate `package-lock.json`, run `npm ci`, and run the production build. |
| `scripts/smoke_headless_egl.sh` | Launch a minimal Gazebo camera world with `DISPLAY` removed and prove a rendered RGB frame arrives through Gazebo Transport. |
| `scripts/capture_environment_lock.sh` | Capture the reviewed Debian/Python/npm/resource environment into tracked text manifests and a stable SHA-256 file. |
| `scripts/verify_environment.sh` | One-shot Phase 1 acceptance entry point that verifies the committed implementation, writes the final recursive checksum as the last staging mutation, and atomically publishes immutable evidence. |
| `scripts/check_environment_seal.sh` | Read-only recursive checksum and result-schema validation for an already sealed Phase 1 evidence directory. |
| `requirements.in` / `requirements.lock` | Exact AI direct requirements and fully resolved hash-locked dependency graph. |
| `requirements-web.in` / `requirements-web.lock` | Exact Gateway direct requirements and fully resolved hash-locked dependency graph. |
| `ros2_ws/src/.gitkeep` | Preserve the Phase 1 ROS source root without inventing a package outside the project plan. |
| `web/frontend/package.json` | Exact direct frontend versions and the npm version shipped by the verified Node tarball. |
| `web/frontend/package-lock.json` | npm lockfile v3 dependency graph. |
| `web/frontend/next.config.mjs` | Minimal production Next.js configuration with no external server dependency. |
| `web/frontend/app/layout.js` | Minimal App Router root layout. |
| `web/frontend/app/page.js` | Environment-baseline page proving the frontend production build. |
| `web/frontend/app/globals.css` | Minimal local styling; no remote asset or font fetch. |
| `tests/environment/test_documentation_gate.sh` | Documentation gate contract test. |
| `tests/environment/test_audit_host.sh` | Read-only audit output and no-mutation contract test. |
| `tests/environment/test_install_host.sh` | Installer plan, package allowlist, forbidden stack, and idempotency contract test. |
| `tests/environment/fixtures/fake_host_command.py` | PATH-injected fake apt, dpkg, systemctl, NVIDIA, sudo, and network command implementation used only against a guarded temporary filesystem root. |
| `tests/environment/test_phase1_resources.sh` | Resource source identity, checksum capture, and Git-exclusion contract test. |
| `tests/environment/test_ros_workspace.sh` | Jazzy sourcing and canonical empty-workspace colcon contract test. |
| `tests/environment/test_ai_environment.sh` | AI lock, version, CUDA, and system-site-packages contract test. |
| `tests/environment/test_gateway_environment.sh` | Gateway lock, exact versions, and `rclpy` contract test. |
| `tests/environment/test_web_environment.sh` | Node/npm ownership, exact direct versions, lockfile v3, `npm ci`, and build contract test. |
| `tests/environment/test_headless_egl.sh` | EGL smoke script and sensor-frame contract test. |
| `tests/environment/test_verify_environment.sh` | Guarded synthetic fresh-seal, existing-final refusal, and failed-unsealed-staging behavior test. |
| `tests/environment/fixtures/headless_camera.sdf` | Minimal Harmonic SDF world containing one OGRE2-rendered RGB camera. |
| `artifacts/environment/dpkg-packages.tsv` | Reviewed full Debian package/version snapshot used as the rebuild lock. |
| `artifacts/environment/ai-pip-freeze.txt` | Reviewed AI environment freeze. |
| `artifacts/environment/gateway-pip-freeze.txt` | Reviewed Gateway environment freeze. |
| `artifacts/environment/node-npm-versions.txt` | Reviewed Node/npm and frontend package-manager identity. |
| `artifacts/environment/resource-downloads.tsv` | Reviewed URL, immutable revision, SHA-256, size, and server target for Phase 1 external payloads. |
| `artifacts/environment/SHA256SUMS` | Stable relative checksums for the five tracked environment lock files. |

### Tracked files modified by this plan

| Path | Change |
|---|---|
| `docs/PROJECT_STATUS.md` | Record Phase 1 result, verified commit, evidence, commands, blockers, and Phase 2 next action. |
| `docs/HANDOFF.md` | Record deterministic per-task resume state, blockers, and the final Phase 2 resume entry. |

### Runtime-only paths created by this plan

| Path | Contents and ownership |
|---|---|
| `.phase1-run.env` | Ignored shell exports for `PHASE1_RUN_ID`, the active unsealed `PHASE1_EVIDENCE_ROOT` staging path, and `PHASE1_EVIDENCE_FINAL`; contains no secret. |
| `.venv`, `.venv-web` | Local Python environments; ignored and never deployed as source. |
| `build/`, `install/`, `log/` | ROS workspace outputs; ignored. |
| `web/frontend/node_modules/`, `web/frontend/.next/` | npm install and Next.js build outputs; ignored. |
| `/opt/substation/toolchains/node-v24.18.0` | Verified immutable Node.js toolchain; root-owned, world-readable. |
| `/opt/substation/toolchains/node-current` | Symlink to the verified 24.18.0 toolchain. |
| `/var/lib/substation/downloads/node/24.18.0/` | Node tarball and official checksum list. |
| `/var/lib/substation/models/base/$YOLO_BASE_SHA256/` | YOLO11n base weight, `.substation-resource.json`, and `source.json`, keyed by its actual SHA-256 and installed atomically as one owned leaf. |
| `/var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment.staging/` | Fresh unsealed working evidence used by Tasks 1-10; it must not contain `SHA256SUMS` before the final seal operation. |
| `/var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment/` | Atomically published immutable Phase 1 evidence after Task 10 writes `SHA256SUMS`; it is never reused or repaired. |

### Required final evidence files

The consolidated verifier must leave these non-empty files below `$PHASE1_EVIDENCE_FINAL`: `acceptance_run_id.txt`, `git_commit.txt`, `documentation-gate.log`, `documentation-gate-final.log`, `storage-paths-before.tsv`, `host-audit.json`, `host-audit-final.json`, `install-host.log`, `install-state.env`, `install-complete.env`, `apt-candidates.tsv`, `apt-changed-package-origins.tsv`, `apt-policy-origins.json`, `apt-sources-before/inventory.tsv`, `apt-sources-after/inventory.tsv`, `policy-rc.d-state.tsv`, `managed-files-after.tsv`, `host-install-version-changes.tsv`, `ros-archive-key.sha256`, `gazebo-archive-key.sha256`, `dpkg-before.tsv`, `dpkg-after.tsv`, `environment.json`, `dpkg-packages.tsv`, `ai-pip-freeze.txt`, `gateway-pip-freeze.txt`, `node-npm-versions.txt`, `node-current-before.tsv`, `resource-downloads.tsv`, `gpu.txt`, `egl.log`, `forbidden-packages.txt`, `disk-memory.txt`, `service-state.txt`, `colcon-build.log`, `colcon-test.log`, `colcon-test-result.log`, `colcon-build-final.log`, `colcon-test-final.log`, `colcon-test-result-final.log`, `frontend-build.log`, `frontend-build-final.log`, per-command logs and JSON metadata under `commands/`, `result.json`, and `SHA256SUMS`. `host-install-new-packages.txt` is also mandatory but may be empty on an already-provisioned compliant host. The recursive checksum includes every file under nested directories such as `apt-sources-before/` and `commands/`.

## Execution Rules for Every Task

1. Work from the repository root returned by `git rev-parse --show-toplevel`; do not hard-code the current developer's home directory into scripts or manifests.
2. Before editing, run `git status --short` and preserve unrelated changes. Stage only the paths listed by the current task.
3. Use `apply_patch` for tracked text changes. Machine-generated lock files are created only by the exact resolver commands in this plan and then reviewed with `git diff --check` and focused validators.
4. After Task 1 initializes the run and before Task 10 publishes the seal, every command that writes runtime evidence begins with:

   ```bash
   source .phase1-run.env
   test -n "$PHASE1_RUN_ID"
   test -d "$PHASE1_EVIDENCE_ROOT"
   ```

   After Task 10 succeeds, `$PHASE1_EVIDENCE_ROOT` no longer exists. Task 11 reads only `$PHASE1_EVIDENCE_FINAL` and invokes only `scripts/check_environment_seal.sh`; it never reruns the one-shot verifier.

5. Each test command is piped through `tee` only to the exact current evidence file. `PIPESTATUS[0]` is checked when the tested command's exit status matters.
6. Each task has a focused implementation commit before any live host mutation that depends on that implementation. After the task's verification, immediately update `docs/PROJECT_STATUS.md` and `docs/HANDOFF.md` with the task commit, exact commands, result, evidence path, blockers, and next action, then create a separate documentation-only status commit. Do not combine implementation commits with status/handoff commits.
7. Task 11 is the final aggregation and truthfulness check; it does not replace the per-task status updates required by rule 6.
8. If an authority conflict or locked-version mismatch appears, stop, save the command output in the active evidence directory, update the authority document through the repository's ADR/synchronization process, and do not continue this plan on an inferred interpretation.

---

### Task 1: Documentation Gate Validator and Acceptance Run Initialization

**Files:**
- Create: `.gitignore`
- Create: `scripts/lib/environment_common.sh`
- Create: `scripts/verify_documentation_gate.sh`
- Create: `scripts/init_phase1_run.sh`
- Create: `tests/environment/test_documentation_gate.sh`

**Interfaces:**
- Consumes: all Phase 0 authority documents, tracked Git state, `docs/PROJECT_STATUS.md`, and `docs/HANDOFF.md`.
- Produces: `bash scripts/verify_documentation_gate.sh`, ignored `.phase1-run.env`, a fresh `$PHASE1_EVIDENCE_ROOT` ending in `01-environment.staging`, an absent `$PHASE1_EVIDENCE_FINAL` ending in `01-environment`, and write-once storage-parent metadata.

- [ ] **Step 1: Write the failing documentation-gate test**

Create `tests/environment/test_documentation_gate.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

test -x scripts/verify_documentation_gate.sh
output="$(bash scripts/verify_documentation_gate.sh)"
grep -Fx 'documentation-gate: PASS' <<<"$output"
```

Run:

```bash
chmod +x tests/environment/test_documentation_gate.sh
bash tests/environment/test_documentation_gate.sh
```

Expected: exit nonzero at `test -x scripts/verify_documentation_gate.sh` because the validator does not exist. No host file, package, service, or evidence directory changes.

- [ ] **Step 2: Add the ignore policy and shared shell helpers**

Create `.gitignore` with this exact content:

```gitignore
.phase1-run.env
.venv/
.venv-web/
.venv.quarantine-*/
.venv-web.quarantine-*/
build/
install/
log/
web/frontend/node_modules/
web/frontend/.next/
web/frontend/npm-debug.log*
artifacts/environment/*.log
artifacts/environment/*.json
artifacts/environment/*.tmp
*.rosbag2
```

Create `scripts/lib/environment_common.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

environment_repo_root() {
  git rev-parse --show-toplevel
}

environment_require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'missing-command: %s\n' "$1" >&2
    return 1
  }
}

environment_require_evidence_dir() {
  local evidence_dir="$1"
  case "$evidence_dir" in
    /var/lib/substation/evidence/acceptance/*/01-environment.staging) ;;
    *)
      printf 'invalid-evidence-dir: %s\n' "$evidence_dir" >&2
      return 1
      ;;
  esac
  test -d "$evidence_dir" || {
    printf 'missing-evidence-dir: %s\n' "$evidence_dir" >&2
    return 1
  }
}

environment_require_final_evidence_target() {
  local evidence_dir="$1"
  case "$evidence_dir" in
    /var/lib/substation/evidence/acceptance/*/01-environment) ;;
    *)
      printf 'invalid-final-evidence-target: %s\n' "$evidence_dir" >&2
      return 1
      ;;
  esac
}

environment_prepare_owned_directory() {
  local manifest="$1"
  local path="$2"
  local expected_mode="$3"
  local expected_owner="$4"
  local expected_group="$5"
  local parent actual_mode actual_owner actual_group device inode
  expected_mode="${expected_mode#0}"
  test "${path#/}" != "$path"
  test "$path" != /
  if test -L "$path"; then
    printf 'refusing-symlink-directory: %s\n' "$path" >&2
    return 1
  fi
  if test -e "$path"; then
    test -d "$path"
    actual_mode="$(stat -c '%a' "$path")"
    actual_owner="$(stat -c '%U' "$path")"
    actual_group="$(stat -c '%G' "$path")"
    device="$(stat -c '%d' "$path")"
    inode="$(stat -c '%i' "$path")"
    printf '%s\t1\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t0\n' \
      "$path" "$actual_mode" "$actual_owner" "$actual_group" "$device" "$inode" \
      "$expected_mode" "$expected_owner" "$expected_group" >> "$manifest"
    test "$actual_mode" = "$expected_mode"
    test "$actual_owner" = "$expected_owner"
    test "$actual_group" = "$expected_group"
    return
  fi
  parent="$(dirname -- "$path")"
  test -d "$parent"
  test ! -L "$parent"
  printf '%s\t0\t-\t-\t-\t-\t-\t%s\t%s\t%s\t1\n' \
    "$path" "$expected_mode" "$expected_owner" "$expected_group" >> "$manifest"
  sudo install -d -m "$expected_mode" -o "$expected_owner" -g "$expected_group" "$path"
}

environment_sha256() {
  sha256sum -- "$1" | awk '{print $1}'
}
```

Expected: these files contain no runtime secrets and `.gitignore` does not exclude `artifacts/environment/*.tsv`, `*.txt`, or `SHA256SUMS`.

- [ ] **Step 3: Implement the read-only documentation validator**

Create `scripts/verify_documentation_gate.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

required_files=(
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
  docs/adr/0004-nvidia-headless-packaging.md
)

for path in "${required_files[@]}"; do
  test -s "$path" || {
    printf 'documentation-gate: missing-or-empty: %s\n' "$path" >&2
    exit 1
  }
  git ls-files --error-unmatch "$path" >/dev/null
done

python3 - <<'PY'
import re
import subprocess
from pathlib import Path

contract = Path("docs/TEST_ACCEPTANCE.md").read_text(encoding="utf-8")
try:
    phase0_full_gate = contract.split("### 4.4 完整可重复 Phase 0 gate", 1)[1].split(
        "## 5. Phase 1 主机与环境验收（当前活动阶段；入口逐项激活）", 1
    )[0]
except IndexError as error:
    raise SystemExit("documentation-gate: Phase 0 full gate section not found") from error

blocks = re.findall(r"```bash\n(.*?)\n```", phase0_full_gate, flags=re.DOTALL)
if len(blocks) != 1:
    raise SystemExit(
        f"documentation-gate: expected exactly one Phase 0 full-gate Bash block, found {len(blocks)}"
    )
completed = subprocess.run(["bash", "-c", blocks[0]], text=True)
if completed.returncode != 0:
    raise SystemExit(
        f"documentation-gate: TEST_ACCEPTANCE section 4.4 failed with exit {completed.returncode}"
    )
PY

printf '%s\n' 'documentation-gate: PASS'
```

The validator first enforces the complete required-file/tracked-file gate, including ADR-0004. It then extracts and executes the single full Bash block in `docs/TEST_ACCEPTANCE.md` section 4.4, so the authoritative Phase 0 gate cannot drift into an abbreviated duplicate. It reads repository files and Git metadata only; it does not call `sudo`, package managers, network clients, ROS, Gazebo, or services.

- [ ] **Step 4: Implement acceptance-run initialization**

Create `scripts/init_phase1_run.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

if test "$#" -ne 2 || test "$1" != --gate-log; then
  printf '%s\n' 'usage: bash scripts/init_phase1_run.sh --gate-log /tmp/documentation-gate.log' >&2
  exit 2
fi

gate_log="$2"
test -f "$gate_log"
grep -Fxq 'documentation-gate: PASS' "$gate_log"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
source scripts/lib/environment_common.sh
test ! -e .phase1-run.env || {
  printf '%s\n' '.phase1-run.env already exists; source it instead of creating a second run' >&2
  exit 1
}

phase1_run_id="$(python3 -c 'import uuid; print(uuid.uuid4())')"
phase1_acceptance_root="/var/lib/substation/evidence/acceptance/${phase1_run_id}"
phase1_evidence_root="$phase1_acceptance_root/01-environment.staging"
phase1_evidence_final="$phase1_acceptance_root/01-environment"
operator_user="$(id -un)"
operator_group="$(id -gn)"

test ! -e "$phase1_evidence_final"
metadata_work="$(mktemp --tmpdir=/tmp)"
cleanup() {
  test ! -e "$metadata_work" || unlink -- "$metadata_work"
}
trap cleanup EXIT
printf 'path\texisted_before\tmode_before\towner_before\tgroup_before\tdevice\tinode\texpected_mode\texpected_owner\texpected_group\tcreated_by_task\n' > "$metadata_work"
environment_prepare_owned_directory "$metadata_work" /var/lib/substation 0750 "$operator_user" "$operator_group"
environment_prepare_owned_directory "$metadata_work" /var/lib/substation/evidence 0750 "$operator_user" "$operator_group"
environment_prepare_owned_directory "$metadata_work" /var/lib/substation/evidence/acceptance 0750 "$operator_user" "$operator_group"
environment_prepare_owned_directory "$metadata_work" "$phase1_acceptance_root" 0750 "$operator_user" "$operator_group"
environment_prepare_owned_directory "$metadata_work" "$phase1_evidence_root" 0750 "$operator_user" "$operator_group"
environment_prepare_owned_directory "$metadata_work" /opt/substation 0755 root root
environment_prepare_owned_directory "$metadata_work" /opt/substation/toolchains 0755 root root
install -m 0640 "$metadata_work" "$phase1_evidence_root/storage-paths-before.tsv"
unlink -- "$metadata_work"
metadata_work=
install -m 0640 "$gate_log" "$phase1_evidence_root/documentation-gate.log"
printf '%s\n' "$phase1_run_id" > "$phase1_evidence_root/acceptance_run_id.txt"
git rev-parse HEAD > "$phase1_evidence_root/git_commit.txt"

umask 077
printf 'export PHASE1_RUN_ID=%q\n' "$phase1_run_id" > .phase1-run.env
printf 'export PHASE1_EVIDENCE_ROOT=%q\n' "$phase1_evidence_root" >> .phase1-run.env
printf 'export PHASE1_EVIDENCE_FINAL=%q\n' "$phase1_evidence_final" >> .phase1-run.env

printf 'PHASE1_RUN_ID=%s\n' "$phase1_run_id"
printf 'PHASE1_EVIDENCE_ROOT=%s\n' "$phase1_evidence_root"
printf 'PHASE1_EVIDENCE_FINAL=%s\n' "$phase1_evidence_final"

trap - EXIT
cleanup
```

Run:

```bash
chmod +x scripts/lib/environment_common.sh scripts/verify_documentation_gate.sh scripts/init_phase1_run.sh
gate_log="$(mktemp --tmpdir=/tmp)"
bash scripts/verify_documentation_gate.sh | tee "$gate_log"
unlink -- "$gate_log"
```

Expected: the validator prints exactly `documentation-gate: PASS` as its final line and no acceptance directory exists yet. Do not run `scripts/init_phase1_run.sh` until the Task 1 implementation commit exists and the worktree is clean.

- [ ] **Step 5: Commit Task 1 implementation before live evidence initialization**

```bash
git add .gitignore scripts/lib/environment_common.sh scripts/verify_documentation_gate.sh scripts/init_phase1_run.sh tests/environment/test_documentation_gate.sh
git diff --cached --check
git commit -m "feat: add phase one documentation gate"
task1_commit="$(git rev-parse HEAD)"
test -z "$(git status --porcelain=v1 --untracked-files=all -- \
  .gitignore scripts/lib/environment_common.sh scripts/verify_documentation_gate.sh scripts/init_phase1_run.sh tests/environment/test_documentation_gate.sh)"
```

Expected: one implementation commit containing only the five listed paths.

- [ ] **Step 6: Create the single acceptance run identity from the clean Task 1 commit**

Run:

```bash
test "$(git rev-parse HEAD)" = "$task1_commit"
gate_log="$(mktemp --tmpdir=/tmp)"
bash scripts/verify_documentation_gate.sh | tee "$gate_log"
bash scripts/init_phase1_run.sh --gate-log "$gate_log"
unlink -- "$gate_log"
source .phase1-run.env
test "$(<"$PHASE1_EVIDENCE_ROOT/git_commit.txt")" = "$task1_commit"
test -f "$PHASE1_EVIDENCE_ROOT/documentation-gate.log"
test -s "$PHASE1_EVIDENCE_ROOT/storage-paths-before.tsv"
test ! -e "$PHASE1_EVIDENCE_FINAL"
bash tests/environment/test_documentation_gate.sh | tee "$PHASE1_EVIDENCE_ROOT/test-documentation-gate.log"
test "${PIPESTATUS[0]}" -eq 0
```

Expected: initialization prints a UUID, a staging path ending in `/01-environment.staging`, and a final path ending in `/01-environment`; `acceptance_run_id.txt`, `git_commit.txt`, the copied gate log, storage metadata, and test log are non-empty. Existing storage directories are accepted only with the exact recorded owner/group/mode; missing leaves are created one at a time. No existing directory is recursively chmodded or chowned. The development checkout may be the current authorized operator checkout; the later deployment/runtime `substation` account is not required for this initializer.

Evidence: `$PHASE1_EVIDENCE_ROOT/documentation-gate.log` and `$PHASE1_EVIDENCE_ROOT/test-documentation-gate.log`.

Safe rollback: preserve the acceptance directory; move `.phase1-run.env` to `.phase1-run.env.rollback-$(date -u +%Y%m%dT%H%M%SZ)`; revert only this task's tracked commit. Do not remove the evidence directory.

- [ ] **Step 7: Update status and handoff for Task 1**

```bash
verified_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
script_sha256="$(sha256sum scripts/init_phase1_run.sh scripts/verify_documentation_gate.sh | LC_ALL=C sort -k2)"
printf 'task_commit=%s\nverified_at=%s\nevidence=%s\nscript_sha256_lines=%s\n' \
  "$task1_commit" "$verified_at" "$PHASE1_EVIDENCE_ROOT" "$script_sha256"
```

Use `apply_patch` to record the literal values in `docs/PROJECT_STATUS.md` and `docs/HANDOFF.md`, including the exact commands from Step 6. Then:

```bash
git add docs/PROJECT_STATUS.md docs/HANDOFF.md
git diff --cached --check
git commit -m "docs: record phase one task 1 status"
```

Expected: the acceptance run identity remains bound to `task1_commit`; the status commit is documentation-only and does not replace `git_commit.txt`.

---

### Task 2: Read-Only Host Audit

**Files:**
- Create: `config/environment/apt-packages.txt`
- Create: `config/environment/forbidden-packages.regex`
- Create: `scripts/audit_host.sh`
- Create: `tests/environment/test_audit_host.sh`

**Interfaces:**
- Consumes: `/etc/os-release`, `/proc/meminfo`, all apt source files (`sources.list`, `*.list`, and deb822 `*.sources`), `apt-cache policy`, `dpkg-query`, independent filesystem/mount statistics for the repository, `/var/lib/substation`, and `/opt/substation`, plus GPU/driver probes.
- Produces: JSON containing source hashes/URIs/suites/components, non-Noble or malformed source blockers, explicitly recorded unrelated external Noble sources, candidate/origin records for every project-requested package, three independent disk/mount records, generic non-Jazzy ROS rejection, forbidden installed/requested packages, inert NVIDIA graphics dependencies, and `$PHASE1_EVIDENCE_ROOT/host-audit.json`. `--preflight` allows only missing not-yet-added official ROS/Gazebo candidates; wrong requested-package origins/candidates, non-Jazzy ROS names, missing Ubuntu candidates, active graphics blockers, and insufficient memory/storage remain hard failures. Default enforcement additionally requires the final driver floor.

- [ ] **Step 1: Write the failing audit test**

Create `tests/environment/test_audit_host.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

test -x scripts/audit_host.sh
test -s config/environment/apt-packages.txt
test -f config/environment/forbidden-packages.regex

fixture_id="phase1-audit-fixture-$(python3 -c 'import uuid; print(uuid.uuid4())')"
fixture_root="/tmp/$fixture_id"
case "$fixture_root" in /tmp/phase1-audit-fixture-*) ;; *) exit 1 ;; esac
test ! -e "$fixture_root"
install -d -m 0700 \
  "$fixture_root/bin" \
  "$fixture_root/etc/apt/sources.list.d" \
  "$fixture_root/proc" \
  "$fixture_root/sys/bus/pci/devices/0000:01:00.0" \
  "$fixture_root/var/lib/substation" \
  "$fixture_root/opt/substation"
cleanup() {
  case "$fixture_root" in /tmp/phase1-audit-fixture-*) find "$fixture_root" -depth -delete ;; *) return 1 ;; esac
}
trap cleanup EXIT

cat > "$fixture_root/etc/os-release" <<'EOF'
ID=ubuntu
VERSION_ID="24.04"
PRETTY_NAME="Ubuntu 24.04 LTS"
EOF
cat > "$fixture_root/proc/meminfo" <<'EOF'
MemTotal:       33554432 kB
EOF
printf '%s\n' 0x10de > "$fixture_root/sys/bus/pci/devices/0000:01:00.0/vendor"
cat > "$fixture_root/etc/apt/sources.list" <<'EOF'
deb http://archive.ubuntu.com/ubuntu noble main universe
deb http://security.ubuntu.com/ubuntu noble-security main universe
EOF
cat > "$fixture_root/etc/apt/sources.list.d/ubuntu.sources" <<'EOF'
Types: deb
URIs: http://archive.ubuntu.com/ubuntu
Suites: noble-updates noble-backports
Components: main universe
EOF

cat > "$fixture_root/bin/dpkg-query" <<'SH'
#!/usr/bin/bash
printf 'ii \tros-jazzy-ros-base\nii \tnginx\nii \txserver-xorg-core\nii \txserver-xorg-video-nvidia-595\nii \tx11-common\n'
if test "${FAKE_DPKG_FORBIDDEN-0}" = 1; then
  printf 'ii \tubuntu-desktop\nii \tgdm3\nii \txvfb\nii \tros-noetic-ros-base\nii \tros-kilted-ros-base\nii \tros-eloquent-desktop\nii \tgazebo11\n'
fi
SH
cat > "$fixture_root/bin/apt-cache" <<'SH'
#!/usr/bin/bash
test "${1-}" = policy
package="${2-}"
if test -z "$package"; then
  printf '%s\n' '500 http://archive.ubuntu.com/ubuntu noble/main amd64 Packages'
  exit 0
fi
if test "${FAKE_APT_POLICY_MODE-}" = missing; then
  case "$package" in
    ros-jazzy-*|gz-harmonic)
      printf '%s\n' '  Candidate: (none)'
      exit 0
      ;;
  esac
fi
expected=1.0-1noble
origin=http://archive.ubuntu.com/ubuntu
case "$package" in
  gz-harmonic) expected=8.9.0-1~noble; origin=http://packages.osrfoundation.org/gazebo/ubuntu-stable ;;
  ros-jazzy-*)
    expected=1.0.23-1-1noble.20260701
    case "$package" in
      ros-jazzy-navigation2|ros-jazzy-nav2-bringup) expected=1.3.12-1-1noble.20260701 ;;
      ros-jazzy-slam-toolbox) expected=2.8.5-1-1noble.20260701 ;;
      ros-jazzy-turtlebot3) expected=2.3.6-1-1noble.20260701 ;;
      ros-jazzy-turtlebot3-simulations) expected=2.3.7-1-1noble.20260701 ;;
    esac
    origin=http://packages.ros.org/ros2/ubuntu
    ;;
esac
if test "${FAKE_APT_POLICY_MODE-}" = wrong && test "$package" = ros-jazzy-ros-gz; then
  expected=9.9.9-1
fi
if test "${FAKE_APT_POLICY_MODE-}" = foreign && test "$package" = nginx; then
  origin=https://ppa.launchpadcontent.net/vendor/project/ubuntu
fi
printf '  Candidate: %s\n' "$expected"
printf '     %s 500\n' "$expected"
printf '        500 %s noble/main amd64 Packages\n' "$origin"
SH
cat > "$fixture_root/bin/nvidia-smi" <<'SH'
#!/usr/bin/bash
printf '%s\n' 'NVIDIA RTX 3060 Ti, 560.35.05'
SH
cat > "$fixture_root/bin/lspci" <<'SH'
#!/usr/bin/bash
printf '%s\n' '01:00.0 VGA compatible controller: NVIDIA Corporation Device'
SH
cat > "$fixture_root/bin/findmnt" <<'SH'
#!/usr/bin/bash
target="${*: -1}"
printf '{"filesystems":[{"target":"%s","source":"fixture-%s","fstype":"ext4"}]}\n' "$target" "$(basename "$target")"
SH
chmod 0750 "$fixture_root/bin/"*

audit_json="$(
  PATH="$fixture_root/bin:$PATH" \
  SUBSTATION_AUDIT_TEST_ROOT="$fixture_root" \
  bash scripts/audit_host.sh --report-only
)"
python3 -c '
import json, sys
data = json.load(sys.stdin)
required = {"schema_version", "status", "os", "architecture", "memory_bytes", "disk_free_bytes", "disks", "apt_sources", "apt_policy", "gpu", "forbidden_packages", "forbidden_apt_sources", "checks"}
assert required <= data.keys()
assert {item["path"] for item in data["disks"]} == {"repository", "/var/lib/substation", "/opt/substation"}
assert data["disk_free_bytes"] == min(item["free_bytes"] for item in data["disks"])
assert {item["format"] for item in data["apt_sources"]} == {"list", "deb822"}
assert {item["suite"] for item in data["apt_sources"]} >= {"noble", "noble-security", "noble-updates", "noble-backports"}
assert data["apt_policy"]["ros-jazzy-ros-gz"]["origins"] == ["http://packages.ros.org/ros2/ubuntu"]
assert data["apt_policy"]["gz-harmonic"]["origins"] == ["http://packages.osrfoundation.org/gazebo/ubuntu-stable"]
assert data["forbidden_packages"] == []
assert {"xserver-xorg-core", "xserver-xorg-video-nvidia-595", "x11-common"} <= set(data["inert_nvidia_graphics_dependencies"])
assert data["forbidden_apt_sources"] == []
' <<<"$audit_json"

PATH="$fixture_root/bin:$PATH" \
FAKE_APT_POLICY_MODE=missing \
SUBSTATION_AUDIT_TEST_ROOT="$fixture_root" \
bash scripts/audit_host.sh --preflight >/dev/null
set +e
PATH="$fixture_root/bin:$PATH" \
FAKE_APT_POLICY_MODE=wrong \
SUBSTATION_AUDIT_TEST_ROOT="$fixture_root" \
bash scripts/audit_host.sh --preflight >/dev/null
wrong_policy_rc=$?
set -e
test "$wrong_policy_rc" -ne 0

set +e
PATH="$fixture_root/bin:$PATH" \
FAKE_APT_POLICY_MODE=foreign \
SUBSTATION_AUDIT_TEST_ROOT="$fixture_root" \
bash scripts/audit_host.sh --preflight >/dev/null
foreign_policy_rc=$?
set -e
test "$foreign_policy_rc" -ne 0

ln -s ubuntu.sources "$fixture_root/etc/apt/sources.list.d/active-symlink.sources"
set +e
PATH="$fixture_root/bin:$PATH" \
SUBSTATION_AUDIT_TEST_ROOT="$fixture_root" \
bash scripts/audit_host.sh --report-only >/dev/null
symlink_source_rc=$?
set -e
test "$symlink_source_rc" -ne 0
unlink -- "$fixture_root/etc/apt/sources.list.d/active-symlink.sources"

printf '%s\n' 'deb https://ppa.launchpadcontent.net/vendor/project/ubuntu noble main' > "$fixture_root/etc/apt/sources.list.d/noble-ppa.list"
printf '%s\n' 'deb https://vendor.example.invalid/ubuntu noble main' > "$fixture_root/etc/apt/sources.list.d/noble-vendor.list"
bad_uri_json="$(PATH="$fixture_root/bin:$PATH" SUBSTATION_AUDIT_TEST_ROOT="$fixture_root" bash scripts/audit_host.sh --report-only)"
python3 -c 'import json,sys; data=json.load(sys.stdin); assert len(data["external_apt_sources"]) >= 2; assert data["forbidden_apt_sources"] == []' <<<"$bad_uri_json"
PATH="$fixture_root/bin:$PATH" SUBSTATION_AUDIT_TEST_ROOT="$fixture_root" bash scripts/audit_host.sh --preflight >/dev/null
unlink -- "$fixture_root/etc/apt/sources.list.d/noble-ppa.list"
unlink -- "$fixture_root/etc/apt/sources.list.d/noble-vendor.list"

printf '%s\n' 'deb http://packages.ros.org/ros/ubuntu focal main' >> "$fixture_root/etc/apt/sources.list"
bad_source_json="$(PATH="$fixture_root/bin:$PATH" SUBSTATION_AUDIT_TEST_ROOT="$fixture_root" bash scripts/audit_host.sh --report-only)"
python3 -c 'import json,sys; data=json.load(sys.stdin); assert any(item["reason"] == "non-Noble suite is forbidden: focal" for item in data["forbidden_apt_sources"])' <<<"$bad_source_json"

forbidden_json="$(PATH="$fixture_root/bin:$PATH" FAKE_DPKG_FORBIDDEN=1 SUBSTATION_AUDIT_TEST_ROOT="$fixture_root" bash scripts/audit_host.sh --report-only)"
python3 -c 'import json,sys; data=json.load(sys.stdin); assert {"ubuntu-desktop", "gdm3", "xvfb", "ros-noetic-ros-base", "ros-kilted-ros-base", "ros-eloquent-desktop", "gazebo11"} <= set(data["forbidden_packages"]); assert "xserver-xorg-core" not in data["forbidden_packages"]' <<<"$forbidden_json"
! rg -n 'sudo|apt-get|apt install|systemctl|curl|wget|tee /etc' scripts/audit_host.sh

trap - EXIT
cleanup
printf '%s\n' 'audit-host-test: PASS'
```

Run:

```bash
chmod +x tests/environment/test_audit_host.sh
bash tests/environment/test_audit_host.sh
```

Expected: exit nonzero because the package request set, `scripts/audit_host.sh`, and the forbidden-package policy do not exist.

- [ ] **Step 2: Add the exact package request and forbidden-package policies**

Create `config/environment/apt-packages.txt` with this exact content, already sorted by byte order:

```text
build-essential
ca-certificates
cmake
curl
git
git-lfs
gnupg
gz-harmonic
jq
libegl1
locales
mesa-utils
nginx
pciutils
pkg-config
python3-colcon-common-extensions
python3-pip
python3-rosdep
python3-vcstool
python3-venv
ros-jazzy-foxglove-bridge
ros-jazzy-nav2-bringup
ros-jazzy-navigation2
ros-jazzy-robot-state-publisher
ros-jazzy-ros-base
ros-jazzy-ros-gz
ros-jazzy-slam-toolbox
ros-jazzy-turtlebot3
ros-jazzy-turtlebot3-simulations
ros-jazzy-vision-msgs
ros-jazzy-xacro
shellcheck
software-properties-common
sqlite3
yamllint
```

Create `config/environment/forbidden-packages.regex` with this exact content:

```text
^(ubuntu-desktop|ubuntu-desktop-minimal|kubuntu-desktop|xubuntu-desktop|lubuntu-desktop|ubuntu-unity-desktop)$
^(gnome-shell|gnome-session|plasma-desktop|kde-plasma-desktop)$
^(xorg|xserver-xorg|xserver-common|xinit)$
^(gdm3|sddm|lightdm|xdm)$
^(nomachine|xvfb|virtualgl)$
^ros-(?!jazzy-)[a-z0-9]+-.*$
^(ros-jazzy-(desktop|desktop-full))$
^(gazebo|gazebo[0-9]+|gazebo-classic|libgazebo.*)$
```

- [ ] **Step 3: Implement the audit in Python embedded by a read-only Bash entry point**

Create `scripts/audit_host.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

mode=enforce
if test "$#" -eq 1 && test "$1" = --report-only; then
  mode=report-only
elif test "$#" -eq 1 && test "$1" = --preflight; then
  mode=preflight
elif test "$#" -ne 0; then
  printf '%s\n' 'usage: bash scripts/audit_host.sh [--report-only|--preflight]' >&2
  exit 2
fi

repo_root="$(git rev-parse --show-toplevel)"
export PHASE1_AUDIT_REPO_ROOT="$repo_root"
export PHASE1_AUDIT_MODE="$mode"
audit_root="${SUBSTATION_AUDIT_TEST_ROOT:-/}"
if test "$audit_root" != /; then
  case "$audit_root" in /tmp/phase1-audit-fixture-*|/tmp/phase1-installer-fixture-*/root) ;; *) printf 'invalid-audit-test-root: %s\n' "$audit_root" >&2; exit 2 ;; esac
  test -d "$audit_root"
fi
export PHASE1_AUDIT_ROOT="$audit_root"

python3 - <<'PY'
import json
import os
import platform
import pwd
import re
import shlex
import shutil
import subprocess
import hashlib
from email.parser import Parser
from pathlib import Path

repo = Path(os.environ["PHASE1_AUDIT_REPO_ROOT"])
mode = os.environ["PHASE1_AUDIT_MODE"]
root = Path(os.environ["PHASE1_AUDIT_ROOT"])

def rooted(path):
    path = Path(path)
    return path if root == Path("/") else root / path.relative_to("/")

os_release = {}
for line in rooted("/etc/os-release").read_text(encoding="utf-8").splitlines():
    if "=" in line:
        key, value = line.split("=", 1)
        os_release[key] = value.strip().strip('"')

meminfo = {}
for line in rooted("/proc/meminfo").read_text(encoding="utf-8").splitlines():
    key, value = line.split(":", 1)
    meminfo[key] = int(value.strip().split()[0]) * 1024

disk_probes = []
probe_paths = {
    "repository": repo,
    "/var/lib/substation": rooted("/var/lib/substation"),
    "/opt/substation": rooted("/opt/substation"),
}
for label, probe in probe_paths.items():
    usage = shutil.disk_usage(probe)
    free_bytes = 160 * 1024**3 if root != Path("/") else usage.free
    mount = subprocess.run(
        ["findmnt", "--json", "--target", str(probe), "--output", "TARGET,SOURCE,FSTYPE"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    filesystem = json.loads(mount.stdout)["filesystems"][0]
    disk_probes.append({
        "path": label,
        "probe_path": str(probe),
        "mount_target": filesystem["target"],
        "mount_source": filesystem["source"],
        "filesystem_type": filesystem["fstype"],
        "free_bytes": free_bytes,
        "required_phase1_residual_free_bytes": 20 * 1024**3,
        "meets_phase1_residual_floor": free_bytes >= 20 * 1024**3,
    })
dpkg = subprocess.run(
    ["dpkg-query", "-W", "-f=${db:Status-Abbrev}\\t${binary:Package}\\n"],
    check=True,
    text=True,
    stdout=subprocess.PIPE,
).stdout.splitlines()
installed_packages = []
for entry in dpkg:
    status, package = entry.split("\t", 1)
    if status == "ii ":
        installed_packages.append(package)

patterns = [
    re.compile(line)
    for line in (repo / "config/environment/forbidden-packages.regex").read_text(encoding="utf-8").splitlines()
    if line
]
requested_packages = [
    line
    for line in (repo / "config/environment/apt-packages.txt").read_text(encoding="utf-8").splitlines()
    if line
]
forbidden = sorted({
    name
    for name in installed_packages + requested_packages
    if any(pattern.fullmatch(name) for pattern in patterns)
})
inert_nvidia_graphics_dependencies = sorted(
    name
    for name in installed_packages
    if name in {"xserver-xorg-core", "x11-common"} or re.fullmatch(r"xserver-xorg-video-nvidia-[0-9]+", name)
)

def source_files():
    candidates = [rooted("/etc/apt/sources.list")]
    source_dir = rooted("/etc/apt/sources.list.d")
    if source_dir.is_dir():
        candidates.extend(sorted(source_dir.glob("*.list")))
        candidates.extend(sorted(source_dir.glob("*.sources")))
    result = []
    for path in candidates:
        if path.is_symlink():
            raise SystemExit(f"apt source symlink is forbidden: {path}")
        if not path.exists():
            continue
        if not path.is_file():
            raise SystemExit(f"apt source is not a regular file: {path}")
        result.append(path)
    return result

apt_sources = []
for source_path in source_files():
    relative = "/" + str(source_path.relative_to(root)) if root != Path("/") else str(source_path)
    digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    if source_path.suffix == ".sources":
        paragraphs = re.split(r"\n\s*\n", source_path.read_text(encoding="utf-8"))
        for paragraph_index, paragraph in enumerate(paragraphs, 1):
            if not paragraph.strip():
                continue
            fields = Parser().parsestr(paragraph)
            if fields.get("Enabled", "yes").strip().lower() == "no":
                continue
            for source_type in fields.get("Types", "").split():
                for uri in fields.get("URIs", "").split():
                    for suite in fields.get("Suites", "").split():
                        apt_sources.append({"path": relative, "format": "deb822", "entry": paragraph_index, "type": source_type, "uri": uri.rstrip("/"), "suite": suite, "components": fields.get("Components", "").split(), "sha256": digest})
    else:
        for line_number, line in enumerate(source_path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            tokens = shlex.split(stripped)
            source_type = tokens.pop(0)
            if tokens and tokens[0].startswith("["):
                while tokens and not tokens.pop(0).endswith("]"):
                    pass
            uri, suite, *components = tokens
            apt_sources.append({"path": relative, "format": "list", "entry": line_number, "type": source_type, "uri": uri.rstrip("/"), "suite": suite, "components": components, "sha256": digest})

allowed_source_uris = {
    "http://archive.ubuntu.com/ubuntu",
    "https://archive.ubuntu.com/ubuntu",
    "http://security.ubuntu.com/ubuntu",
    "https://security.ubuntu.com/ubuntu",
    "http://packages.ros.org/ros2/ubuntu",
    "https://packages.ros.org/ros2/ubuntu",
    "http://packages.osrfoundation.org/gazebo/ubuntu-stable",
    "https://packages.osrfoundation.org/gazebo/ubuntu-stable",
}
external_apt_sources = []
forbidden_apt_sources = []
for entry in apt_sources:
    uri = entry["uri"]
    suite = entry["suite"]
    if entry["type"] not in {"deb", "deb-src"}:
        forbidden_apt_sources.append({"path": entry["path"], "entry": entry["entry"], "reason": f"unsupported apt source type: {entry['type']}"})
    if uri not in allowed_source_uris:
        external_apt_sources.append({"path": entry["path"], "entry": entry["entry"], "uri": uri, "suite": suite, "reason": "external Noble source recorded but not used for project requested packages"})
    if not (suite == "noble" or suite.startswith("noble-")):
        forbidden_apt_sources.append({"path": entry["path"], "entry": entry["entry"], "reason": f"non-Noble suite is forbidden: {suite}"})

locked_upstream = {
    "ros-jazzy-ros-gz": "1.0.23-1",
    "ros-jazzy-navigation2": "1.3.12-1",
    "ros-jazzy-nav2-bringup": "1.3.12-1",
    "ros-jazzy-slam-toolbox": "2.8.5-1",
    "ros-jazzy-turtlebot3": "2.3.6-1",
    "ros-jazzy-turtlebot3-simulations": "2.3.7-1",
}

ubuntu_origins = {
    "http://archive.ubuntu.com/ubuntu", "https://archive.ubuntu.com/ubuntu",
    "http://security.ubuntu.com/ubuntu", "https://security.ubuntu.com/ubuntu",
}
ros_origins = {
    "http://packages.ros.org/ros2/ubuntu", "https://packages.ros.org/ros2/ubuntu",
}
gazebo_origins = {
    "http://packages.osrfoundation.org/gazebo/ubuntu-stable",
    "https://packages.osrfoundation.org/gazebo/ubuntu-stable",
}

def allowed_origins_for(package):
    if package.startswith("ros-jazzy-"):
        return ros_origins
    if re.match(r"^(gz-|libgz-|sdformat|libsdformat|ignition-|libignition-)", package):
        return gazebo_origins
    return ubuntu_origins

apt_policy = {}
for package in requested_packages:
    expected = locked_upstream.get(package)
    allowed_origins = allowed_origins_for(package)
    completed = subprocess.run(["apt-cache", "policy", package], check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    candidate_match = re.search(r"^\s*Candidate:\s*(\S+)", completed.stdout, re.MULTILINE)
    origins = sorted({
        match.group(1).rstrip("/")
        for match in re.finditer(r"^\s*\d+\s+(https?://\S+)\s+\S+\s+\S+\s+Packages$", completed.stdout, re.MULTILINE)
    })
    candidate = candidate_match.group(1) if candidate_match else None
    candidate_ok = candidate not in {None, "(none)"} and (expected is None or candidate == expected or (candidate.startswith(expected) and not candidate[len(expected):len(expected)+1].isdigit()))
    origin_ok = bool(origins) and set(origins) <= allowed_origins
    apt_policy[package] = {"candidate": candidate, "expected_upstream": expected, "allowed_origins": sorted(allowed_origins), "origins": origins, "candidate_ok": candidate_ok, "origin_ok": origin_ok, "raw": completed.stdout}

gpu_present = any(
    vendor.read_text(encoding="utf-8").strip().lower() == "0x10de"
    for vendor in rooted("/sys/bus/pci/devices").glob("*/vendor")
)
if shutil.which("lspci"):
    lspci = subprocess.run(["lspci", "-nn"], check=True, text=True, stdout=subprocess.PIPE).stdout
    gpu_present = bool(re.search(r"(VGA compatible controller|3D controller).*NVIDIA", lspci, re.IGNORECASE))

driver_version = None
gpu_name = None
if shutil.which("nvidia-smi"):
    query = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if query.returncode == 0 and query.stdout.strip():
        first = query.stdout.splitlines()[0]
        gpu_name, driver_version = [item.strip() for item in first.split(",", 1)]
        gpu_present = True

def version_tuple(value):
    return tuple(int(part) for part in value.split(".") if part.isdigit())

current_user = pwd.getpwuid(os.getuid()).pw_name
driver_meets_floor = driver_version is not None and version_tuple(driver_version) >= version_tuple("560.35.05")
def apt_policy_acceptable(item):
    if mode == "report-only":
        return True
    if mode == "preflight" and item["candidate"] in {None, "(none)"} and (
        item["allowed_origins"] == sorted(ros_origins)
        or item["allowed_origins"] == sorted(gazebo_origins)
    ):
        return True
    return item["candidate_ok"] and item["origin_ok"]

checks = {
    "ubuntu_24_04": os_release.get("ID") == "ubuntu" and os_release.get("VERSION_ID") == "24.04",
    "architecture_x86_64": platform.machine() == "x86_64",
    "physical_memory_at_least_15_gib": meminfo.get("MemTotal", 0) >= 15 * 1024**3,
    "all_three_storage_paths_keep_20_gib_phase1_residual": all(item["meets_phase1_residual_floor"] for item in disk_probes),
    "nvidia_gpu_present": gpu_present,
    "no_forbidden_packages": not forbidden,
    "no_forbidden_apt_sources": not forbidden_apt_sources,
    "requested_package_candidates_and_origins": all(apt_policy_acceptable(item) for item in apt_policy.values()),
    "driver_floor_for_final_enforcement": mode != "enforce" or driver_meets_floor,
}

status = "passed" if all(checks.values()) else "failed"
document = {
    "schema_version": 1,
    "status": status,
    "os": {"id": os_release.get("ID"), "version_id": os_release.get("VERSION_ID"), "pretty_name": os_release.get("PRETTY_NAME")},
    "architecture": platform.machine(),
    "memory_bytes": meminfo.get("MemTotal", 0),
    "disk_free_bytes": min(item["free_bytes"] for item in disk_probes),
    "disks": disk_probes,
    "repository": str(repo),
    "user": current_user,
    "display_set": "DISPLAY" in os.environ,
    "gpu": {
        "present": gpu_present,
        "name": gpu_name,
        "driver_version": driver_version,
        "required_driver_floor": "560.35.05",
        "driver_meets_floor": driver_meets_floor,
        "driver_transaction_required": not driver_meets_floor,
    },
    "inert_nvidia_graphics_dependencies": inert_nvidia_graphics_dependencies,
    "forbidden_packages": forbidden,
    "forbidden_apt_sources": forbidden_apt_sources,
    "external_apt_sources": external_apt_sources,
    "apt_sources": apt_sources,
    "apt_policy": apt_policy,
    "checks": checks,
}
print(json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2))
if mode != "report-only" and status != "passed":
    raise SystemExit(1)
PY
```

- [ ] **Step 4: Run the fake-host test and commit Task 2 implementation**

```bash
chmod +x scripts/audit_host.sh tests/environment/test_audit_host.sh
LC_ALL=C sort -c config/environment/apt-packages.txt
bash tests/environment/test_audit_host.sh
git add config/environment/apt-packages.txt config/environment/forbidden-packages.regex scripts/audit_host.sh tests/environment/test_audit_host.sh
git diff --cached --check
git commit -m "feat: add read only host audit"
task2_commit="$(git rev-parse HEAD)"
test -z "$(git status --porcelain=v1 --untracked-files=all -- \
  config/environment/apt-packages.txt config/environment/forbidden-packages.regex scripts/audit_host.sh tests/environment/test_audit_host.sh)"
```

Expected test final line: `audit-host-test: PASS`; one implementation commit contains only the four listed paths.

- [ ] **Step 5: Run the live preflight audit from the clean Task 2 commit**

```bash
test "$(git rev-parse HEAD)" = "$task2_commit"
source .phase1-run.env
bash scripts/audit_host.sh --preflight | tee "$PHASE1_EVIDENCE_ROOT/host-audit.json"
test "${PIPESTATUS[0]}" -eq 0
```

Expected preflight JSON: `"status": "passed"`, Ubuntu `24.04`, architecture `x86_64`, at least `16106127360` memory bytes, independently recorded repository, `/var/lib/substation`, and `/opt/substation` mounts each retaining at least `21474836480` free bytes for the Phase 1 residual floor, an NVIDIA GPU, empty forbidden package/source arrays, complete hashes and parsed entries for every active apt source file, explicit `external_apt_sources` records for unrelated Noble Docker/Tailscale/vendor sources if present, and a policy record for every project-requested package. Project-requested packages and later changed packages must resolve only from the package-family-specific official Ubuntu, ROS 2, or Gazebo origins. Missing official ROS/Gazebo candidates or a below-floor driver stops before mutation with a clear remediation reason; a missing Ubuntu candidate, wrong origin/candidate, non-Jazzy ROS name, forbidden active graphics stack/package, or Phase 1 residual capacity failure is a hard stop. Task 10 reruns default enforcement, which requires the final driver and every requested candidate/origin.

If enforcement fails, stop before Task 3. The JSON is the evidence; do not "fix" a capacity or GPU failure by weakening thresholds. Do not claim full dataset/training capacity from this Phase 1 residual check; large downloads must pass their own expected-size-plus-20-GiB gate in the later data phase.

Evidence: `$PHASE1_EVIDENCE_ROOT/host-audit.json`; the report preserves every failed boolean when enforcement stops the phase.

Safe rollback: this task has no host mutation. Revert only its tracked commit; preserve `host-audit.json`.

- [ ] **Step 6: Update status and handoff for Task 2**

```bash
verified_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
script_sha256="$(sha256sum scripts/audit_host.sh config/environment/apt-packages.txt config/environment/forbidden-packages.regex | LC_ALL=C sort -k2)"
printf 'task_commit=%s\nverified_at=%s\nevidence=%s\nscript_sha256_lines=%s\n' \
  "$task2_commit" "$verified_at" "$PHASE1_EVIDENCE_ROOT/host-audit.json" "$script_sha256"
```

Use `apply_patch` to record the literal values in `docs/PROJECT_STATUS.md` and `docs/HANDOFF.md`, including the exact preflight command and result. Then:

```bash
git add docs/PROJECT_STATUS.md docs/HANDOFF.md
git diff --cached --check
git commit -m "docs: record phase one task 2 status"
```

Expected: the host audit evidence remains bound to `task2_commit`; the status commit is documentation-only.

---

### Task 3: Official Apt, ROS 2 Jazzy, Gazebo Harmonic, and NVIDIA Audit

**Files:**
- Create: `scripts/install_host.sh`
- Create: `scripts/rollback_host.sh`
- Create: `tests/environment/fixtures/fake_host_command.py`
- Create: `tests/environment/test_install_host.sh`
- Modify: `docs/PROJECT_STATUS.md` and `docs/HANDOFF.md` after Task 3 verification, as required for every Phase 1 task

**Interfaces:**
- Consumes: the exact Task 2 `config/environment/apt-packages.txt`, a passing preflight host audit, Ubuntu Noble official repositories with `universe` already enabled, `packages.ros.org`, `packages.osrfoundation.org`, and an already compliant Ubuntu official NVIDIA driver.
- Produces: installed approved non-driver Debian packages, exact allowlisted-origin evidence for every requested and changed package, write-once backups for every active `sources.list`, `*.list`, and deb822 `*.sources` file and every file it mutates, temporary `policy-rc.d` service suppression with exact restoration, stopped/disabled Nginx, initialized rosdep, and `scripts/rollback_host.sh` whose apply path always passes strict inert-data state parsing and the recorded simulation before mutation. If the NVIDIA driver is absent, below `560.35.05`, non-Ubuntu, or fails headless probes, the script exits before package mutation with `install-host: DRIVER_TRANSACTION_REQUIRED`; a separate reviewed driver transaction is required and this Phase 1 task does not perform it. A guarded temporary-root seam plus PATH-injected fake commands exercises the same state machine before any real `sudo` mutation.

- [ ] **Step 1: Write the failing installer contract test**

Create `tests/environment/test_install_host.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

test -x scripts/install_host.sh
test -s config/environment/apt-packages.txt
plan="$(bash scripts/install_host.sh --plan)"
grep -Fx 'ros-jazzy-ros-base' <<<"$plan"
grep -Fx 'ros-jazzy-ros-gz' <<<"$plan"
grep -Fx 'ros-jazzy-navigation2' <<<"$plan"
grep -Fx 'ros-jazzy-nav2-bringup' <<<"$plan"
grep -Fx 'ros-jazzy-slam-toolbox' <<<"$plan"
grep -Fx 'ros-jazzy-turtlebot3' <<<"$plan"
grep -Fx 'ros-jazzy-turtlebot3-simulations' <<<"$plan"
grep -Fx 'gz-harmonic' <<<"$plan"
grep -Fx 'ros-jazzy-foxglove-bridge' <<<"$plan"
! grep -E 'ros-.*-desktop|ubuntu-desktop|xorg|xserver-xorg|nomachine|xvfb|virtualgl|nvidia-cuda-toolkit' <<<"$plan"
test "$(LC_ALL=C sort config/environment/apt-packages.txt | uniq -d | wc -l)" -eq 0
rg -F '"ros-jazzy-ros-gz": "1.0.23-1"' scripts/install_host.sh
rg -F '"ros-jazzy-navigation2": "1.3.12-1"' scripts/install_host.sh
rg -F '"ros-jazzy-nav2-bringup": "1.3.12-1"' scripts/install_host.sh
rg -F '"ros-jazzy-slam-toolbox": "2.8.5-1"' scripts/install_host.sh
rg -F '"ros-jazzy-turtlebot3": "2.3.6-1"' scripts/install_host.sh
rg -F '"ros-jazzy-turtlebot3-simulations": "2.3.7-1"' scripts/install_host.sh
rg -F 'install-complete.env' scripts/install_host.sh
rg -F 'host-install-version-changes.tsv' scripts/install_host.sh
rg -F 'managed-files-after.tsv' scripts/install_host.sh
rg -F 'nginx_unit_present_before=' scripts/install_host.sh
rg -F 'source_path\texisted\tmode\tsha256\tbackup_file' scripts/install_host.sh

test -x scripts/rollback_host.sh
test -x tests/environment/fixtures/fake_host_command.py
fixture_root="/tmp/phase1-installer-fixture-$(python3 -c 'import uuid; print(uuid.uuid4())')"
case "$fixture_root" in /tmp/phase1-installer-fixture-*) ;; *) exit 1 ;; esac
test ! -e "$fixture_root"
install -d -m 0700 "$fixture_root"
cleanup() {
  case "$fixture_root" in /tmp/phase1-installer-fixture-*) find "$fixture_root" -depth -delete ;; *) return 1 ;; esac
}
trap cleanup EXIT

make_case() {
  local name="$1"
  local driver_ready="$2"
  local case_root="$fixture_root/$name"
  local host_root="$case_root/root"
  local evidence_dir="$case_root/evidence/01-environment.staging"
  local fake_bin="$case_root/bin"
  install -d -m 0700 \
    "$fake_bin" \
    "$evidence_dir" \
    "$host_root/etc/apt/sources.list.d" \
    "$host_root/etc/ros/rosdep/sources.list.d" \
    "$host_root/etc/default" \
    "$host_root/usr/share/keyrings" \
    "$host_root/usr/sbin" \
    "$host_root/opt/ros/jazzy" \
    "$host_root/opt/substation" \
    "$host_root/var/lib/dpkg" \
    "$host_root/var/lib/substation" \
    "$host_root/proc" \
    "$host_root/sys/bus/pci/devices/0000:01:00.0"
  cat > "$host_root/etc/os-release" <<'EOF'
ID=ubuntu
VERSION_ID="24.04"
PRETTY_NAME="Ubuntu 24.04 LTS"
EOF
  printf '%s\n' 'MemTotal:       33554432 kB' > "$host_root/proc/meminfo"
  printf '%s\n' 0x10de > "$host_root/sys/bus/pci/devices/0000:01:00.0/vendor"
  cat > "$host_root/etc/apt/sources.list" <<'EOF'
deb http://archive.ubuntu.com/ubuntu noble main universe
EOF
  cat > "$host_root/etc/apt/sources.list.d/ubuntu.sources" <<'EOF'
Types: deb
URIs: http://archive.ubuntu.com/ubuntu
Suites: noble-updates noble-security
Components: main universe
EOF
  printf '%s\n' 'ORIGINAL_POLICY' > "$host_root/usr/sbin/policy-rc.d"
  chmod 0755 "$host_root/usr/sbin/policy-rc.d"
  printf '%s\n' 'export ROS_DISTRO=jazzy' > "$host_root/opt/ros/jazzy/setup.bash"
  python3 tests/environment/fixtures/fake_host_command.py init \
    --state "$case_root/state.json" \
    --operations "$case_root/operations.jsonl" \
    --driver-ready "$driver_ready"
  for command_name in sudo apt-get apt-cache dpkg-query systemctl nvidia-smi curl locale-gen update-locale rosdep gz lspci findmnt; do
    ln -s "$repo_root/tests/environment/fixtures/fake_host_command.py" "$fake_bin/$command_name"
  done
  printf '%s\t%s\t%s\t%s\n' "$case_root" "$host_root" "$evidence_dir" "$fake_bin"
}

run_case_install() {
  local case_root="$1"
  local host_root="$2"
  local evidence_dir="$3"
  local fake_bin="$4"
  shift 4
  PATH="$fake_bin:$PATH" \
  SUBSTATION_INSTALL_TEST_ROOT="$host_root" \
  SUBSTATION_AUDIT_TEST_ROOT="$host_root" \
  FAKE_HOST_STATE="$case_root/state.json" \
  FAKE_HOST_OPERATIONS="$case_root/operations.jsonl" \
  "$@" bash scripts/install_host.sh --apply --evidence-dir "$evidence_dir"
}

IFS=$'\t' read -r success_case success_root success_evidence success_bin < <(make_case fresh-success 1)
run_case_install "$success_case" "$success_root" "$success_evidence" "$success_bin" env
grep -Fxq 'state=PASS' "$success_evidence/install-complete.env"
grep -Fq $'/etc/apt/sources.list\t1\t' "$success_evidence/apt-sources-before/inventory.tsv"
grep -Fq $'/etc/apt/sources.list.d/ubuntu.sources\t1\t' "$success_evidence/apt-sources-before/inventory.tsv"
grep -Fxq 'ORIGINAL_POLICY' "$success_root/usr/sbin/policy-rc.d"
test -s "$success_evidence/apt-policy-origins.json"
python3 - "$success_evidence/apt-candidates.tsv" config/environment/apt-packages.txt "$success_evidence/host-install-version-changes.tsv" "$success_evidence/apt-changed-package-origins.tsv" <<'PY'
import csv, sys
from pathlib import Path
candidate_path, requested_path, changes_path, changed_origin_path = map(Path, sys.argv[1:])
with candidate_path.open(encoding="utf-8", newline="") as handle:
    candidates = list(csv.DictReader(handle, delimiter="\t"))
requested = [line for line in requested_path.read_text(encoding="utf-8").splitlines() if line]
assert [row["package"] for row in candidates] == requested
with changes_path.open(encoding="utf-8", newline="") as handle:
    changes = list(csv.DictReader(handle, delimiter="\t"))
with changed_origin_path.open(encoding="utf-8", newline="") as handle:
    changed_origins = list(csv.DictReader(handle, delimiter="\t"))
assert [row["package"] for row in changed_origins] == [row["package"] for row in changes]
PY
python3 - "$success_case/operations.jsonl" <<'PY'
import json, sys
operations = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")]
assert any(item["command"] == "apt-get" and "install" in item["argv"] for item in operations)
assert not any(item["command"] == "systemctl" and "start" in item["argv"] for item in operations)
assert any(item["command"] == "systemctl" and "disable" in item["argv"] and "--now" in item["argv"] for item in operations)
PY

IFS=$'\t' read -r candidate_case candidate_root candidate_evidence candidate_bin < <(make_case candidate-failure 1)
set +e
run_case_install "$candidate_case" "$candidate_root" "$candidate_evidence" "$candidate_bin" env FAKE_CANDIDATE_FAILURE=1
candidate_rc=$?
set -e
test "$candidate_rc" -ne 0
test ! -e "$candidate_evidence/install-complete.env"
test ! -e "$candidate_evidence/install-state.env"
grep -Fxq 'ORIGINAL_POLICY' "$candidate_root/usr/sbin/policy-rc.d"
grep -Fxq 'deb http://archive.ubuntu.com/ubuntu noble main universe' "$candidate_root/etc/apt/sources.list"
test ! -e "$candidate_root/etc/apt/sources.list.d/ros2.list"
test ! -e "$candidate_root/etc/apt/sources.list.d/gazebo-stable.list"
python3 - "$candidate_case/operations.jsonl" <<'PY'
import json, sys
operations = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")]
target_installs = [item for item in operations if item["command"] == "apt-get" and "install" in item["argv"] and "ros-jazzy-ros-base" in item["argv"]]
assert target_installs == []
PY

IFS=$'\t' read -r requested_origin_case requested_origin_root requested_origin_evidence requested_origin_bin < <(make_case requested-origin-failure 1)
set +e
run_case_install "$requested_origin_case" "$requested_origin_root" "$requested_origin_evidence" "$requested_origin_bin" env FAKE_REQUESTED_ORIGIN_FAILURE=1
requested_origin_rc=$?
set -e
test "$requested_origin_rc" -ne 0
test ! -e "$requested_origin_evidence/install-state.env"

for source_kind in ppa vendor; do
  IFS=$'\t' read -r source_case source_root source_evidence source_bin < <(make_case "noble-$source_kind-source" 1)
  if test "$source_kind" = ppa; then
    source_uri=https://ppa.launchpadcontent.net/vendor/project/ubuntu
  else
    source_uri=https://vendor.example.invalid/ubuntu
  fi
  printf 'deb %s noble main\n' "$source_uri" > "$source_root/etc/apt/sources.list.d/foreign.list"
  run_case_install "$source_case" "$source_root" "$source_evidence" "$source_bin" env
  grep -Fxq 'state=PASS' "$source_evidence/install-complete.env"
  python3 - "$source_evidence/apt-policy-origins.json" <<'PY'
import json, sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert data["external_apt_sources"]
assert data["forbidden_apt_sources"] == []
PY
done

IFS=$'\t' read -r symlink_case symlink_root symlink_evidence symlink_bin < <(make_case apt-source-symlink 1)
ln -s ubuntu.sources "$symlink_root/etc/apt/sources.list.d/active-symlink.sources"
set +e
run_case_install "$symlink_case" "$symlink_root" "$symlink_evidence" "$symlink_bin" env
symlink_rc=$?
set -e
test "$symlink_rc" -ne 0
test ! -e "$symlink_evidence/install-state.env"

IFS=$'\t' read -r driver_block_case driver_block_root driver_block_evidence driver_block_bin < <(make_case driver-transaction-required 0)
set +e
run_case_install "$driver_block_case" "$driver_block_root" "$driver_block_evidence" "$driver_block_bin" env
driver_block_rc=$?
set -e
test "$driver_block_rc" -eq 23
test ! -e "$driver_block_evidence/install-complete.env"
grep -Eq $'^/usr/sbin/policy-rc.d\t[01]\t.*\t1$' "$driver_block_evidence/policy-rc.d-state.tsv"

snapshot="$success_case/completed.snapshot"
find "$success_evidence" -type f -printf '%P\0' | LC_ALL=C sort -z | xargs -0 -r -I{} sha256sum "$success_evidence/{}" > "$snapshot"
mutations_before_completed_rerun="$(python3 - "$success_case/operations.jsonl" <<'PY'
import json, sys
operations = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")]
mutating = []
for item in operations:
    argv = item["argv"]
    if item["command"] in {"locale-gen", "update-locale", "rosdep"}:
        mutating.append(item)
    elif item["command"] == "apt-get" and any(action in argv for action in {"update", "install", "remove"}) and "--simulate" not in argv and "-s" not in argv:
        mutating.append(item)
    elif item["command"] == "systemctl" and any(action in argv for action in {"start", "stop", "enable", "disable", "mask", "unmask"}):
        mutating.append(item)
print(len(mutating))
PY
)"
run_case_install "$success_case" "$success_root" "$success_evidence" "$success_bin" env
mutations_after_completed_rerun="$(python3 - "$success_case/operations.jsonl" <<'PY'
import json, sys
operations = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")]
mutating = []
for item in operations:
    argv = item["argv"]
    if item["command"] in {"locale-gen", "update-locale", "rosdep"}:
        mutating.append(item)
    elif item["command"] == "apt-get" and any(action in argv for action in {"update", "install", "remove"}) and "--simulate" not in argv and "-s" not in argv:
        mutating.append(item)
    elif item["command"] == "systemctl" and any(action in argv for action in {"start", "stop", "enable", "disable", "mask", "unmask"}):
        mutating.append(item)
print(len(mutating))
PY
)"
test "$mutations_after_completed_rerun" -eq "$mutations_before_completed_rerun"
find "$success_evidence" -type f -printf '%P\0' | LC_ALL=C sort -z | xargs -0 -r -I{} sha256sum "$success_evidence/{}" > "$success_case/completed.after"
cmp "$snapshot" "$success_case/completed.after"

IFS=$'\t' read -r partial_case partial_root partial_evidence partial_bin < <(make_case partial-state 1)
printf '%s\n' 'state=INITIAL_INSTALL_STARTED' > "$partial_evidence/install-state.env"
set +e
run_case_install "$partial_case" "$partial_root" "$partial_evidence" "$partial_bin" env
partial_rc=$?
set -e
test "$partial_rc" -ne 0
python3 - "$partial_case/operations.jsonl" <<'PY'
import json, sys
operations = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")]
for item in operations:
    argv = item["argv"]
    assert not (item["command"] == "apt-get" and any(action in argv for action in {"update", "install", "remove"}) and "--simulate" not in argv and "-s" not in argv)
    assert item["command"] not in {"locale-gen", "update-locale", "rosdep"}
PY

IFS=$'\t' read -r tamper_case tamper_root tamper_evidence tamper_bin < <(make_case backup-tamper 1)
run_case_install "$tamper_case" "$tamper_root" "$tamper_evidence" "$tamper_bin" env
backup_file="$(awk -F '\t' '$2 == 1 {print $5; exit}' "$tamper_evidence/apt-sources-before/inventory.tsv")"
printf '%s\n' tampered >> "$tamper_evidence/apt-sources-before/$backup_file"
set +e
run_case_install "$tamper_case" "$tamper_root" "$tamper_evidence" "$tamper_bin" env
tamper_rc=$?
set -e
test "$tamper_rc" -ne 0
test ! -e "$tamper_evidence/install-complete.env"

IFS=$'\t' read -r changed_origin_case changed_origin_root changed_origin_evidence changed_origin_bin < <(make_case changed-origin-failure 1)
set +e
run_case_install "$changed_origin_case" "$changed_origin_root" "$changed_origin_evidence" "$changed_origin_bin" env FAKE_CHANGED_ORIGIN_FAILURE=1
changed_origin_rc=$?
set -e
test "$changed_origin_rc" -ne 0
test ! -e "$changed_origin_evidence/install-complete.env"

IFS=$'\t' read -r state_case state_root state_evidence state_bin < <(make_case rollback-state-tamper 1)
run_case_install "$state_case" "$state_root" "$state_evidence" "$state_bin" env
state_operations_before="$(wc -l < "$state_case/operations.jsonl")"
printf 'started_at=$(touch %s)\n' "$state_case/source-executed" >> "$state_evidence/install-state.env"
set +e
PATH="$state_bin:$PATH" \
SUBSTATION_INSTALL_TEST_ROOT="$state_root" \
FAKE_HOST_STATE="$state_case/state.json" \
FAKE_HOST_OPERATIONS="$state_case/operations.jsonl" \
bash scripts/rollback_host.sh --apply --evidence-dir "$state_evidence" --confirm-run-id "$(basename "$(dirname "$state_evidence")")"
state_tamper_rc=$?
set -e
test "$state_tamper_rc" -ne 0
test ! -e "$state_case/source-executed"
python3 - "$state_case/operations.jsonl" "$state_operations_before" <<'PY'
import json, sys
operations = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")][int(sys.argv[2]):]
for item in operations:
    argv = item["argv"]
    assert not (item["command"] == "apt-get" and any(action in argv for action in {"install", "remove"}) and "--simulate" not in argv and "-s" not in argv)
    assert not (item["command"] == "systemctl" and any(action in argv for action in {"start", "stop", "enable", "disable", "mask", "unmask"}))
PY

IFS=$'\t' read -r nginx_case nginx_root nginx_evidence nginx_bin < <(make_case nginx-absence-rollback 1)
run_case_install "$nginx_case" "$nginx_root" "$nginx_evidence" "$nginx_bin" env
set +e
PATH="$nginx_bin:$PATH" \
SUBSTATION_INSTALL_TEST_ROOT="$nginx_root" \
FAKE_HOST_STATE="$nginx_case/state.json" \
FAKE_HOST_OPERATIONS="$nginx_case/operations.jsonl" \
FAKE_KEEP_NGINX_UNIT=1 \
bash scripts/rollback_host.sh --apply --evidence-dir "$nginx_evidence" --confirm-run-id "$(basename "$(dirname "$nginx_evidence")")"
nginx_absence_rc=$?
set -e
test "$nginx_absence_rc" -ne 0

PATH="$success_bin:$PATH" \
SUBSTATION_INSTALL_TEST_ROOT="$success_root" \
FAKE_HOST_STATE="$success_case/state.json" \
FAKE_HOST_OPERATIONS="$success_case/operations.jsonl" \
bash scripts/rollback_host.sh --plan --evidence-dir "$success_evidence"
PATH="$success_bin:$PATH" \
SUBSTATION_INSTALL_TEST_ROOT="$success_root" \
FAKE_HOST_STATE="$success_case/state.json" \
FAKE_HOST_OPERATIONS="$success_case/operations.jsonl" \
bash scripts/rollback_host.sh --apply --evidence-dir "$success_evidence" --confirm-run-id "$(basename "$(dirname "$success_evidence")")"
grep -Fxq 'deb http://archive.ubuntu.com/ubuntu noble main universe' "$success_root/etc/apt/sources.list"
grep -Fxq 'Types: deb' "$success_root/etc/apt/sources.list.d/ubuntu.sources"
grep -Fxq 'Suites: noble-updates noble-security' "$success_root/etc/apt/sources.list.d/ubuntu.sources"
test ! -e "$success_root/etc/apt/sources.list.d/ros2.list"
test ! -e "$success_root/etc/apt/sources.list.d/gazebo-stable.list"
grep -Fxq 'ORIGINAL_POLICY' "$success_root/usr/sbin/policy-rc.d"
python3 - "$success_case/operations.jsonl" <<'PY'
import json, sys
operations = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")]
simulate = [index for index, item in enumerate(operations) if item["command"] == "apt-get" and ("--simulate" in item["argv"] or "-s" in item["argv"])]
actual = [index for index, item in enumerate(operations) if item["command"] == "apt-get" and ("remove" in item["argv"] or "install" in item["argv"]) and "--simulate" not in item["argv"] and "-s" not in item["argv"]]
assert simulate and actual and max(simulate) < max(actual)
PY

trap - EXIT
cleanup
printf '%s\n' 'install-host-test: PASS'
```

Create `tests/environment/fixtures/fake_host_command.py` with this exact content:

```python
#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path


LOCKED = {
    "ros-jazzy-ros-gz": "1.0.23-1-1noble.20260701",
    "ros-jazzy-navigation2": "1.3.12-1-1noble.20260701",
    "ros-jazzy-nav2-bringup": "1.3.12-1-1noble.20260701",
    "ros-jazzy-slam-toolbox": "2.8.5-1-1noble.20260701",
    "ros-jazzy-turtlebot3": "2.3.6-1-1noble.20260701",
    "ros-jazzy-turtlebot3-simulations": "2.3.7-1-1noble.20260701",
    "gz-harmonic": "8.9.0-1~noble",
}


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_state():
    return json.loads(Path(os.environ["FAKE_HOST_STATE"]).read_text(encoding="utf-8"))


def save_state(state):
    write_json(os.environ["FAKE_HOST_STATE"], state)


def record(command, argv):
    path = Path(os.environ["FAKE_HOST_OPERATIONS"])
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"command": command, "argv": argv}, sort_keys=True) + "\n")


def init(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--operations", required=True)
    parser.add_argument("--driver-ready", choices=("0", "1"), required=True)
    args = parser.parse_args(argv)
    state = {
        "packages": {"base-files": "13ubuntu10.1"},
        "candidates": LOCKED,
        "driver_ready": args.driver_ready == "1",
        "nginx_unit": False,
        "nginx_active": False,
        "nginx_enabled": "disabled",
    }
    write_json(args.state, state)
    Path(args.operations).write_text("", encoding="utf-8")
    return 0


def package_version(package, state):
    if package in state["candidates"]:
        return state["candidates"][package]
    return "1.0-1noble"


def apt_get(argv, state):
    record("apt-get", argv)
    action = next((item for item in argv if item in {"update", "install", "remove"}), None)
    if action == "update":
        return 0
    simulate = "--simulate" in argv or "-s" in argv
    action_index = argv.index(action)
    packages = [item for item in argv[action_index + 1 :] if not item.startswith("-")]
    if simulate:
        prefix = "Inst" if action == "install" else "Remv"
        for spec in packages:
            print(prefix, spec.split("=", 1)[0])
        return 0
    if action == "install":
        for spec in packages:
            package, _, requested = spec.partition("=")
            state["packages"][package] = requested or package_version(package, state)
            if package == "nginx":
                state["nginx_unit"] = True
                policy = Path(os.environ["SUBSTATION_INSTALL_TEST_ROOT"]) / "usr/sbin/policy-rc.d"
                if not policy.is_file() or "exit 101" not in policy.read_text(encoding="utf-8"):
                    state["nginx_active"] = True
        if os.environ.get("FAKE_CHANGED_ORIGIN_FAILURE") == "1":
            state["packages"]["foreign-dependency"] = "1.0-1noble"
        save_state(state)
        return 0
    if action == "remove":
        for package in packages:
            state["packages"].pop(package, None)
            if package == "nginx":
                if os.environ.get("FAKE_KEEP_NGINX_UNIT") != "1":
                    state["nginx_unit"] = False
                    state["nginx_active"] = False
                    state["nginx_enabled"] = "disabled"
        save_state(state)
        return 0
    return 2


def apt_cache(argv, state):
    record("apt-cache", argv)
    if argv == ["policy"]:
        print("500 http://archive.ubuntu.com/ubuntu noble/universe amd64 Packages")
        return 0
    if len(argv) != 2 or argv[0] != "policy":
        return 2
    package = argv[1]
    candidate = state["candidates"].get(package, "1.0-1noble")
    if os.environ.get("FAKE_CANDIDATE_FAILURE") == "1" and package == "ros-jazzy-ros-gz":
        candidate = "9.9.9-1"
    print(f"  Candidate: {candidate}")
    print(f"     {candidate} 500")
    if package.startswith("ros-jazzy-"):
        origin = "http://packages.ros.org/ros2/ubuntu"
    elif package == "gz-harmonic" or package.startswith(("gz-", "libgz-", "sdformat", "libsdformat")):
        origin = "http://packages.osrfoundation.org/gazebo/ubuntu-stable"
    else:
        origin = "http://archive.ubuntu.com/ubuntu"
    if os.environ.get("FAKE_REQUESTED_ORIGIN_FAILURE") == "1" and package == "nginx":
        origin = "https://ppa.launchpadcontent.net/vendor/project/ubuntu"
    if os.environ.get("FAKE_CHANGED_ORIGIN_FAILURE") == "1" and package == "foreign-dependency":
        origin = "https://vendor.example.invalid/ubuntu"
    print(f"        500 {origin} noble/main amd64 Packages")
    return 0


def dpkg_query(argv, state):
    record("dpkg-query", argv)
    packages = [item for item in argv if not item.startswith("-") and "${" not in item]
    format_arg = next((item for item in argv if item.startswith("-f")), "")
    selected = packages or sorted(state["packages"])
    for package in selected:
        if package not in state["packages"]:
            return 1
        version = state["packages"][package]
        if "Status-Abbrev" in format_arg:
            print(f"ii \t{package}")
        elif "${Package}" in format_arg:
            print(f"{package}\t{version}")
        else:
            print(version, end="" if len(selected) == 1 else "\n")
    return 0


def systemctl(argv, state):
    record("systemctl", argv)
    if "list-unit-files" in argv:
        if state["nginx_unit"]:
            print("nginx.service enabled")
            return 0
        return 1
    if "is-active" in argv:
        if state["nginx_active"]:
            if "--quiet" not in argv:
                print("active")
            return 0
        if "--quiet" not in argv:
            print("inactive")
        return 3
    if "is-enabled" in argv:
        print(state["nginx_enabled"])
        return 0 if state["nginx_enabled"] == "enabled" else 1
    if "disable" in argv:
        state["nginx_enabled"] = "disabled"
        if "--now" in argv:
            state["nginx_active"] = False
        save_state(state)
        return 0
    if "enable" in argv:
        state["nginx_enabled"] = "enabled"
        save_state(state)
        return 0
    if "start" in argv:
        state["nginx_active"] = True
        save_state(state)
        return 0
    if "stop" in argv:
        state["nginx_active"] = False
        save_state(state)
        return 0
    if "mask" in argv or "unmask" in argv:
        return 0
    return 2


def main():
    invoked_as = Path(sys.argv[0]).name
    if invoked_as == "fake_host_command.py" and len(sys.argv) > 1 and sys.argv[1] == "init":
        return init(sys.argv[2:])
    command = invoked_as
    argv = sys.argv[1:]
    state = load_state()
    if command == "sudo":
        record("sudo", argv)
        os.execvp(argv[0], argv)
    if command == "apt-get":
        return apt_get(argv, state)
    if command == "apt-cache":
        return apt_cache(argv, state)
    if command == "dpkg-query":
        return dpkg_query(argv, state)
    if command == "systemctl":
        return systemctl(argv, state)
    record(command, argv)
    if command == "nvidia-smi":
        if not state["driver_ready"]:
            return 1
        query = next((item for item in argv if item.startswith("--query-gpu=")), "")
        if query == "--query-gpu=driver_version":
            print("560.35.05")
        elif query == "--query-gpu=name,driver_version":
            print("NVIDIA RTX 3060 Ti, 560.35.05")
        else:
            print("NVIDIA RTX 3060 Ti, 560.35.05, 8192 MiB")
        return 0
    if command == "curl":
        output = argv[argv.index("-o") + 1]
        Path(output).write_text("fixture-key:" + argv[-2] + "\n", encoding="utf-8")
        return 0
    if command == "rosdep" and argv and argv[0] == "init":
        path = Path(os.environ["SUBSTATION_INSTALL_TEST_ROOT"]) / "etc/ros/rosdep/sources.list.d/20-default.list"
        path.write_text("fixture rosdep\n", encoding="utf-8")
        return 0
    if command == "gz":
        print("Gazebo Sim, version 8.9.0")
        return 0
    if command == "lspci":
        print("01:00.0 VGA compatible controller: NVIDIA Corporation Device")
        return 0
    if command == "findmnt":
        target = argv[argv.index("--target") + 1]
        print(json.dumps({"filesystems": [{"target": target, "source": "fixture", "fstype": "ext4"}]}))
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Run:

```bash
chmod +x tests/environment/test_install_host.sh
bash tests/environment/test_install_host.sh
```

Expected: exit nonzero because `scripts/install_host.sh`, `scripts/rollback_host.sh`, and the fake-host fixture do not exist; the Task 2 package list is already present and sorted.

- [ ] **Step 2: Verify the inherited exact package request set**

```bash
test -s config/environment/apt-packages.txt
LC_ALL=C sort -c config/environment/apt-packages.txt
test "$(uniq -d config/environment/apt-packages.txt | wc -l)" -eq 0
! awk '/^ros-/ && $0 !~ /^ros-jazzy-/ {print NR ":" $0; found=1} END {exit found ? 0 : 1}' config/environment/apt-packages.txt
! rg -n '^(ros-jazzy-(desktop|desktop-full)|ubuntu-desktop|xorg|xserver-xorg.*|nomachine|xvfb|virtualgl|nvidia-cuda-toolkit)$' config/environment/apt-packages.txt
```

Expected: all commands exit 0; Task 3 consumes the exact tracked request set already reviewed and committed by Task 2 and does not redefine or restage it.

- [ ] **Step 3: Implement the plan/apply installer**

Create `scripts/install_host.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

if test "$#" -eq 1 && test "$1" = --plan; then
  LC_ALL=C sort config/environment/apt-packages.txt
  exit 0
fi
if test "$#" -ne 3 || test "$1" != --apply || test "$2" != --evidence-dir; then
  printf '%s\n' 'usage: bash scripts/install_host.sh --plan | --apply --evidence-dir /var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment.staging' >&2
  exit 2
fi

evidence_dir="$3"
source scripts/lib/environment_common.sh
test_root="${SUBSTATION_INSTALL_TEST_ROOT:-}"
if test -n "$test_root"; then
  case "$test_root" in /tmp/phase1-installer-fixture-*/root) ;; *) printf 'invalid-install-test-root: %s\n' "$test_root" >&2; exit 2 ;; esac
  case "$evidence_dir" in /tmp/phase1-installer-fixture-*/evidence/01-environment.staging) ;; *) printf 'invalid-install-test-evidence: %s\n' "$evidence_dir" >&2; exit 2 ;; esac
  test -d "$test_root"
  test -d "$evidence_dir"
else
  environment_require_evidence_dir "$evidence_dir"
fi

host_path() {
  local logical="$1"
  test "${logical#/}" != "$logical"
  if test -n "$test_root"; then
    printf '%s%s\n' "$test_root" "$logical"
  else
    printf '%s\n' "$logical"
  fi
}

run_privileged() {
  if test -n "$test_root"; then
    "$@"
  else
    sudo "$@"
  fi
}

bash scripts/audit_host.sh --preflight >/dev/null

apt_sources_before="$evidence_dir/apt-sources-before"
state_file="$evidence_dir/install-state.env"
complete_marker="$evidence_dir/install-complete.env"
before_packages="$evidence_dir/dpkg-before.tsv"
after_packages="$evidence_dir/dpkg-after.tsv"
new_packages="$evidence_dir/host-install-new-packages.txt"
version_changes="$evidence_dir/host-install-version-changes.tsv"
candidate_file="$evidence_dir/apt-candidates.tsv"
changed_origin_file="$evidence_dir/apt-changed-package-origins.tsv"
managed_after="$evidence_dir/managed-files-after.tsv"
apt_sources_after="$evidence_dir/apt-sources-after"
policy_state="$evidence_dir/policy-rc.d-state.tsv"
managed_paths=(
  /etc/apt/sources.list.d/ros2.list
  /etc/apt/sources.list.d/gazebo-stable.list
  /usr/share/keyrings/ros-archive-keyring.gpg
  /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
  /etc/default/locale
  /etc/ros/rosdep/sources.list.d/20-default.list
  /usr/sbin/policy-rc.d
)

key_work=
list_work=
capture_work=
inventory_work=
source_paths_work=
policy_active=0
cleanup() {
  local path
  for path in "$key_work" "$list_work" "$capture_work" "$inventory_work" "$source_paths_work"; do
    if test -n "$path" && test -e "$path"; then
      unlink -- "$path"
    fi
  done
  if test "$policy_active" -eq 1; then
    restore_policy_blocker
  fi
}
trap cleanup EXIT

backup_name_for() {
  printf '%s' "$1" | sed 's#^/##; s#/#__#g'
}

collect_apt_source_paths() {
  local live source_dir
  live="$(host_path /etc/apt/sources.list)"
  if test -L "$live"; then
    printf 'apt source symlink is forbidden: %s\n' "$live" >&2
    return 1
  elif test -e "$live"; then
    test -f "$live" || {
      printf 'apt source is not a regular file: %s\n' "$live" >&2
      return 1
    }
    printf '%s\n' /etc/apt/sources.list
  fi
  source_dir="$(host_path /etc/apt/sources.list.d)"
  for live in "$source_dir"/*.list "$source_dir"/*.sources; do
    if test -L "$live"; then
      printf 'apt source symlink is forbidden: %s\n' "$live" >&2
      return 1
    fi
    test -e "$live" || continue
    test -f "$live" || {
      printf 'apt source is not a regular file: %s\n' "$live" >&2
      return 1
    }
    if test -n "$test_root"; then
      printf '%s\n' "${live#"$test_root"}"
    else
      printf '%s\n' "$live"
    fi
  done
}

restore_policy_blocker() {
  local logical=/usr/sbin/policy-rc.d
  local live backup mode existed
  live="$(host_path "$logical")"
  IFS=$'\t' read -r _ existed mode _ backup < <(
    awk -F '\t' -v path="$logical" '$1 == path {print; exit}' "$apt_sources_before/inventory.tsv"
  )
  if test "$existed" = 1; then
    run_privileged install -m "$mode" "$apt_sources_before/$backup" "$live"
  elif test -e "$live"; then
    run_privileged unlink -- "$live"
  fi
  policy_active=0
  if test -s "$policy_state"; then
    python3 - "$policy_state" <<'PY'
import csv
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
rows = list(csv.DictReader(path.open(encoding="utf-8"), delimiter="\t"))
assert len(rows) == 1
rows[0]["restored"] = "1"
work = path.with_name(path.name + ".new")
with work.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
os.replace(work, path)
PY
  fi
}

activate_policy_blocker() {
  local live
  live="$(host_path /usr/sbin/policy-rc.d)"
  capture_work="$(mktemp --tmpdir=/tmp)"
  printf '%s\n' '#!/usr/bin/env sh' 'exit 101' > "$capture_work"
  run_privileged install -m 0755 "$capture_work" "$live"
  policy_active=1
  unlink -- "$capture_work"
  capture_work=
  printf 'path\texisted_before\tmode_before\tsha256_before\trestored\n/usr/sbin/policy-rc.d\t%s\t%s\t%s\t0\n' \
    "$policy_existed_before" "$policy_mode_before" "$policy_sha_before" > "$policy_state"
}

record_policy_restored() {
  restore_policy_blocker
}

driver_is_ready() {
  command -v nvidia-smi >/dev/null 2>&1 || return 1
  local driver_version
  driver_version="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -n1)"
  test -n "$driver_version"
  dpkg --compare-versions "$driver_version" ge 560.35.05
}

require_upstream_version() {
  local package="$1"
  local expected="$2"
  local installed
  installed="$(dpkg-query -W -f='${Version}' "$package")"
  case "$installed" in
    "$expected"|"$expected"[!0-9]*) ;;
    *)
      printf 'installed-version-mismatch: %s expected %s got %s\n' \
        "$package" "$expected" "$installed" >&2
      return 1
      ;;
  esac
}

capture_package_policy() {
  local input_path="$1"
  local input_kind="$2"
  local output_path="$3"
  python3 - "$input_path" "$input_kind" "$output_path" <<'PY'
import csv
import re
import subprocess
import sys
from pathlib import Path

input_path = Path(sys.argv[1])
input_kind = sys.argv[2]
output_path = Path(sys.argv[3])
locked_upstream = {
    "ros-jazzy-ros-gz": "1.0.23-1",
    "ros-jazzy-navigation2": "1.3.12-1",
    "ros-jazzy-nav2-bringup": "1.3.12-1",
    "ros-jazzy-slam-toolbox": "2.8.5-1",
    "ros-jazzy-turtlebot3": "2.3.6-1",
    "ros-jazzy-turtlebot3-simulations": "2.3.7-1",
}
ubuntu_origins = {
    "http://archive.ubuntu.com/ubuntu", "https://archive.ubuntu.com/ubuntu",
    "http://security.ubuntu.com/ubuntu", "https://security.ubuntu.com/ubuntu",
}
ros_origins = {
    "http://packages.ros.org/ros2/ubuntu", "https://packages.ros.org/ros2/ubuntu",
}
gazebo_origins = {
    "http://packages.osrfoundation.org/gazebo/ubuntu-stable",
    "https://packages.osrfoundation.org/gazebo/ubuntu-stable",
}

def allowed_origins_for(package):
    if package.startswith("ros-jazzy-"):
        return ros_origins
    if re.match(r"^(gz-|libgz-|sdformat|libsdformat|ignition-|libignition-)", package):
        return gazebo_origins
    return ubuntu_origins

if input_kind == "requested":
    packages = [line for line in input_path.read_text(encoding="utf-8").splitlines() if line]
elif input_kind == "changed":
    with input_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        assert reader.fieldnames == ["package", "before_version", "after_version", "change"]
        changed_rows = list(reader)
    if any(row["change"] == "removed" for row in changed_rows):
        raise SystemExit("package removal during installation is forbidden")
    packages = [row["package"] for row in changed_rows]
else:
    raise SystemExit(f"unknown policy input kind: {input_kind}")
if packages != sorted(set(packages)):
    raise SystemExit("package policy input must be sorted and unique")

rows = []
for package in packages:
    if package.startswith("ros-") and not package.startswith("ros-jazzy-"):
        raise SystemExit(f"non-Jazzy ROS package is forbidden: {package}")
    if re.fullmatch(r"ros-jazzy-(desktop|desktop-full)", package):
        raise SystemExit(f"Jazzy desktop metapackage is forbidden: {package}")
    completed = subprocess.run(
        ["apt-cache", "policy", package],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    candidate_match = re.search(r"^\s*Candidate:\s*(\S+)", completed.stdout, re.MULTILINE)
    candidate = candidate_match.group(1) if candidate_match else None
    if candidate in {None, "(none)"}:
        raise SystemExit(f"missing candidate for package: {package}")
    expected = locked_upstream.get(package)
    if expected is not None and not (
        candidate == expected
        or (
            candidate.startswith(expected)
            and len(candidate) > len(expected)
            and not candidate[len(expected)].isdigit()
        )
    ):
        raise SystemExit(
            f"candidate-version-mismatch: {package} expected {expected} got {candidate}"
        )
    origins = sorted({
        match.group(1).rstrip("/")
        for match in re.finditer(
            r"^\s*\d+\s+(https?://\S+)\s+\S+\s+\S+\s+Packages$",
            completed.stdout,
            re.MULTILINE,
        )
    })
    allowed = allowed_origins_for(package)
    if not origins or not set(origins) <= allowed:
        raise SystemExit(
            f"package origin is not allowed: {package}: {','.join(origins) or '(none)'}"
        )
    rows.append((
        package,
        expected or "-",
        candidate,
        ",".join(sorted(allowed)),
        ",".join(origins),
    ))

with output_path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
    writer.writerow(("package", "expected_upstream", "candidate", "allowed_origins", "origins"))
    writer.writerows(rows)
PY
}

validate_installed_stack() {
  driver_is_ready
  source "$(host_path /opt/ros/jazzy/setup.bash)"
  test "$ROS_DISTRO" = jazzy
  require_upstream_version ros-jazzy-ros-gz 1.0.23-1
  require_upstream_version ros-jazzy-navigation2 1.3.12-1
  require_upstream_version ros-jazzy-nav2-bringup 1.3.12-1
  require_upstream_version ros-jazzy-slam-toolbox 2.8.5-1
  require_upstream_version ros-jazzy-turtlebot3 2.3.6-1
  require_upstream_version ros-jazzy-turtlebot3-simulations 2.3.7-1
  gz sim --versions | grep -E '(^|[^0-9])8\.[0-9]'
  if systemctl is-active --quiet nginx.service; then
    printf '%s\n' 'nginx must remain stopped during the environment baseline' >&2
    return 1
  fi
  test "$(systemctl is-enabled nginx.service 2>/dev/null || true)" = disabled
}

capture_after_state() {
  test ! -e "$after_packages"
  test ! -e "$new_packages"
  test ! -e "$version_changes"
  test ! -e "$changed_origin_file"
  test ! -e "$managed_after"
  capture_work="$(mktemp --tmpdir=/tmp)"
  dpkg-query -W -f='${Package}\t${Version}\n' | LC_ALL=C sort > "$capture_work"
  install -m 0640 "$capture_work" "$after_packages"
  unlink -- "$capture_work"
  capture_work="$(mktemp --tmpdir=/tmp)"
  awk -F '\t' 'NR==FNR {before[$1]=1; next} !($1 in before) {print $1}' \
    "$before_packages" "$after_packages" | LC_ALL=C sort > "$capture_work"
  install -m 0640 "$capture_work" "$new_packages"
  unlink -- "$capture_work"

  capture_work="$(mktemp --tmpdir=/tmp)"
  python3 - "$before_packages" "$after_packages" "$capture_work" <<'PY'
import csv
import sys
from pathlib import Path

before_path, after_path, output_path = map(Path, sys.argv[1:])
def versions(path):
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        package, version = line.split("\t", 1)
        rows[package] = version
    return rows

before = versions(before_path)
after = versions(after_path)
with output_path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
    writer.writerow(("package", "before_version", "after_version", "change"))
    for package in sorted(set(before) | set(after)):
        old = before.get(package)
        new = after.get(package)
        if old == new:
            continue
        if old is None:
            change = "added"
        elif new is None:
            change = "removed"
        else:
            change = "version-changed"
        writer.writerow((package, old or "-", new or "-", change))
PY
  install -m 0640 "$capture_work" "$version_changes"
  unlink -- "$capture_work"

  capture_work="$(mktemp --tmpdir=/tmp)"
  capture_package_policy "$version_changes" changed "$capture_work"
  install -m 0640 "$capture_work" "$changed_origin_file"
  unlink -- "$capture_work"

  capture_work="$(mktemp --tmpdir=/tmp)"
  printf 'source_path\texisted_after\tmode\tsha256\n' > "$capture_work"
  for source_path in "${managed_paths[@]}"; do
    live_path="$(host_path "$source_path")"
    test ! -L "$live_path"
    if test -e "$live_path"; then
      test -f "$live_path"
      printf '%s\t1\t%s\t%s\n' \
        "$source_path" "$(stat -c '%a' "$live_path")" "$(environment_sha256 "$live_path")" \
        >> "$capture_work"
    else
      printf '%s\t0\t-\t-\n' "$source_path" >> "$capture_work"
    fi
  done
  install -m 0640 "$capture_work" "$managed_after"
  unlink -- "$capture_work"
  capture_work=

  test ! -e "$apt_sources_after"
  install -d -m 0750 "$apt_sources_after"
  capture_work="$(mktemp --tmpdir=/tmp)"
  source_paths_work="$(mktemp --tmpdir=/tmp)"
  collect_apt_source_paths > "$source_paths_work"
  LC_ALL=C sort -u -o "$source_paths_work" "$source_paths_work"
  printf 'source_path\tmode\tsha256\n' > "$capture_work"
  while IFS= read -r source_path; do
    live_path="$(host_path "$source_path")"
    printf '%s\t%s\t%s\n' "$source_path" "$(stat -c '%a' "$live_path")" "$(environment_sha256 "$live_path")" >> "$capture_work"
  done < "$source_paths_work"
  install -m 0640 "$capture_work" "$apt_sources_after/inventory.tsv"
  unlink -- "$capture_work"
  capture_work=
  unlink -- "$source_paths_work"
  source_paths_work=
}

mark_complete() {
  validate_installed_stack
  capture_after_state
  verify_managed_evidence
  capture_work="$(mktemp --tmpdir=/tmp)"
  printf 'state=PASS\ncompleted_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$capture_work"
  test ! -e "$complete_marker"
  install -m 0640 "$capture_work" "$complete_marker"
  unlink -- "$capture_work"
  capture_work=
}

verify_managed_evidence() {
  python3 - "$apt_sources_before/inventory.tsv" "$managed_after" "${test_root:-/}" <<'PY'
import csv
import hashlib
import sys
from pathlib import Path

inventory_path, after_path, root = map(Path, sys.argv[1:])
expected_paths = {
    "/etc/apt/sources.list.d/ros2.list",
    "/etc/apt/sources.list.d/gazebo-stable.list",
    "/usr/share/keyrings/ros-archive-keyring.gpg",
    "/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg",
    "/etc/default/locale",
    "/etc/ros/rosdep/sources.list.d/20-default.list",
    "/usr/sbin/policy-rc.d",
}

with inventory_path.open(encoding="utf-8", newline="") as handle:
    inventory = list(csv.DictReader(handle, delimiter="\t"))
assert expected_paths <= {row["source_path"] for row in inventory}
for row in inventory:
    if row["existed"] == "1":
        backup_name = row["backup_file"]
        assert backup_name not in {"", "-"}
        assert Path(backup_name).name == backup_name
        backup = inventory_path.parent / backup_name
        assert backup.is_file()
        assert hashlib.sha256(backup.read_bytes()).hexdigest() == row["sha256"]
        assert row["mode"].isdigit()
    else:
        assert row["existed"] == "0"
        assert row["mode"] == row["sha256"] == row["backup_file"] == "-"

with after_path.open(encoding="utf-8", newline="") as handle:
    after = list(csv.DictReader(handle, delimiter="\t"))
assert {row["source_path"] for row in after} == expected_paths
for row in after:
    logical = Path(row["source_path"])
    path = logical if root == Path("/") else root / logical.relative_to("/")
    if row["existed_after"] == "1":
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
        assert f"{path.stat().st_mode & 0o777:o}" == row["mode"]
    else:
        assert row["existed_after"] == "0"
        assert not path.exists()
        assert row["mode"] == row["sha256"] == "-"
PY
}

verify_backup_inventory() {
  python3 - "$apt_sources_before/inventory.tsv" <<'PY'
import csv
import hashlib
import sys
from pathlib import Path

inventory_path = Path(sys.argv[1])
rows = list(csv.DictReader(inventory_path.open(encoding="utf-8"), delimiter="\t"))
assert rows
for row in rows:
    if row["existed"] == "1":
        backup = inventory_path.parent / row["backup_file"]
        assert backup.is_file()
        assert hashlib.sha256(backup.read_bytes()).hexdigest() == row["sha256"]
        assert row["mode"].isdigit()
    else:
        assert row["existed"] == "0"
        assert row["mode"] == row["sha256"] == row["backup_file"] == "-"
PY
}

verify_completed_state() {
  test -s "$state_file"
  test -s "$before_packages"
  test -s "$apt_sources_before/inventory.tsv"
  test -s "$candidate_file"
  test -s "$after_packages"
  test -f "$new_packages"
  test -s "$version_changes"
  test -s "$changed_origin_file"
  test -s "$managed_after"
  test -s "$apt_sources_after/inventory.tsv"
  test -s "$policy_state"
  grep -Fxq 'state=INITIAL_INSTALL_STARTED' "$state_file"
  grep -Fxq 'state=PASS' "$complete_marker"
  grep -Eq $'^/usr/sbin/policy-rc.d\t[01]\t.*\t1$' "$policy_state"
  verify_managed_evidence
  validate_installed_stack
  capture_work="$(mktemp --tmpdir=/tmp)"
  capture_package_policy config/environment/apt-packages.txt requested "$capture_work"
  cmp "$candidate_file" "$capture_work"
  unlink -- "$capture_work"
  capture_work="$(mktemp --tmpdir=/tmp)"
  capture_package_policy "$version_changes" changed "$capture_work"
  cmp "$changed_origin_file" "$capture_work"
  unlink -- "$capture_work"
  capture_work="$(mktemp --tmpdir=/tmp)"
  dpkg-query -W -f='${Package}\t${Version}\n' | LC_ALL=C sort > "$capture_work"
  cmp "$after_packages" "$capture_work"
  unlink -- "$capture_work"
  capture_work=
}

if test -s "$complete_marker"; then
  verify_completed_state
  trap - EXIT
  cleanup
  printf '%s\n' 'install-host: PASS'
  exit 0
fi

for initial_artifact in \
  "$state_file" \
  "$before_packages" \
  "$apt_sources_before" \
  "$candidate_file" \
  "$evidence_dir/apt-policy-origins.json" \
  "$policy_state" \
  "$evidence_dir/ros-archive-key.sha256" \
  "$evidence_dir/gazebo-archive-key.sha256" \
  "$after_packages" \
  "$new_packages" \
  "$version_changes" \
  "$changed_origin_file" \
  "$managed_after" \
  "$apt_sources_after"; do
  if test -e "$initial_artifact"; then
    printf 'incomplete-install-evidence-requires-review: %s\n' "$initial_artifact" >&2
    exit 1
  fi
done

universe_present=0
if apt-cache policy | grep -q 'noble/universe'; then
  universe_present=1
fi
test "$universe_present" -eq 1 || {
  printf '%s\n' 'Ubuntu Noble universe must already be enabled; refusing to mutate an existing Ubuntu source file' >&2
  exit 1
}
nginx_unit_present_before=0
nginx_active_before=absent
nginx_enabled_before=absent
if systemctl list-unit-files --type=service --no-legend nginx.service 2>/dev/null \
  | grep -q '^nginx\.service'; then
  nginx_unit_present_before=1
  nginx_active_before="$(systemctl is-active nginx.service 2>/dev/null || true)"
  nginx_enabled_before="$(systemctl is-enabled nginx.service 2>/dev/null || true)"
  case "$nginx_active_before" in
    active|inactive) ;;
    *) printf 'unsupported nginx active state before install: %s\n' "$nginx_active_before" >&2; exit 1 ;;
  esac
  case "$nginx_enabled_before" in
    enabled|disabled|masked) ;;
    *) printf 'unsupported nginx enabled state before install: %s\n' "$nginx_enabled_before" >&2; exit 1 ;;
  esac
fi
capture_work="$(mktemp --tmpdir=/tmp)"
printf 'state=INITIAL_INSTALL_STARTED\nuniverse_present_before=%s\nnginx_unit_present_before=%s\nnginx_active_before=%s\nnginx_enabled_before=%s\nstarted_at=%s\n' \
  "$universe_present" "$nginx_unit_present_before" "$nginx_active_before" "$nginx_enabled_before" \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$capture_work"
install -m 0640 "$capture_work" "$state_file"
unlink -- "$capture_work"

capture_work="$(mktemp --tmpdir=/tmp)"
dpkg-query -W -f='${Package}\t${Version}\n' | LC_ALL=C sort > "$capture_work"
install -m 0640 "$capture_work" "$before_packages"
unlink -- "$capture_work"
capture_work=

install -d -m 0750 "$apt_sources_before"
inventory_work="$(mktemp --tmpdir=/tmp)"
printf 'source_path\texisted\tmode\tsha256\tbackup_file\n' > "$inventory_work"
source_paths_work="$(mktemp --tmpdir=/tmp)"
printf '%s\n' "${managed_paths[@]}" > "$source_paths_work"
collect_apt_source_paths >> "$source_paths_work"
LC_ALL=C sort -u -o "$source_paths_work" "$source_paths_work"
mapfile -t backup_paths < "$source_paths_work"
unlink -- "$source_paths_work"
source_paths_work=
for source_path in "${backup_paths[@]}"; do
  live_path="$(host_path "$source_path")"
  test ! -L "$live_path"
  if test -e "$live_path"; then
    test -f "$live_path"
    backup_name="$(backup_name_for "$source_path")"
    original_mode="$(stat -c '%a' "$live_path")"
    install -m 0640 "$live_path" "$apt_sources_before/$backup_name"
    original_sha="$(environment_sha256 "$apt_sources_before/$backup_name")"
    printf '%s\t1\t%s\t%s\t%s\n' \
      "$source_path" "$original_mode" "$original_sha" "$backup_name" >> "$inventory_work"
  else
    printf '%s\t0\t-\t-\t-\n' "$source_path" >> "$inventory_work"
  fi
done
install -m 0640 "$inventory_work" "$apt_sources_before/inventory.tsv"
unlink -- "$inventory_work"
inventory_work=

IFS=$'\t' read -r _ policy_existed_before policy_mode_before policy_sha_before _ < <(
  awk -F '\t' '$1 == "/usr/sbin/policy-rc.d" {print; exit}' "$apt_sources_before/inventory.tsv"
)
activate_policy_blocker

run_privileged apt-get update
run_privileged apt-get install -y ca-certificates curl gnupg locales software-properties-common

key_work="$(mktemp --tmpdir=/tmp)"
list_work="$(mktemp --tmpdir=/tmp)"
curl -fsSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o "$key_work"
environment_sha256 "$key_work" > "$evidence_dir/ros-archive-key.sha256"
run_privileged install -m 0644 "$key_work" "$(host_path /usr/share/keyrings/ros-archive-keyring.gpg)"
architecture="$(dpkg --print-architecture)"
printf 'deb [arch=%s signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu noble main\n' "$architecture" > "$list_work"
run_privileged install -m 0644 "$list_work" "$(host_path /etc/apt/sources.list.d/ros2.list)"

curl -fsSL https://packages.osrfoundation.org/gazebo.gpg -o "$key_work"
environment_sha256 "$key_work" > "$evidence_dir/gazebo-archive-key.sha256"
run_privileged install -m 0644 "$key_work" "$(host_path /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg)"
printf 'deb [arch=%s signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable noble main\n' "$architecture" > "$list_work"
run_privileged install -m 0644 "$list_work" "$(host_path /etc/apt/sources.list.d/gazebo-stable.list)"

run_privileged apt-get update
capture_work="$(mktemp --tmpdir=/tmp)"
capture_package_policy config/environment/apt-packages.txt requested "$capture_work"
install -m 0640 "$capture_work" "$candidate_file"
unlink -- "$capture_work"
capture_work=

bash scripts/audit_host.sh --report-only > "$evidence_dir/apt-policy-origins.json"
python3 - "$evidence_dir/apt-policy-origins.json" config/environment/apt-packages.txt <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
requested = {
    line
    for line in Path(sys.argv[2]).read_text(encoding="utf-8").splitlines()
    if line
}
assert set(data["apt_policy"]) == requested
assert not data["forbidden_apt_sources"]
assert not data["forbidden_packages"]
assert all(item["candidate_ok"] and item["origin_ok"] for item in data["apt_policy"].values())
PY

mapfile -t requested_packages < config/environment/apt-packages.txt
if test -n "$test_root"; then
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${requested_packages[@]}"
else
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${requested_packages[@]}"
fi

run_privileged locale-gen en_US en_US.UTF-8
run_privileged update-locale LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8
if test ! -f "$(host_path /etc/ros/rosdep/sources.list.d/20-default.list)"; then
  run_privileged rosdep init
fi
rosdep update --rosdistro jazzy

if systemctl list-unit-files nginx.service >/dev/null 2>&1; then
  run_privileged systemctl disable --now nginx.service
fi

if ! driver_is_ready; then
  record_policy_restored
  trap - EXIT
  cleanup
  printf '%s\n' 'install-host: DRIVER_TRANSACTION_REQUIRED'
  exit 23
fi

record_policy_restored
mark_complete
trap - EXIT
cleanup
printf '%s\n' 'install-host: PASS'
```

The installer has two normal states plus one explicit driver-blocked state. A first run creates `install-state.env`, `dpkg-before.tsv`, `apt-sources-before/`, key hashes, and `apt-candidates.tsv` exactly once before the corresponding mutations; the candidate file covers every requested package and accepts only the package-family-specific official Ubuntu, ROS 2, or Gazebo origins. The state file records Nginx's original unit, active, and enabled states but is later treated only as inert data. If the current NVIDIA driver is not already compliant, the script restores temporary service suppression, prints `install-host: DRIVER_TRANSACTION_REQUIRED`, exits 23, and creates no after-state evidence or driver package mutation. A separate reviewed driver transaction may be performed outside this plan, after which a new clean Phase 1 run starts from Task 2. Every added or version-changed package receives the same exact origin validation; an unexpected removal or origin fails closed. The managed-file verifier checks every original backup against its recorded SHA-256 and checks the live after-state against its own mode and SHA-256. A completed rerun writes no evidence and compares the live package and managed-file sets with the captured after-state before printing `PASS`. Any partial state without a complete marker fails closed for operator review. The script never installs a desktop metapackage, starts a project service, changes NVIDIA driver packages, or exposes a port; Nginx is explicitly disabled and stopped after package installation.

- [ ] **Step 4: Implement simulation-gated exact rollback**

Create `scripts/rollback_host.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

mode=
evidence_dir=
confirm_run_id=
if test "$#" -eq 3 && test "$1" = --plan && test "$2" = --evidence-dir; then
  mode=plan
  evidence_dir="$3"
elif test "$#" -eq 5 && test "$1" = --apply && test "$2" = --evidence-dir && test "$4" = --confirm-run-id; then
  mode=apply
  evidence_dir="$3"
  confirm_run_id="$5"
else
  printf '%s\n' 'usage: bash scripts/rollback_host.sh --plan --evidence-dir DIR | --apply --evidence-dir DIR --confirm-run-id RUN_ID' >&2
  exit 2
fi

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
source scripts/lib/environment_common.sh
test_root="${SUBSTATION_INSTALL_TEST_ROOT:-}"
if test -n "$test_root"; then
  case "$test_root" in /tmp/phase1-installer-fixture-*/root) ;; *) exit 2 ;; esac
  case "$evidence_dir" in /tmp/phase1-installer-fixture-*/evidence/01-environment.staging) ;; *) exit 2 ;; esac
else
  environment_require_evidence_dir "$evidence_dir"
fi

host_path() {
  if test -n "$test_root"; then printf '%s%s\n' "$test_root" "$1"; else printf '%s\n' "$1"; fi
}
run_privileged() {
  if test -n "$test_root"; then "$@"; else sudo "$@"; fi
}

state_file="$evidence_dir/install-state.env"
before_packages="$evidence_dir/dpkg-before.tsv"
changes="$evidence_dir/host-install-version-changes.tsv"
additions="$evidence_dir/host-install-new-packages.txt"
before_inventory="$evidence_dir/apt-sources-before/inventory.tsv"
after_inventory="$evidence_dir/apt-sources-after/inventory.tsv"
managed_after="$evidence_dir/managed-files-after.tsv"
for required in "$state_file" "$before_packages" "$changes" "$before_inventory" "$after_inventory" "$managed_after" "$evidence_dir/install-complete.env"; do
  test -s "$required"
done
test -f "$additions"
grep -Fxq 'state=PASS' "$evidence_dir/install-complete.env"

state_values="$(python3 - "$state_file" <<'PY'
import datetime
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
expected_keys = {
    "state",
    "universe_present_before",
    "nginx_unit_present_before",
    "nginx_active_before",
    "nginx_enabled_before",
    "started_at",
}
values = {}
for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
    if not re.fullmatch(r"[a-z_]+=[A-Za-z0-9_.:+-]+", line):
        raise SystemExit(f"unsafe install-state line {line_number}")
    key, value = line.split("=", 1)
    if key in values:
        raise SystemExit(f"duplicate install-state key: {key}")
    values[key] = value
if set(values) != expected_keys:
    raise SystemExit(
        f"install-state keys changed: missing={sorted(expected_keys - set(values))}, "
        f"extra={sorted(set(values) - expected_keys)}"
    )
if values["state"] != "INITIAL_INSTALL_STARTED":
    raise SystemExit("invalid install-state state")
if values["universe_present_before"] != "1":
    raise SystemExit("install-state must record universe present")
if values["nginx_unit_present_before"] not in {"0", "1"}:
    raise SystemExit("invalid nginx unit presence")
if values["nginx_unit_present_before"] == "0":
    if values["nginx_active_before"] != "absent" or values["nginx_enabled_before"] != "absent":
        raise SystemExit("absent nginx unit has inconsistent state")
else:
    if values["nginx_active_before"] not in {"active", "inactive"}:
        raise SystemExit("invalid nginx active state")
    if values["nginx_enabled_before"] not in {"enabled", "disabled", "masked"}:
        raise SystemExit("invalid nginx enabled state")
try:
    datetime.datetime.strptime(values["started_at"], "%Y-%m-%dT%H:%M:%SZ")
except ValueError as error:
    raise SystemExit("invalid install-state UTC timestamp") from error
print("\t".join(values[key] for key in (
    "state",
    "universe_present_before",
    "nginx_unit_present_before",
    "nginx_active_before",
    "nginx_enabled_before",
    "started_at",
)))
PY
)"
IFS=$'\t' read -r install_state universe_present_before nginx_unit_present_before nginx_active_before nginx_enabled_before install_started_at <<<"$state_values"
install_state_validated=1

python3 - "$before_inventory" "$after_inventory" "$managed_after" "${test_root:-/}" <<'PY'
import csv
import hashlib
import sys
from pathlib import Path

before_path, apt_after_path, managed_after_path, root = map(Path, sys.argv[1:])
before = list(csv.DictReader(before_path.open(encoding="utf-8"), delimiter="\t"))
assert before
for row in before:
    if row["existed"] == "1":
        backup = before_path.parent / row["backup_file"]
        assert backup.is_file()
        assert hashlib.sha256(backup.read_bytes()).hexdigest() == row["sha256"]

expected = {}
for path in (apt_after_path, managed_after_path):
    for row in csv.DictReader(path.open(encoding="utf-8"), delimiter="\t"):
        expected[row["source_path"]] = row
for logical_text, row in expected.items():
    logical = Path(logical_text)
    live = logical if root == Path("/") else root / logical.relative_to("/")
    existed = row.get("existed_after", "1")
    if existed == "1":
        assert live.is_file()
        assert hashlib.sha256(live.read_bytes()).hexdigest() == row["sha256"]
        assert f"{live.stat().st_mode & 0o777:o}" == row["mode"]
    else:
        assert existed == "0" and not live.exists()
PY

mapfile -t rollback_versions < <(
  awk -F '\t' 'NR > 1 && ($4 == "version-changed" || $4 == "removed") {print $1 "=" $2}' "$changes"
)
mapfile -t added_packages < "$additions"

validate_simulation() (
  local action="$1"
  shift
  local output expected_work actual_work
  expected_work="$(mktemp --tmpdir=/tmp)"
  actual_work="$(mktemp --tmpdir=/tmp)"
  cleanup_simulation() {
    unlink -- "$expected_work"
    unlink -- "$actual_work"
  }
  trap cleanup_simulation EXIT
  printf '%s\n' "$@" | sed 's/=.*//' | LC_ALL=C sort -u > "$expected_work"
  if test "$action" = install; then
    run_privileged apt-get --simulate install --yes --allow-downgrades --no-install-recommends "$@" \
      | awk '$1 == "Inst" {print $2}' | LC_ALL=C sort -u > "$actual_work"
  else
    run_privileged apt-get --simulate remove --no-auto-remove --yes "$@" \
      | awk '$1 == "Remv" {print $2}' | LC_ALL=C sort -u > "$actual_work"
  fi
  cmp "$expected_work" "$actual_work"
)

if test "${#rollback_versions[@]}" -gt 0; then
  validate_simulation install "${rollback_versions[@]}"
fi
if test "${#added_packages[@]}" -gt 0; then
  validate_simulation remove "${added_packages[@]}"
fi
printf '%s\n' 'rollback-host-plan: PASS'
if test "$mode" = plan; then
  exit 0
fi

run_id="$(basename "$(dirname "$evidence_dir")")"
test "$confirm_run_id" = "$run_id"

if test "${#rollback_versions[@]}" -gt 0; then
  run_privileged apt-get install --yes --allow-downgrades --no-install-recommends "${rollback_versions[@]}"
fi
if test "${#added_packages[@]}" -gt 0; then
  run_privileged apt-get remove --no-auto-remove --yes "${added_packages[@]}"
fi

while IFS=$'\t' read -r source_path existed_before mode_before sha_before backup_file; do
  test "$source_path" != source_path || continue
  live="$(host_path "$source_path")"
  if test "$existed_before" = 1; then
    backup="$evidence_dir/apt-sources-before/$backup_file"
    test "$(environment_sha256 "$backup")" = "$sha_before"
    if test ! -f "$live" || test "$(environment_sha256 "$live")" != "$sha_before" || test "$(stat -c '%a' "$live")" != "$mode_before"; then
      run_privileged install -m "$mode_before" "$backup" "$live"
    fi
  elif test -e "$live"; then
    case "$source_path" in
      /etc/apt/sources.list.d/ros2.list|/etc/apt/sources.list.d/gazebo-stable.list|/usr/share/keyrings/ros-archive-keyring.gpg|/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg|/etc/default/locale|/etc/ros/rosdep/sources.list.d/20-default.list|/usr/sbin/policy-rc.d) ;;
      *) printf 'refusing-to-unlink-unowned-path: %s\n' "$source_path" >&2; exit 1 ;;
    esac
    run_privileged unlink -- "$live"
  fi
done < "$before_inventory"

test "$install_state_validated" -eq 1
if test "$nginx_unit_present_before" = 1; then
  case "$nginx_enabled_before" in
    enabled) run_privileged systemctl enable nginx.service ;;
    disabled) run_privileged systemctl disable nginx.service ;;
    masked) run_privileged systemctl mask nginx.service ;;
    *) printf 'unsupported recorded nginx enabled state: %s\n' "$nginx_enabled_before" >&2; exit 1 ;;
  esac
  case "$nginx_active_before" in
    active) run_privileged systemctl start nginx.service ;;
    inactive) run_privileged systemctl stop nginx.service ;;
    *) printf 'unsupported recorded nginx active state: %s\n' "$nginx_active_before" >&2; exit 1 ;;
  esac
elif systemctl list-unit-files --type=service --no-legend nginx.service 2>/dev/null \
  | grep -q '^nginx\.service'; then
  printf '%s\n' 'nginx unit remains after rollback although it was absent before installation' >&2
  exit 1
fi

current_work="$(mktemp --tmpdir=/tmp)"
cleanup() { test ! -e "$current_work" || unlink -- "$current_work"; }
trap cleanup EXIT
dpkg-query -W -f='${Package}\t${Version}\n' | LC_ALL=C sort > "$current_work"
python3 - "$before_packages" "$current_work" <<'PY'
import sys
from pathlib import Path

def rows(path):
    return {line.split("\t", 1)[0]: line.split("\t", 1)[1] for line in Path(path).read_text(encoding="utf-8").splitlines()}
before, current = map(rows, sys.argv[1:])
for package in sorted(set(before) | set(current)):
    if package.startswith("nvidia-"):
        continue
    assert before.get(package) == current.get(package), (package, before.get(package), current.get(package))
PY
printf '%s\n' 'rollback-host-apply: PASS'
```

The rollback `--plan` and `--apply` paths first parse `install-state.env` as inert data with an exact key set, single-occurrence enforcement, a shell-inert value grammar, allowed enums, UTC timestamp validation, and Nginx cross-field constraints. Neither path sources the file. The `--apply` path then invokes the same strict simulation internally before any package or file mutation. The simulation output may name only the exact recorded restore/remove package sets; extra apt dependency changes fail. Current live files and every backup are hash/mode validated before application. Only the seven explicitly owned created paths may be unlinked; every existing `sources.list`, `.list`, and deb822 `.sources` file is restored byte-for-byte with its recorded mode.

- [ ] **Step 5: Run behavioral tests before the host mutation**

```bash
chmod +x scripts/install_host.sh scripts/rollback_host.sh tests/environment/test_install_host.sh tests/environment/fixtures/fake_host_command.py
bash tests/environment/test_install_host.sh
LC_ALL=C sort -c config/environment/apt-packages.txt
```

Expected: `install-host-test: PASS`; the fake-host scenarios prove fresh success, all-requested-package candidate/origin coverage, unrelated Noble external-source recording without project package leakage, changed-package origin rejection, candidate failure before target install, explicit driver-transaction refusal without driver mutation, completed read-only rerun, partial-state refusal, backup tamper refusal, tampered `install-state.env` rejection before any fake mutation or shell evaluation, temporary service suppression restoration, and simulation-gated package/source rollback. No `sudo` command touches the real host during this test.

- [ ] **Step 6: Commit the installer before the first live host mutation, then apply it**

```bash
git add scripts/install_host.sh scripts/rollback_host.sh tests/environment/test_install_host.sh tests/environment/fixtures/fake_host_command.py
git diff --cached --check
git commit -m "feat: install locked ros and gazebo baseline"
install_commit="$(git rev-parse HEAD)"
test -z "$(git status --porcelain=v1 --untracked-files=all -- \
  scripts/install_host.sh scripts/rollback_host.sh tests/environment/test_install_host.sh tests/environment/fixtures/fake_host_command.py)"
```

Expected: the exact script and test implementation is committed before any real apt source, package, service or storage mutation. All subsequent evidence for this task records `install_commit` plus the SHA-256 of `scripts/install_host.sh` and `config/environment/apt-packages.txt`.

Run:

```bash
source .phase1-run.env
test "$(git rev-parse HEAD)" = "$install_commit"
set +e
test ! -e "$PHASE1_EVIDENCE_ROOT/install-host.log"
bash scripts/install_host.sh --apply --evidence-dir "$PHASE1_EVIDENCE_ROOT" \
  2>&1 | tee "$PHASE1_EVIDENCE_ROOT/install-host.log"
install_rc="${PIPESTATUS[0]}"
set -e
test "$install_rc" -eq 0 || test "$install_rc" -eq 23
```

Expected with the already compliant server driver: final line `install-host: PASS`, exit 0. If the driver is absent, below `560.35.05`, non-Ubuntu, or fails required headless evidence, the final line is `install-host: DRIVER_TRANSACTION_REQUIRED`, exit 23. In that case stop Phase 1, preserve `install-host.log`, `install-state.env`, `dpkg-before.tsv`, `apt-sources-before/inventory.tsv`, `apt-candidates.tsv`, key hashes, and policy evidence, update `PROJECT_STATUS`/`HANDOFF` with the blocker, and do not reboot or run a driver installer in this plan.

After a successful exit 0, immediately update the status documents for Task 3:

```bash
task_commit="$install_commit"
repo_root="$(git rev-parse --show-toplevel)"
branch_name="$(git branch --show-current)"
verified_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
script_sha256="$(sha256sum scripts/install_host.sh | awk '{print $1}')"
package_manifest_sha256="$(sha256sum config/environment/apt-packages.txt | awk '{print $1}')"
printf 'task_commit=%s\nrepo_root=%s\nbranch=%s\nverified_at=%s\nscript_sha256=%s\npackage_manifest_sha256=%s\nevidence=%s\n' \
  "$task_commit" "$repo_root" "$branch_name" "$verified_at" "$script_sha256" "$package_manifest_sha256" "$PHASE1_EVIDENCE_ROOT"
```

Use `apply_patch` to record those literal values in `docs/PROJECT_STATUS.md` and `docs/HANDOFF.md`, including the exact install command and result. Then commit only those two documents:

```bash
git add docs/PROJECT_STATUS.md docs/HANDOFF.md
git diff --cached --check
git commit -m "docs: record phase one task 3 status"
```

If a status-document commit is created, later live evidence continues to identify the task implementation commit and script SHA, not the documentation-only status commit.

- [ ] **Step 7: Verify exact distribution families immediately after install**

```bash
source .phase1-run.env
source /opt/ros/jazzy/setup.bash
test "$ROS_DISTRO" = jazzy
dpkg-query -W -f='${Package}\t${Version}\n' ros-jazzy-ros-gz \
  | grep -E $'^ros-jazzy-ros-gz\t1\.0\.23-1([^0-9].*)?$'
dpkg-query -W -f='${Package}\t${Version}\n' ros-jazzy-navigation2 ros-jazzy-nav2-bringup \
  | tee "$PHASE1_EVIDENCE_ROOT/navigation2-packages.txt"
grep -E $'^ros-jazzy-navigation2\t1\.3\.12-1([^0-9].*)?$' "$PHASE1_EVIDENCE_ROOT/navigation2-packages.txt"
grep -E $'^ros-jazzy-nav2-bringup\t1\.3\.12-1([^0-9].*)?$' "$PHASE1_EVIDENCE_ROOT/navigation2-packages.txt"
dpkg-query -W -f='${Version}\n' ros-jazzy-slam-toolbox \
  | grep -E '^2\.8\.5-1([^0-9].*)?$'
dpkg-query -W -f='${Package}\t${Version}\n' ros-jazzy-turtlebot3 ros-jazzy-turtlebot3-simulations \
  | tee "$PHASE1_EVIDENCE_ROOT/turtlebot3-packages.txt"
grep -E $'^ros-jazzy-turtlebot3\t2\.3\.6-1([^0-9].*)?$' "$PHASE1_EVIDENCE_ROOT/turtlebot3-packages.txt"
grep -E $'^ros-jazzy-turtlebot3-simulations\t2\.3\.7-1([^0-9].*)?$' "$PHASE1_EVIDENCE_ROOT/turtlebot3-packages.txt"
gz sim --versions | grep -E '(^|[^0-9])8\.[0-9]'
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
driver_version="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -n1)"
dpkg --compare-versions "$driver_version" ge 560.35.05
test -s "$PHASE1_EVIDENCE_ROOT/dpkg-before.tsv"
test -s "$PHASE1_EVIDENCE_ROOT/dpkg-after.tsv"
test -s "$PHASE1_EVIDENCE_ROOT/apt-candidates.tsv"
test -s "$PHASE1_EVIDENCE_ROOT/apt-changed-package-origins.tsv"
test -s "$PHASE1_EVIDENCE_ROOT/apt-policy-origins.json"
test -s "$PHASE1_EVIDENCE_ROOT/apt-sources-before/inventory.tsv"
test -s "$PHASE1_EVIDENCE_ROOT/apt-sources-after/inventory.tsv"
grep -Eq $'^/usr/sbin/policy-rc.d\t[01]\t.*\t1$' "$PHASE1_EVIDENCE_ROOT/policy-rc.d-state.tsv"
test -f "$PHASE1_EVIDENCE_ROOT/host-install-new-packages.txt"
test -s "$PHASE1_EVIDENCE_ROOT/host-install-version-changes.tsv"
test -s "$PHASE1_EVIDENCE_ROOT/managed-files-after.tsv"
grep -Fx 'state=PASS' "$PHASE1_EVIDENCE_ROOT/install-complete.env"
```

Expected: every command exits 0; ROS is Jazzy, `ros_gz` upstream is 1.0.23-1, Navigation2 is 1.3.12-1, SLAM Toolbox is 2.8.5-1, TurtleBot3 core and simulation expose 2.3.6-1 and 2.3.7-1 respectively, Gazebo major is 8, and the driver meets the floor. Full Ubuntu package revisions are captured for review later; they are not silently normalized away.

Evidence: `install-host.log`, `dpkg-before.tsv`, `dpkg-after.tsv`, `host-install-new-packages.txt`, `host-install-version-changes.tsv`, `managed-files-after.tsv`, `install-state.env`, `install-complete.env`, `apt-candidates.tsv`, `apt-changed-package-origins.tsv`, `apt-policy-origins.json`, `policy-rc.d-state.tsv`, key SHA files, and the complete before/after apt-source inventories below `$PHASE1_EVIDENCE_ROOT/apt-sources-before` and `apt-sources-after`.

Safe rollback: first run `bash scripts/rollback_host.sh --plan --evidence-dir "$PHASE1_EVIDENCE_ROOT"`. Review the exact simulated package set, then run `bash scripts/rollback_host.sh --apply --evidence-dir "$PHASE1_EVIDENCE_ROOT" --confirm-run-id "$PHASE1_RUN_ID"`. The numbered details below explain that script's recorded transaction; do not execute individual snippets as a substitute for its validation gate.

1. Preserve all evidence.
2. Review `$PHASE1_EVIDENCE_ROOT/host-install-version-changes.tsv`. Restore every `version-changed` or `removed` row through an operator-reviewed exact-version transaction before removing additions:

   ```bash
   mapfile -t rollback_versions < <(
     awk -F '\t' 'NR > 1 && ($4 == "version-changed" || $4 == "removed") {print $1 "=" $2}' \
       "$PHASE1_EVIDENCE_ROOT/host-install-version-changes.tsv"
   )
   if test "${#rollback_versions[@]}" -gt 0; then
     sudo apt-get install --yes --allow-downgrades --no-install-recommends "${rollback_versions[@]}"
   fi
   ```

   Stop if an exact prior version is unavailable or apt proposes an unrecorded package change. Never substitute a nearby version.
3. Review `$PHASE1_EVIDENCE_ROOT/host-install-new-packages.txt`; remove only confirmed `added` rows, with no automatic dependency cleanup:

   ```bash
   mapfile -t added_packages < "$PHASE1_EVIDENCE_ROOT/host-install-new-packages.txt"
   if test "${#added_packages[@]}" -gt 0; then
     sudo apt-get remove --no-auto-remove --yes "${added_packages[@]}"
   fi
   ```
4. Restore every managed path, including locale and rosdep, from the two manifests. The loop refuses to touch a path unless its current state still matches `managed-files-after.tsv`; it restores every `existed=1` backup with the recorded mode and SHA-256 and unlinks every `existed=0` path that Task 3 created:

   ```bash
   declare -A after_exists after_sha
   while IFS=$'\t' read -r source_path existed_after mode sha256; do
     test "$source_path" != source_path || continue
     after_exists["$source_path"]="$existed_after"
     after_sha["$source_path"]="$sha256"
   done < "$PHASE1_EVIDENCE_ROOT/managed-files-after.tsv"

   while IFS=$'\t' read -r source_path existed_before mode sha256 backup_file; do
     test "$source_path" != source_path || continue
     if test "${after_exists[$source_path]}" = 1; then
       if test -f "$source_path"; then
         test "$(sha256sum -- "$source_path" | awk '{print $1}')" = "${after_sha[$source_path]}"
       elif test "$existed_before" = 0; then
         continue
       fi
     else
       test ! -e "$source_path"
     fi
     if test "$existed_before" = 1; then
       backup_path="$PHASE1_EVIDENCE_ROOT/apt-sources-before/$backup_file"
       test -f "$backup_path"
       test "$(sha256sum -- "$backup_path" | awk '{print $1}')" = "$sha256"
       sudo install -m "$mode" "$backup_path" "$source_path"
     elif test -e "$source_path"; then
       sudo unlink -- "$source_path"
     fi
   done < "$PHASE1_EVIDENCE_ROOT/apt-sources-before/inventory.tsv"
   ```

5. Restore the original Nginx state recorded in `install-state.env`. The canonical rollback first parses this file strictly as inert data, requiring the exact six-key schema, one occurrence per key, a safe value grammar, allowed enums, a valid UTC timestamp, and consistent absent/present Nginx fields; it never sources the file. If `nginx_unit_present_before=0`, confirm the unit disappears with the newly added packages. Otherwise restore only the validated `enabled`/`disabled`/`masked` and `active`/`inactive` combination; any other recorded state requires operator review rather than normalization:

   ```bash
   test "$install_state_validated" -eq 1
   if test "$nginx_unit_present_before" = 0; then
     ! systemctl list-unit-files --type=service --no-legend nginx.service 2>/dev/null \
       | grep -q '^nginx\.service'
   else
     case "$nginx_enabled_before" in
       enabled) sudo systemctl enable nginx.service ;;
       disabled) sudo systemctl disable nginx.service ;;
       masked) sudo systemctl mask nginx.service ;;
       *) printf 'unsupported recorded nginx enabled state: %s\n' "$nginx_enabled_before" >&2; false ;;
     esac
     case "$nginx_active_before" in
       active) sudo systemctl start nginx.service ;;
       inactive) sudo systemctl stop nginx.service ;;
       *) printf 'unsupported recorded nginx active state: %s\n' "$nginx_active_before" >&2; false ;;
     esac
   fi
   ```
6. The installer requires Noble `universe` to exist before mutation and never edits it, so rollback must not add, remove, or normalize an Ubuntu base source.
7. Compare a fresh sorted `dpkg-query` snapshot with `dpkg-before.tsv`. Every non-NVIDIA difference is an incomplete rollback. Do not attempt an automated NVIDIA driver rollback; boot the previously known-good kernel/driver package set and require an operator-reviewed exact-version transaction for those remaining rows.
8. Revert the Task 3 implementation commit and the Task 3 status/handoff commit only after the restored host state and retained evidence have been reviewed.

- [ ] **Step 8: Commit Task 3**

```bash
if ! git log -1 --format=%s -- scripts/install_host.sh scripts/rollback_host.sh tests/environment/test_install_host.sh tests/environment/fixtures/fake_host_command.py \
  | grep -Fxq 'feat: install locked ros and gazebo baseline'; then
  git add scripts/install_host.sh scripts/rollback_host.sh tests/environment/test_install_host.sh tests/environment/fixtures/fake_host_command.py
  git diff --cached --check
  git commit -m "feat: install locked ros and gazebo baseline"
fi
```

Expected: the installer, rollback entry point, fake-host fixture, and behavioral test exist in one focused implementation commit. A successful live run has one later documentation-only `docs/PROJECT_STATUS.md`/`docs/HANDOFF.md` synchronization commit. A `DRIVER_TRANSACTION_REQUIRED` run has the same documentation update but records Phase 1 as blocked and does not proceed to Task 4.

---

### Task 4: Resource Identity Manifest and Early Checksummed Downloads

**Files:**
- Create: `config/environment/resource-sources.tsv`
- Create: `scripts/download_phase1_resources.sh`
- Create: `scripts/verify_phase1_resources.sh`
- Create: `tests/environment/test_phase1_resources.sh`

**Interfaces:**
- Consumes: official Node.js 24.18.0 release files, the Ultralytics assets v8.4.0 YOLO11n URL, external user-training reference identities fixed by `docs/VERSION_MATRIX.md`, a pre-download capacity calculation proving expected bytes plus at least 20 GiB remaining on the affected mount, and the active unsealed evidence directory.
- Produces: atomically installed task-owned Node and YOLO leaves below `/var/lib/substation`, provenance markers plus YOLO `source.json`, `$PHASE1_EVIDENCE_ROOT/resource-downloads.tsv`, and a separate checksum-only `scripts/verify_phase1_resources.sh`. The downloader preflights any locked row or existing target before persistent installation, traps every temporary path, and refuses foreign/incomplete content-addressed directories. The verifier has no network, download, repair, or manifest rewrite path.

- [ ] **Step 1: Write the failing resource-governance test**

**Solo fast-track override (authoritative):** the user waived the heavyweight fake-resource behavior matrix for this personal project. The tracked `tests/environment/test_phase1_resources.sh` is the source of truth for this checkpoint: it checks the two Phase 1 download identities, all four external user-training reference rows, absence of Phase 4 dataset acquisition rows, the downloader list, Git large-file exclusion, and absence of install/start/build commands in the resource scripts; its final line is `phase1-resource-static-test: PASS`. The longer fixture below is retained only as a superseded hardening reference and must not be treated as the active acceptance contract.

Superseded pre-fast-track hardening reference:

```bash
#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

test -x scripts/download_phase1_resources.sh
test -x scripts/verify_phase1_resources.sh
test -s config/environment/resource-sources.tsv
grep -F $'node-linux-x64\tphase1' config/environment/resource-sources.tsv
grep -F $'yolo11n-base\tphase1' config/environment/resource-sources.tsv
grep -F $'substation-equipment-15\texternal-user-training-reference' config/environment/resource-sources.tsv
grep -F $'hard-hat-workers-v10\texternal-user-training-reference' config/environment/resource-sources.tsv
grep -F $'d-fire\texternal-user-training-reference' config/environment/resource-sources.tsv
grep -F $'insplad\texternal-user-training-reference-resolve-commit-first' config/environment/resource-sources.tsv
! awk -F '\t' 'NR > 1 && $1 ~ /^(substation-equipment-15|hard-hat-workers-v10|d-fire|insplad)$/ && $2 ~ /^phase4/ {bad=1} END {exit bad ? 0 : 1}' config/environment/resource-sources.tsv
grep -F $'gazebo-meter\tphase2-and-phase4-generated' config/environment/resource-sources.tsv
bash scripts/download_phase1_resources.sh --list | grep -Fx 'node-linux-x64'
bash scripts/download_phase1_resources.sh --list | grep -Fx 'yolo11n-base'
rg -F 'resource identity changed' scripts/download_phase1_resources.sh
! git ls-files | grep -E '\.(pt|onnx|engine|tar\.xz|zip)$'

fixture_root="/tmp/phase1-resource-fixture-$(python3 -c 'import uuid; print(uuid.uuid4())')"
case "$fixture_root" in /tmp/phase1-resource-fixture-*) ;; *) exit 1 ;; esac
test ! -e "$fixture_root"
install -d -m 0700 "$fixture_root/bin" "$fixture_root/root/var/lib/substation" "$fixture_root/evidence/01-environment.staging"
cleanup() {
  case "$fixture_root" in /tmp/phase1-resource-fixture-*) find "$fixture_root" -depth -delete ;; *) return 1 ;; esac
}
trap cleanup EXIT
cat > "$fixture_root/bin/curl" <<'SH'
#!/usr/bin/bash
output=
url=
while test "$#" -gt 0; do
  case "$1" in
    -o) output="$2"; shift 2 ;;
    http*) url="$1"; shift ;;
    *) shift ;;
  esac
done
case "$url" in
  */node-v24.18.0-linux-x64.tar.xz) printf '%s' 'fixture-node-24.18.0' > "$output" ;;
  */SHASUMS256.txt)
    digest="$(printf '%s' 'fixture-node-24.18.0' | sha256sum | awk '{print $1}')"
    printf '%s  %s\n' "$digest" node-v24.18.0-linux-x64.tar.xz > "$output"
    ;;
  */yolo11n.pt) printf '%s' 'fixture-yolo11n-v8.4.0' > "$output" ;;
  *) exit 2 ;;
esac
SH
chmod 0750 "$fixture_root/bin/curl"

PATH="$fixture_root/bin:$PATH" \
SUBSTATION_RESOURCE_TEST_ROOT="$fixture_root/root" \
bash scripts/download_phase1_resources.sh --resource all --evidence-dir "$fixture_root/evidence/01-environment.staging"
manifest="$fixture_root/evidence/01-environment.staging/resource-downloads.tsv"
test "$(wc -l < "$manifest")" -eq 3
yolo_logical="$(awk -F '\t' '$1 == "yolo11n-base" {print $6}' "$manifest")"
yolo_dir="$fixture_root/root$(dirname "$yolo_logical")"
test -s "$yolo_dir/source.json"
test -s "$yolo_dir/.substation-resource.json"
python3 - "$yolo_dir/source.json" <<'PY'
import json, sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert data["resource_id"] == "yolo11n-base"
assert data["revision"] == "v8.4.0"
assert data["source_url"].endswith("/v8.4.0/yolo11n.pt")
assert len(data["sha256"]) == 64
PY

find "$fixture_root/root/var/lib/substation" -type f -printf '%P\0' | LC_ALL=C sort -z | xargs -0 -r -I{} sha256sum "$fixture_root/root/var/lib/substation/{}" > "$fixture_root/resources.before"
cat > "$fixture_root/bin/curl" <<'SH'
#!/usr/bin/bash
printf '%s\n' 'curl must not be called by checksum-only verification' >&2
exit 99
SH
PATH="$fixture_root/bin:$PATH" \
SUBSTATION_RESOURCE_TEST_ROOT="$fixture_root/root" \
bash scripts/verify_phase1_resources.sh --evidence-dir "$fixture_root/evidence/01-environment.staging"
find "$fixture_root/root/var/lib/substation" -type f -printf '%P\0' | LC_ALL=C sort -z | xargs -0 -r -I{} sha256sum "$fixture_root/root/var/lib/substation/{}" > "$fixture_root/resources.after"
cmp "$fixture_root/resources.before" "$fixture_root/resources.after"

printf '%s' foreign > "$yolo_dir/foreign-extra.bin"
set +e
PATH="$fixture_root/bin:$PATH" SUBSTATION_RESOURCE_TEST_ROOT="$fixture_root/root" bash scripts/verify_phase1_resources.sh --evidence-dir "$fixture_root/evidence/01-environment.staging"
verify_extra_rc=$?
set -e
test "$verify_extra_rc" -ne 0
grep -Fxq foreign "$yolo_dir/foreign-extra.bin"
unlink -- "$yolo_dir/foreign-extra.bin"

printf '%s' tampered > "$yolo_dir/yolo11n.pt"
set +e
PATH="$fixture_root/bin:$PATH" SUBSTATION_RESOURCE_TEST_ROOT="$fixture_root/root" bash scripts/verify_phase1_resources.sh --evidence-dir "$fixture_root/evidence/01-environment.staging"
verify_tamper_rc=$?
set -e
test "$verify_tamper_rc" -ne 0
grep -Fxq tampered "$yolo_dir/yolo11n.pt"

foreign_root="$fixture_root/foreign-root"
foreign_evidence="$fixture_root/foreign-evidence/01-environment.staging"
install -d -m 0700 "$foreign_root/var/lib/substation/models/base" "$foreign_evidence"
foreign_sha="$(printf '%s' 'fixture-yolo11n-v8.4.0' | sha256sum | awk '{print $1}')"
install -d -m 0700 "$foreign_root/var/lib/substation/models/base/$foreign_sha"
printf '%s' foreign > "$foreign_root/var/lib/substation/models/base/$foreign_sha/unowned.bin"
cat > "$fixture_root/bin/curl" <<'SH'
#!/usr/bin/bash
output=
while test "$#" -gt 0; do if test "$1" = -o; then output="$2"; shift 2; else shift; fi; done
printf '%s' 'fixture-yolo11n-v8.4.0' > "$output"
SH
set +e
PATH="$fixture_root/bin:$PATH" SUBSTATION_RESOURCE_TEST_ROOT="$foreign_root" bash scripts/download_phase1_resources.sh --resource yolo11n-base --evidence-dir "$foreign_evidence"
foreign_rc=$?
set -e
test "$foreign_rc" -ne 0
test ! -e "$foreign_root/var/lib/substation/models/base/$foreign_sha/.substation-resource.json"
test "$(find "$foreign_root/var/lib/substation/models/base" -maxdepth 1 -type d -name '.*.staging-*' | wc -l)" -eq 0

trap - EXIT
cleanup
printf '%s\n' 'phase1-resource-test: PASS'
```

Run:

```bash
chmod +x tests/environment/test_phase1_resources.sh
bash tests/environment/test_phase1_resources.sh
```

Historical expectation only: before the fast-track implementation this exited nonzero because neither the manifest nor downloader existed. Current execution uses the authoritative tracked static test described above.

- [ ] **Step 2: Add the exact resource identity and phase sequence**

Create `config/environment/resource-sources.tsv` with this exact tab-separated content:

```text
resource_id	phase	immutable_identity	source_url	server_storage	git_policy
node-linux-x64	phase1	24.18.0	https://nodejs.org/dist/v24.18.0/node-v24.18.0-linux-x64.tar.xz	/var/lib/substation/downloads/node/24.18.0	manifest-and-sha-only
yolo11n-base	phase1	ultralytics-assets-v8.4.0	https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt	/var/lib/substation/models/base/sha256-keyed	manifest-and-sha-only
substation-equipment-15	external-user-training-reference	c63ed3c7f5ea33ac8e9024c467a70a62b849b2ad	https://huggingface.co/datasets/AndrzejDD/15-class-Substation-Equipment	provided-by-user-training-manifest	reference-and-provenance-only
hard-hat-workers-v10	external-user-training-reference	provider-version-10	https://public.roboflow.com/object-detection/hard-hat-workers/10	provided-by-user-training-manifest	reference-and-provenance-only
d-fire	external-user-training-reference	4bf9c31b18fadcd44d5f0b6d66f82bc56fa5e328	https://github.com/gaia-solutions-on-demand/DFireDataset	provided-by-user-training-manifest	reference-and-provenance-only
insplad	external-user-training-reference-resolve-commit-first	resolve-one-40-character-commit-before-fetch	https://github.com/andreluizbvs/InsPLAD	provided-by-user-training-manifest	reference-and-provenance-only
gazebo-meter	phase2-and-phase4-generated	generator-commit-plus-config-sha-plus-gazebo-version-plus-seeds	project-owned	/var/lib/substation/datasets/synthetic/gazebo-meter/generation-sha256	manifest-and-sha-only
gazebo-anomalies	phase2-and-phase4-generated	generator-commit-plus-config-sha-plus-gazebo-version-plus-seeds	project-owned	/var/lib/substation/datasets/synthetic/gazebo-anomalies/generation-sha256	manifest-and-sha-only
```

The file records both the Phase 1 acquisition sequence and later external user-training references; only rows whose phase is `phase1` are downloadable by this phase. It is not `datasets/manifest.yaml` or `models/manifest.yaml`. Those production manifests are imported later from a user-published immutable GitHub model release only when their complete schema can be truthfully populated; this avoids inventing unmeasured file hashes or production mappings.

- [ ] **Step 3: Implement early downloads with first-use locking**

Create `scripts/download_phase1_resources.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
source scripts/lib/environment_common.sh

if test "$#" -eq 1 && test "$1" = --list; then
  printf '%s\n' node-linux-x64 yolo11n-base
  exit 0
fi
if test "$#" -ne 4 || test "$1" != --resource || test "$3" != --evidence-dir; then
  printf '%s\n' 'usage: bash scripts/download_phase1_resources.sh --resource node-linux-x64|yolo11n-base|all --evidence-dir /var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment.staging' >&2
  exit 2
fi

selection="$2"
evidence_dir="$4"
test_root="${SUBSTATION_RESOURCE_TEST_ROOT:-}"
if test -n "$test_root"; then
  case "$test_root" in /tmp/phase1-resource-fixture-*) ;; *) printf 'invalid-resource-test-root: %s\n' "$test_root" >&2; exit 2 ;; esac
  case "$evidence_dir" in /tmp/phase1-resource-fixture-*/01-environment.staging) ;; *) printf 'invalid-resource-test-evidence: %s\n' "$evidence_dir" >&2; exit 2 ;; esac
  test -d "$test_root"
  test -d "$evidence_dir"
else
  environment_require_evidence_dir "$evidence_dir"
fi
case "$selection" in
  node-linux-x64|yolo11n-base|all) ;;
  *) printf 'unknown-resource: %s\n' "$selection" >&2; exit 2 ;;
esac

operator_user="$(id -un)"
operator_group="$(id -gn)"
resource_path() {
  if test -n "$test_root"; then printf '%s%s\n' "$test_root" "$1"; else printf '%s\n' "$1"; fi
}
run_privileged() {
  if test -n "$test_root"; then "$@"; else sudo "$@"; fi
}

storage_manifest="$evidence_dir/storage-paths-before.tsv"
if test ! -e "$storage_manifest"; then
  printf 'path\texisted_before\tmode_before\towner_before\tgroup_before\tdevice\tinode\texpected_mode\texpected_owner\texpected_group\tcreated_by_task\n' > "$storage_manifest"
fi
prepare_directory() {
  local logical="$1"
  local mode="$2"
  local live parent actual_mode actual_owner actual_group
  mode="${mode#0}"
  live="$(resource_path "$logical")"
  test ! -L "$live"
  if test -e "$live"; then
    test -d "$live"
    actual_mode="$(stat -c '%a' "$live")"
    actual_owner="$(stat -c '%U' "$live")"
    actual_group="$(stat -c '%G' "$live")"
    if test -z "$test_root"; then
      test "$actual_mode" = "$mode"
      test "$actual_owner" = "$operator_user"
      test "$actual_group" = "$operator_group"
    fi
    if ! awk -F '\t' -v path="$logical" 'NR > 1 && $1 == path {found=1} END {exit !found}' "$storage_manifest"; then
      printf '%s\t1\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t0\n' \
        "$logical" "$actual_mode" "$actual_owner" "$actual_group" "$(stat -c '%d' "$live")" "$(stat -c '%i' "$live")" \
        "$mode" "$operator_user" "$operator_group" >> "$storage_manifest"
    fi
    return
  fi
  parent="$(dirname -- "$live")"
  test -d "$parent"
  test ! -L "$parent"
  printf '%s\t0\t-\t-\t-\t-\t-\t%s\t%s\t%s\t1\n' "$logical" "$mode" "$operator_user" "$operator_group" >> "$storage_manifest"
  run_privileged install -d -m "$mode" -o "$operator_user" -g "$operator_group" "$live"
}

prepare_directory /var/lib/substation/downloads 0750
prepare_directory /var/lib/substation/downloads/node 0750
prepare_directory /var/lib/substation/models 0750
prepare_directory /var/lib/substation/models/base 0750

if test -s "$evidence_dir/resource-downloads.tsv"; then
  SUBSTATION_RESOURCE_TEST_ROOT="$test_root" bash scripts/verify_phase1_resources.sh --evidence-dir "$evidence_dir"
fi

manifest_work="$(mktemp --tmpdir=/tmp)"
printf 'resource_id\trevision\tsha256\tsize_bytes\tsource_url\tserver_path\n' > "$manifest_work"

archive_work=
sums_work=
weight_work=
stage_root=
cleanup() {
  local path
  for path in "$manifest_work" "$archive_work" "$sums_work" "$weight_work"; do
    test -z "$path" || test ! -e "$path" || unlink -- "$path"
  done
  if test -n "$stage_root" && test -e "$stage_root"; then
    case "$stage_root" in
      /var/lib/substation/downloads/node/.*.staging-*|/var/lib/substation/models/base/.*.staging-*|/tmp/phase1-resource-fixture-*/root/var/lib/substation/downloads/node/.*.staging-*|/tmp/phase1-resource-fixture-*/root/var/lib/substation/models/base/.*.staging-*|/tmp/phase1-resource-fixture-*/foreign-root/var/lib/substation/models/base/.*.staging-*) find "$stage_root" -depth -delete ;;
      *) printf 'refusing-resource-stage-cleanup: %s\n' "$stage_root" >&2; return 1 ;;
    esac
  fi
}
trap cleanup EXIT

download_node() {
  local node_dir_logical=/var/lib/substation/downloads/node/24.18.0
  local node_parent archive marker source_url prior
  local node_dir
  local archive=node-v24.18.0-linux-x64.tar.xz
  local archive_path sums_path
  local expected actual size operation_id
  source_url="https://nodejs.org/dist/v24.18.0/$archive"
  node_dir="$(resource_path "$node_dir_logical")"
  node_parent="$(dirname -- "$node_dir")"
  archive_path="$node_dir/$archive"
  sums_path="$node_dir/SHASUMS256.txt"
  marker="$node_dir/.substation-resource.json"
  prior="$(awk -F '\t' '$1 == "node-linux-x64" {print; exit}' "$evidence_dir/resource-downloads.tsv" 2>/dev/null || true)"
  if test -n "$prior"; then
    IFS=$'\t' read -r _ prior_revision prior_sha prior_size prior_url prior_path <<<"$prior"
    test "$prior_revision" = 24.18.0
    test "$prior_url" = "$source_url"
    test "$prior_path" = "$node_dir_logical/$archive"
    printf '%s\n' "$prior" >> "$manifest_work"
    return
  fi
  if test -e "$node_dir"; then
    printf 'resource target exists without locked manifest: %s\n' "$node_dir_logical" >&2
    return 1
  fi
  operation_id="$(python3 -c 'import uuid; print(uuid.uuid4())')"
  stage_root="$node_parent/.24.18.0.staging-$operation_id"
  test ! -e "$stage_root"
  run_privileged install -d -m 0750 -o "$operator_user" -g "$operator_group" "$stage_root"
  archive_work="$(mktemp --tmpdir=/tmp)"
  sums_work="$(mktemp --tmpdir=/tmp)"
  curl -fL --retry 3 --retry-delay 2 "$source_url" -o "$archive_work"
    curl -fL --retry 3 --retry-delay 2 https://nodejs.org/dist/v24.18.0/SHASUMS256.txt -o "$sums_work"
    expected="$(awk -v file="$archive" '$2 == file {print $1}' "$sums_work")"
    test "$expected" != ""
    actual="$(environment_sha256 "$archive_work")"
    test "$actual" = "$expected"
  install -m 0640 "$archive_work" "$stage_root/$archive"
  install -m 0640 "$sums_work" "$stage_root/SHASUMS256.txt"
  python3 - "$stage_root/.substation-resource.json" "$actual" "$(stat -c '%s' "$archive_work")" "$source_url" <<'PY'
import json
import sys
from pathlib import Path

path, digest, size, url = sys.argv[1:]
Path(path).write_text(json.dumps({"schema_version": 1, "owner": "phase1-resource", "resource_id": "node-linux-x64", "revision": "24.18.0", "sha256": digest, "size_bytes": int(size), "source_url": url}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
    unlink -- "$archive_work"
    unlink -- "$sums_work"
  archive_work=
  sums_work=
  test ! -e "$node_dir"
  run_privileged mv -- "$stage_root" "$node_dir"
  stage_root=
  expected="$(awk -v file="$archive" '$2 == file {print $1}' "$sums_path")"
  actual="$(environment_sha256 "$archive_path")"
  test "$actual" = "$expected"
  size="$(stat -c '%s' "$archive_path")"
  printf 'node-linux-x64\t24.18.0\t%s\t%s\thttps://nodejs.org/dist/v24.18.0/%s\t%s\n' \
    "$actual" "$size" "$archive" "$node_dir_logical/$archive" >> "$manifest_work"
}

download_yolo() {
  local source_url=https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt
  local prior weight_sha weight_dir_logical weight_dir weight_path size operation_id marker
  prior="$(awk -F '\t' '$1 == "yolo11n-base" {print; exit}' "$evidence_dir/resource-downloads.tsv" 2>/dev/null || true)"
  if test -n "$prior"; then
    IFS=$'\t' read -r _ prior_revision prior_sha prior_size prior_url prior_path <<<"$prior"
    test "$prior_revision" = v8.4.0
    test "$prior_url" = "$source_url"
    test "$prior_path" = "/var/lib/substation/models/base/$prior_sha/yolo11n.pt"
    printf '%s\n' "$prior" >> "$manifest_work"
    return
  fi
  weight_work="$(mktemp --tmpdir=/tmp)"
  curl -fL --retry 3 --retry-delay 2 "$source_url" -o "$weight_work"
  weight_sha="$(environment_sha256 "$weight_work")"
  weight_dir_logical="/var/lib/substation/models/base/$weight_sha"
  weight_dir="$(resource_path "$weight_dir_logical")"
  weight_path="$weight_dir/yolo11n.pt"
  marker="$weight_dir/.substation-resource.json"
  if test -e "$weight_dir"; then
    test -d "$weight_dir"
    test -s "$marker"
    test -s "$weight_dir/source.json"
    test -f "$weight_path"
    test "$(environment_sha256 "$weight_path")" = "$weight_sha"
    python3 - "$marker" "$weight_dir/source.json" "$weight_sha" "$(stat -c '%s' "$weight_path")" "$source_url" <<'PY'
import json
import sys
from pathlib import Path

marker_path, source_path, digest, size, url = sys.argv[1:]
leaf = Path(marker_path).parent
children = list(leaf.iterdir())
assert {path.name for path in children} == {
    ".substation-resource.json", "source.json", "yolo11n.pt"
}
assert all(path.is_file() and not path.is_symlink() for path in children)
for path in (marker_path, source_path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    assert data["resource_id"] == "yolo11n-base"
    assert data["revision"] == "v8.4.0"
    assert data["sha256"] == digest
    assert data["size_bytes"] == int(size)
    assert data["source_url"] == url
assert json.loads(Path(marker_path).read_text(encoding="utf-8"))["owner"] == "phase1-resource"
PY
  else
    operation_id="$(python3 -c 'import uuid; print(uuid.uuid4())')"
    stage_root="$(resource_path /var/lib/substation/models/base)/.$weight_sha.staging-$operation_id"
    test ! -e "$stage_root"
    run_privileged install -d -m 0750 -o "$operator_user" -g "$operator_group" "$stage_root"
    install -m 0640 "$weight_work" "$stage_root/yolo11n.pt"
    size="$(stat -c '%s' "$weight_work")"
    python3 - "$stage_root/.substation-resource.json" "$stage_root/source.json" "$weight_sha" "$size" "$source_url" <<'PY'
import json
import sys
from pathlib import Path

marker_path, source_path, digest, size, url = sys.argv[1:]
common = {"schema_version": 1, "resource_id": "yolo11n-base", "revision": "v8.4.0", "sha256": digest, "size_bytes": int(size), "source_url": url}
Path(marker_path).write_text(json.dumps(common | {"owner": "phase1-resource"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
Path(source_path).write_text(json.dumps(common, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
    test ! -e "$weight_dir"
    run_privileged mv -- "$stage_root" "$weight_dir"
    stage_root=
  fi
  unlink -- "$weight_work"
  weight_work=
  size="$(stat -c '%s' "$weight_path")"
  printf 'yolo11n-base\tv8.4.0\t%s\t%s\t%s\t%s\n' \
    "$weight_sha" "$size" "$source_url" "$weight_dir_logical/yolo11n.pt" >> "$manifest_work"
}

if test "$selection" = node-linux-x64 || test "$selection" = all; then
  download_node
fi
if test "$selection" = yolo11n-base || test "$selection" = all; then
  download_yolo
fi

python3 - "$manifest_work" "$evidence_dir/resource-downloads.tsv" <<'PY'
import csv
import os
import sys
from pathlib import Path

incoming_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])
fields = ["resource_id", "revision", "sha256", "size_bytes", "source_url", "server_path"]

def read_rows(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames != fields:
            raise SystemExit(f"resource manifest header changed: {reader.fieldnames}")
        rows = list(reader)
    identifiers = [row["resource_id"] for row in rows]
    if len(identifiers) != len(set(identifiers)):
        raise SystemExit("resource manifest contains duplicate resource_id values")
    return rows

existing = {row["resource_id"]: row for row in read_rows(output_path)}
incoming = read_rows(incoming_path)
for row in incoming:
    resource_id = row["resource_id"]
    prior = existing.get(resource_id)
    if prior is not None and prior != row:
        changed = [field for field in fields[1:] if prior[field] != row[field]]
        raise SystemExit(
            f"resource identity changed for {resource_id}: {','.join(changed)}"
        )
    existing[resource_id] = row

new_path = output_path.with_name(output_path.name + ".new")
with new_path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(existing[key] for key in sorted(existing))
os.replace(new_path, output_path)
PY

trap - EXIT
cleanup
printf 'phase1-resources: PASS: %s\n' "$selection"
```

Create `scripts/verify_phase1_resources.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

if test "$#" -ne 2 || test "$1" != --evidence-dir; then
  printf '%s\n' 'usage: bash scripts/verify_phase1_resources.sh --evidence-dir DIR' >&2
  exit 2
fi
evidence_dir="$2"
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
source scripts/lib/environment_common.sh
test_root="${SUBSTATION_RESOURCE_TEST_ROOT:-}"
if test -n "$test_root"; then
  case "$test_root" in /tmp/phase1-resource-fixture-*) ;; *) exit 2 ;; esac
  case "$evidence_dir" in /tmp/phase1-resource-fixture-*/01-environment.staging) ;; *) exit 2 ;; esac
else
  environment_require_evidence_dir "$evidence_dir"
fi
manifest="$evidence_dir/resource-downloads.tsv"
test -s "$manifest"

python3 - "$manifest" config/environment/resource-sources.tsv "${test_root:-/}" <<'PY'
import csv
import hashlib
import json
import sys
from pathlib import Path

manifest_path, sources_path, root = map(Path, sys.argv[1:])
fields = ["resource_id", "revision", "sha256", "size_bytes", "source_url", "server_path"]
with manifest_path.open(encoding="utf-8", newline="") as handle:
    reader = csv.DictReader(handle, delimiter="\t")
    assert reader.fieldnames == fields
    rows = list(reader)
identifiers = [row["resource_id"] for row in rows]
assert identifiers == sorted(set(identifiers))
assert set(identifiers) <= {"node-linux-x64", "yolo11n-base"}
assert identifiers

with sources_path.open(encoding="utf-8", newline="") as handle:
    source_rows = {row["resource_id"]: row for row in csv.DictReader(handle, delimiter="\t")}

for row in rows:
    logical = Path(row["server_path"])
    assert logical.is_absolute()
    live = logical if root == Path("/") else root / logical.relative_to("/")
    assert live.is_file()
    expected_names = (
        {".substation-resource.json", "SHASUMS256.txt", live.name}
        if row["resource_id"] == "node-linux-x64"
        else {".substation-resource.json", "source.json", "yolo11n.pt"}
    )
    children = list(live.parent.iterdir())
    assert {path.name for path in children} == expected_names
    assert all(path.is_file() and not path.is_symlink() for path in children)
    payload = live.read_bytes()
    assert len(payload) == int(row["size_bytes"])
    assert hashlib.sha256(payload).hexdigest() == row["sha256"]
    marker_path = live.parent / ".substation-resource.json"
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    assert marker == {
        "owner": "phase1-resource",
        "resource_id": row["resource_id"],
        "revision": row["revision"],
        "schema_version": 1,
        "sha256": row["sha256"],
        "size_bytes": int(row["size_bytes"]),
        "source_url": row["source_url"],
    }
    source = source_rows[row["resource_id"]]
    expected_revision = "24.18.0" if row["resource_id"] == "node-linux-x64" else "v8.4.0"
    assert row["revision"] == expected_revision
    assert row["source_url"] == source["source_url"]
    if row["resource_id"] == "node-linux-x64":
        assert logical == Path("/var/lib/substation/downloads/node/24.18.0/node-v24.18.0-linux-x64.tar.xz")
        sums = live.parent / "SHASUMS256.txt"
        expected = [line.split()[0] for line in sums.read_text(encoding="utf-8").splitlines() if line.split()[1] == live.name]
        assert expected == [row["sha256"]]
    else:
        assert logical == Path(f"/var/lib/substation/models/base/{row['sha256']}/yolo11n.pt")
        source_metadata = json.loads((live.parent / "source.json").read_text(encoding="utf-8"))
        assert source_metadata == {key: value for key, value in marker.items() if key != "owner"}
PY

printf '%s\n' 'verify-phase1-resources: PASS'
```

- [ ] **Step 4: Run the static test, then begin the approved downloads**

```bash
chmod +x scripts/download_phase1_resources.sh scripts/verify_phase1_resources.sh tests/environment/test_phase1_resources.sh
bash tests/environment/test_phase1_resources.sh
source .phase1-run.env
bash scripts/download_phase1_resources.sh --resource all --evidence-dir "$PHASE1_EVIDENCE_ROOT" \
  2>&1 | tee "$PHASE1_EVIDENCE_ROOT/download-phase1-resources.log"
test "${PIPESTATUS[0]}" -eq 0
manifest_snapshot="$(mktemp --tmpdir=/tmp)"
install -m 0600 "$PHASE1_EVIDENCE_ROOT/resource-downloads.tsv" "$manifest_snapshot"
bash scripts/download_phase1_resources.sh --resource all --evidence-dir "$PHASE1_EVIDENCE_ROOT"
cmp "$manifest_snapshot" "$PHASE1_EVIDENCE_ROOT/resource-downloads.tsv"
unlink -- "$manifest_snapshot"
bash scripts/verify_phase1_resources.sh --evidence-dir "$PHASE1_EVIDENCE_ROOT"
```

Expected: the static test prints `phase1-resource-static-test: PASS`; both live calls print `phase1-resources: PASS: all`; the checksum-only call prints `verify-phase1-resources: PASS`. Exactly two data rows exist; the Node leaf has its archive, official sums, and ownership marker; the YOLO content-addressed leaf has `yolo11n.pt`, `.substation-resource.json`, and `source.json`. The second identical download call performs a preflight checksum verification and leaves the manifest byte-for-byte unchanged. Checksum mismatch or missing locked metadata remains a hard failure and is never repaired by the verifier.

Run the exact post-download validation:

```bash
source .phase1-run.env
python3 - "$PHASE1_EVIDENCE_ROOT/resource-downloads.tsv" <<'PY'
import csv
import hashlib
import sys
from pathlib import Path

rows = list(csv.DictReader(Path(sys.argv[1]).open(encoding="utf-8"), delimiter="\t"))
assert len(rows) == 2
assert {row["resource_id"] for row in rows} == {"node-linux-x64", "yolo11n-base"}
for row in rows:
    path = Path(row["server_path"])
    assert path.is_file()
    assert path.stat().st_size == int(row["size_bytes"])
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == row["sha256"]
print("phase1-resource-manifest: PASS")
PY
```

Expected: exactly `phase1-resource-manifest: PASS`.

Evidence: `resource-downloads.tsv` and `download-phase1-resources.log` in the active environment evidence directory.

Safe rollback: keep the manifest and logs. A downloaded payload may be quarantined only by moving its exact recorded `server_path` to the same parent with suffix `.quarantine-$PHASE1_RUN_ID`; do not delete it and do not alter another revision directory. Revert only the Task 4 Git commit.

- [ ] **Step 5: Commit Task 4**

```bash
git add config/environment/resource-sources.tsv scripts/download_phase1_resources.sh scripts/verify_phase1_resources.sh tests/environment/test_phase1_resources.sh
git diff --cached --check
git commit -m "feat: lock phase one resource acquisition"
```

Expected: no `.pt`, tarball, dataset, or runtime manifest under `/var/lib/substation` is staged.

---

### Task 5: ROS 2 Workspace Baseline

**Files:**
- Create: `ros2_ws/src/.gitkeep`
- Create: `scripts/setup_ros_workspace.sh`
- Create: `tests/environment/test_ros_workspace.sh`

**Interfaces:**
- Consumes: `/opt/ros/jazzy/setup.bash`, `rosdep`, `colcon`, and an intentionally empty `ros2_ws/src`.
- Produces: canonical `colcon build`, `colcon test`, and `colcon test-result` logs without inventing a non-plan ROS package.

- [ ] **Step 1: Write the failing ROS workspace test**

Create `tests/environment/test_ros_workspace.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

test -f ros2_ws/src/.gitkeep
test -x scripts/setup_ros_workspace.sh
source /opt/ros/jazzy/setup.bash
test "$ROS_DISTRO" = jazzy
test "$(find ros2_ws/src -mindepth 1 -maxdepth 1 ! -name .gitkeep | wc -l)" -eq 0
```

Run:

```bash
chmod +x tests/environment/test_ros_workspace.sh
bash tests/environment/test_ros_workspace.sh
```

Expected: exit nonzero because the workspace marker and setup script do not exist.

- [ ] **Step 2: Create the source root and canonical build script**

Create the empty file `ros2_ws/src/.gitkeep` and create `scripts/setup_ros_workspace.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

if test "$#" -ne 2 || test "$1" != --evidence-dir; then
  printf '%s\n' 'usage: bash scripts/setup_ros_workspace.sh --evidence-dir /var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment.staging' >&2
  exit 2
fi

evidence_dir="$2"
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
source scripts/lib/environment_common.sh
environment_require_evidence_dir "$evidence_dir"
source /opt/ros/jazzy/setup.bash
test "$ROS_DISTRO" = jazzy
test -d ros2_ws/src

rosdep check --from-paths ros2_ws/src --ignore-src --rosdistro jazzy \
  2>&1 | tee "$evidence_dir/rosdep-check.log"
test "${PIPESTATUS[0]}" -eq 0

colcon --log-base log build \
  --base-paths ros2_ws/src \
  --build-base build \
  --install-base install \
  --event-handlers console_direct+ \
  2>&1 | tee "$evidence_dir/colcon-build.log"
test "${PIPESTATUS[0]}" -eq 0

colcon --log-base log test \
  --base-paths ros2_ws/src \
  --build-base build \
  --install-base install \
  --event-handlers console_direct+ \
  --return-code-on-test-failure \
  2>&1 | tee "$evidence_dir/colcon-test.log"
test "${PIPESTATUS[0]}" -eq 0

colcon test-result --test-result-base build --all --verbose \
  2>&1 | tee "$evidence_dir/colcon-test-result.log"
test "${PIPESTATUS[0]}" -eq 0

printf '%s\n' 'ros-workspace: PASS'
```

- [ ] **Step 3: Run the test and baseline build**

```bash
chmod +x scripts/setup_ros_workspace.sh tests/environment/test_ros_workspace.sh
bash tests/environment/test_ros_workspace.sh
source .phase1-run.env
bash scripts/setup_ros_workspace.sh --evidence-dir "$PHASE1_EVIDENCE_ROOT" \
  2>&1 | tee "$PHASE1_EVIDENCE_ROOT/setup-ros-workspace.log"
test "${PIPESTATUS[0]}" -eq 0
```

Expected: final line `ros-workspace: PASS`; all three colcon commands exit 0; `colcon-test-result.log` reports no failed tests. A zero-package summary is correct for this phase and prevents environment verification from being confused with Phase 2 package implementation.

Evidence: `rosdep-check.log`, `colcon-build.log`, `colcon-test.log`, `colcon-test-result.log`, and `setup-ros-workspace.log`.

Safe rollback: keep evidence; move the exact generated `build`, `install`, and `log` directories to `build.quarantine-$PHASE1_RUN_ID`, `install.quarantine-$PHASE1_RUN_ID`, and `log.quarantine-$PHASE1_RUN_ID` if diagnosis requires a clean rerun; revert only the Task 5 commit.

- [ ] **Step 4: Commit Task 5**

```bash
git add ros2_ws/src/.gitkeep scripts/setup_ros_workspace.sh tests/environment/test_ros_workspace.sh
git diff --cached --check
git commit -m "feat: add ros workspace baseline"
```

Expected: generated `build`, `install`, and `log` directories remain ignored and unstaged.

---

### Task 6: CUDA-Enabled AI Virtual Environment

**Files:**
- Create: `requirements.in`
- Create: `requirements.lock`
- Create: `scripts/compile_requirements.sh`
- Create: `scripts/lib/venv_provenance.py`
- Create: `scripts/setup_python_env.sh`
- Create: `tests/environment/test_ai_environment.sh`

**Interfaces:**
- Consumes: Python 3.12, ROS Jazzy system packages, NVIDIA driver `>=560.35.05`, PyPI, the PyTorch CUDA 12.6 wheel index, and the hashed lock.
- Produces: `.venv`, exact import/version/CUDA proof, and `$PHASE1_EVIDENCE_ROOT/ai-pip-freeze.txt`.

- [ ] **Step 1: Write the failing AI environment test**

Create `tests/environment/test_ai_environment.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

test -x scripts/setup_python_env.sh
test -s requirements.lock
grep -q -- '--hash=sha256:' requirements.lock
source /opt/ros/jazzy/setup.bash
.venv/bin/python - <<'PY'
import cv2
import numpy
import rclpy
import torch
import torchvision
import ultralytics

assert torch.__version__.split("+")[0] == "2.12.1"
assert torchvision.__version__.split("+")[0] == "0.27.1"
assert ultralytics.__version__ == "8.4.104"
assert numpy.__version__ == "1.26.4"
assert cv2.__version__ == "4.11.0"
assert torch.cuda.is_available()
assert torch.version.cuda == "12.6"
print("ai-environment: PASS")
PY
python3 scripts/lib/venv_provenance.py verify --kind ai --venv .venv --lock requirements.lock

fixture_root="/tmp/phase1-venv-fixture-$(python3 -c 'import uuid; print(uuid.uuid4())')"
case "$fixture_root" in /tmp/phase1-venv-fixture-*) ;; *) exit 1 ;; esac
install -d -m 0700 "$fixture_root/foreign/bin"
printf '%s\n' 'include-system-site-packages = true' > "$fixture_root/foreign/pyvenv.cfg"
ln -s "$(command -v python3)" "$fixture_root/foreign/bin/python"
set +e
python3 scripts/lib/venv_provenance.py verify --kind ai --venv "$fixture_root/foreign" --lock requirements.lock
foreign_rc=$?
set -e
test "$foreign_rc" -ne 0
case "$fixture_root" in /tmp/phase1-venv-fixture-*) find "$fixture_root" -depth -delete ;; *) exit 1 ;; esac
```

Run:

```bash
chmod +x tests/environment/test_ai_environment.sh
bash tests/environment/test_ai_environment.sh
```

Expected: exit nonzero because the lock, provenance helper, setup script, and `.venv` do not exist. After implementation it also proves that a Python-looking directory without the task-owned marker is rejected without mutation.

- [ ] **Step 2: Add exact direct AI requirements**

Create `requirements.in` with this exact content:

```text
--extra-index-url https://download.pytorch.org/whl/cu126

numpy==1.26.4
opencv-python==4.11.0.86
torch==2.12.1
torchvision==0.27.1
ultralytics==8.4.104
```

- [ ] **Step 3: Implement the reusable hash-lock compiler**

Create `scripts/compile_requirements.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

if test "$#" -ne 2 || test "$1" != --profile; then
  printf '%s\n' 'usage: bash scripts/compile_requirements.sh --profile ai|gateway' >&2
  exit 2
fi

case "$2" in
  ai) input=requirements.in; output=requirements.lock ;;
  gateway) input=requirements-web.in; output=requirements-web.lock ;;
  *) printf 'unknown-profile: %s\n' "$2" >&2; exit 2 ;;
esac

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
test -s "$input"

resolver_dir="$(mktemp -d --tmpdir=/tmp)"
cleanup() {
  if test -d "$resolver_dir"; then
    python3 - "$resolver_dir" <<'PY'
import shutil
import sys
shutil.rmtree(sys.argv[1])
PY
  fi
}
trap cleanup EXIT

python3 -m venv "$resolver_dir"
"$resolver_dir/bin/python" -m pip install --disable-pip-version-check pip-tools==7.4.1
"$resolver_dir/bin/pip-compile" \
  --resolver=backtracking \
  --generate-hashes \
  --strip-extras \
  --index-url https://pypi.org/simple \
  --output-file "$output" \
  "$input"
grep -q -- '--hash=sha256:' "$output"
printf 'requirements-lock: PASS: %s\n' "$output"
```

Run:

```bash
chmod +x scripts/compile_requirements.sh
bash scripts/compile_requirements.sh --profile ai
```

Expected: final line `requirements-lock: PASS: requirements.lock`; every resolved distribution entry has one or more SHA-256 hashes; direct versions remain exact.

- [ ] **Step 4: Implement task-owned virtual-environment provenance**

Create `scripts/lib/venv_provenance.py` with this exact content:

```python
#!/usr/bin/env python3
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected(kind: str, venv: Path, lock: Path) -> dict:
    cfg = venv / "pyvenv.cfg"
    python = venv / "bin/python"
    if not cfg.is_file() or not python.is_file():
        raise SystemExit(f"not a complete virtual environment: {venv}")
    values = {}
    for line in cfg.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    if values.get("include-system-site-packages") != "true":
        raise SystemExit(f"system-site-packages is not enabled: {venv}")
    version = subprocess.run(
        [str(python), "-c", "import platform; print(platform.python_version())"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    if not version.startswith("3.12."):
        raise SystemExit(f"unexpected Python version: {version}")
    return {
        "schema_version": 1,
        "owner": "phase1-environment",
        "kind": kind,
        "python_version": version,
        "system_site_packages": True,
        "lock_path": lock.name,
        "lock_sha256": sha256(lock),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "verify"))
    parser.add_argument("--kind", choices=("ai", "gateway"), required=True)
    parser.add_argument("--venv", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    args = parser.parse_args()
    marker = args.venv / ".substation-environment.json"
    document = expected(args.kind, args.venv, args.lock)
    if args.action == "write":
        if marker.exists():
            raise SystemExit(f"refusing to overwrite provenance marker: {marker}")
        marker.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        if not marker.is_file():
            raise SystemExit(f"foreign virtual environment without provenance: {args.venv}")
        actual = json.loads(marker.read_text(encoding="utf-8"))
        if actual != document:
            raise SystemExit(f"virtual environment provenance mismatch: {args.venv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Implement create-once AI environment setup**

Create `scripts/setup_python_env.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

if test "$#" -ne 2 || test "$1" != --evidence-dir; then
  printf '%s\n' 'usage: bash scripts/setup_python_env.sh --evidence-dir /var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment.staging' >&2
  exit 2
fi

evidence_dir="$2"
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
source scripts/lib/environment_common.sh
environment_require_evidence_dir "$evidence_dir"
source /opt/ros/jazzy/setup.bash
test "$ROS_DISTRO" = jazzy
python3 -c 'import sys; assert sys.version_info[:2] == (3, 12)'
test -s requirements.lock

stage=".venv.staging-$(python3 -c 'import uuid; print(uuid.uuid4())')"
cleanup() {
  if test -e "$stage"; then
    case "$stage" in .venv.staging-*) find "$stage" -depth -delete ;; *) return 1 ;; esac
  fi
}
trap cleanup EXIT
if test -e .venv; then
  test -d .venv
  test ! -L .venv
  python3 scripts/lib/venv_provenance.py verify --kind ai --venv .venv --lock requirements.lock
else
  test ! -e "$stage"
  python3 -m venv --system-site-packages "$stage"
  grep -Fxq 'include-system-site-packages = true' "$stage/pyvenv.cfg"
  "$stage/bin/python" -m pip install --disable-pip-version-check --require-hashes -r requirements.lock
  "$stage/bin/python" - <<'PY'
import cv2
import numpy
import rclpy
import torch
import torchvision
import ultralytics

assert torch.__version__.split("+")[0] == "2.12.1"
assert torchvision.__version__.split("+")[0] == "0.27.1"
assert ultralytics.__version__ == "8.4.104"
assert numpy.__version__ == "1.26.4"
assert cv2.__version__ == "4.11.0"
assert torch.cuda.is_available()
assert torch.version.cuda == "12.6"
PY
  python3 scripts/lib/venv_provenance.py write --kind ai --venv "$stage" --lock requirements.lock
  mv -- "$stage" .venv
fi

.venv/bin/python - <<'PY'
import cv2
import numpy
import rclpy
import torch
import torchvision
import ultralytics

assert torch.__version__.split("+")[0] == "2.12.1"
assert torchvision.__version__.split("+")[0] == "0.27.1"
assert ultralytics.__version__ == "8.4.104"
assert numpy.__version__ == "1.26.4"
assert cv2.__version__ == "4.11.0"
assert torch.cuda.is_available()
assert torch.version.cuda == "12.6"
print(torch.__version__, torch.version.cuda, torch.cuda.get_device_name(0))
PY

.venv/bin/python -m pip freeze --all | LC_ALL=C sort > "$evidence_dir/ai-pip-freeze.txt"
python3 scripts/lib/venv_provenance.py verify --kind ai --venv .venv --lock requirements.lock
trap - EXIT
cleanup
printf '%s\n' 'setup-python-env: PASS'
```

- [ ] **Step 6: Validate the lock, create `.venv`, and run the test**

```bash
python3 - <<'PY'
from pathlib import Path
for line in Path("requirements.lock").read_text(encoding="utf-8").splitlines():
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith("--") or stripped.startswith(" ") or stripped.startswith("\\"):
        continue
    assert "==" in stripped, stripped
    assert ">=" not in stripped and "~=" not in stripped and "*" not in stripped, stripped
print("ai-lock-shape: PASS")
PY
source .phase1-run.env
bash scripts/setup_python_env.sh --evidence-dir "$PHASE1_EVIDENCE_ROOT" \
  2>&1 | tee "$PHASE1_EVIDENCE_ROOT/setup-python-env.log"
test "${PIPESTATUS[0]}" -eq 0
bash tests/environment/test_ai_environment.sh
```

Expected: `ai-lock-shape: PASS`, `setup-python-env: PASS`, and `ai-environment: PASS`; CUDA reports version `12.6` and the installed NVIDIA GPU.

Evidence: `setup-python-env.log` and `ai-pip-freeze.txt`.

Safe rollback: keep evidence and lock files; move exactly `.venv` to `.venv.quarantine-$(date -u +%Y%m%dT%H%M%SZ)`; never uninstall system Python or ROS packages and never run a global pip command. Revert only Task 6's tracked commit.

- [ ] **Step 7: Commit Task 6**

```bash
git add requirements.in requirements.lock scripts/compile_requirements.sh scripts/lib/venv_provenance.py scripts/setup_python_env.sh tests/environment/test_ai_environment.sh
git diff --cached --check
git commit -m "feat: add locked cuda ai environment"
```

Expected: `.venv` is ignored; the generated lock is reviewed and committed.

---

### Task 7: FastAPI ROS Gateway Virtual Environment

**Files:**
- Create: `requirements-web.in`
- Create: `requirements-web.lock`
- Create: `scripts/setup_gateway_env.sh`
- Create: `tests/environment/test_gateway_environment.sh`

**Interfaces:**
- Consumes: Python 3.12, ROS Jazzy `rclpy`, PyPI, `scripts/compile_requirements.sh`, and the hashed Gateway lock.
- Produces: a create-once `.venv-web` with task-owned provenance bound to the exact Gateway lock, exact import/version proof, and `$PHASE1_EVIDENCE_ROOT/gateway-pip-freeze.txt`. A foreign or mismatched existing environment fails before pip mutation.

- [ ] **Step 1: Write the failing Gateway environment test**

Create `tests/environment/test_gateway_environment.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

test -x scripts/setup_gateway_env.sh
test -s requirements-web.lock
grep -q -- '--hash=sha256:' requirements-web.lock
source /opt/ros/jazzy/setup.bash
.venv-web/bin/python - <<'PY'
import fastapi
import pydantic
import rclpy
import uvicorn
import websockets

assert fastapi.__version__ == "0.139.2"
assert uvicorn.__version__ == "0.51.0"
assert pydantic.__version__ == "2.13.4"
assert websockets.__version__ == "16.1.1"
print("gateway-environment: PASS")
PY
python3 scripts/lib/venv_provenance.py verify --kind gateway --venv .venv-web --lock requirements-web.lock
```

Run:

```bash
chmod +x tests/environment/test_gateway_environment.sh
bash tests/environment/test_gateway_environment.sh
```

Expected: exit nonzero because the Gateway lock, setup script, and `.venv-web` do not exist.

- [ ] **Step 2: Add exact direct Gateway requirements and compile the lock**

Create `requirements-web.in` with this exact content:

```text
fastapi==0.139.2
pydantic==2.13.4
uvicorn==0.51.0
websockets==16.1.1
```

Run:

```bash
bash scripts/compile_requirements.sh --profile gateway
```

Expected: final line `requirements-lock: PASS: requirements-web.lock` and fully hashed transitive dependencies.

- [ ] **Step 3: Implement idempotent Gateway environment setup**

Create `scripts/setup_gateway_env.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

if test "$#" -ne 2 || test "$1" != --evidence-dir; then
  printf '%s\n' 'usage: bash scripts/setup_gateway_env.sh --evidence-dir /var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment.staging' >&2
  exit 2
fi

evidence_dir="$2"
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
source scripts/lib/environment_common.sh
environment_require_evidence_dir "$evidence_dir"
source /opt/ros/jazzy/setup.bash
test "$ROS_DISTRO" = jazzy
python3 -c 'import sys; assert sys.version_info[:2] == (3, 12)'
test -s requirements-web.lock

stage=".venv-web.staging-$(python3 -c 'import uuid; print(uuid.uuid4())')"
cleanup() {
  if test -e "$stage"; then
    case "$stage" in .venv-web.staging-*) find "$stage" -depth -delete ;; *) return 1 ;; esac
  fi
}
trap cleanup EXIT
if test -e .venv-web; then
  test -d .venv-web
  test ! -L .venv-web
  python3 scripts/lib/venv_provenance.py verify --kind gateway --venv .venv-web --lock requirements-web.lock
else
  test ! -e "$stage"
  python3 -m venv --system-site-packages "$stage"
  grep -Fxq 'include-system-site-packages = true' "$stage/pyvenv.cfg"
  "$stage/bin/python" -m pip install --disable-pip-version-check --require-hashes -r requirements-web.lock
  "$stage/bin/python" - <<'PY'
import fastapi
import pydantic
import rclpy
import uvicorn
import websockets

assert fastapi.__version__ == "0.139.2"
assert uvicorn.__version__ == "0.51.0"
assert pydantic.__version__ == "2.13.4"
assert websockets.__version__ == "16.1.1"
PY
  python3 scripts/lib/venv_provenance.py write --kind gateway --venv "$stage" --lock requirements-web.lock
  mv -- "$stage" .venv-web
fi

.venv-web/bin/python - <<'PY'
import fastapi
import pydantic
import rclpy
import uvicorn
import websockets

assert fastapi.__version__ == "0.139.2"
assert uvicorn.__version__ == "0.51.0"
assert pydantic.__version__ == "2.13.4"
assert websockets.__version__ == "16.1.1"
print(fastapi.__version__, uvicorn.__version__, pydantic.__version__, websockets.__version__)
PY

.venv-web/bin/python -m pip freeze --all | LC_ALL=C sort > "$evidence_dir/gateway-pip-freeze.txt"
python3 scripts/lib/venv_provenance.py verify --kind gateway --venv .venv-web --lock requirements-web.lock
trap - EXIT
cleanup
printf '%s\n' 'setup-gateway-env: PASS'
```

- [ ] **Step 4: Validate, create `.venv-web`, and run the test**

```bash
python3 - <<'PY'
from pathlib import Path
for line in Path("requirements-web.lock").read_text(encoding="utf-8").splitlines():
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith("--") or stripped.startswith(" ") or stripped.startswith("\\"):
        continue
    assert "==" in stripped, stripped
    assert ">=" not in stripped and "~=" not in stripped and "*" not in stripped, stripped
print("gateway-lock-shape: PASS")
PY
source .phase1-run.env
bash scripts/setup_gateway_env.sh --evidence-dir "$PHASE1_EVIDENCE_ROOT" \
  2>&1 | tee "$PHASE1_EVIDENCE_ROOT/setup-gateway-env.log"
test "${PIPESTATUS[0]}" -eq 0
bash tests/environment/test_gateway_environment.sh
```

Expected: `gateway-lock-shape: PASS`, `setup-gateway-env: PASS`, and `gateway-environment: PASS`; `rclpy` imports from the Jazzy system installation.

Evidence: `setup-gateway-env.log` and `gateway-pip-freeze.txt`.

Safe rollback: keep evidence and lock files; move exactly `.venv-web` to `.venv-web.quarantine-$(date -u +%Y%m%dT%H%M%SZ)`; do not modify `.venv` or system Python. Revert only Task 7's tracked commit.

- [ ] **Step 5: Commit Task 7**

```bash
git add requirements-web.in requirements-web.lock scripts/setup_gateway_env.sh tests/environment/test_gateway_environment.sh
git diff --cached --check
git commit -m "feat: add locked gateway environment"
```

Expected: `.venv-web` is ignored and no Gateway service is started.

---

### Task 8: Node.js 24.18.0 and Next.js Frontend Baseline

**Files:**
- Create: `scripts/write_frontend_manifest.py`
- Create: `scripts/setup_web_env.sh`
- Create: `web/frontend/package.json`
- Create: `web/frontend/package-lock.json`
- Create: `web/frontend/next.config.mjs`
- Create: `web/frontend/app/layout.js`
- Create: `web/frontend/app/page.js`
- Create: `web/frontend/app/globals.css`
- Create: `tests/environment/test_web_environment.sh`

**Interfaces:**
- Consumes: the verified Node tarball recorded in `$PHASE1_EVIDENCE_ROOT/resource-downloads.tsv`, npm registry packages, and exact frontend versions in `docs/VERSION_MATRIX.md`.
- Produces: `/opt/substation/toolchains/node-v24.18.0`, command symlinks, an exact `packageManager` field derived from that toolchain, lockfile v3, `node_modules`, a successful production build, and Node/frontend evidence.

- [ ] **Step 1: Write the failing Web environment test**

Create `tests/environment/test_web_environment.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

test -x scripts/setup_web_env.sh
node --version | grep -Fx v24.18.0
npm_spec="$(node -p 'require("./web/frontend/package.json").packageManager')"
[[ "$npm_spec" =~ ^npm@[0-9]+\.[0-9]+\.[0-9]+$ ]]
test "$(npm --prefix web/frontend --version)" = "${npm_spec#npm@}"
test "$(node -p 'require("./web/frontend/package-lock.json").lockfileVersion')" = 3
npm --prefix web/frontend ls next --depth=0 | grep -F 'next@16.2.11'
npm --prefix web/frontend ls react react-dom --depth=0 | grep -F 'react@19.2.8'
npm --prefix web/frontend ls react react-dom --depth=0 | grep -F 'react-dom@19.2.8'
npm --prefix web/frontend ls typescript --depth=0 | grep -F 'typescript@6.0.3'
npm --prefix web/frontend ls tailwindcss --depth=0 | grep -F 'tailwindcss@4.3.3'
npm --prefix web/frontend ls three --depth=0 | grep -F 'three@0.185.1'
npm --prefix web/frontend ls @react-three/fiber --depth=0 | grep -F '@react-three/fiber@9.6.1'
npm --prefix web/frontend ls echarts --depth=0 | grep -F 'echarts@6.1.0'
web/frontend/node_modules/.bin/playwright --version | grep -Fx 'Version 1.61.1'
test -L /opt/substation/toolchains/node-current
test "$(readlink -f /opt/substation/toolchains/node-current)" = /opt/substation/toolchains/node-v24.18.0
python3 - /opt/substation/toolchains/node-v24.18.0/.substation-toolchain.json <<'PY'
import json, sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert data["owner"] == "phase1-environment"
assert data["toolchain"] == "node"
assert data["version"] == "24.18.0"
assert len(data["archive_sha256"]) == 64
PY
```

Run:

```bash
chmod +x tests/environment/test_web_environment.sh
bash tests/environment/test_web_environment.sh
```

Expected: exit nonzero because the toolchain, manifest, lock, and setup script do not exist.

- [ ] **Step 2: Add the exact manifest generator**

Create `scripts/write_frontend_manifest.py` with this exact content:

```python
#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--npm-version", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", args.npm_version):
        raise SystemExit("npm version must be an exact semantic version")

    document = {
        "name": "substation-inspection-frontend",
        "version": "0.1.0",
        "private": True,
        "packageManager": f"npm@{args.npm_version}",
        "scripts": {
            "build": "next build",
            "dev": "next dev --hostname 127.0.0.1 --port 3000",
            "start": "next start --hostname 127.0.0.1 --port 3000",
        },
        "dependencies": {
            "@react-three/fiber": "9.6.1",
            "echarts": "6.1.0",
            "next": "16.2.11",
            "react": "19.2.8",
            "react-dom": "19.2.8",
            "three": "0.185.1",
        },
        "devDependencies": {
            "@playwright/test": "1.61.1",
            "tailwindcss": "4.3.3",
            "typescript": "6.0.3",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    work = args.output.with_suffix(args.output.suffix + ".new")
    work.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.output.exists():
        actual = json.loads(args.output.read_text(encoding="utf-8"))
        if actual != document:
            work.unlink()
            raise SystemExit(f"refusing to overwrite changed frontend manifest: {args.output}")
        work.unlink()
    else:
        work.replace(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

The only runtime-derived field is `packageManager`; its value comes from the already verified Node 24.18.0 tarball, never from `latest` or a version range.

- [ ] **Step 3: Add the minimal local-only App Router baseline**

Create `web/frontend/next.config.mjs`:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
};

export default nextConfig;
```

Create `web/frontend/app/layout.js`:

```javascript
import "./globals.css";

export const metadata = {
  title: "Substation Inspection",
  description: "Phase 1 environment baseline",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
```

Create `web/frontend/app/page.js`:

```javascript
export default function HomePage() {
  return (
    <main>
      <h1>Substation Inspection</h1>
      <p>Phase 1 environment baseline</p>
    </main>
  );
}
```

Create `web/frontend/app/globals.css`:

```css
:root {
  color-scheme: dark;
  font-family: system-ui, sans-serif;
  background: #07111f;
  color: #e7eef8;
}

body {
  margin: 0;
}

main {
  max-width: 48rem;
  margin: 0 auto;
  padding: 4rem 2rem;
}
```

This page is a build probe only. It does not invent product routes or bypass the Gateway.

- [ ] **Step 4: Implement the verified toolchain and frontend setup**

Create `scripts/setup_web_env.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

if test "$#" -ne 2 || test "$1" != --evidence-dir; then
  printf '%s\n' 'usage: bash scripts/setup_web_env.sh --evidence-dir /var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment.staging' >&2
  exit 2
fi

evidence_dir="$2"
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
source scripts/lib/environment_common.sh
environment_require_evidence_dir "$evidence_dir"
test -s "$evidence_dir/resource-downloads.tsv"

node_archive="$(awk -F '\t' '$1 == "node-linux-x64" {print $6}' "$evidence_dir/resource-downloads.tsv")"
node_sha="$(awk -F '\t' '$1 == "node-linux-x64" {print $3}' "$evidence_dir/resource-downloads.tsv")"
test -f "$node_archive"
test "$(environment_sha256 "$node_archive")" = "$node_sha"

toolchain_root=/opt/substation/toolchains
node_root="$toolchain_root/node-v24.18.0"
stage_root="$toolchain_root/.node-v24.18.0-${PHASE1_RUN_ID:?}"
marker="$node_root/.substation-toolchain.json"
node_current="$toolchain_root/node-current"
node_current_before="$evidence_dir/node-current-before.tsv"
link_work=
cleanup() {
  if test -n "$link_work" && test -e "$link_work"; then
    case "$link_work" in /opt/substation/toolchains/.node-current-*) sudo unlink -- "$link_work" ;; *) return 1 ;; esac
  fi
  if test -e "$stage_root"; then
    case "$stage_root" in /opt/substation/toolchains/.node-v24.18.0-*) sudo find "$stage_root" -depth -delete ;; *) return 1 ;; esac
  fi
}
trap cleanup EXIT
test -d "$toolchain_root"
test ! -L "$toolchain_root"
test "$(stat -c '%a:%U:%G' "$toolchain_root")" = 755:root:root
if test -e "$node_current" && test ! -L "$node_current"; then
  printf 'refusing-foreign-node-current: %s\n' "$node_current" >&2
  exit 1
fi
if test -e "$node_root"; then
  test -d "$node_root"
  test ! -L "$node_root"
  test -s "$marker"
  python3 - "$marker" "$node_sha" <<'PY'
import json, sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert data == {"archive_sha256": sys.argv[2], "owner": "phase1-environment", "schema_version": 1, "toolchain": "node", "version": "24.18.0"}
PY
else
  test ! -e "$stage_root"
  sudo install -d -m 0755 "$stage_root"
  sudo tar -xJf "$node_archive" -C "$stage_root" --strip-components=1 --no-same-owner --owner=root --group=root
  marker_work="$(mktemp --tmpdir=/tmp)"
  python3 - "$marker_work" "$node_sha" <<'PY'
import json, sys
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps({"archive_sha256": sys.argv[2], "owner": "phase1-environment", "schema_version": 1, "toolchain": "node", "version": "24.18.0"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  sudo install -m 0644 "$marker_work" "$stage_root/.substation-toolchain.json"
  unlink -- "$marker_work"
  sudo mv -- "$stage_root" "$node_root"
fi
"$node_root/bin/node" --version | grep -Fx v24.18.0

for command_name in node npm npx corepack; do
  command_target="$node_root/bin/$command_name"
  command_link="/usr/local/bin/$command_name"
  test -x "$command_target"
  if test -L "$command_link"; then
    test "$(readlink -f "$command_link")" = "$command_target"
  elif test -e "$command_link"; then
    printf 'refusing-to-overwrite-command: %s\n' "$command_link" >&2
    exit 1
  else
    sudo ln -s "$command_target" "$command_link"
  fi
done

if test ! -e "$node_current_before"; then
  if test -L "$node_current"; then
    printf 'path\texisted_before\ttarget_before\n%s\t1\t%s\n' "$node_current" "$(readlink -- "$node_current")" > "$node_current_before"
  elif test -e "$node_current"; then
    printf 'refusing-foreign-node-current: %s\n' "$node_current" >&2
    exit 1
  else
    printf 'path\texisted_before\ttarget_before\n%s\t0\t-\n' "$node_current" > "$node_current_before"
  fi
else
  test -L "$node_current"
  test "$(readlink -f "$node_current")" = "$node_root"
fi
if test ! -L "$node_current" || test "$(readlink -f "$node_current")" != "$node_root"; then
  link_work="$toolchain_root/.node-current-${PHASE1_RUN_ID:?}"
  test ! -e "$link_work"
  sudo ln -s "$node_root" "$link_work"
  sudo mv -Tf -- "$link_work" "$node_current"
  link_work=
fi

npm_version="$(npm --version)"
python3 scripts/write_frontend_manifest.py \
  --npm-version "$npm_version" \
  --output web/frontend/package.json

if test -e web/frontend/package-lock.json; then
  test -f web/frontend/package-lock.json
  test ! -L web/frontend/package-lock.json
else
  npm --prefix web/frontend install --package-lock-only --ignore-scripts
fi
test "$(node -p 'require("./web/frontend/package-lock.json").lockfileVersion')" = 3
npm --prefix web/frontend ci
npm --prefix web/frontend run build \
  2>&1 | tee "$evidence_dir/frontend-build.log"
test "${PIPESTATUS[0]}" -eq 0

{
  node --version
  npm --version
  node -p 'require("./web/frontend/package.json").packageManager'
} > "$evidence_dir/node-npm-versions.txt"
trap - EXIT
cleanup
printf '%s\n' 'setup-web-env: PASS'
```

- [ ] **Step 5: Install, lock, build, and test**

```bash
chmod +x scripts/write_frontend_manifest.py scripts/setup_web_env.sh tests/environment/test_web_environment.sh
source .phase1-run.env
bash scripts/setup_web_env.sh --evidence-dir "$PHASE1_EVIDENCE_ROOT" \
  2>&1 | tee "$PHASE1_EVIDENCE_ROOT/setup-web-env.log"
test "${PIPESTATUS[0]}" -eq 0
bash tests/environment/test_web_environment.sh
npm --prefix web/frontend ci
npm --prefix web/frontend run build
```

Expected: `setup-web-env: PASS`; `node --version` is exactly `v24.18.0`; `packageManager` is one exact npm version equal to `npm --prefix web/frontend --version`; lockfile version is 3; all direct dependency checks pass; the production build exits 0.

Evidence: `setup-web-env.log`, `frontend-build.log`, and `node-npm-versions.txt`.

Safe rollback: preserve evidence and `package-lock.json`. First require `node-current` to be a symlink resolving to `/opt/substation/toolchains/node-v24.18.0`; read `node-current-before.tsv`; if `existed_before=1`, atomically replace it with a temporary symlink using the exact recorded raw target, otherwise unlink only that exact symlink. Refuse a non-symlink at every point. Remove `/usr/local/bin/{node,npm,npx,corepack}` only when each exact path is a symlink whose resolved target is below the owned Node directory. Move `/opt/substation/toolchains/node-v24.18.0` to `/opt/substation/toolchains/node-v24.18.0.quarantine-$PHASE1_RUN_ID` only after `.substation-toolchain.json` exactly matches the archive SHA/version/owner marker. Move `node_modules` and `.next` to sibling quarantine names; revert only Task 8's tracked commit.

- [ ] **Step 6: Commit Task 8**

```bash
git add scripts/write_frontend_manifest.py scripts/setup_web_env.sh web/frontend/package.json web/frontend/package-lock.json web/frontend/next.config.mjs web/frontend/app/layout.js web/frontend/app/page.js web/frontend/app/globals.css tests/environment/test_web_environment.sh
git diff --cached --check
git commit -m "feat: add locked frontend baseline"
```

Expected: `node_modules` and `.next` remain ignored; the commit contains the npm-derived exact `packageManager` and lockfile v3.

---

### Task 9: Gazebo Harmonic OGRE2/EGL Headless Smoke Test

**Files:**
- Create: `tests/environment/fixtures/headless_camera.sdf`
- Create: `scripts/smoke_headless_egl.sh`
- Create: `tests/environment/test_headless_egl.sh`

**Interfaces:**
- Consumes: Gazebo Harmonic, `gz-sim 8.x`, NVIDIA/EGL, and no `DISPLAY` variable.
- Produces: a rendered 64×48 RGB camera message and `$PHASE1_EVIDENCE_ROOT/egl.log` without X11 or a virtual display.

- [ ] **Step 1: Write the failing EGL smoke test**

Create `tests/environment/test_headless_egl.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

test -x scripts/smoke_headless_egl.sh
test -s tests/environment/fixtures/headless_camera.sdf
grep -F '<render_engine>ogre2</render_engine>' tests/environment/fixtures/headless_camera.sdf
grep -F '<topic>/phase1/camera</topic>' tests/environment/fixtures/headless_camera.sdf
! rg -n 'Xvfb|VirtualGL|DISPLAY=|xvfb-run' scripts/smoke_headless_egl.sh tests/environment/fixtures/headless_camera.sdf
```

Run:

```bash
chmod +x tests/environment/test_headless_egl.sh
bash tests/environment/test_headless_egl.sh
```

Expected: exit nonzero because the fixture and smoke script do not exist.

- [ ] **Step 2: Add the exact minimal camera world**

Create `tests/environment/fixtures/headless_camera.sdf` with this exact content:

```xml
<?xml version="1.0" ?>
<sdf version="1.10">
  <world name="phase1_headless">
    <physics name="1ms" type="ignored">
      <max_step_size>0.001</max_step_size>
      <real_time_factor>1.0</real_time_factor>
    </physics>
    <plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-user-commands-system" name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>
    <plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors">
      <render_engine>ogre2</render_engine>
    </plugin>
    <gravity>0 0 -9.8</gravity>
    <scene>
      <ambient>0.4 0.4 0.4 1</ambient>
      <background>0.05 0.05 0.05 1</background>
    </scene>
    <light name="sun" type="directional">
      <cast_shadows>true</cast_shadows>
      <pose>0 0 10 0 0 0</pose>
      <diffuse>0.8 0.8 0.8 1</diffuse>
      <specular>0.2 0.2 0.2 1</specular>
      <direction>-0.5 0.1 -0.9</direction>
    </light>
    <model name="target_box">
      <static>true</static>
      <pose>3 0 0.5 0 0 0</pose>
      <link name="link">
        <visual name="visual">
          <geometry><box><size>1 1 1</size></box></geometry>
          <material><ambient>0.8 0.1 0.1 1</ambient><diffuse>0.8 0.1 0.1 1</diffuse></material>
        </visual>
      </link>
    </model>
    <model name="camera_probe">
      <static>true</static>
      <pose>0 0 1 0 0 0</pose>
      <link name="link">
        <sensor name="rgb_camera" type="camera">
          <always_on>true</always_on>
          <update_rate>2</update_rate>
          <topic>/phase1/camera</topic>
          <camera>
            <horizontal_fov>1.047</horizontal_fov>
            <image>
              <width>64</width>
              <height>48</height>
              <format>R8G8B8</format>
            </image>
            <clip><near>0.1</near><far>20</far></clip>
          </camera>
        </sensor>
      </link>
    </model>
  </world>
</sdf>
```

- [ ] **Step 3: Implement the exact headless probe**

Create `scripts/smoke_headless_egl.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

if test "$#" -ne 2 || test "$1" != --evidence-dir; then
  printf '%s\n' 'usage: bash scripts/smoke_headless_egl.sh --evidence-dir /var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment.staging' >&2
  exit 2
fi

evidence_dir="$2"
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
source scripts/lib/environment_common.sh
environment_require_evidence_dir "$evidence_dir"
world=tests/environment/fixtures/headless_camera.sdf
test -s "$world"

frame_log="$evidence_dir/egl-frame.txt"
topic_log="$evidence_dir/egl-topics.txt"
: > "$evidence_dir/egl.log"
: > "$frame_log"

printf 'DISPLAY-present-before-unset=%s\n' "${DISPLAY+x}" >> "$evidence_dir/egl.log"
printf '%s\n' 'command=env -u DISPLAY gz sim -s -r --headless-rendering tests/environment/fixtures/headless_camera.sdf' >> "$evidence_dir/egl.log"

env -u DISPLAY gz sim -s -r --headless-rendering "$world" >> "$evidence_dir/egl.log" 2>&1 &
gz_pid=$!
cleanup() {
  if kill -0 "$gz_pid" >/dev/null 2>&1; then
    kill "$gz_pid"
    wait "$gz_pid" || true
  fi
}
trap cleanup EXIT

topic_ready=0
for attempt in $(seq 1 30); do
  if ! kill -0 "$gz_pid" >/dev/null 2>&1; then
    printf '%s\n' 'gazebo exited before camera topic became ready' >&2
    exit 1
  fi
  env -u DISPLAY gz topic -l > "$topic_log"
  if grep -Fxq '/phase1/camera' "$topic_log"; then
    topic_ready=1
    break
  fi
  sleep 1
done
test "$topic_ready" -eq 1

set +e
env -u DISPLAY timeout 8s gz topic -e -t /phase1/camera > "$frame_log" 2>> "$evidence_dir/egl.log"
frame_rc=$?
set -e
test "$frame_rc" -eq 0 || test "$frame_rc" -eq 124
grep -Eq '^width: 64$' "$frame_log"
grep -Eq '^height: 48$' "$frame_log"
grep -Eq 'pixel_format_type: RGB_INT8|pixel_format: RGB_INT8|pixel_format_type: 3' "$frame_log"

printf '%s\n' 'camera-topic=/phase1/camera' >> "$evidence_dir/egl.log"
grep -m1 -E '^width:|^height:|pixel_format' "$frame_log" >> "$evidence_dir/egl.log"
printf '%s\n' 'headless-egl: PASS' >> "$evidence_dir/egl.log"

trap - EXIT
cleanup
printf '%s\n' 'headless-egl: PASS'
```

The readiness loop polls once per second with `sleep 1`, aborts immediately if the exact Gazebo PID exits, and cleanup targets only that PID.

- [ ] **Step 4: Run static and live smoke tests**

```bash
chmod +x scripts/smoke_headless_egl.sh tests/environment/test_headless_egl.sh
bash tests/environment/test_headless_egl.sh
source .phase1-run.env
bash scripts/smoke_headless_egl.sh --evidence-dir "$PHASE1_EVIDENCE_ROOT" \
  2>&1 | tee "$PHASE1_EVIDENCE_ROOT/test-headless-egl.log"
test "${PIPESTATUS[0]}" -eq 0
grep -Fx 'headless-egl: PASS' "$PHASE1_EVIDENCE_ROOT/egl.log"
```

Expected: the live command prints `headless-egl: PASS`; `egl.log` records the `env -u DISPLAY` command; the frame evidence contains width 64, height 48, and RGB pixel format; no persistent Gazebo process remains.

Evidence: `egl.log`, `egl-frame.txt`, `egl-topics.txt`, and `test-headless-egl.log`.

Safe rollback: preserve all evidence; if the script is interrupted, read its exact PID from the active shell job and terminate only that process; do not use process-name-wide termination. Revert only Task 9's tracked commit.

- [ ] **Step 5: Commit Task 9**

```bash
git add tests/environment/fixtures/headless_camera.sdf scripts/smoke_headless_egl.sh tests/environment/test_headless_egl.sh
git diff --cached --check
git commit -m "test: add headless gazebo egl smoke probe"
```

Expected: the SDF fixture is small text; no rendered image or Gazebo log is committed.

---

### Task 10: Captured Environment Lock and One-Time Evidence Seal

**Files:**
- Create: `scripts/capture_environment_lock.sh`
- Create: `scripts/verify_environment.sh`
- Create: `scripts/check_environment_seal.sh`
- Create: `tests/environment/test_verify_environment.sh`
- Create: `artifacts/environment/dpkg-packages.tsv`
- Create: `artifacts/environment/ai-pip-freeze.txt`
- Create: `artifacts/environment/gateway-pip-freeze.txt`
- Create: `artifacts/environment/node-npm-versions.txt`
- Create: `artifacts/environment/resource-downloads.tsv`
- Create: `artifacts/environment/SHA256SUMS`

**Interfaces:**
- Consumes: all Task 1–9 scripts, locks, toolchains, downloads, tests, the approved installed host, the existing unsealed `$PHASE1_EVIDENCE_ROOT`, and the absent `$PHASE1_EVIDENCE_FINAL`.
- Produces: the one-shot Phase 1 acceptance entry point `bash scripts/verify_environment.sh --evidence-dir "$PHASE1_EVIDENCE_FINAL"`, a reviewed tracked environment lock, an atomically published immutable `$PHASE1_EVIDENCE_FINAL`, and the read-only sealed-evidence checker `bash scripts/check_environment_seal.sh --evidence-dir "$PHASE1_EVIDENCE_FINAL"`.
- Invariant: the canonical verifier derives the staging sibling by appending `.staging` to its final-target argument. It refuses an existing final target, a missing staging directory, any pre-existing staging `SHA256SUMS`, or any prior `commands/`, `environment.json`, or `result.json`. Before sealing, it strictly parses `install-state.env` as inert six-key data and revalidates the exact requested/changed package-origin evidence. It never downloads, repairs, installs, compiles locks, calls an environment setup script, or runs `npm ci`.

- [ ] **Step 1: Write the failing synthetic seal behavior test**

Create `tests/environment/test_verify_environment.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

test -x scripts/verify_environment.sh
test -x scripts/check_environment_seal.sh
rg -F 'unsafe install-state line' scripts/verify_environment.sh
! rg -n 'source .*install-state|source "\$state_file"' \
  scripts/verify_environment.sh scripts/rollback_host.sh

fixture_root="/tmp/phase1-seal-fixture-$(python3 -c 'import uuid; print(uuid.uuid4())')"
case "$fixture_root" in /tmp/phase1-seal-fixture-*) ;; *) exit 2 ;; esac
test ! -e "$fixture_root"
install -d -m 0750 "$fixture_root/acceptance"
installer_fixture_root="/tmp/phase1-installer-fixture-$(python3 -c 'import uuid; print(uuid.uuid4())')"
case "$installer_fixture_root" in /tmp/phase1-installer-fixture-*) ;; *) exit 2 ;; esac
test ! -e "$installer_fixture_root"
install -d -m 0700 "$installer_fixture_root"

cleanup() {
  case "$fixture_root" in /tmp/phase1-seal-fixture-*) ;; *) return 1 ;; esac
  if test -e "$fixture_root"; then
    find "$fixture_root" -depth -delete
  fi
  if test -e "$installer_fixture_root"; then
    find "$installer_fixture_root" -depth -delete
  fi
}
trap cleanup EXIT

create_staging() {
  local run_id="$1"
  local staging="$fixture_root/acceptance/$run_id/01-environment.staging"
  install -d -m 0750 "$staging"
  printf '%s\n' "$run_id" > "$staging/acceptance_run_id.txt"
  printf '%s\n' "seed=$run_id" > "$staging/fixture-seed.txt"
  printf '%s\n' "$staging"
}

snapshot_tree() {
  local root="$1"
  local output="$2"
  (
    cd "$root"
    find . -printf '%y\t%m\t%p\n' | LC_ALL=C sort
    find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum
  ) > "$output"
}

make_installer_case() {
  local name="$1"
  local case_root="$installer_fixture_root/$name"
  local host_root="$case_root/root"
  local evidence_dir="$case_root/evidence/01-environment.staging"
  local fake_bin="$case_root/bin"
  local logical_path live_path live_mode live_owner live_group
  install -d -m 0700 \
    "$fake_bin" "$evidence_dir" \
    "$host_root/etc/apt/sources.list.d" \
    "$host_root/etc/ros/rosdep/sources.list.d" \
    "$host_root/etc/default" \
    "$host_root/usr/share/keyrings" \
    "$host_root/usr/sbin" \
    "$host_root/opt/ros/jazzy" \
    "$host_root/opt/substation/toolchains" \
    "$host_root/var/lib/dpkg" \
    "$host_root/var/lib/substation/evidence/acceptance/verifier-fixture/01-environment.staging" \
    "$host_root/proc" \
    "$host_root/sys/bus/pci/devices/0000:01:00.0"
  chmod 0755 "$host_root/opt/substation" "$host_root/opt/substation/toolchains"
  chmod 0750 \
    "$host_root/var/lib/substation" \
    "$host_root/var/lib/substation/evidence" \
    "$host_root/var/lib/substation/evidence/acceptance" \
    "$host_root/var/lib/substation/evidence/acceptance/verifier-fixture" \
    "$host_root/var/lib/substation/evidence/acceptance/verifier-fixture/01-environment.staging"
  cat > "$host_root/etc/os-release" <<'EOF'
ID=ubuntu
VERSION_ID="24.04"
PRETTY_NAME="Ubuntu 24.04 LTS"
EOF
  printf '%s\n' 'MemTotal:       33554432 kB' > "$host_root/proc/meminfo"
  printf '%s\n' 0x10de > "$host_root/sys/bus/pci/devices/0000:01:00.0/vendor"
  cat > "$host_root/etc/apt/sources.list" <<'EOF'
deb http://archive.ubuntu.com/ubuntu noble main universe
EOF
  cat > "$host_root/etc/apt/sources.list.d/ubuntu.sources" <<'EOF'
Types: deb
URIs: http://archive.ubuntu.com/ubuntu
Suites: noble-updates noble-security
Components: main universe
EOF
  printf '%s\n' 'ORIGINAL_POLICY' > "$host_root/usr/sbin/policy-rc.d"
  chmod 0755 "$host_root/usr/sbin/policy-rc.d"
  printf '%s\n' 'export ROS_DISTRO=jazzy' > "$host_root/opt/ros/jazzy/setup.bash"
  python3 tests/environment/fixtures/fake_host_command.py init \
    --state "$case_root/state.json" \
    --operations "$case_root/operations.jsonl" \
    --driver-ready 1
  for command_name in sudo apt-get apt-cache dpkg-query systemctl nvidia-smi curl locale-gen update-locale rosdep gz lspci findmnt; do
    ln -s "$repo_root/tests/environment/fixtures/fake_host_command.py" "$fake_bin/$command_name"
  done
  PATH="$fake_bin:$PATH" \
  SUBSTATION_INSTALL_TEST_ROOT="$host_root" \
  SUBSTATION_AUDIT_TEST_ROOT="$host_root" \
  FAKE_HOST_STATE="$case_root/state.json" \
  FAKE_HOST_OPERATIONS="$case_root/operations.jsonl" \
    bash scripts/install_host.sh --apply --evidence-dir "$evidence_dir" >/dev/null
  printf 'path\texisted_before\tmode_before\towner_before\tgroup_before\tdevice\tinode\texpected_mode\texpected_owner\texpected_group\tcreated_by_task\n' \
    > "$evidence_dir/storage-paths-before.tsv"
  for logical_path in \
    /var/lib/substation \
    /var/lib/substation/evidence \
    /var/lib/substation/evidence/acceptance \
    /var/lib/substation/evidence/acceptance/verifier-fixture \
    /var/lib/substation/evidence/acceptance/verifier-fixture/01-environment.staging \
    /opt/substation \
    /opt/substation/toolchains; do
    live_path="$host_root$logical_path"
    live_mode="$(stat -c '%a' "$live_path")"
    live_owner="$(stat -c '%U' "$live_path")"
    live_group="$(stat -c '%G' "$live_path")"
    printf '%s\t1\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t0\n' \
      "$logical_path" "$live_mode" "$live_owner" "$live_group" \
      "$(stat -c '%d' "$live_path")" "$(stat -c '%i' "$live_path")" \
      "$live_mode" "$live_owner" "$live_group" \
      >> "$evidence_dir/storage-paths-before.tsv"
  done
  printf 'path\texisted_before\ttarget_before\n/opt/substation/toolchains/node-current\t0\t-\n' \
    > "$evidence_dir/node-current-before.tsv"
  printf '%s\t%s\t%s\t%s\n' "$case_root" "$host_root" "$evidence_dir" "$fake_bin"
}

assert_failed_installer_evidence_run() {
  local case_root="$1"
  local host_root="$2"
  local evidence_dir="$3"
  local fake_bin="$4"
  local run_id="$5"
  local installer_expectation="$6"
  shift 6
  local staging final before after evidence_before operations_before rc
  staging="$(create_staging "$run_id")"
  final="$fixture_root/acceptance/$run_id/01-environment"
  cp -a "$evidence_dir/." "$staging/"
  evidence_before="$fixture_root/$run_id-evidence-before.sha256"
  (
    cd "$staging"
    find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum
  ) > "$evidence_before"
  before="$fixture_root/$run_id-host-before.tsv"
  after="$fixture_root/$run_id-host-after.tsv"
  snapshot_tree "$host_root" "$before"
  operations_before="$(wc -l < "$case_root/operations.jsonl")"
  set +e
  PATH="$fake_bin:$PATH" \
  SUBSTATION_VERIFY_TEST_ROOT="$fixture_root" \
  SUBSTATION_VERIFY_INSTALLER_EVIDENCE_TEST=1 \
  SUBSTATION_VERIFY_INSTALLER_HOST_ROOT="$host_root" \
  FAKE_HOST_STATE="$case_root/state.json" \
  FAKE_HOST_OPERATIONS="$case_root/operations.jsonl" \
    "$@" bash scripts/verify_environment.sh --evidence-dir "$final" \
    > "$fixture_root/$run_id.log" 2>&1
  rc=$?
  set -e
  test "$rc" -ne 0
  test ! -e "$final"
  test -d "$staging"
  test ! -e "$staging/SHA256SUMS"
  test -s "$staging/result.json"
  python3 - "$staging/result.json" "$installer_expectation" <<'PY'
import json
import sys
from pathlib import Path
result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert result["status"] == "failed"
if sys.argv[2] == "zero":
    assert result["exit_codes"]["installer-evidence"] == 0
else:
    assert sys.argv[2] == "nonzero"
    assert result["exit_codes"]["installer-evidence"] != 0
assert result["exit_codes"]["verify_environment"] != 0
PY
  (
    cd "$staging"
    sha256sum -c "$evidence_before" >/dev/null
  )
  snapshot_tree "$host_root" "$after"
  cmp "$before" "$after"
  python3 - "$case_root/operations.jsonl" "$operations_before" <<'PY'
import json
import sys
operations = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")][int(sys.argv[2]):]
assert all(item["command"] == "apt-cache" and item["argv"][0] == "policy" for item in operations)
PY
}

IFS=$'\t' read -r clean_case clean_root clean_evidence clean_bin < <(make_installer_case verifier-clean-control)
assert_failed_installer_evidence_run "$clean_case" "$clean_root" "$clean_evidence" "$clean_bin" verifier-clean-control zero env

IFS=$'\t' read -r state_case state_root state_evidence state_bin < <(make_installer_case verifier-state-tamper)
printf 'started_at=$(touch %s)\n' "$state_case/source-executed" >> "$state_evidence/install-state.env"
state_hash="$(sha256sum "$state_evidence/install-state.env")"
assert_failed_installer_evidence_run "$state_case" "$state_root" "$state_evidence" "$state_bin" verifier-state-tamper nonzero env
grep -Fq 'unsafe install-state line' "$fixture_root/verifier-state-tamper.log"
test ! -e "$state_case/source-executed"
test "$(sha256sum "$state_evidence/install-state.env")" = "$state_hash"

IFS=$'\t' read -r origin_case origin_root origin_evidence origin_bin < <(make_installer_case verifier-origin-tamper)
origin_hash="$(sha256sum "$origin_evidence/apt-changed-package-origins.tsv")"
assert_failed_installer_evidence_run "$origin_case" "$origin_root" "$origin_evidence" "$origin_bin" verifier-origin-tamper nonzero env FAKE_REQUESTED_ORIGIN_FAILURE=1
grep -Fq 'changed package origin is not allowed: nginx' "$fixture_root/verifier-origin-tamper.log"
test "$(sha256sum "$origin_evidence/apt-changed-package-origins.tsv")" = "$origin_hash"

success_run=seal-success
success_staging="$(create_staging "$success_run")"
success_final="$fixture_root/acceptance/$success_run/01-environment"
SUBSTATION_VERIFY_TEST_ROOT="$fixture_root" \
  bash scripts/verify_environment.sh --evidence-dir "$success_final"
test ! -e "$success_staging"
test -d "$success_final"
test -s "$success_final/SHA256SUMS"
SUBSTATION_VERIFY_TEST_ROOT="$fixture_root" \
  bash scripts/check_environment_seal.sh --evidence-dir "$success_final"

before_snapshot="$fixture_root/success-before.tsv"
after_snapshot="$fixture_root/success-after.tsv"
snapshot_tree "$success_final" "$before_snapshot"
set +e
SUBSTATION_VERIFY_TEST_ROOT="$fixture_root" \
  bash scripts/verify_environment.sh --evidence-dir "$success_final" \
  > "$fixture_root/existing-final-refusal.log" 2>&1
existing_rc=$?
set -e
test "$existing_rc" -ne 0
snapshot_tree "$success_final" "$after_snapshot"
cmp "$before_snapshot" "$after_snapshot"
SUBSTATION_VERIFY_TEST_ROOT="$fixture_root" \
  bash scripts/check_environment_seal.sh --evidence-dir "$success_final"

failure_run=seal-failure
failure_staging="$(create_staging "$failure_run")"
failure_final="$fixture_root/acceptance/$failure_run/01-environment"
set +e
SUBSTATION_VERIFY_TEST_ROOT="$fixture_root" \
SUBSTATION_VERIFY_TEST_FAILURE=23 \
  bash scripts/verify_environment.sh --evidence-dir "$failure_final" \
  > "$fixture_root/failure.log" 2>&1
failure_rc=$?
set -e
test "$failure_rc" -eq 23
test ! -e "$failure_final"
test -d "$failure_staging"
test ! -e "$failure_staging/SHA256SUMS"
test -s "$failure_staging/result.json"
test -s "$failure_staging/commands/fixture-check.json"
python3 - "$failure_staging/result.json" <<'PY'
import json
import sys
from pathlib import Path

result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert result["status"] == "failed"
assert result["failures"]
assert result["exit_codes"] == {"fixture-check": 23, "verify_environment": 23}
assert result["commands"][0]["id"] == "fixture-check"
assert result["commands"][0]["exit_code"] == 23
PY

failed_snapshot="$fixture_root/failure-before-rerun.tsv"
failed_after="$fixture_root/failure-after-rerun.tsv"
snapshot_tree "$failure_staging" "$failed_snapshot"
set +e
SUBSTATION_VERIFY_TEST_ROOT="$fixture_root" \
  bash scripts/verify_environment.sh --evidence-dir "$failure_final" \
  > "$fixture_root/failed-staging-refusal.log" 2>&1
rerun_rc=$?
set -e
test "$rerun_rc" -ne 0
snapshot_tree "$failure_staging" "$failed_after"
cmp "$failed_snapshot" "$failed_after"

printf '%s\n' 'verify-environment-test: PASS'
```

Run:

```bash
chmod +x tests/environment/test_verify_environment.sh
bash tests/environment/test_verify_environment.sh
```

Expected: exit nonzero at the first missing executable. The test itself is limited to a guarded `/tmp/phase1-seal-fixture-*` root and never reads or mutates the live Phase 1 evidence tree.

- [ ] **Step 2: Implement create-once tracked environment-lock capture**

Create `scripts/capture_environment_lock.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

if test "$#" -ne 2 || test "$1" != --evidence-dir; then
  printf '%s\n' 'usage: bash scripts/capture_environment_lock.sh --evidence-dir /var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment.staging' >&2
  exit 2
fi

evidence_dir="$2"
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
source scripts/lib/environment_common.sh
environment_require_evidence_dir "$evidence_dir"

for name in ai-pip-freeze.txt gateway-pip-freeze.txt node-npm-versions.txt resource-downloads.tsv; do
  test -s "$evidence_dir/$name"
done

target=artifacts/environment
run_id="$(basename "$(dirname "$evidence_dir")")"
stage="artifacts/.environment-capture-$run_id"
candidate=
cleanup() {
  local path
  for path in "$stage" "$candidate"; do
    test -n "$path" || continue
    if test -e "$path"; then
      case "$path" in
        artifacts/.environment-capture-*|/tmp/phase1-environment-lock-*) ;;
        *) return 1 ;;
      esac
      find "$path" -depth -delete
    fi
  done
}
trap cleanup EXIT

build_candidate() {
  local destination="$1"
  install -d -m 0755 "$destination"
  dpkg-query -W -f='${Package}\t${Version}\n' | LC_ALL=C sort \
    > "$destination/dpkg-packages.tsv"
  install -m 0644 "$evidence_dir/ai-pip-freeze.txt" "$destination/ai-pip-freeze.txt"
  install -m 0644 "$evidence_dir/gateway-pip-freeze.txt" "$destination/gateway-pip-freeze.txt"
  install -m 0644 "$evidence_dir/node-npm-versions.txt" "$destination/node-npm-versions.txt"
  install -m 0644 "$evidence_dir/resource-downloads.tsv" "$destination/resource-downloads.tsv"
  (
    cd "$destination"
    for name in \
      ai-pip-freeze.txt \
      dpkg-packages.tsv \
      gateway-pip-freeze.txt \
      node-npm-versions.txt \
      resource-downloads.tsv; do
      sha256sum -- "$name"
    done > SHA256SUMS
    sha256sum -c SHA256SUMS
  )
}

tracked_files=(
  artifacts/environment/dpkg-packages.tsv
  artifacts/environment/ai-pip-freeze.txt
  artifacts/environment/gateway-pip-freeze.txt
  artifacts/environment/node-npm-versions.txt
  artifacts/environment/resource-downloads.tsv
  artifacts/environment/SHA256SUMS
)

if test -e "$target"; then
  test -d "$target"
  test ! -L "$target"
  for path in "${tracked_files[@]}"; do
    git ls-files --error-unmatch "$path" >/dev/null || {
      printf 'refusing-existing-untracked-or-partial-baseline: %s\n' "$target" >&2
      exit 1
    }
  done
  test -z "$(git status --porcelain=v1 --untracked-files=all -- "$target")" || {
    printf 'refusing-dirty-tracked-baseline: %s\n' "$target" >&2
    exit 1
  }
  candidate="/tmp/phase1-environment-lock-$(python3 -c 'import uuid; print(uuid.uuid4())')"
  test ! -e "$candidate"
  install -d -m 0700 "$candidate"
  build_candidate "$candidate"
  diff -ru --no-dereference "$target" "$candidate"
  printf '%s\n' 'capture-environment-lock: PASS: tracked-baseline-unchanged'
  trap - EXIT
  cleanup
  exit 0
fi

test ! -e "$stage"
install -d -m 0755 artifacts
build_candidate "$stage"
mv -T -- "$stage" "$target"
stage=
printf '%s\n' 'capture-environment-lock: PASS: first-baseline-created'
trap - EXIT
cleanup
```

This script never overwrites `artifacts/environment`. An already tracked, clean six-file baseline is accepted only when a freshly captured candidate is byte-for-byte identical. Any existing untracked, partial, dirty, or mismatched baseline is refused before mutation.

- [ ] **Step 3: Implement the read-only sealed-evidence checker and one-shot verifier**

Create `scripts/check_environment_seal.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

if test "$#" -ne 2 || test "$1" != --evidence-dir; then
  printf '%s\n' 'usage: bash scripts/check_environment_seal.sh --evidence-dir /var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment' >&2
  exit 2
fi

evidence_dir="$2"
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
source scripts/lib/environment_common.sh
test_root="${SUBSTATION_VERIFY_TEST_ROOT:-}"
if test -n "$test_root"; then
  case "$test_root" in /tmp/phase1-seal-fixture-*) ;; *) exit 2 ;; esac
  case "$evidence_dir" in "$test_root"/acceptance/**/01-environment) ;; *) exit 2 ;; esac
else
  environment_require_final_evidence_target "$evidence_dir"
fi

test -d "$evidence_dir"
test ! -L "$evidence_dir"
test ! -e "$evidence_dir.staging"
test -s "$evidence_dir/SHA256SUMS"
python3 - "$evidence_dir" <<'PY'
import hashlib
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
manifest = root / "SHA256SUMS"
entries = {}
for line in manifest.read_text(encoding="utf-8").splitlines():
    if len(line) < 67 or line[64:66] != "  ":
        raise SystemExit(f"malformed SHA256SUMS entry: {line!r}")
    digest, relative = line[:64], line[66:]
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise SystemExit(f"invalid SHA-256: {digest!r}")
    if not relative or relative.startswith("/") or "\\" in relative or "\n" in relative:
        raise SystemExit(f"unsafe checksum path: {relative!r}")
    path = Path(relative)
    if ".." in path.parts or relative in entries:
        raise SystemExit(f"duplicate or escaping checksum path: {relative!r}")
    entries[relative] = digest

actual = set()
for path in root.rglob("*"):
    if path.is_symlink():
        raise SystemExit(f"symlink forbidden in sealed evidence: {path}")
    if path.is_file() and path.name != "SHA256SUMS":
        actual.add(path.relative_to(root).as_posix())
    elif not path.is_dir() and not path.is_file():
        raise SystemExit(f"unsupported evidence entry: {path}")
if set(entries) != actual:
    raise SystemExit(
        f"checksum path set mismatch: missing={sorted(actual - set(entries))}, "
        f"extra={sorted(set(entries) - actual)}"
    )
for relative, expected in entries.items():
    digest = hashlib.sha256((root / relative).read_bytes()).hexdigest()
    if digest != expected:
        raise SystemExit(f"checksum mismatch: {relative}")

result = json.loads((root / "result.json").read_text(encoding="utf-8"))
required = {
    "schema_version", "acceptance_run_id", "git_commit", "started_at",
    "completed_at", "commands", "exit_codes", "thresholds", "measurements",
    "artifacts", "status", "failures",
}
if not required <= result.keys():
    raise SystemExit("result.json schema keys missing")
if result["status"] != "passed" or result["failures"] != []:
    raise SystemExit("sealed result is not passed")
if not re.fullmatch(r"[0-9a-f]{40}", result["git_commit"]):
    raise SystemExit("result git_commit is not a full commit")
if result["acceptance_run_id"] != root.parent.name:
    raise SystemExit("acceptance run id does not match evidence parent")
expected_artifacts = sorted(actual - {"result.json"})
if result["artifacts"] != expected_artifacts:
    raise SystemExit("result artifact inventory does not match sealed files")
records = result["commands"]
if len({record["id"] for record in records}) != len(records):
    raise SystemExit("duplicate command ids")
if result["exit_codes"] != (
    {record["id"]: record["exit_code"] for record in records}
    | {"verify_environment": 0}
):
    raise SystemExit("exit-code map does not match command records")
for record in records:
    if record["exit_code"] != 0 or record["capture_exit_code"] != 0:
        raise SystemExit(f"nonzero sealed command record: {record['id']}")
    if not (root / record["log"]).is_file():
        raise SystemExit(f"missing sealed command log: {record['log']}")
PY

printf '%s\n' 'check-environment-seal: PASS'
```

Create `scripts/verify_environment.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

if test "$#" -ne 2 || test "$1" != --evidence-dir; then
  printf '%s\n' 'usage: bash scripts/verify_environment.sh --evidence-dir /var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment' >&2
  exit 2
fi

final_dir="$2"
staging_dir="$final_dir.staging"
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
source scripts/lib/environment_common.sh
test_root="${SUBSTATION_VERIFY_TEST_ROOT:-}"
test_mode=0
if test -n "$test_root"; then
  case "$test_root" in /tmp/phase1-seal-fixture-*) ;; *) exit 2 ;; esac
  case "$final_dir" in "$test_root"/acceptance/**/01-environment) ;; *) exit 2 ;; esac
  test_mode=1
else
  environment_require_final_evidence_target "$final_dir"
fi

parent_dir="$(dirname "$final_dir")"
test -d "$parent_dir"
test ! -L "$parent_dir"
exec 9<"$parent_dir"
flock -n 9 || {
  printf 'phase1-seal-lock-busy: %s\n' "$(basename "$parent_dir")" >&2
  exit 1
}

test ! -e "$final_dir" || {
  printf 'refusing-existing-final-evidence: %s\n' "$final_dir" >&2
  exit 1
}
test -d "$staging_dir"
test ! -L "$staging_dir"
test ! -e "$staging_dir/SHA256SUMS" || {
  printf 'refusing-presealed-staging-evidence: %s\n' "$staging_dir" >&2
  exit 1
}
for prior in commands environment.json result.json; do
  test ! -e "$staging_dir/$prior" || {
    printf 'refusing-prior-verifier-state: %s\n' "$staging_dir/$prior" >&2
    exit 1
  }
done

acceptance_run_id="$(basename "$(dirname "$final_dir")")"
test "$(<"$staging_dir/acceptance_run_id.txt")" = "$acceptance_run_id"
[[ "$acceptance_run_id" =~ ^[A-Za-z0-9._-]+$ ]]
test "$(stat -c '%d' "$staging_dir")" = "$(stat -c '%d' "$parent_dir")"
verify_parent_rename() (
  set -euo pipefail
  local rename_probe rename_probe_after
  rename_probe="$parent_dir/.phase1-rename-probe-$(python3 -c 'import uuid; print(uuid.uuid4())')"
  rename_probe_after="$rename_probe.renamed"
  cleanup_probe() {
    test ! -d "$rename_probe" || rmdir -- "$rename_probe"
    test ! -d "$rename_probe_after" || rmdir -- "$rename_probe_after"
  }
  trap cleanup_probe EXIT
  test ! -e "$rename_probe"
  test ! -e "$rename_probe_after"
  install -d -m 0700 "$rename_probe"
  mv -T -- "$rename_probe" "$rename_probe_after"
  rmdir -- "$rename_probe_after"
)
verify_parent_rename

commands_dir="$staging_dir/commands"
started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
git_commit="$(git rev-parse HEAD)"
checksum_work=
cleanup() {
  if test -n "$checksum_work" && test -e "$checksum_work"; then
    unlink -- "$checksum_work"
  fi
  flock -u 9 || true
}
trap cleanup EXIT

write_failed_result() {
  local rc="$1"
  local line="$2"
  trap - ERR
  test ! -e "$staging_dir/SHA256SUMS"
  python3 - "$staging_dir/result.json" "$acceptance_run_id" "$git_commit" "$started_at" "$rc" "$line" "$commands_dir" <<'PY'
import datetime
import json
import sys
from pathlib import Path

path, run_id, commit, started, rc, line, commands_dir = sys.argv[1:]
records = []
commands = Path(commands_dir)
if commands.is_dir():
    for record_path in sorted(commands.glob("*.json")):
        records.append(json.loads(record_path.read_text(encoding="utf-8")))
result = {
    "schema_version": 1,
    "acceptance_run_id": run_id,
    "git_commit": commit,
    "started_at": started,
    "completed_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "commands": records,
    "exit_codes": {record["id"]: record["exit_code"] for record in records}
        | {"verify_environment": int(rc)},
    "thresholds": {
        "phase1_residual_free_bytes_min": 20 * 1024**3,
        "physical_memory_bytes_min": 15 * 1024**3,
        "nvidia_driver_min": "560.35.05",
    },
    "measurements": {},
    "artifacts": [],
    "status": "failed",
    "failures": [f"verify_environment failed at shell line {line} with exit {rc}"],
}
Path(path).write_text(
    json.dumps(result, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
  exit "$rc"
}
trap 'write_failed_result "$?" "$LINENO"' ERR

install -d -m 0750 "$commands_dir"

run_recorded() {
  local command_id="$1"
  local log_relative="$2"
  shift 2
  test "$1" = --
  shift
  [[ "$command_id" =~ ^[a-z0-9-]+$ ]]
  [[ "$log_relative" != /* && "$log_relative" != *..* ]]
  local log_path="$staging_dir/$log_relative"
  local record_path="$commands_dir/$command_id.json"
  local command_started command_completed command_rc capture_rc saved_err_trap
  local -a pipeline_status
  test ! -e "$log_path"
  test ! -e "$record_path"
  command_started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  saved_err_trap="$(trap -p ERR)"
  trap - ERR
  set +e
  (set -euo pipefail; "$@") 2>&1 | tee "$log_path"
  pipeline_status=("${PIPESTATUS[@]}")
  eval "$saved_err_trap"
  set -e
  command_rc="${pipeline_status[0]}"
  capture_rc="${pipeline_status[1]}"
  command_completed="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  python3 - "$record_path" "$command_id" "$log_relative" \
    "$command_started" "$command_completed" "$command_rc" "$capture_rc" "$@" <<'PY'
import json
import sys
from pathlib import Path

record_path, command_id, log_path, started, completed, command_rc, capture_rc, *argv = sys.argv[1:]
record = {
    "schema_version": 1,
    "id": command_id,
    "argv": argv,
    "started_at": started,
    "completed_at": completed,
    "exit_code": int(command_rc),
    "capture_exit_code": int(capture_rc),
    "log": log_path,
}
Path(record_path).write_text(
    json.dumps(record, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
  test "$command_rc" -eq 0 || return "$command_rc"
  test "$capture_rc" -eq 0 || return "$capture_rc"
}

if test "$test_mode" -eq 1 \
  && test "${SUBSTATION_VERIFY_INSTALLER_EVIDENCE_TEST:-0}" != 1; then
  fixture_check() {
    local requested_rc="${SUBSTATION_VERIFY_TEST_FAILURE:-0}"
    printf 'fixture-check: rc=%s\n' "$requested_rc"
    test "$requested_rc" -eq 0 || return "$requested_rc"
  }
  run_recorded fixture-check fixture-check.log -- fixture_check
  python3 - "$staging_dir/environment.json" "$git_commit" <<'PY'
import json
import sys
from pathlib import Path
Path(sys.argv[1]).write_text(
    json.dumps(
        {"schema_version": 1, "git_commit": sys.argv[2], "fixture": True},
        indent=2,
        sort_keys=True,
    ) + "\n",
    encoding="utf-8",
)
PY
  measurements='{}'
else
  installer_host_root=/
  if test "$test_mode" -eq 1; then
    installer_host_root="${SUBSTATION_VERIFY_INSTALLER_HOST_ROOT:?}"
  fi
  if test "$test_mode" -eq 0; then
    required_preexisting=(
      storage-paths-before.tsv
      documentation-gate.log
      host-audit.json
      install-host.log
      install-state.env
      install-complete.env
      apt-candidates.tsv
      apt-changed-package-origins.tsv
      apt-policy-origins.json
      apt-sources-before/inventory.tsv
      apt-sources-after/inventory.tsv
      policy-rc.d-state.tsv
      managed-files-after.tsv
      host-install-version-changes.tsv
      ros-archive-key.sha256
      gazebo-archive-key.sha256
      dpkg-before.tsv
      dpkg-after.tsv
      ai-pip-freeze.txt
      gateway-pip-freeze.txt
      node-npm-versions.txt
      node-current-before.tsv
      resource-downloads.tsv
      colcon-build.log
      colcon-test.log
      colcon-test-result.log
      frontend-build.log
    )
    for relative_path in "${required_preexisting[@]}"; do
      test -s "$staging_dir/$relative_path" || {
        printf 'missing-preexisting-evidence: %s\n' "$relative_path" >&2
        false
      }
    done
    test -f "$staging_dir/host-install-new-packages.txt"
    test "$(tail -n1 "$staging_dir/install-host.log")" = 'install-host: PASS'
    grep -Fxq 'state=PASS' "$staging_dir/install-complete.env"

    tracked_paths=(
      scripts/capture_environment_lock.sh
      scripts/verify_environment.sh
      scripts/check_environment_seal.sh
      tests/environment/test_verify_environment.sh
      artifacts/environment/dpkg-packages.tsv
      artifacts/environment/ai-pip-freeze.txt
      artifacts/environment/gateway-pip-freeze.txt
      artifacts/environment/node-npm-versions.txt
      artifacts/environment/resource-downloads.tsv
      artifacts/environment/SHA256SUMS
    )
    for path in "${tracked_paths[@]}"; do
      git ls-files --error-unmatch "$path" >/dev/null
      git diff --quiet HEAD -- "$path"
    done
    test -z "$(git status --porcelain=v1 --untracked-files=all -- "${tracked_paths[@]}")"
  fi

  verify_installer_evidence() {
    python3 - "$staging_dir" "$installer_host_root" <<'PY'
import csv
import datetime
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
host_root = Path(sys.argv[2])

def host_path(logical):
    logical = Path(logical)
    assert logical.is_absolute()
    return logical if host_root == Path("/") else host_root / logical.relative_to("/")

def logical_path(path):
    return (
        path.as_posix()
        if host_root == Path("/")
        else "/" + path.relative_to(host_root).as_posix()
    )

before_path = root / "apt-sources-before/inventory.tsv"
after_path = root / "apt-sources-after/inventory.tsv"
managed_path = root / "managed-files-after.tsv"
policy_path = root / "policy-rc.d-state.tsv"

state_path = root / "install-state.env"
expected_state_keys = {
    "state",
    "universe_present_before",
    "nginx_unit_present_before",
    "nginx_active_before",
    "nginx_enabled_before",
    "started_at",
}
state_values = {}
for line_number, line in enumerate(
    state_path.read_text(encoding="utf-8").splitlines(), 1
):
    if not re.fullmatch(r"[a-z_]+=[A-Za-z0-9_.:+-]+", line):
        raise AssertionError(f"unsafe install-state line {line_number}")
    key, value = line.split("=", 1)
    assert key not in state_values, f"duplicate install-state key: {key}"
    state_values[key] = value
assert set(state_values) == expected_state_keys
assert state_values["state"] == "INITIAL_INSTALL_STARTED"
assert state_values["universe_present_before"] == "1"
assert state_values["nginx_unit_present_before"] in {"0", "1"}
if state_values["nginx_unit_present_before"] == "0":
    assert state_values["nginx_active_before"] == "absent"
    assert state_values["nginx_enabled_before"] == "absent"
else:
    assert state_values["nginx_active_before"] in {"active", "inactive"}
    assert state_values["nginx_enabled_before"] in {"enabled", "disabled", "masked"}
datetime.datetime.strptime(state_values["started_at"], "%Y-%m-%dT%H:%M:%SZ")

with before_path.open(encoding="utf-8", newline="") as handle:
    before = list(csv.DictReader(handle, delimiter="\t"))
assert before
assert len({row["source_path"] for row in before}) == len(before)
managed_expected = {
    "/etc/apt/sources.list.d/ros2.list",
    "/etc/apt/sources.list.d/gazebo-stable.list",
    "/usr/share/keyrings/ros-archive-keyring.gpg",
    "/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg",
    "/etc/default/locale",
    "/etc/ros/rosdep/sources.list.d/20-default.list",
    "/usr/sbin/policy-rc.d",
}
assert managed_expected <= {row["source_path"] for row in before}
before_by_path = {row["source_path"]: row for row in before}
for row in before:
    if row["existed"] == "1":
        backup = before_path.parent / row["backup_file"]
        assert backup.is_file()
        assert hashlib.sha256(backup.read_bytes()).hexdigest() == row["sha256"]
        assert row["mode"].isdigit()
    else:
        assert row["existed"] == "0"
        assert row["mode"] == row["sha256"] == row["backup_file"] == "-"

current_sources = []
source_list = host_path("/etc/apt/sources.list")
source_dir = host_path("/etc/apt/sources.list.d")
candidates = [source_list]
for pattern in ("*.list", "*.sources"):
    candidates.extend(source_dir.glob(pattern))
for path in candidates:
    if path.is_symlink():
        raise AssertionError(f"apt source symlink is forbidden: {path}")
    if not path.exists():
        continue
    assert path.is_file(), f"apt source is not a regular file: {path}"
    current_sources.append(path)
current_source_names = {logical_path(path) for path in current_sources}
with after_path.open(encoding="utf-8", newline="") as handle:
    after = list(csv.DictReader(handle, delimiter="\t"))
assert len({row["source_path"] for row in after}) == len(after)
assert {row["source_path"] for row in after} == current_source_names
for row in after:
    path = host_path(row["source_path"])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
    assert f"{path.stat().st_mode & 0o777:o}" == row["mode"]

with managed_path.open(encoding="utf-8", newline="") as handle:
    managed = list(csv.DictReader(handle, delimiter="\t"))
assert {row["source_path"] for row in managed} == managed_expected
for row in managed:
    path = host_path(row["source_path"])
    if row["existed_after"] == "1":
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
        assert f"{path.stat().st_mode & 0o777:o}" == row["mode"]
    else:
        assert row["existed_after"] == "0"
        assert not path.exists()
        assert row["mode"] == row["sha256"] == "-"

with policy_path.open(encoding="utf-8", newline="") as handle:
    policy = list(csv.DictReader(handle, delimiter="\t"))
assert len(policy) == 1
assert policy[0]["path"] == "/usr/sbin/policy-rc.d"
assert policy[0]["restored"] == "1"
policy_before = before_by_path["/usr/sbin/policy-rc.d"]
policy_live = host_path("/usr/sbin/policy-rc.d")
if policy_before["existed"] == "1":
    assert policy_live.is_file()
    assert hashlib.sha256(policy_live.read_bytes()).hexdigest() == policy_before["sha256"]
    assert f"{policy_live.stat().st_mode & 0o777:o}" == policy_before["mode"]
else:
    assert not policy_live.exists()

audit = json.loads((root / "apt-policy-origins.json").read_text(encoding="utf-8"))
requested = [
    line
    for line in Path("config/environment/apt-packages.txt").read_text(encoding="utf-8").splitlines()
    if line
]
assert set(audit["apt_policy"]) == set(requested)
assert not audit["forbidden_packages"]
assert not audit["forbidden_apt_sources"]
assert all(
    item["candidate_ok"] and item["origin_ok"]
    for item in audit["apt_policy"].values()
)
with (root / "apt-candidates.tsv").open(encoding="utf-8", newline="") as handle:
    candidate_reader = csv.DictReader(handle, delimiter="\t")
    assert candidate_reader.fieldnames == [
        "package", "expected_upstream", "candidate", "allowed_origins", "origins"
    ]
    candidate_rows = list(candidate_reader)
assert [row["package"] for row in candidate_rows] == requested
for row in candidate_rows:
    policy = audit["apt_policy"][row["package"]]
    assert row["expected_upstream"] == (policy["expected_upstream"] or "-")
    assert row["candidate"] == policy["candidate"]
    assert row["allowed_origins"].split(",") == policy["allowed_origins"]
    assert row["origins"].split(",") == policy["origins"]

def versions(path):
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        package, version = line.split("\t", 1)
        rows[package] = version
    return rows

before_packages = versions(root / "dpkg-before.tsv")
after_packages = versions(root / "dpkg-after.tsv")
expected_changes = []
for package in sorted(set(before_packages) | set(after_packages)):
    old = before_packages.get(package)
    new = after_packages.get(package)
    if old == new:
        continue
    expected_changes.append({
        "package": package,
        "before_version": old or "-",
        "after_version": new or "-",
        "change": "added" if old is None else "removed" if new is None else "version-changed",
    })
with (root / "host-install-version-changes.tsv").open(
    encoding="utf-8", newline=""
) as handle:
    actual_changes = list(csv.DictReader(handle, delimiter="\t"))
assert actual_changes == expected_changes
assert not any(row["change"] == "removed" for row in actual_changes)
assert (root / "host-install-new-packages.txt").read_text(
    encoding="utf-8"
).splitlines() == [
    row["package"] for row in expected_changes if row["change"] == "added"
]

ubuntu_origins = {
    "http://archive.ubuntu.com/ubuntu", "https://archive.ubuntu.com/ubuntu",
    "http://security.ubuntu.com/ubuntu", "https://security.ubuntu.com/ubuntu",
}
ros_origins = {
    "http://packages.ros.org/ros2/ubuntu", "https://packages.ros.org/ros2/ubuntu",
}
gazebo_origins = {
    "http://packages.osrfoundation.org/gazebo/ubuntu-stable",
    "https://packages.osrfoundation.org/gazebo/ubuntu-stable",
}
def allowed_origins_for(package):
    if package.startswith("ros-jazzy-"):
        return ros_origins
    if re.match(r"^(gz-|libgz-|sdformat|libsdformat|ignition-|libignition-)", package):
        return gazebo_origins
    return ubuntu_origins

with (root / "apt-changed-package-origins.tsv").open(
    encoding="utf-8", newline=""
) as handle:
    changed_reader = csv.DictReader(handle, delimiter="\t")
    assert changed_reader.fieldnames == [
        "package", "expected_upstream", "candidate", "allowed_origins", "origins"
    ]
    changed_origin_rows = list(changed_reader)
assert [row["package"] for row in changed_origin_rows] == [
    row["package"] for row in expected_changes
]
for row in changed_origin_rows:
    package = row["package"]
    completed = subprocess.run(
        ["apt-cache", "policy", package],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    candidate_match = re.search(r"^\s*Candidate:\s*(\S+)", completed.stdout, re.MULTILINE)
    assert candidate_match and candidate_match.group(1) == row["candidate"]
    origins = sorted({
        match.group(1).rstrip("/")
        for match in re.finditer(
            r"^\s*\d+\s+(https?://\S+)\s+\S+\s+\S+\s+Packages$",
            completed.stdout,
            re.MULTILINE,
        )
    })
    allowed = allowed_origins_for(package)
    if not origins or not set(origins) <= allowed:
        raise AssertionError(
            f"changed package origin is not allowed: {package}: "
            f"{','.join(origins) if origins else '-'}"
        )
    assert row["allowed_origins"].split(",") == sorted(allowed)
    assert row["origins"].split(",") == origins

with (root / "storage-paths-before.tsv").open(
    encoding="utf-8", newline=""
) as handle:
    storage_rows = list(csv.DictReader(handle, delimiter="\t"))
assert storage_rows
for row in storage_rows:
    path = host_path(row["path"])
    assert path.is_dir() and not path.is_symlink()
    assert (path.stat().st_mode & 0o777) == int(row["expected_mode"], 8)
    assert path.owner() == row["expected_owner"]
    assert path.group() == row["expected_group"]

with (root / "node-current-before.tsv").open(
    encoding="utf-8", newline=""
) as handle:
    node_rows = list(csv.DictReader(handle, delimiter="\t"))
assert len(node_rows) == 1
assert logical_path(host_path(node_rows[0]["path"])) == \
    "/opt/substation/toolchains/node-current"
PY
    printf '%s\n' 'installer-evidence: PASS'
  }

  if test "$test_mode" -eq 1; then
    run_recorded installer-evidence installer-evidence.log -- \
      verify_installer_evidence
    printf '%s\n' 'installer evidence negative fixture unexpectedly passed' >&2
    false
  fi

  verify_tracked_lock() {
    dpkg-query -W -f='${Package}\t${Version}\n' | LC_ALL=C sort \
      > "$staging_dir/dpkg-packages.tsv"
    cmp artifacts/environment/dpkg-packages.tsv "$staging_dir/dpkg-packages.tsv"
    cmp artifacts/environment/ai-pip-freeze.txt "$staging_dir/ai-pip-freeze.txt"
    cmp artifacts/environment/gateway-pip-freeze.txt "$staging_dir/gateway-pip-freeze.txt"
    cmp artifacts/environment/node-npm-versions.txt "$staging_dir/node-npm-versions.txt"
    cmp artifacts/environment/resource-downloads.tsv "$staging_dir/resource-downloads.tsv"
    (cd artifacts/environment && sha256sum -c SHA256SUMS)
    printf '%s\n' 'tracked-environment-lock: PASS'
  }

  verify_versions() {
    source /opt/ros/jazzy/setup.bash
    test "$ROS_DISTRO" = jazzy
    dpkg-query -W -f='${Package}\t${Version}\n' ros-jazzy-ros-gz \
      | grep -E $'^ros-jazzy-ros-gz\t1\.0\.23-1([^0-9].*)?$'
    dpkg-query -W -f='${Package}\t${Version}\n' \
      ros-jazzy-navigation2 ros-jazzy-nav2-bringup \
      | tee "$staging_dir/navigation2-packages.txt"
    grep -E $'^ros-jazzy-navigation2\t1\.3\.12-1([^0-9].*)?$' \
      "$staging_dir/navigation2-packages.txt"
    grep -E $'^ros-jazzy-nav2-bringup\t1\.3\.12-1([^0-9].*)?$' \
      "$staging_dir/navigation2-packages.txt"
    dpkg-query -W -f='${Version}\n' ros-jazzy-slam-toolbox \
      | grep -E '^2\.8\.5-1([^0-9].*)?$'
    dpkg-query -W -f='${Package}\t${Version}\n' \
      ros-jazzy-turtlebot3 ros-jazzy-turtlebot3-simulations \
      | tee "$staging_dir/turtlebot3-packages.txt"
    grep -E $'^ros-jazzy-turtlebot3\t2\.3\.6-1([^0-9].*)?$' \
      "$staging_dir/turtlebot3-packages.txt"
    grep -E $'^ros-jazzy-turtlebot3-simulations\t2\.3\.7-1([^0-9].*)?$' \
      "$staging_dir/turtlebot3-packages.txt"
    gz sim --versions | tee "$staging_dir/gazebo-version.txt"
    grep -E '(^|[^0-9])8\.[0-9]' "$staging_dir/gazebo-version.txt"
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader \
      | tee "$staging_dir/gpu.txt"
    driver_version="$(
      nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -n1
    )"
    dpkg --compare-versions "$driver_version" ge 560.35.05
    if systemctl is-active --quiet nginx.service; then
      printf '%s\n' 'nginx must remain stopped during Phase 1 verification' >&2
      return 1
    fi
    nginx_enabled="$(systemctl is-enabled nginx.service 2>/dev/null || true)"
    test "$nginx_enabled" = disabled
    printf 'nginx.service=inactive\nnginx.enabled=%s\n' "$nginx_enabled" \
      > "$staging_dir/service-state.txt"
    printf '%s\n' 'locked-version-checks: PASS'
  }

  capture_ai_lock() {
    .venv/bin/python -m pip freeze --all | LC_ALL=C sort \
      > "$staging_dir/ai-pip-freeze-final.txt"
    cmp artifacts/environment/ai-pip-freeze.txt \
      "$staging_dir/ai-pip-freeze-final.txt"
    printf '%s\n' 'ai-freeze-lock: PASS'
  }

  capture_gateway_lock() {
    .venv-web/bin/python -m pip freeze --all | LC_ALL=C sort \
      > "$staging_dir/gateway-pip-freeze-final.txt"
    cmp artifacts/environment/gateway-pip-freeze.txt \
      "$staging_dir/gateway-pip-freeze-final.txt"
    printf '%s\n' 'gateway-freeze-lock: PASS'
  }

  verify_resources() {
    bash scripts/verify_phase1_resources.sh --evidence-dir "$staging_dir"
    cmp artifacts/environment/resource-downloads.tsv \
      "$staging_dir/resource-downloads.tsv"
    printf '%s\n' 'resource-lock-check: PASS'
  }

  verify_ros_workspace() {
    source /opt/ros/jazzy/setup.bash
    colcon --log-base log build --base-paths ros2_ws/src --build-base build --install-base install --event-handlers console_direct+ 2>&1 \
      | tee "$staging_dir/colcon-build-final.log"
    test "${PIPESTATUS[0]}" -eq 0
    colcon --log-base log test --base-paths ros2_ws/src --build-base build --install-base install --event-handlers console_direct+ --return-code-on-test-failure 2>&1 \
      | tee "$staging_dir/colcon-test-final.log"
    test "${PIPESTATUS[0]}" -eq 0
    colcon test-result --test-result-base build --all --verbose 2>&1 \
      | tee "$staging_dir/colcon-test-result-final.log"
    test "${PIPESTATUS[0]}" -eq 0
    printf '%s\n' 'ros-workspace-final: PASS'
  }

  capture_node_lock() {
    {
      node --version
      npm --version
      node -p 'require("./web/frontend/package.json").packageManager'
    } > "$staging_dir/node-npm-versions-final.txt"
    cmp artifacts/environment/node-npm-versions.txt \
      "$staging_dir/node-npm-versions-final.txt"
    printf '%s\n' 'node-npm-lock: PASS'
  }

  run_recorded documentation-gate documentation-gate-final.log -- \
    bash scripts/verify_documentation_gate.sh
  run_recorded host-audit host-audit-final.json -- bash scripts/audit_host.sh
  python3 - "$staging_dir/host-audit-final.json" \
    "$staging_dir/disk-memory.txt" \
    "$staging_dir/forbidden-packages.txt" <<'PY'
import json
import sys
from pathlib import Path

audit_path, disk_path, forbidden_path = map(Path, sys.argv[1:])
data = json.loads(audit_path.read_text(encoding="utf-8"))
assert data["status"] == "passed"
disk_path.write_text(
    f"disk_free_bytes={data['disk_free_bytes']}\n"
    f"memory_bytes={data['memory_bytes']}\n",
    encoding="utf-8",
)
packages = data["forbidden_packages"]
forbidden_path.write_text(
    "forbidden-packages: none\n"
    if not packages
    else "\n".join(packages) + "\n",
    encoding="utf-8",
)
assert not packages
PY
  run_recorded installer-evidence installer-evidence.log -- \
    verify_installer_evidence
  run_recorded tracked-lock tracked-lock-check.log -- verify_tracked_lock
  run_recorded version-checks version-checks.log -- verify_versions
  run_recorded ai-environment test-ai-environment-final.log -- \
    bash tests/environment/test_ai_environment.sh
  run_recorded gateway-environment test-gateway-environment-final.log -- \
    bash tests/environment/test_gateway_environment.sh
  run_recorded ai-lock ai-lock-check.log -- capture_ai_lock
  run_recorded gateway-lock gateway-lock-check.log -- capture_gateway_lock
  run_recorded resource-lock resource-lock-check.log -- verify_resources
  run_recorded ros-workspace ros-workspace-final.log -- verify_ros_workspace
  run_recorded web-environment test-web-environment-final.log -- \
    bash tests/environment/test_web_environment.sh
  run_recorded node-lock node-lock-check.log -- capture_node_lock
  run_recorded frontend-build frontend-build-final.log -- \
    npm --prefix web/frontend run build
  run_recorded headless-egl verify-headless-egl-final.log -- \
    bash scripts/smoke_headless_egl.sh --evidence-dir "$staging_dir"

  python3 - "$staging_dir/environment.json" \
    "$staging_dir/host-audit-final.json" "$git_commit" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

output, audit_path, commit = sys.argv[1:]
audit = json.loads(Path(audit_path).read_text(encoding="utf-8"))

def command(*args):
    return subprocess.run(
        args, check=True, text=True, stdout=subprocess.PIPE
    ).stdout.strip()

document = {
    "schema_version": 1,
    "git_commit": commit,
    "ubuntu": audit["os"],
    "architecture": audit["architecture"],
    "memory_bytes": audit["memory_bytes"],
    "disk_free_bytes": audit["disk_free_bytes"],
    "gpu": audit["gpu"],
    "python": command("python3", "--version"),
    "ros_distro": "jazzy",
    "gazebo": command("gz", "sim", "--versions"),
    "node": command("node", "--version"),
    "npm": command("npm", "--version"),
    "headless_rendering": "ogre2-egl",
}
Path(output).write_text(
    json.dumps(document, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
  measurements="$(
    python3 - "$staging_dir/host-audit-final.json" <<'PY'
import json
import sys
from pathlib import Path
audit = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(json.dumps({
    "disk_free_bytes": audit["disk_free_bytes"],
    "memory_bytes": audit["memory_bytes"],
    "driver_version": audit["gpu"]["driver_version"],
}, sort_keys=True))
PY
  )"
fi

completed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 - "$staging_dir/result.json" "$acceptance_run_id" "$git_commit" \
  "$started_at" "$completed_at" "$commands_dir" "$measurements" <<'PY'
import json
import sys
from pathlib import Path

output, run_id, commit, started, completed, commands_dir, measurements = sys.argv[1:]
records = [
    json.loads(path.read_text(encoding="utf-8"))
    for path in sorted(Path(commands_dir).glob("*.json"))
]
root = Path(output).parent
artifacts = sorted(
    path.relative_to(root).as_posix()
    for path in root.rglob("*")
    if path.is_file() and path.name not in {"result.json", "SHA256SUMS"}
)
result = {
    "schema_version": 1,
    "acceptance_run_id": run_id,
    "git_commit": commit,
    "started_at": started,
    "completed_at": completed,
    "commands": records,
    "exit_codes": {record["id"]: record["exit_code"] for record in records}
        | {"verify_environment": 0},
    "thresholds": {
        "phase1_residual_free_bytes_min": 20 * 1024**3,
        "physical_memory_bytes_min": 15 * 1024**3,
        "nvidia_driver_min": "560.35.05",
    },
    "measurements": json.loads(measurements),
    "artifacts": artifacts,
    "status": "passed",
    "failures": [],
}
Path(output).write_text(
    json.dumps(result, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

if test "$test_mode" -eq 0; then
  final_required=(
    acceptance_run_id.txt
    documentation-gate.log
    documentation-gate-final.log
    storage-paths-before.tsv
    host-audit.json
    host-audit-final.json
    install-host.log
    install-state.env
    install-complete.env
    apt-candidates.tsv
    apt-changed-package-origins.tsv
    apt-policy-origins.json
    apt-sources-before/inventory.tsv
    apt-sources-after/inventory.tsv
    policy-rc.d-state.tsv
    managed-files-after.tsv
    host-install-version-changes.tsv
    ros-archive-key.sha256
    gazebo-archive-key.sha256
    dpkg-before.tsv
    dpkg-after.tsv
    environment.json
    dpkg-packages.tsv
    ai-pip-freeze.txt
    gateway-pip-freeze.txt
    node-npm-versions.txt
    node-current-before.tsv
    resource-downloads.tsv
    gpu.txt
    egl.log
    forbidden-packages.txt
    disk-memory.txt
    service-state.txt
    colcon-build.log
    colcon-test.log
    colcon-test-result.log
    colcon-build-final.log
    colcon-test-final.log
    colcon-test-result-final.log
    frontend-build.log
    frontend-build-final.log
    result.json
  )
  for relative_path in "${final_required[@]}"; do
    test -s "$staging_dir/$relative_path" || {
      printf 'missing-mandatory-final-artifact: %s\n' "$relative_path" >&2
      false
    }
  done
  test -f "$staging_dir/host-install-new-packages.txt"
fi

checksum_work="$(mktemp --tmpdir=/tmp)"
python3 - "$staging_dir" "$checksum_work" <<'PY'
import hashlib
import sys
from pathlib import Path

root, output = map(Path, sys.argv[1:])
paths = []
for path in root.rglob("*"):
    if path.is_symlink():
        raise SystemExit(f"symlink forbidden in evidence: {path}")
    if path.is_file():
        if path.name == "SHA256SUMS":
            raise SystemExit("SHA256SUMS unexpectedly exists before seal")
        relative = path.relative_to(root).as_posix()
        if "\\" in relative or "\n" in relative:
            raise SystemExit(f"unsupported checksum path: {relative!r}")
        paths.append(relative)
    elif not path.is_dir():
        raise SystemExit(f"unsupported evidence entry: {path}")
with output.open("w", encoding="utf-8") as handle:
    for relative in sorted(paths):
        digest = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        handle.write(f"{digest}  {relative}\n")
PY
(
  cd "$staging_dir"
  sha256sum -c "$checksum_work"
)

trap - ERR
install -m 0640 "$checksum_work" "$staging_dir/SHA256SUMS"
python3 - "$staging_dir" "$final_dir" <<'PY'
import ctypes
import os
import sys

source, target = map(os.fsencode, sys.argv[1:])
libc = ctypes.CDLL(None, use_errno=True)
renameat2 = libc.renameat2
renameat2.argtypes = [
    ctypes.c_int,
    ctypes.c_char_p,
    ctypes.c_int,
    ctypes.c_char_p,
    ctypes.c_uint,
]
renameat2.restype = ctypes.c_int
AT_FDCWD = -100
RENAME_NOREPLACE = 1
if renameat2(AT_FDCWD, source, AT_FDCWD, target, RENAME_NOREPLACE) != 0:
    error = ctypes.get_errno()
    raise OSError(error, os.strerror(error), sys.argv[2])
PY

bash scripts/check_environment_seal.sh --evidence-dir "$final_dir"
printf '%s\n' 'verify-environment: PASS'
```

The only mutation after successful command/result creation is the final `install` of staging `SHA256SUMS`; the following `renameat2(..., RENAME_NOREPLACE)` publishes that already sealed directory without replacing a concurrent target. The verifier has no code path that unlinks or rewrites `SHA256SUMS`. A failure before that final mutation writes `result.json.status=failed`, leaves the staging directory without `SHA256SUMS`, and makes a rerun refuse the prior verifier state. A failure after checksum publication is treated as sealed-but-unpublished or sealed-final evidence and is never repaired in place.

- [ ] **Step 4: Run the synthetic seal behavior test**

```bash
chmod +x \
  scripts/capture_environment_lock.sh \
  scripts/verify_environment.sh \
  scripts/check_environment_seal.sh \
  tests/environment/test_verify_environment.sh
bash tests/environment/test_verify_environment.sh
```

Expected: exactly `verify-environment-test: PASS` as the final line. The fresh fixture is sealed and renamed; a second call against the same final target exits nonzero and leaves an exact tree snapshot unchanged; the injected exit 23 leaves an unsealed staging directory with failed `result.json`; a rerun against that partial verifier state is refused without mutation.

Run the static no-repair contract:

```bash
if rg -n \
  'download_phase1_resources|install_host|setup_(ros_workspace|python_env|gateway_env|web_env)|compile_requirements|npm[^[:alnum:]]+ci|(^|[[:space:];])(unlink|rm)[[:space:]][^[:cntrl:]]*SHA256SUMS' \
  scripts/verify_environment.sh scripts/check_environment_seal.sh; then
  exit 1
else
  printf '%s\n' 'verify-environment-no-repair-contract: PASS'
fi
```

Expected: exactly `verify-environment-no-repair-contract: PASS`.

- [ ] **Step 5: Capture and review the proposed tracked lock before sealing**

Run:

```bash
source .phase1-run.env
test -d "$PHASE1_EVIDENCE_ROOT"
test ! -e "$PHASE1_EVIDENCE_FINAL"
test ! -e "$PHASE1_EVIDENCE_ROOT/SHA256SUMS"
bash scripts/capture_environment_lock.sh --evidence-dir "$PHASE1_EVIDENCE_ROOT"
git diff -- artifacts/environment
(cd artifacts/environment && sha256sum -c SHA256SUMS)
git status --short
```

Expected: `capture-environment-lock: PASS: first-baseline-created` for the first baseline, or `tracked-baseline-unchanged` only for a clean pre-existing approved baseline. Five `OK` lines follow. Review the complete Debian snapshot and all four other manifests; stop on any forbidden package, unexpected version, resource identity change, or dirty/partial prior baseline.

Safe rollback before commit distinguishes the two cases:

1. If `artifacts/environment` was already tracked before this task, preserve it byte-for-byte. Never move, delete, or rewrite it; correct the underlying environment or authority conflict instead.
2. If this is the first untracked baseline created by this step and review rejects it before commit, run `test -z "$(git ls-files artifacts/environment)"`, then move it with plain `mv -- artifacts/environment "artifacts/environment.rejected-$PHASE1_RUN_ID"` after confirming the quarantine target is absent. Do not use `git mv` for an untracked directory.
3. If the first baseline has already been committed, revert the focused Task 10 commit instead of manually editing tracked manifests. Preserve every runtime evidence directory.

- [ ] **Step 6: Commit the verifier implementation and reviewed lock**

```bash
git add \
  scripts/capture_environment_lock.sh \
  scripts/verify_environment.sh \
  scripts/check_environment_seal.sh \
  tests/environment/test_verify_environment.sh \
  artifacts/environment
git diff --cached --check
git diff --cached --stat
git commit -m "test: verify phase one environment baseline"
verified_commit="$(git rev-parse HEAD)"
test -z "$(git status --porcelain=v1 --untracked-files=all -- \
  scripts/capture_environment_lock.sh \
  scripts/verify_environment.sh \
  scripts/check_environment_seal.sh \
  tests/environment/test_verify_environment.sh \
  artifacts/environment)"
```

Expected: one focused implementation/lock commit exists before any live seal. `verified_commit` is the exact code and tracked lock that the immutable evidence will identify.

- [ ] **Step 7: Perform the one live canonical seal, then use only the read-only checker**

Run exactly once for this acceptance run:

```bash
source .phase1-run.env
verified_commit="$(git rev-parse HEAD)"
test -d "$PHASE1_EVIDENCE_ROOT"
test ! -e "$PHASE1_EVIDENCE_FINAL"
test ! -e "$PHASE1_EVIDENCE_ROOT/SHA256SUMS"
bash scripts/verify_environment.sh --evidence-dir "$PHASE1_EVIDENCE_FINAL"
test ! -e "$PHASE1_EVIDENCE_ROOT"
test -d "$PHASE1_EVIDENCE_FINAL"
bash scripts/check_environment_seal.sh --evidence-dir "$PHASE1_EVIDENCE_FINAL"
test "$(
  python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["git_commit"])' \
    "$PHASE1_EVIDENCE_FINAL/result.json"
)" = "$verified_commit"
```

Expected: final lines `verify-environment: PASS` and `check-environment-seal: PASS`; `result.json.status` is `passed`, failures is empty, every command/capture exit is zero, the recursive path set exactly matches `SHA256SUMS`, the staging path no longer exists, and `result.json.git_commit` is the already committed Task 10 implementation/lock commit. Do not call `verify_environment.sh` again for this run; all later checks use `check_environment_seal.sh`.

If the command fails before `SHA256SUMS` is created, preserve the failed unsealed staging tree and start a new acceptance run after correcting the cause. If it fails after checksum creation or atomic publication, preserve that sealed state and stop for operator review; never delete, repair, or reseal it.

Evidence: the immutable complete set rooted at `$PHASE1_EVIDENCE_FINAL`, plus the reviewed tracked six-file lock under `artifacts/environment`.

---

### Task 11: Project Status and Handoff Update

**Files:**
- Modify: `docs/PROJECT_STATUS.md`
- Modify: `docs/HANDOFF.md`

**Interfaces:**
- Consumes: the immutable Task 10 implementation verification record, `$PHASE1_EVIDENCE_FINAL/result.json`, `$PHASE1_EVIDENCE_FINAL/SHA256SUMS`, all verification commands, current Git status, and service state.
- Produces: a documentation-only synchronization commit that names the earlier verified implementation commit and a deterministic Phase 2 resume entry. It does not rewrite the immutable environment result to pretend that the later documentation commit was environment-tested.

- [ ] **Step 1: Capture the exact dynamic values before editing**

```bash
source .phase1-run.env
verified_commit="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["git_commit"])' "$PHASE1_EVIDENCE_FINAL/result.json")"
verified_at="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["completed_at"])' "$PHASE1_EVIDENCE_FINAL/result.json")"
verified_status="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "$PHASE1_EVIDENCE_FINAL/result.json")"
repo_root="$(git rev-parse --show-toplevel)"
branch_name="$(git branch --show-current)"
verification_command="$(printf 'bash scripts/verify_environment.sh --evidence-dir %q' "$PHASE1_EVIDENCE_FINAL")"
seal_check_command="$(printf 'bash scripts/check_environment_seal.sh --evidence-dir %q' "$PHASE1_EVIDENCE_FINAL")"
status_commit_command='git log -1 --format=%H -- docs/PROJECT_STATUS.md docs/HANDOFF.md'
resume_command="$(printf 'cd %q && source .phase1-run.env && bash scripts/check_environment_seal.sh --evidence-dir %q' "$repo_root" "$PHASE1_EVIDENCE_FINAL")"
printf 'verified_commit=%s\nverified_at=%s\nverified_status=%s\nrepo_root=%s\nbranch=%s\nevidence=%s\nverification_command=%s\nseal_check_command=%s\nstatus_commit_command=%s\nresume_command=%s\n' \
  "$verified_commit" "$verified_at" "$verified_status" "$repo_root" "$branch_name" "$PHASE1_EVIDENCE_FINAL" "$verification_command" "$seal_check_command" "$status_commit_command" "$resume_command"
test "$verified_status" = passed
test "$(git rev-parse HEAD)" = "$verified_commit"
bash scripts/check_environment_seal.sh --evidence-dir "$PHASE1_EVIDENCE_FINAL"
git status --short
```

Expected: `verified_status=passed`; `verified_commit` is both the current HEAD and the Task 10 implementation commit before documentation edits; evidence is the active absolute `/var/lib/substation/evidence/acceptance/.../01-environment` path and its checksum verifies; only the two status documents may be edited in this task.

- [ ] **Step 2: Update `docs/PROJECT_STATUS.md` with actual values using `apply_patch`**

Keep the document's existing headings, but make its current fact set exactly equivalent to:

```markdown
- Current phase: Phase 1 environment baseline complete; Phase 2 Gazebo world planning is next.
- Verified implementation commit: the literal `verified_commit` printed in Step 1.
- Verification time: the literal UTC `verified_at` printed in Step 1.
- Verification command: the exact `verification_command` line printed in Step 1.
- Read-only seal check: the exact `seal_check_command` line printed in Step 1; this is the only evidence command used after the one-shot verifier.
- Result: `passed`; `result.json` and `SHA256SUMS` both verified.
- Evidence scope: `result.json.git_commit` intentionally identifies the verified Task 10 implementation commit. The later status/handoff commit is documentation-only and must not be represented as an environment implementation commit.
- Status-document commit: resolve the current value with the exact literal `status_commit_command` printed in Step 1; the document does not embed its own commit hash because that would be self-referential.
- Completed: documentation gate, read-only host audit, official host install, early resource checksums, ROS workspace, AI and Gateway locks, Node/frontend build, headless EGL camera probe, and consolidated verifier.
- Running project services: none. Package installation must not leave Gazebo, ROS project nodes, Gateway, frontend, Foxglove Bridge, or Nginx serving the product.
- Blockers: none when the result is passed.
- Next three actions: write the Phase 2 test-first world plan; implement `substation_description` and `substation_gazebo` only after that plan is approved; preserve the same version/resource locks while proving `/clock`, camera, CameraInfo, LiDAR, environment sensors, odometry, TF, and scenario state without `DISPLAY`.
```

Do not write shell variable names into the final Markdown; insert their literal Step 1 output. Do not mark any Phase 2 function complete.

- [ ] **Step 3: Update `docs/HANDOFF.md` with actual values using `apply_patch`**

Keep the existing recovery structure, and make it exactly equivalent to:

```markdown
- Repository: the literal `repo_root` printed in Step 1.
- Branch: the literal branch printed in Step 1.
- Verified environment implementation commit: the literal `verified_commit` printed in Step 1.
- Status synchronization commit: resolve it from Git with the exact literal `status_commit_command` printed in Step 1; it is documentation-only and later than the verified implementation commit.
- Canonical one-shot verification command: the exact `verification_command` line printed in Step 1; do not rerun it for this acceptance run.
- Last successful command: the exact read-only `seal_check_command` line printed in Step 1.
- Result: passed at the literal UTC verification time.
- Evidence: the literal environment evidence path; `result.json` status passed; `SHA256SUMS` verified.
- Runtime services: none.
- Local runtime state: `.phase1-run.env`, `.venv`, `.venv-web`, ROS build/install/log, Node toolchain, `node_modules`, and `.next`; all are ignored or outside Git.
- Large resources: Node archive and `yolo11n.pt` are outside Git and recorded by `artifacts/environment/resource-downloads.tsv`.
- Uncommitted work: `git status --short` output captured immediately before the handoff commit; unrelated pre-existing changes remain untouched.
- First resume command: the exact `resume_command` line printed in Step 1.
- Next implementation action: create and approve a zero-context Phase 2 Gazebo world plan before adding ROS packages or the product world.
```

Insert literal paths and values from Step 1. Do not claim Nginx, Gateway, frontend, Gazebo, or ROS application services are deployed.

- [ ] **Step 4: Validate status truthfulness and Commit Task 11**

```bash
source .phase1-run.env
verified_commit="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["git_commit"])' "$PHASE1_EVIDENCE_FINAL/result.json")"
rg -n 'Phase 1|environment baseline|环境基线|verify_environment.sh|check_environment_seal.sh|result.json|SHA256SUMS|Phase 2|Gazebo' docs/PROJECT_STATUS.md docs/HANDOFF.md
rg -n -F "$PHASE1_EVIDENCE_FINAL" docs/PROJECT_STATUS.md docs/HANDOFF.md
git diff --check
git add docs/PROJECT_STATUS.md docs/HANDOFF.md
git diff --cached --check
git commit -m "docs: record phase one environment completion"
status_commit="$(git rev-parse HEAD)"
test "$status_commit" != "$verified_commit"
test "$(git log -1 --format=%H -- docs/PROJECT_STATUS.md docs/HANDOFF.md)" = "$status_commit"
test "$(git diff --name-only "$verified_commit" "$status_commit" | LC_ALL=C sort)" = $'docs/HANDOFF.md\ndocs/PROJECT_STATUS.md'
```

Expected: both documents contain the same verified implementation commit, UTC time, evidence root, passed result, no-running-service fact, documentation-only synchronization rule, and Phase 2 next action. The Git diff proves that the later status commit changed only the two documents.

Safe rollback: revert only the status/handoff commit. Never change environment evidence or tracked lock files to make a status statement appear true.

- [ ] **Step 5: Verify the immutable implementation record and the documentation-only HEAD**

```bash
source .phase1-run.env
verified_commit="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["git_commit"])' "$PHASE1_EVIDENCE_FINAL/result.json")"
status_commit="$(git rev-parse HEAD)"
evidence_commit="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["git_commit"])' "$PHASE1_EVIDENCE_FINAL/result.json")"
test "$evidence_commit" = "$verified_commit"
test "$status_commit" != "$verified_commit"
test "$(git diff --name-only "$verified_commit" "$status_commit" | LC_ALL=C sort)" = $'docs/HANDOFF.md\ndocs/PROJECT_STATUS.md'
bash scripts/check_environment_seal.sh --evidence-dir "$PHASE1_EVIDENCE_FINAL"
bash scripts/verify_documentation_gate.sh
git status --short
```

Expected: environment evidence still refers exactly to the Task 10 implementation commit and all checksums pass without rewriting any evidence. The current HEAD differs only by the two status documents, and the documentation gate passes at that documentation-only HEAD. Only unrelated pre-existing changes, if any, remain.

Evidence: the immutable `$PHASE1_EVIDENCE_FINAL/result.json`, `$PHASE1_EVIDENCE_FINAL/SHA256SUMS`, the literal Git diff between implementation and status commits, and the two committed current-state documents.

---

## Plan Self-Review and Execution Exit Gate

Before an implementer starts Task 1, and again after any plan edit, run:

```bash
rg -n '^### Task|^- \[ \] \*\*Step|^\*\*Files:|^\*\*Interfaces:' docs/plans/PHASE-01-ENVIRONMENT.md
rg -n 'scripts/verify_environment.sh|tests/environment|artifacts/environment|requirements.lock|package-lock.json' docs/plans/PHASE-01-ENVIRONMENT.md
```

Expected: eleven task headings; every task has Files and Interfaces; every task contains multiple checkbox steps; later tasks consume only paths created earlier.

Run the path and type consistency check:

```bash
python3 - <<'PY'
from pathlib import Path

plan = Path("docs/plans/PHASE-01-ENVIRONMENT.md").read_text(encoding="utf-8")
required_paths = (
    "scripts/verify_documentation_gate.sh",
    "scripts/audit_host.sh",
    "scripts/install_host.sh",
    "scripts/rollback_host.sh",
    "scripts/download_phase1_resources.sh",
    "scripts/verify_phase1_resources.sh",
    "scripts/setup_ros_workspace.sh",
    "scripts/setup_python_env.sh",
    "scripts/setup_gateway_env.sh",
    "scripts/setup_web_env.sh",
    "scripts/smoke_headless_egl.sh",
    "scripts/verify_environment.sh",
    "scripts/check_environment_seal.sh",
    "scripts/lib/venv_provenance.py",
    "requirements.lock",
    "requirements-web.lock",
    "web/frontend/package-lock.json",
    "artifacts/environment/dpkg-packages.tsv",
    "artifacts/environment/SHA256SUMS",
)
for path in required_paths:
    assert plan.count(path) >= 2, path
assert sum(line.startswith("### Task ") for line in plan.splitlines()) == 11
assert "--evidence-dir" in plan
assert ".venv-web" in plan and ".venv" in plan
print("plan-path-type-consistency: PASS")
PY
```

Expected: exactly `plan-path-type-consistency: PASS`.

Run the unresolved-marker scan:

```bash
scan_pattern='T''BD|T''ODO|F''IXME|PLACE''HOLDER|待''定|待''补|以后再''定'
if rg -n -i "$scan_pattern" docs/plans/PHASE-01-ENVIRONMENT.md; then
  exit 1
else
  printf '%s\n' 'plan-unresolved-marker-scan: PASS'
fi
```

Expected: exactly `plan-unresolved-marker-scan: PASS`.

Run the command-safety scan:

```bash
python3 - <<'PY'
from pathlib import Path

text = Path("docs/plans/PHASE-01-ENVIRONMENT.md").read_text(encoding="utf-8")
unsafe_command_prefixes = (
    "rm -rf",
    "git reset --hard",
    "git checkout --",
    "sudo pip",
    "sudo apt-get autoremove",
)
for line_number, line in enumerate(text.splitlines(), 1):
    stripped = line.lstrip()
    for prefix in unsafe_command_prefixes:
        assert not stripped.startswith(prefix), (line_number, prefix)
assert "apt-get remove --no-auto-remove" in text
assert "env -u DISPLAY gz sim -s -r --headless-rendering" in text
print("plan-command-safety: PASS")
PY
```

Expected: exactly `plan-command-safety: PASS`.

Before requesting the final independent plan review, mechanically extract every exact tracked-file code block into a fresh temporary Git repository and run the guarded controller behavior probes:

```bash
review_id="$(python3 -c 'import uuid; print(uuid.uuid4())')"
review_root="/tmp/phase1-plan-review-$review_id"
test ! -e "$review_root"
install -d -m 0700 "$review_root"
cleanup_plan_review() {
  case "$review_root" in
    /tmp/phase1-plan-review-*) find "$review_root" -depth -delete ;;
    *) return 1 ;;
  esac
}
trap cleanup_plan_review EXIT
python3 - "$review_root" <<'PY'
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
lines = Path("docs/plans/PHASE-01-ENVIRONMENT.md").read_text(encoding="utf-8").splitlines()
pattern = re.compile(
    r"^Create `([^`]+)`(?: with this exact(?: tab-separated)? content,?[^:]*|):$"
)
created = []
for index, line in enumerate(lines):
    match = pattern.match(line)
    if not match:
        continue
    relative = match.group(1)
    start = index + 1
    while start < len(lines) and not lines[start].startswith("```"):
        start += 1
    assert start < len(lines), relative
    fence = lines[start][: len(lines[start]) - len(lines[start].lstrip("`"))]
    end = start + 1
    while end < len(lines) and lines[end] != fence:
        end += 1
    assert end < len(lines), relative
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines[start + 1 : end]) + "\n", encoding="utf-8")
    created.append(relative)
assert len(created) == 40, created
print("plan-extracted-files: PASS: 40")
PY
(
  cd "$review_root"
  chmod +x scripts/*.sh tests/environment/*.sh tests/environment/fixtures/fake_host_command.py
  git init -q
  git config user.name 'Phase 1 Plan Validator'
  git config user.email validator@example.invalid
  git add .
  git commit -qm baseline
  bash tests/environment/test_audit_host.sh
  bash tests/environment/test_install_host.sh
  bash tests/environment/test_phase1_resources.sh
  bash tests/environment/test_verify_environment.sh
)
printf '%s\n' 'phase1-plan-controller-behavior: PASS'
trap - EXIT
cleanup_plan_review
```

Expected final lines include `audit-host-test: PASS`, `install-host-test: PASS`, `phase1-resource-static-test: PASS`, `verify-environment-test: PASS`, and `phase1-plan-controller-behavior: PASS`. Negative cases intentionally print rejection messages or Python assertion tracebacks before their enclosing test reaches its PASS line.

Only after these behavior probes and all syntax/static checks pass may the final independent review begin. Record the reviewed plan SHA-256 and the final Critical/Important/Minor counts. In `.superpowers/sdd/task-5-report.md`, explicitly mark any earlier narrower “0 findings” conclusion as superseded by the later controller-level review and its remediation; never present the earlier conclusion as the final review result.

Run final Markdown and diff checks:

```bash
git diff --check
git diff -- docs/plans/PHASE-01-ENVIRONMENT.md
```

Expected: `git diff --check` has no output; the diff contains only this Phase 1 plan during plan authoring. During implementation, each task's diff contains only that task's declared paths.

## Completion Conditions

Phase 1 is complete only when all eleven task commits exist, the Task 10 implementation commit has an immutable verifier result with `result.json.status` equal to `passed`, both environment SHA manifests verify, no forbidden package is installed, the exact versions match `docs/VERSION_MATRIX.md`, CUDA is available, the colcon commands pass, the frontend production build passes, and a Gazebo RGB frame is proven with `DISPLAY` removed. The later Task 11 HEAD must differ from that verified implementation commit only by `docs/PROJECT_STATUS.md` and `docs/HANDOFF.md`; those documents must explicitly distinguish the two commits and truthfully identify Phase 2 as next.

Do not continue directly into product-world code from an unreviewed working tree. The next session first writes and approves the Phase 2 Gazebo world implementation plan, then implements it test-first against the locked environment produced here.
