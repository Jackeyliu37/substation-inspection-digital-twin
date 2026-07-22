# Phase 1 Environment Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and prove a reproducible Ubuntu 24.04 environment for ROS 2 Jazzy, Gazebo Harmonic OGRE2/EGL headless rendering, CUDA-enabled YOLO11n development, the FastAPI ROS Gateway, and the locked Next.js frontend before Phase 2 world development begins.

**Architecture:** A documentation gate runs before the first host mutation. Small idempotent scripts then audit the host, install only the approved repositories and packages, acquire early external resources into `/var/lib/substation`, build an empty ROS workspace baseline, create isolated AI and Gateway virtual environments, create the frontend baseline, exercise Gazebo through EGL with `DISPLAY` removed, and consolidate every result into one checksummed acceptance directory. Git stores scripts, tests, lock files, manifests, source code, and checksums; large downloads, virtual environments, build trees, logs, model files, and acceptance payloads stay on the Ubuntu server.

**Tech Stack:** Ubuntu 24.04 LTS, Bash, Python 3.12, ROS 2 Jazzy Jalisco, `colcon`, Gazebo Harmonic `gz-sim 8.x`, OGRE2/EGL, NVIDIA driver `>=560.35.05`, PyTorch 2.12.1 CUDA 12.6, Ultralytics 8.4.104, FastAPI 0.139.2, Node.js 24.18.0, npm, Next.js 16.2.11, React 19.2.8, TypeScript 6.0.3, Git, SHA-256.

## Global Constraints

- The root project plan is the scope authority. This phase creates only the environment, repository baselines, early immutable resource downloads, tests, and evidence required by Phase 1 acceptance.
- Use Ubuntu 24.04 LTS, ROS 2 Jazzy Jalisco, Gazebo Harmonic `gz-sim 8.x`, and Python 3.12. Stop if the host or resolved upstream versions contradict `docs/VERSION_MATRIX.md`.
- Preserve the approved ROS upstream identities: `ros_gz 1.0.23-1`, Navigation2 `1.3.12-1`, SLAM Toolbox `2.8.5-1`, TurtleBot3 core `2.3.6-1`, and TurtleBot3 simulation `2.3.7-1`; full Noble package revisions enter the Debian manifest.
- Gazebo rendering is OGRE2/EGL headless only. Ubuntu desktop metapackages, GNOME/KDE shells, Xorg servers, display managers, NoMachine, Xvfb, and VirtualGL are forbidden.
- Do not introduce ROS 1, Gazebo Classic, another ROS distribution, Conda CUDA, Ubuntu `nvidia-cuda-toolkit`, a global `sudo pip`, or pip CUDA packages outside the approved PyTorch CUDA 12.6 wheel source.
- The AI environment is repository-root `.venv`; the Gateway environment is repository-root `.venv-web`; both use `python3 -m venv --system-site-packages` so ROS `rclpy` remains available.
- The product browser boundary is unchanged: normal users eventually access only `http://ros-server/`; browsers never connect to DDS; Gateway and frontend processes remain loopback-only; Foxglove remains a separate read-only diagnostic path.
- The target server operator is the non-root account `substation`, and its checkout is `/home/substation/substation-inspection-digital-twin`, as fixed by `docs/DEPLOYMENT.md`. Authoring this plan from another checkout does not relax that execution precondition.
- Safety detection, equipment detection, defect classification, and meter reading stay separate. The only Phase 1 model download is the immutable YOLO11n base weight; it is not a production model.
- Instrument data remains Gazebo-generated only. Phase 1 does not add, download, or describe an external meter dataset.
- Every manually acquired external payload in this phase, specifically the Node.js archive and `yolo11n.pt`, is written below `/var/lib/substation`, receives a SHA-256 and byte count, and is recorded in `artifacts/environment/resource-downloads.tsv`. Large payloads never enter Git.
- Dataset source downloads are not silently mixed into the environment phase. `config/environment/resource-sources.tsv` records their immutable identities and the later Phase 4 sequence. Phase 1 immediately acquires Node.js and `yolo11n.pt`; Debian resolution is recorded in the Debian package manifest, while Python and npm resolution is recorded in their hashed lock files and reviewed freeze/version manifests.
- `InsPLAD` is not fetched from a floating branch. Its later downloader must first resolve and commit one complete 40-character revision as required by `docs/DATA_AND_MODELS.md`.
- Do not modify original public data. Do not commit raw/derived datasets, weights, virtual environments, `node_modules`, ROS build/install/log trees, acceptance evidence, service logs, or rosbag2.
- Tests precede implementation in every task. A test is first run against the missing or incomplete implementation and must fail for the stated reason; after the minimal implementation it must pass.
- Initial host snapshots and source backups are write-once, and the complete evidence tree becomes immutable after its final recursive `SHA256SUMS` is published. Rollback preserves `/var/lib/substation/evidence`; it reverts tracked code or restores only explicitly recorded files/packages.
- Never remove packages with automatic dependency cleanup. Package rollback may remove only package names recorded as newly installed by `scripts/install_host.sh`, using `apt-get remove --no-auto-remove` after human review.
- Do not overwrite existing virtual environments, toolchains, manifests, repository files, or apt source/key files. Refuse, back up to the active evidence directory, or move the exact owned path to a timestamped quarantine name.
- Any version mismatch, missing SHA-256, forbidden package, capacity below 80 GiB free or 16 GiB memory, failed CUDA check, failed colcon command, failed frontend build, or failed EGL probe is a hard failure.
- Normal completion updates `docs/PROJECT_STATUS.md` and `docs/HANDOFF.md` only after the consolidated verifier passes. The sole earlier exception is a required pre-reboot `docs/HANDOFF.md` update when Task 3 returns `REBOOT_REQUIRED`; final documents distinguish the verified implementation commit from the later documentation-only synchronization commit.

---

## Exact Phase 1 File Map

### Tracked files created by this plan

| Path | Single responsibility |
|---|---|
| `.gitignore` | Exclude local virtual environments, Node/ROS build trees, local run state, large resource payloads, and runtime evidence while leaving manifests and checksums trackable. |
| `config/environment/apt-packages.txt` | Exact explicit Debian package request set for the Ubuntu, ROS 2, Gazebo, navigation, build, SQLite, Nginx, and diagnostic baseline. |
| `config/environment/forbidden-packages.regex` | Anchored installed-package name patterns that make headless acceptance fail. |
| `config/environment/resource-sources.tsv` | Source identity and phase sequence for Node.js, YOLO11n, public datasets, and Gazebo synthetic resources. |
| `scripts/lib/environment_common.sh` | Shared argument, repository-root, evidence-path, command, and SHA-256 helpers used by Phase 1 scripts. |
| `scripts/verify_documentation_gate.sh` | Re-run the Phase 0 document gate without changing the host. |
| `scripts/init_phase1_run.sh` | Create one acceptance run directory after the document gate passes and write ignored `.phase1-run.env`. |
| `scripts/audit_host.sh` | Read-only OS, architecture, GPU, driver, memory, disk, forbidden-package, and session audit. |
| `scripts/install_host.sh` | Add only official ROS/Gazebo apt sources, validate locked candidates before installing them, preserve write-once before/after evidence across a reboot resume, install the approved package set and recommended NVIDIA driver when required, and leave services stopped. |
| `scripts/download_phase1_resources.sh` | Download and verify Node.js 24.18.0 and YOLO11n v8.4.0 into controlled server storage. |
| `scripts/setup_ros_workspace.sh` | Source Jazzy and run the canonical colcon build/test/test-result baseline. |
| `scripts/compile_requirements.sh` | Resolve one Python input file to a fully hashed lock with a short-lived pinned `pip-tools` resolver environment. |
| `scripts/setup_python_env.sh` | Create `.venv`, install the AI lock with `--require-hashes`, and prove the locked CUDA stack. |
| `scripts/setup_gateway_env.sh` | Create `.venv-web`, install the Gateway lock with `--require-hashes`, and prove `rclpy` plus locked Web packages. |
| `scripts/write_frontend_manifest.py` | Write the exact frontend dependency manifest while taking the npm version only from Node.js 24.18.0. |
| `scripts/setup_web_env.sh` | Install the verified Node toolchain under `/opt/substation/toolchains`, generate `package-lock.json`, run `npm ci`, and run the production build. |
| `scripts/smoke_headless_egl.sh` | Launch a minimal Gazebo camera world with `DISPLAY` removed and prove a rendered RGB frame arrives through Gazebo Transport. |
| `scripts/capture_environment_lock.sh` | Capture the reviewed Debian/Python/npm/resource environment into tracked text manifests and a stable SHA-256 file. |
| `scripts/verify_environment.sh` | Canonical Phase 1 acceptance entry point with per-command logs/metadata and recursive evidence checksum required by `docs/TEST_ACCEPTANCE.md`. |
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
| `tests/environment/test_phase1_resources.sh` | Resource source identity, checksum capture, and Git-exclusion contract test. |
| `tests/environment/test_ros_workspace.sh` | Jazzy sourcing and canonical empty-workspace colcon contract test. |
| `tests/environment/test_ai_environment.sh` | AI lock, version, CUDA, and system-site-packages contract test. |
| `tests/environment/test_gateway_environment.sh` | Gateway lock, exact versions, and `rclpy` contract test. |
| `tests/environment/test_web_environment.sh` | Node/npm ownership, exact direct versions, lockfile v3, `npm ci`, and build contract test. |
| `tests/environment/test_headless_egl.sh` | EGL smoke script and sensor-frame contract test. |
| `tests/environment/test_verify_environment.sh` | Consolidated verifier outputs, schema, checksum, and failure-closed contract test. |
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
| `docs/HANDOFF.md` | Record a deterministic pre-reboot resume state when required, then the final Phase 2 resume entry. |

### Runtime-only paths created by this plan

| Path | Contents and ownership |
|---|---|
| `.phase1-run.env` | Ignored shell exports for the active `PHASE1_RUN_ID` and `PHASE1_EVIDENCE_ROOT`; contains no secret. |
| `.venv`, `.venv-web` | Local Python environments; ignored and never deployed as source. |
| `build/`, `install/`, `log/` | ROS workspace outputs; ignored. |
| `web/frontend/node_modules/`, `web/frontend/.next/` | npm install and Next.js build outputs; ignored. |
| `/opt/substation/toolchains/node-v24.18.0` | Verified immutable Node.js toolchain; root-owned, world-readable. |
| `/opt/substation/toolchains/node-current` | Symlink to the verified 24.18.0 toolchain. |
| `/var/lib/substation/downloads/node/24.18.0/` | Node tarball and official checksum list. |
| `/var/lib/substation/models/base/$YOLO_BASE_SHA256/` | YOLO11n base weight and source metadata, keyed by its actual SHA-256. |
| `/var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment/` | Gate, audit, install, resource, colcon, Python, npm, GPU, EGL, JSON result, and checksum evidence. |

### Required final evidence files

The consolidated verifier must leave these non-empty files below `$PHASE1_EVIDENCE_ROOT`: `acceptance_run_id.txt`, `documentation-gate.log`, `host-audit.json`, `install-host.log`, `install-state.env`, `install-complete.env`, `apt-candidates.tsv`, `apt-sources-before/inventory.tsv`, `managed-files-after.tsv`, `host-install-version-changes.tsv`, `ros-archive-key.sha256`, `gazebo-archive-key.sha256`, `dpkg-before.tsv`, `dpkg-after.tsv`, `environment.json`, `dpkg-packages.tsv`, `ai-pip-freeze.txt`, `gateway-pip-freeze.txt`, `node-npm-versions.txt`, `resource-downloads.tsv`, `gpu.txt`, `egl.log`, `forbidden-packages.txt`, `disk-memory.txt`, `colcon-build.log`, `colcon-test.log`, `colcon-test-result.log`, `frontend-build.log`, per-command logs and JSON metadata under `commands/`, `result.json`, and `SHA256SUMS`. `host-install-new-packages.txt` is also mandatory but may be empty on an already-provisioned compliant host. If a reboot occurred, `install-resume.env` is mandatory and remains as immutable history. The recursive checksum includes every file under nested directories such as `apt-sources-before/` and `commands/`.

## Execution Rules for Every Task

1. Work from the repository root returned by `git rev-parse --show-toplevel`; do not hard-code the current developer's home directory into scripts or manifests.
2. Before editing, run `git status --short` and preserve unrelated changes. Stage only the paths listed by the current task.
3. Use `apply_patch` for tracked text changes. Machine-generated lock files are created only by the exact resolver commands in this plan and then reviewed with `git diff --check` and focused validators.
4. After Task 1 initializes the run, every command that writes runtime evidence begins with:

   ```bash
   source .phase1-run.env
   test -n "$PHASE1_RUN_ID"
   test -d "$PHASE1_EVIDENCE_ROOT"
   ```

5. Each test command is piped through `tee` only to the exact current evidence file. `PIPESTATUS[0]` is checked when the tested command's exit status matters.
6. Each task ends with its focused verification and one focused commit. Do not combine task commits.
7. If an authority conflict or locked-version mismatch appears, stop, save the command output in the active evidence directory, update the authority document through the repository's ADR/synchronization process, and do not continue this plan on an inferred interpretation.

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
- Produces: `bash scripts/verify_documentation_gate.sh`, ignored `.phase1-run.env`, and `$PHASE1_EVIDENCE_ROOT/documentation-gate.log`.

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
    /var/lib/substation/evidence/acceptance/*/01-environment) ;;
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
    phase0 = contract.split("## 4. Phase 0 文档门槛（当前可运行）", 1)[1].split(
        "## 5. Phase 1 主机与环境验收（未来）", 1
    )[0]
except IndexError as error:
    raise SystemExit("documentation-gate: Phase 0 authority section not found") from error

blocks = re.findall(r"```bash\n(.*?)\n```", phase0, flags=re.DOTALL)
if len(blocks) != 2:
    raise SystemExit(
        f"documentation-gate: expected exactly two Phase 0 Bash blocks, found {len(blocks)}"
    )
for index, block in enumerate(blocks, 1):
    completed = subprocess.run(["bash", "-c", block], text=True)
    if completed.returncode != 0:
        raise SystemExit(
            f"documentation-gate: TEST_ACCEPTANCE section 4 block {index} failed "
            f"with exit {completed.returncode}"
        )
PY

printf '%s\n' 'documentation-gate: PASS'
```

The validator first enforces the complete required-file/tracked-file gate from `docs/TEST_ACCEPTANCE.md` section 4.3. It then extracts and executes exactly the two Bash blocks in section 4, so the full baseline-literal validator, row-specific dataset license checks, unresolved-marker scan, interface scan, browser/DDS/Foxglove boundary scan, and `git diff --check` cannot drift into an abbreviated duplicate. It reads repository files and Git metadata only; it does not call `sudo`, package managers, network clients, ROS, Gazebo, or services.

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
test "$(id -un)" = substation
test "$repo_root" = /home/substation/substation-inspection-digital-twin
test ! -e .phase1-run.env || {
  printf '%s\n' '.phase1-run.env already exists; source it instead of creating a second run' >&2
  exit 1
}

phase1_run_id="$(python3 -c 'import uuid; print(uuid.uuid4())')"
phase1_evidence_root="/var/lib/substation/evidence/acceptance/${phase1_run_id}/01-environment"
operator_user="$(id -un)"
operator_group="$(id -gn)"

sudo install -d -m 0750 -o "$operator_user" -g "$operator_group" \
  /var/lib/substation \
  /var/lib/substation/evidence \
  /var/lib/substation/evidence/acceptance \
  "/var/lib/substation/evidence/acceptance/${phase1_run_id}" \
  "$phase1_evidence_root"
install -m 0640 "$gate_log" "$phase1_evidence_root/documentation-gate.log"
printf '%s\n' "$phase1_run_id" > "$phase1_evidence_root/acceptance_run_id.txt"
git rev-parse HEAD > "$phase1_evidence_root/git_commit_at_start.txt"

umask 077
printf 'export PHASE1_RUN_ID=%q\n' "$phase1_run_id" > .phase1-run.env
printf 'export PHASE1_EVIDENCE_ROOT=%q\n' "$phase1_evidence_root" >> .phase1-run.env

printf 'PHASE1_RUN_ID=%s\n' "$phase1_run_id"
printf 'PHASE1_EVIDENCE_ROOT=%s\n' "$phase1_evidence_root"
```

Run:

```bash
chmod +x scripts/lib/environment_common.sh scripts/verify_documentation_gate.sh scripts/init_phase1_run.sh
gate_log="$(mktemp --tmpdir=/tmp)"
bash scripts/verify_documentation_gate.sh | tee "$gate_log"
bash scripts/init_phase1_run.sh --gate-log "$gate_log"
unlink -- "$gate_log"
source .phase1-run.env
test -f "$PHASE1_EVIDENCE_ROOT/documentation-gate.log"
```

Expected: the validator prints exactly `documentation-gate: PASS` as its final line; initialization prints a UUID and an evidence path ending in `/01-environment`; the copied gate log is non-empty.

- [ ] **Step 5: Re-run the test and record Task 1 evidence**

Run:

```bash
source .phase1-run.env
bash tests/environment/test_documentation_gate.sh | tee "$PHASE1_EVIDENCE_ROOT/test-documentation-gate.log"
test "${PIPESTATUS[0]}" -eq 0
```

Expected: one line `documentation-gate: PASS`, exit 0, and a non-empty test log.

Evidence: `$PHASE1_EVIDENCE_ROOT/documentation-gate.log` and `$PHASE1_EVIDENCE_ROOT/test-documentation-gate.log`.

Safe rollback: preserve the acceptance directory; move `.phase1-run.env` to `.phase1-run.env.rollback-$(date -u +%Y%m%dT%H%M%SZ)`; revert only this task's tracked commit. Do not remove the evidence directory.

- [ ] **Step 6: Commit Task 1**

```bash
git add .gitignore scripts/lib/environment_common.sh scripts/verify_documentation_gate.sh scripts/init_phase1_run.sh tests/environment/test_documentation_gate.sh
git diff --cached --check
git commit -m "feat: add phase one documentation gate"
```

Expected: one commit containing only the five listed paths.

---

### Task 2: Read-Only Host Audit

**Files:**
- Create: `config/environment/forbidden-packages.regex`
- Create: `scripts/audit_host.sh`
- Create: `tests/environment/test_audit_host.sh`

**Interfaces:**
- Consumes: `/etc/os-release`, `/proc/meminfo`, repository filesystem statistics, `dpkg-query`, `lspci` when present, and `nvidia-smi` when present.
- Produces: JSON on stdout, exit 0 only for a compliant host in enforcement mode, and `$PHASE1_EVIDENCE_ROOT/host-audit.json`.

- [ ] **Step 1: Write the failing audit test**

Create `tests/environment/test_audit_host.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

test -x scripts/audit_host.sh
test -f config/environment/forbidden-packages.regex
audit_json="$(bash scripts/audit_host.sh --report-only)"
python3 -c '
import json, sys
data = json.load(sys.stdin)
required = {"schema_version", "status", "os", "architecture", "memory_bytes", "disk_free_bytes", "gpu", "forbidden_packages", "checks"}
assert required <= data.keys()
assert data["schema_version"] == 1
assert isinstance(data["forbidden_packages"], list)
' <<<"$audit_json"
! rg -n 'sudo|apt-get|apt install|systemctl|curl|wget|tee /etc' scripts/audit_host.sh
```

Run:

```bash
chmod +x tests/environment/test_audit_host.sh
bash tests/environment/test_audit_host.sh
```

Expected: exit nonzero because `scripts/audit_host.sh` and the forbidden-package policy do not exist.

- [ ] **Step 2: Add the exact forbidden-package policy**

Create `config/environment/forbidden-packages.regex` with this exact content:

```text
^(ubuntu-desktop|ubuntu-desktop-minimal|kubuntu-desktop|xubuntu-desktop|lubuntu-desktop|ubuntu-unity-desktop)$
^(gnome-shell|plasma-desktop|kde-plasma-desktop)$
^(xorg|xserver-xorg|xserver-xorg-core|xserver-xorg-video-all)$
^(gdm3|sddm|lightdm)$
^(nomachine|xvfb|virtualgl)$
```

- [ ] **Step 3: Implement the audit in Python embedded by a read-only Bash entry point**

Create `scripts/audit_host.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

mode=enforce
if test "$#" -eq 1 && test "$1" = --report-only; then
  mode=report-only
elif test "$#" -ne 0; then
  printf '%s\n' 'usage: bash scripts/audit_host.sh [--report-only]' >&2
  exit 2
fi

repo_root="$(git rev-parse --show-toplevel)"
export PHASE1_AUDIT_REPO_ROOT="$repo_root"
export PHASE1_AUDIT_MODE="$mode"

python3 - <<'PY'
import json
import os
import platform
import pwd
import re
import shutil
import subprocess
from pathlib import Path

repo = Path(os.environ["PHASE1_AUDIT_REPO_ROOT"])
mode = os.environ["PHASE1_AUDIT_MODE"]

os_release = {}
for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
    if "=" in line:
        key, value = line.split("=", 1)
        os_release[key] = value.strip().strip('"')

meminfo = {}
for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
    key, value = line.split(":", 1)
    meminfo[key] = int(value.strip().split()[0]) * 1024

disk_free = shutil.disk_usage(repo).free
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
forbidden = sorted({name for name in installed_packages if any(pattern.fullmatch(name) for pattern in patterns)})

gpu_present = any(
    vendor.read_text(encoding="utf-8").strip().lower() == "0x10de"
    for vendor in Path("/sys/bus/pci/devices").glob("*/vendor")
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
checks = {
    "ubuntu_24_04": os_release.get("ID") == "ubuntu" and os_release.get("VERSION_ID") == "24.04",
    "architecture_x86_64": platform.machine() == "x86_64",
    "memory_at_least_16_gib": meminfo.get("MemTotal", 0) >= 16 * 1024**3,
    "disk_at_least_80_gib": disk_free >= 80 * 1024**3,
    "nvidia_gpu_present": gpu_present,
    "no_forbidden_packages": not forbidden,
    "operator_user_substation": current_user == "substation",
    "repository_path_matches_deployment": str(repo) == "/home/substation/substation-inspection-digital-twin",
}

status = "passed" if all(checks.values()) else "failed"
document = {
    "schema_version": 1,
    "status": status,
    "os": {"id": os_release.get("ID"), "version_id": os_release.get("VERSION_ID"), "pretty_name": os_release.get("PRETTY_NAME")},
    "architecture": platform.machine(),
    "memory_bytes": meminfo.get("MemTotal", 0),
    "disk_free_bytes": disk_free,
    "repository": str(repo),
    "user": current_user,
    "display_set": "DISPLAY" in os.environ,
    "gpu": {
        "present": gpu_present,
        "name": gpu_name,
        "driver_version": driver_version,
        "required_driver_floor": "560.35.05",
        "driver_meets_floor": driver_meets_floor,
        "driver_install_required": not driver_meets_floor,
    },
    "forbidden_packages": forbidden,
    "checks": checks,
}
print(json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2))
if mode == "enforce" and status != "passed":
    raise SystemExit(1)
PY
```

- [ ] **Step 4: Run the test and the enforced precondition**

```bash
chmod +x scripts/audit_host.sh tests/environment/test_audit_host.sh
bash tests/environment/test_audit_host.sh
source .phase1-run.env
bash scripts/audit_host.sh | tee "$PHASE1_EVIDENCE_ROOT/host-audit.json"
test "${PIPESTATUS[0]}" -eq 0
```

Expected test output: none and exit 0. Expected enforced JSON: `"status": "passed"`, Ubuntu `24.04`, architecture `x86_64`, user `substation`, repository `/home/substation/substation-inspection-digital-twin`, at least `17179869184` memory bytes, at least `85899345920` free bytes, an NVIDIA GPU, and an empty forbidden package array. `gpu.driver_install_required` is true when the driver is absent or below `560.35.05`; Task 3 is allowed to correct that installable gap, while Task 10 enforces the final floor.

If enforcement fails, stop before Task 3. The JSON is the evidence; do not "fix" a capacity or GPU failure by weakening thresholds.

Evidence: `$PHASE1_EVIDENCE_ROOT/host-audit.json`; the report preserves every failed boolean when enforcement stops the phase.

Safe rollback: this task has no host mutation. Revert only its tracked commit; preserve `host-audit.json`.

- [ ] **Step 5: Commit Task 2**

```bash
git add config/environment/forbidden-packages.regex scripts/audit_host.sh tests/environment/test_audit_host.sh
git diff --cached --check
git commit -m "feat: add read only host audit"
```

Expected: one commit containing only the three listed paths.

---

### Task 3: Official Apt, ROS 2 Jazzy, Gazebo Harmonic, and NVIDIA Installer

**Files:**
- Create: `config/environment/apt-packages.txt`
- Create: `scripts/install_host.sh`
- Create: `tests/environment/test_install_host.sh`
- Modify conditionally: `docs/HANDOFF.md` only when an NVIDIA driver change requires a reboot, once immediately before reboot and once immediately after successful resume

**Interfaces:**
- Consumes: a passing enforced host audit, Ubuntu Noble official repositories, `packages.ros.org`, `packages.osrfoundation.org`, and `ubuntu-drivers`.
- Produces: installed approved Debian packages, locked-candidate evidence, write-once source/key backups and package snapshots under `$PHASE1_EVIDENCE_ROOT`, stopped Nginx, initialized rosdep, and an explicit resumable reboot boundary when required.

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
rg -F $'ros-jazzy-ros-gz\t1.0.23-1' scripts/install_host.sh
rg -F $'ros-jazzy-navigation2\t1.3.12-1' scripts/install_host.sh
rg -F $'ros-jazzy-nav2-bringup\t1.3.12-1' scripts/install_host.sh
rg -F $'ros-jazzy-slam-toolbox\t2.8.5-1' scripts/install_host.sh
rg -F $'ros-jazzy-turtlebot3\t2.3.6-1' scripts/install_host.sh
rg -F $'ros-jazzy-turtlebot3-simulations\t2.3.7-1' scripts/install_host.sh
rg -F 'install-resume.env' scripts/install_host.sh
rg -F 'install-complete.env' scripts/install_host.sh
rg -F 'host-install-version-changes.tsv' scripts/install_host.sh
rg -F 'managed-files-after.tsv' scripts/install_host.sh
rg -F 'nginx_unit_present_before=' scripts/install_host.sh
rg -F $'source_path\texisted\tmode\tsha256\tbackup_file' scripts/install_host.sh
```

Run:

```bash
chmod +x tests/environment/test_install_host.sh
bash tests/environment/test_install_host.sh
```

Expected: exit nonzero because the package list and installer do not exist.

- [ ] **Step 2: Add the exact explicit package request set**

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
python3-venv
python3-vcstool
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
ubuntu-drivers-common
yamllint
```

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
  printf '%s\n' 'usage: bash scripts/install_host.sh --plan | --apply --evidence-dir /var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment' >&2
  exit 2
fi

evidence_dir="$3"
source scripts/lib/environment_common.sh
environment_require_evidence_dir "$evidence_dir"
bash scripts/audit_host.sh >/dev/null

apt_sources_before="$evidence_dir/apt-sources-before"
state_file="$evidence_dir/install-state.env"
resume_marker="$evidence_dir/install-resume.env"
complete_marker="$evidence_dir/install-complete.env"
before_packages="$evidence_dir/dpkg-before.tsv"
after_packages="$evidence_dir/dpkg-after.tsv"
new_packages="$evidence_dir/host-install-new-packages.txt"
version_changes="$evidence_dir/host-install-version-changes.tsv"
candidate_file="$evidence_dir/apt-candidates.tsv"
managed_after="$evidence_dir/managed-files-after.tsv"
managed_paths=(
  /etc/apt/sources.list.d/ros2.list
  /etc/apt/sources.list.d/gazebo-stable.list
  /usr/share/keyrings/ros-archive-keyring.gpg
  /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
  /etc/default/locale
  /etc/ros/rosdep/sources.list.d/20-default.list
)

key_work=
list_work=
capture_work=
inventory_work=
cleanup() {
  local path
  for path in "$key_work" "$list_work" "$capture_work" "$inventory_work"; do
    if test -n "$path" && test -e "$path"; then
      unlink -- "$path"
    fi
  done
}
trap cleanup EXIT

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

validate_installed_stack() {
  driver_is_ready
  source /opt/ros/jazzy/setup.bash
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
  printf 'source_path\texisted_after\tmode\tsha256\n' > "$capture_work"
  for source_path in "${managed_paths[@]}"; do
    if test -f "$source_path"; then
      printf '%s\t1\t%s\t%s\n' \
        "$source_path" "$(stat -c '%a' "$source_path")" "$(environment_sha256 "$source_path")" \
        >> "$capture_work"
    else
      printf '%s\t0\t-\t-\n' "$source_path" >> "$capture_work"
    fi
  done
  install -m 0640 "$capture_work" "$managed_after"
  unlink -- "$capture_work"
  capture_work=
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
  python3 - "$apt_sources_before/inventory.tsv" "$managed_after" <<'PY'
import csv
import hashlib
import sys
from pathlib import Path

inventory_path, after_path = map(Path, sys.argv[1:])
expected_paths = {
    "/etc/apt/sources.list.d/ros2.list",
    "/etc/apt/sources.list.d/gazebo-stable.list",
    "/usr/share/keyrings/ros-archive-keyring.gpg",
    "/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg",
    "/etc/default/locale",
    "/etc/ros/rosdep/sources.list.d/20-default.list",
}

with inventory_path.open(encoding="utf-8", newline="") as handle:
    inventory = list(csv.DictReader(handle, delimiter="\t"))
assert {row["source_path"] for row in inventory} == expected_paths
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
    path = Path(row["source_path"])
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

verify_completed_state() {
  test -s "$state_file"
  test -s "$before_packages"
  test -s "$apt_sources_before/inventory.tsv"
  test -s "$candidate_file"
  test -s "$after_packages"
  test -f "$new_packages"
  test -s "$version_changes"
  test -s "$managed_after"
  grep -Fxq 'state=INITIAL_INSTALL_STARTED' "$state_file"
  grep -Fxq 'state=PASS' "$complete_marker"
  if test -e "$resume_marker"; then
    grep -Fxq 'state=REBOOT_REQUIRED' "$resume_marker"
  fi
  verify_managed_evidence
  validate_installed_stack
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

if test -s "$resume_marker"; then
  grep -Fxq 'state=REBOOT_REQUIRED' "$resume_marker"
  test -s "$state_file"
  test -s "$before_packages"
  test -s "$apt_sources_before/inventory.tsv"
  test -s "$candidate_file"
  test ! -e "$after_packages"
  test ! -e "$new_packages"
  test ! -e "$version_changes"
  test ! -e "$managed_after"
  driver_is_ready || {
    printf '%s\n' 'rebooted NVIDIA driver is absent or below 560.35.05' >&2
    exit 1
  }
  mark_complete
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
  "$evidence_dir/ros-archive-key.sha256" \
  "$evidence_dir/gazebo-archive-key.sha256" \
  "$after_packages" \
  "$new_packages" \
  "$version_changes" \
  "$managed_after"; do
  if test -e "$initial_artifact"; then
    printf 'incomplete-install-evidence-requires-review: %s\n' "$initial_artifact" >&2
    exit 1
  fi
done

universe_present=0
if apt-cache policy | grep -q 'noble/universe'; then
  universe_present=1
fi
nginx_unit_present_before=0
nginx_active_before=absent
nginx_enabled_before=absent
if systemctl list-unit-files --type=service --no-legend nginx.service 2>/dev/null \
  | grep -q '^nginx\.service'; then
  nginx_unit_present_before=1
  nginx_active_before="$(systemctl is-active nginx.service 2>/dev/null || true)"
  nginx_enabled_before="$(systemctl is-enabled nginx.service 2>/dev/null || true)"
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
for source_path in "${managed_paths[@]}"; do
  if test -f "$source_path"; then
    backup_name="$(printf '%s' "$source_path" | sed 's#^/##; s#/#__#g')"
    original_mode="$(stat -c '%a' "$source_path")"
    install -m 0640 "$source_path" "$apt_sources_before/$backup_name"
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

sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg locales software-properties-common ubuntu-drivers-common
if test "$universe_present" -eq 0; then
  sudo add-apt-repository -y universe
fi

key_work="$(mktemp --tmpdir=/tmp)"
list_work="$(mktemp --tmpdir=/tmp)"
curl -fsSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o "$key_work"
environment_sha256 "$key_work" > "$evidence_dir/ros-archive-key.sha256"
sudo install -m 0644 "$key_work" /usr/share/keyrings/ros-archive-keyring.gpg
architecture="$(dpkg --print-architecture)"
printf 'deb [arch=%s signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu noble main\n' "$architecture" > "$list_work"
sudo install -m 0644 "$list_work" /etc/apt/sources.list.d/ros2.list

curl -fsSL https://packages.osrfoundation.org/gazebo.gpg -o "$key_work"
environment_sha256 "$key_work" > "$evidence_dir/gazebo-archive-key.sha256"
sudo install -m 0644 "$key_work" /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
printf 'deb [arch=%s signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable noble main\n' "$architecture" > "$list_work"
sudo install -m 0644 "$list_work" /etc/apt/sources.list.d/gazebo-stable.list

sudo apt-get update
capture_work="$(mktemp --tmpdir=/tmp)"
printf 'package\texpected_upstream\tcandidate\n' > "$capture_work"
while IFS=$'\t' read -r package expected; do
  candidate="$(apt-cache policy "$package" | awk '$1 == "Candidate:" {print $2; exit}')"
  test -n "$candidate"
  test "$candidate" != '(none)'
  case "$candidate" in
    "$expected"|"$expected"[!0-9]*) ;;
    *)
      printf 'candidate-version-mismatch: %s expected %s got %s\n' \
        "$package" "$expected" "$candidate" >&2
      exit 1
      ;;
  esac
  printf '%s\t%s\t%s\n' "$package" "$expected" "$candidate" >> "$capture_work"
done <<'VERSIONS'
ros-jazzy-ros-gz	1.0.23-1
ros-jazzy-navigation2	1.3.12-1
ros-jazzy-nav2-bringup	1.3.12-1
ros-jazzy-slam-toolbox	2.8.5-1
ros-jazzy-turtlebot3	2.3.6-1
ros-jazzy-turtlebot3-simulations	2.3.7-1
VERSIONS
install -m 0640 "$capture_work" "$candidate_file"
unlink -- "$capture_work"
capture_work=

mapfile -t requested_packages < config/environment/apt-packages.txt
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${requested_packages[@]}"

sudo locale-gen en_US en_US.UTF-8
sudo update-locale LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8
if test ! -f /etc/ros/rosdep/sources.list.d/20-default.list; then
  sudo rosdep init
fi
rosdep update --rosdistro jazzy

if systemctl list-unit-files nginx.service >/dev/null 2>&1; then
  sudo systemctl disable --now nginx.service
fi

if ! driver_is_ready; then
  sudo ubuntu-drivers install
  capture_work="$(mktemp --tmpdir=/tmp)"
  printf 'state=REBOOT_REQUIRED\nrequested_at=%s\nresume_command=bash scripts/install_host.sh --apply --evidence-dir %s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$evidence_dir" > "$capture_work"
  install -m 0640 "$capture_work" "$resume_marker"
  unlink -- "$capture_work"
  capture_work=
  trap - EXIT
  cleanup
  printf '%s\n' 'install-host: REBOOT_REQUIRED'
  exit 20
fi

mark_complete
trap - EXIT
cleanup
printf '%s\n' 'install-host: PASS'
```

The installer has three explicit states. A first run creates `install-state.env`, `dpkg-before.tsv`, `apt-sources-before/`, key hashes, and `apt-candidates.tsv` exactly once before the corresponding mutations; the state file also records Nginx's original unit, active, and enabled states. A `REBOOT_REQUIRED` run leaves `install-resume.env` and exits 20 without creating after-state evidence. The resume path skips repository setup and every package installation command, validates the rebooted driver, creates `dpkg-after.tsv`, `host-install-new-packages.txt`, `host-install-version-changes.tsv`, `managed-files-after.tsv`, and `install-complete.env`, then finishes. The managed-file verifier checks every original backup against its recorded SHA-256 and checks the live after-state against its own mode and SHA-256. A completed rerun writes no evidence and compares the live package and managed-file sets with the captured after-state before printing `PASS`. Any partial state without a valid resume or complete marker fails closed for operator review. The script never installs a desktop metapackage, starts a project service, or exposes a port; Nginx is explicitly disabled and stopped after package installation.

- [ ] **Step 4: Run static tests before the host mutation**

```bash
chmod +x scripts/install_host.sh tests/environment/test_install_host.sh
bash tests/environment/test_install_host.sh
LC_ALL=C sort -c config/environment/apt-packages.txt
```

Expected: both commands exit 0; the plan output contains every required ROS/Gazebo package and none of the forbidden stack names.

- [ ] **Step 5: Apply the installer and handle the explicit reboot boundary**

Run:

```bash
source .phase1-run.env
set +e
test ! -e "$PHASE1_EVIDENCE_ROOT/install-host.log"
bash scripts/install_host.sh --apply --evidence-dir "$PHASE1_EVIDENCE_ROOT" \
  2>&1 | tee "$PHASE1_EVIDENCE_ROOT/install-host.log"
install_rc="${PIPESTATUS[0]}"
set -e
test "$install_rc" -eq 0 || test "$install_rc" -eq 20
```

Expected without a driver change: final line `install-host: PASS`, exit 0. Expected after installing/updating the NVIDIA driver: final line `install-host: REBOOT_REQUIRED`, exit 20.

If exit 20 occurs, do not reboot until the installer commit and a reboot handoff commit both exist. Run:

```bash
git add config/environment/apt-packages.txt scripts/install_host.sh tests/environment/test_install_host.sh
git diff --cached --check
git commit -m "feat: install locked ros and gazebo baseline"
install_commit="$(git rev-parse HEAD)"
repo_root="$(git rev-parse --show-toplevel)"
branch_name="$(git branch --show-current)"
handoff_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
resume_command="$(printf 'cd %q && source .phase1-run.env && bash scripts/install_host.sh --apply --evidence-dir %q' "$repo_root" "$PHASE1_EVIDENCE_ROOT")"
printf 'install_commit=%s\nrepo_root=%s\nbranch=%s\nhandoff_at=%s\nresume_command=%s\n' \
  "$install_commit" "$repo_root" "$branch_name" "$handoff_at" "$resume_command"
```

Immediately use `apply_patch` to keep the existing recovery structure in `docs/HANDOFF.md` but set its active state exactly equivalent to:

```markdown
- State: Phase 1 host installation stopped at the explicit `REBOOT_REQUIRED` boundary; it is not complete.
- Installer commit: the literal `install_commit` printed above.
- Recorded at: the literal UTC `handoff_at` printed above.
- Repository and branch: the literal `repo_root` and `branch_name` printed above.
- Evidence: the literal `$PHASE1_EVIDENCE_ROOT`; `install-state.env`, `install-resume.env`, `dpkg-before.tsv`, `apt-sources-before/inventory.tsv`, and `apt-candidates.tsv` are write-once; after-state files do not exist yet.
- Last installer result: `install-host: REBOOT_REQUIRED`, exit 20.
- First resume command: the literal `resume_command` printed above.
- Resume rule: the command may validate the rebooted NVIDIA driver and create after-state evidence only; it must not repeat apt source setup, backups, candidate resolution, or package installation.
```

Then commit and reboot:

```bash
git add docs/HANDOFF.md
git diff --cached --check
git commit -m "docs: record phase one reboot handoff"
sync
sudo systemctl reboot
```

After the server returns, run only the recorded resume path and append to the original log:

```bash
cd /home/substation/substation-inspection-digital-twin
source .phase1-run.env
bash scripts/install_host.sh --apply --evidence-dir "$PHASE1_EVIDENCE_ROOT" \
  2>&1 | tee -a "$PHASE1_EVIDENCE_ROOT/install-host.log"
test "${PIPESTATUS[0]}" -eq 0
test "$(tail -n1 "$PHASE1_EVIDENCE_ROOT/install-host.log")" = 'install-host: PASS'
grep -Fx 'state=REBOOT_REQUIRED' "$PHASE1_EVIDENCE_ROOT/install-resume.env"
grep -Fx 'state=PASS' "$PHASE1_EVIDENCE_ROOT/install-complete.env"
```

Use `apply_patch` immediately after that success to change the handoff state to “reboot completed, driver validated, Task 3 verification in progress,” preserve the same installer commit/evidence path, and set the first resume action to Step 6 below. Commit only `docs/HANDOFF.md` with `git commit -m "docs: record phase one reboot completion"`. If the resume command attempts any apt/source mutation, overwrites an initial artifact, or observes a different locked core version, stop for authority review.

- [ ] **Step 6: Verify exact distribution families immediately after install**

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
test -s "$PHASE1_EVIDENCE_ROOT/apt-sources-before/inventory.tsv"
test -f "$PHASE1_EVIDENCE_ROOT/host-install-new-packages.txt"
test -s "$PHASE1_EVIDENCE_ROOT/host-install-version-changes.tsv"
test -s "$PHASE1_EVIDENCE_ROOT/managed-files-after.tsv"
grep -Fx 'state=PASS' "$PHASE1_EVIDENCE_ROOT/install-complete.env"
```

Expected: every command exits 0; ROS is Jazzy, `ros_gz` upstream is 1.0.23-1, Navigation2 is 1.3.12-1, SLAM Toolbox is 2.8.5-1, TurtleBot3 core and simulation expose 2.3.6-1 and 2.3.7-1 respectively, Gazebo major is 8, and the driver meets the floor. Full Ubuntu package revisions are captured for review later; they are not silently normalized away.

Evidence: `install-host.log`, `dpkg-before.tsv`, `dpkg-after.tsv`, `host-install-new-packages.txt`, `host-install-version-changes.tsv`, `managed-files-after.tsv`, `install-state.env`, `install-complete.env`, optional historical `install-resume.env`, `apt-candidates.tsv`, key SHA files, and the recursive source backup inventory below `$PHASE1_EVIDENCE_ROOT/apt-sources-before`.

Safe rollback:

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

5. Restore the original Nginx state recorded in `install-state.env`. If `nginx_unit_present_before=0`, confirm the unit disappears with the newly added packages. Otherwise restore only the recorded `enabled`/`disabled`/`masked` and `active`/`inactive` combination; any other recorded state requires operator review rather than normalization:

   ```bash
   source "$PHASE1_EVIDENCE_ROOT/install-state.env"
   if test "$nginx_unit_present_before" = 0; then
     ! systemctl list-unit-files --type=service --no-legend nginx.service 2>/dev/null \
       | grep -q '^nginx\.service'
   else
     case "$nginx_enabled_before" in
       enabled) sudo systemctl unmask nginx.service; sudo systemctl enable nginx.service ;;
       enabled-runtime) sudo systemctl unmask --runtime nginx.service; sudo systemctl enable --runtime nginx.service ;;
       disabled) sudo systemctl unmask nginx.service; sudo systemctl disable nginx.service ;;
       masked) sudo systemctl mask nginx.service ;;
       masked-runtime) sudo systemctl mask --runtime nginx.service ;;
       *) printf 'unsupported recorded nginx enabled state: %s\n' "$nginx_enabled_before" >&2; false ;;
     esac
     case "$nginx_active_before" in
       active) sudo systemctl start nginx.service ;;
       inactive) sudo systemctl stop nginx.service ;;
       *) printf 'unsupported recorded nginx active state: %s\n' "$nginx_active_before" >&2; false ;;
     esac
   fi
   ```
6. If `universe_present_before=0`, run `sudo add-apt-repository -y --remove universe` only after verifying no other project depends on it.
7. Compare a fresh sorted `dpkg-query` snapshot with `dpkg-before.tsv`. Every non-NVIDIA difference is an incomplete rollback. Do not attempt an automated NVIDIA driver rollback; boot the previously known-good kernel/driver package set and require an operator-reviewed exact-version transaction for those remaining rows.
8. Revert the Task 3 implementation commit and any conditional reboot handoff commits only after the restored host state and retained evidence have been reviewed.

- [ ] **Step 7: Commit Task 3**

```bash
if ! git log -1 --format=%s -- config/environment/apt-packages.txt scripts/install_host.sh tests/environment/test_install_host.sh \
  | grep -Fxq 'feat: install locked ros and gazebo baseline'; then
  git add config/environment/apt-packages.txt scripts/install_host.sh tests/environment/test_install_host.sh
  git diff --cached --check
  git commit -m "feat: install locked ros and gazebo baseline"
fi
```

Expected: the installer implementation exists in one focused commit containing only the three implementation paths. A reboot path additionally has two focused `docs/HANDOFF.md` synchronization commits; a no-reboot path has neither.

---

### Task 4: Resource Identity Manifest and Early Checksummed Downloads

**Files:**
- Create: `config/environment/resource-sources.tsv`
- Create: `scripts/download_phase1_resources.sh`
- Create: `tests/environment/test_phase1_resources.sh`

**Interfaces:**
- Consumes: official Node.js 24.18.0 release files, the Ultralytics assets v8.4.0 YOLO11n URL, the dataset revisions fixed by `docs/VERSION_MATRIX.md`, at least 80 GiB free space, and the active evidence directory.
- Produces: verified Node.js and `yolo11n.pt` payloads below `/var/lib/substation`, plus `$PHASE1_EVIDENCE_ROOT/resource-downloads.tsv`. It also freezes the later dataset download order without downloading raw datasets during the environment phase.

- [ ] **Step 1: Write the failing resource-governance test**

Create `tests/environment/test_phase1_resources.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

test -x scripts/download_phase1_resources.sh
test -s config/environment/resource-sources.tsv
grep -F $'node-linux-x64\tphase1' config/environment/resource-sources.tsv
grep -F $'yolo11n-base\tphase1' config/environment/resource-sources.tsv
grep -F 'c63ed3c7f5ea33ac8e9024c467a70a62b849b2ad' config/environment/resource-sources.tsv
grep -F '4bf9c31b18fadcd44d5f0b6d66f82bc56fa5e328' config/environment/resource-sources.tsv
grep -F $'hard-hat-workers-v10\tphase4' config/environment/resource-sources.tsv
grep -F $'insplad\tphase4-resolve-commit-first' config/environment/resource-sources.tsv
grep -F $'gazebo-meter\tphase2-and-phase4-generated' config/environment/resource-sources.tsv
bash scripts/download_phase1_resources.sh --list | grep -Fx 'node-linux-x64'
bash scripts/download_phase1_resources.sh --list | grep -Fx 'yolo11n-base'
rg -F 'resource identity changed' scripts/download_phase1_resources.sh
! git ls-files | grep -E '\.(pt|onnx|engine|tar\.xz|zip)$'
```

Run:

```bash
chmod +x tests/environment/test_phase1_resources.sh
bash tests/environment/test_phase1_resources.sh
```

Expected: exit nonzero because neither the manifest nor downloader exists.

- [ ] **Step 2: Add the exact resource identity and phase sequence**

Create `config/environment/resource-sources.tsv` with this exact tab-separated content:

```text
resource_id	phase	immutable_identity	source_url	server_storage	git_policy
node-linux-x64	phase1	24.18.0	https://nodejs.org/dist/v24.18.0/node-v24.18.0-linux-x64.tar.xz	/var/lib/substation/downloads/node/24.18.0	manifest-and-sha-only
yolo11n-base	phase1	ultralytics-assets-v8.4.0	https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt	/var/lib/substation/models/base/sha256-keyed	manifest-and-sha-only
substation-equipment-15	phase4	c63ed3c7f5ea33ac8e9024c467a70a62b849b2ad	https://huggingface.co/datasets/AndrzejDD/15-class-Substation-Equipment	/var/lib/substation/datasets/raw/substation-equipment-15/c63ed3c7f5ea33ac8e9024c467a70a62b849b2ad	manifest-and-sha-only
hard-hat-workers-v10	phase4	provider-version-10	https://public.roboflow.com/object-detection/hard-hat-workers/10	/var/lib/substation/datasets/raw/hard-hat-workers-v10/10	manifest-and-sha-only
d-fire	phase4	4bf9c31b18fadcd44d5f0b6d66f82bc56fa5e328	https://github.com/gaia-solutions-on-demand/DFireDataset	/var/lib/substation/datasets/raw/d-fire/4bf9c31b18fadcd44d5f0b6d66f82bc56fa5e328	manifest-and-sha-only
insplad	phase4-resolve-commit-first	resolve-one-40-character-commit-before-fetch	https://github.com/andreluizbvs/InsPLAD	/var/lib/substation/datasets/raw/insplad/sha40-keyed	manifest-and-sha-only
gazebo-meter	phase2-and-phase4-generated	generator-commit-plus-config-sha-plus-gazebo-version-plus-seeds	project-owned	/var/lib/substation/datasets/synthetic/gazebo-meter/generation-sha256	manifest-and-sha-only
gazebo-anomalies	phase2-and-phase4-generated	generator-commit-plus-config-sha-plus-gazebo-version-plus-seeds	project-owned	/var/lib/substation/datasets/synthetic/gazebo-anomalies/generation-sha256	manifest-and-sha-only
```

The file is an acquisition sequence, not `datasets/manifest.yaml` or `models/manifest.yaml`. Those production manifests are created only when their complete schema can be truthfully populated; this avoids inventing unmeasured file hashes or production mappings.

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
  printf '%s\n' 'usage: bash scripts/download_phase1_resources.sh --resource node-linux-x64|yolo11n-base|all --evidence-dir /var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment' >&2
  exit 2
fi

selection="$2"
evidence_dir="$4"
environment_require_evidence_dir "$evidence_dir"
case "$selection" in
  node-linux-x64|yolo11n-base|all) ;;
  *) printf 'unknown-resource: %s\n' "$selection" >&2; exit 2 ;;
esac

operator_user="$(id -un)"
operator_group="$(id -gn)"
sudo install -d -m 0750 -o "$operator_user" -g "$operator_group" \
  /var/lib/substation/downloads \
  /var/lib/substation/downloads/node \
  /var/lib/substation/downloads/node/24.18.0 \
  /var/lib/substation/models \
  /var/lib/substation/models/base

manifest_work="$(mktemp --tmpdir=/tmp)"
printf 'resource_id\trevision\tsha256\tsize_bytes\tsource_url\tserver_path\n' > "$manifest_work"

cleanup() {
  test ! -e "$manifest_work" || unlink -- "$manifest_work"
}
trap cleanup EXIT

download_node() {
  local node_dir=/var/lib/substation/downloads/node/24.18.0
  local archive=node-v24.18.0-linux-x64.tar.xz
  local archive_path="$node_dir/$archive"
  local sums_path="$node_dir/SHASUMS256.txt"
  local archive_work sums_work expected actual size
  if test ! -f "$archive_path"; then
    archive_work="$(mktemp --tmpdir="$node_dir")"
    sums_work="$(mktemp --tmpdir="$node_dir")"
    curl -fL --retry 3 --retry-delay 2 "https://nodejs.org/dist/v24.18.0/$archive" -o "$archive_work"
    curl -fL --retry 3 --retry-delay 2 https://nodejs.org/dist/v24.18.0/SHASUMS256.txt -o "$sums_work"
    expected="$(awk -v file="$archive" '$2 == file {print $1}' "$sums_work")"
    test "$expected" != ""
    actual="$(environment_sha256 "$archive_work")"
    test "$actual" = "$expected"
    install -m 0640 "$archive_work" "$archive_path"
    install -m 0640 "$sums_work" "$sums_path"
    unlink -- "$archive_work" "$sums_work"
  fi
  expected="$(awk -v file="$archive" '$2 == file {print $1}' "$sums_path")"
  actual="$(environment_sha256 "$archive_path")"
  test "$actual" = "$expected"
  size="$(stat -c '%s' "$archive_path")"
  printf 'node-linux-x64\t24.18.0\t%s\t%s\thttps://nodejs.org/dist/v24.18.0/%s\t%s\n' \
    "$actual" "$size" "$archive" "$archive_path" >> "$manifest_work"
}

download_yolo() {
  local source_url=https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt
  local weight_work weight_sha weight_dir weight_path size
  weight_work="$(mktemp --tmpdir=/var/lib/substation/models/base)"
  curl -fL --retry 3 --retry-delay 2 "$source_url" -o "$weight_work"
  weight_sha="$(environment_sha256 "$weight_work")"
  weight_dir="/var/lib/substation/models/base/$weight_sha"
  weight_path="$weight_dir/yolo11n.pt"
  sudo install -d -m 0750 -o "$operator_user" -g "$operator_group" "$weight_dir"
  if test -f "$weight_path"; then
    test "$(environment_sha256 "$weight_path")" = "$weight_sha"
  else
    install -m 0640 "$weight_work" "$weight_path"
  fi
  unlink -- "$weight_work"
  size="$(stat -c '%s' "$weight_path")"
  printf 'yolo11n-base\tv8.4.0\t%s\t%s\t%s\t%s\n' \
    "$weight_sha" "$size" "$source_url" "$weight_path" >> "$manifest_work"
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

- [ ] **Step 4: Run the static test, then begin the approved downloads**

```bash
chmod +x scripts/download_phase1_resources.sh tests/environment/test_phase1_resources.sh
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
```

Expected: both calls print `phase1-resources: PASS: all`; exactly two data rows exist in `resource-downloads.tsv`; both target files exist outside Git and match their recorded SHA-256 and size; the second identical call leaves the manifest byte-for-byte unchanged. Any existing row whose revision, SHA-256, size, URL, or server path differs from the newly resolved row fails with `resource identity changed` before replacing the manifest.

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
git add config/environment/resource-sources.tsv scripts/download_phase1_resources.sh tests/environment/test_phase1_resources.sh
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
  printf '%s\n' 'usage: bash scripts/setup_ros_workspace.sh --evidence-dir /var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment' >&2
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
```

Run:

```bash
chmod +x tests/environment/test_ai_environment.sh
bash tests/environment/test_ai_environment.sh
```

Expected: exit nonzero because the lock, setup script, and `.venv` do not exist.

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

- [ ] **Step 4: Implement idempotent AI environment setup**

Create `scripts/setup_python_env.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

if test "$#" -ne 2 || test "$1" != --evidence-dir; then
  printf '%s\n' 'usage: bash scripts/setup_python_env.sh --evidence-dir /var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment' >&2
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

if test -e .venv && test ! -x .venv/bin/python; then
  printf '%s\n' '.venv exists but is not a Python environment; move it to a reviewed quarantine path' >&2
  exit 1
fi
if test ! -d .venv; then
  python3 -m venv --system-site-packages .venv
fi
grep -Fxq 'include-system-site-packages = true' .venv/pyvenv.cfg
.venv/bin/python -m pip install --disable-pip-version-check --require-hashes -r requirements.lock

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
printf '%s\n' 'setup-python-env: PASS'
```

- [ ] **Step 5: Validate the lock, create `.venv`, and run the test**

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

- [ ] **Step 6: Commit Task 6**

```bash
git add requirements.in requirements.lock scripts/compile_requirements.sh scripts/setup_python_env.sh tests/environment/test_ai_environment.sh
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
- Produces: `.venv-web`, exact Gateway import/version proof, and `$PHASE1_EVIDENCE_ROOT/gateway-pip-freeze.txt`.

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
  printf '%s\n' 'usage: bash scripts/setup_gateway_env.sh --evidence-dir /var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment' >&2
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

if test -e .venv-web && test ! -x .venv-web/bin/python; then
  printf '%s\n' '.venv-web exists but is not a Python environment; move it to a reviewed quarantine path' >&2
  exit 1
fi
if test ! -d .venv-web; then
  python3 -m venv --system-site-packages .venv-web
fi
grep -Fxq 'include-system-site-packages = true' .venv-web/pyvenv.cfg
.venv-web/bin/python -m pip install --disable-pip-version-check --require-hashes -r requirements-web.lock

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
npm --prefix web/frontend exec playwright -- --version | grep -Fx 'Version 1.61.1'
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
  printf '%s\n' 'usage: bash scripts/setup_web_env.sh --evidence-dir /var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment' >&2
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
operator_user="$(id -un)"
operator_group="$(id -gn)"
sudo install -d -m 0755 "$toolchain_root"
if test ! -d "$node_root"; then
  test ! -e "$stage_root"
  sudo install -d -m 0755 "$stage_root"
  sudo tar -xJf "$node_archive" -C "$stage_root" --strip-components=1
  sudo chown -R root:root "$stage_root"
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

link_work="$toolchain_root/.node-current-${PHASE1_RUN_ID:?}"
test ! -e "$link_work"
sudo ln -s "$node_root" "$link_work"
sudo mv -Tf -- "$link_work" "$toolchain_root/node-current"

npm_version="$(npm --version)"
python3 scripts/write_frontend_manifest.py \
  --npm-version "$npm_version" \
  --output web/frontend/package.json

npm --prefix web/frontend install --package-lock-only --ignore-scripts
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

Safe rollback: preserve evidence and `package-lock.json`; remove `/usr/local/bin/{node,npm,npx,corepack}` only when each exact path is a symlink whose resolved target is below `/opt/substation/toolchains/node-v24.18.0/bin`; move `/opt/substation/toolchains/node-v24.18.0` to `/opt/substation/toolchains/node-v24.18.0.quarantine-$PHASE1_RUN_ID`; move `node_modules` and `.next` to sibling quarantine names; revert only Task 8's tracked commit.

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
  printf '%s\n' 'usage: bash scripts/smoke_headless_egl.sh --evidence-dir /var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment' >&2
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

### Task 10: Captured Environment Lock and Consolidated Verifier

**Files:**
- Create: `scripts/capture_environment_lock.sh`
- Create: `scripts/verify_environment.sh`
- Create: `tests/environment/test_verify_environment.sh`
- Create: `artifacts/environment/dpkg-packages.tsv`
- Create: `artifacts/environment/ai-pip-freeze.txt`
- Create: `artifacts/environment/gateway-pip-freeze.txt`
- Create: `artifacts/environment/node-npm-versions.txt`
- Create: `artifacts/environment/resource-downloads.tsv`
- Create: `artifacts/environment/SHA256SUMS`

**Interfaces:**
- Consumes: all Task 1–9 scripts, locks, toolchains, downloads, tests, and the approved installed host.
- Produces: the unique Phase 1 entry point `bash scripts/verify_environment.sh --evidence-dir "$PHASE1_EVIDENCE_ROOT"`, a reviewed tracked environment lock, per-command stdout/stderr plus structured argv/time/exit metadata, and the complete checksummed Phase 1 evidence set required by `docs/TEST_ACCEPTANCE.md`.

- [ ] **Step 1: Write the failing consolidated-verifier test**

Create `tests/environment/test_verify_environment.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
source .phase1-run.env

test -x scripts/verify_environment.sh
bash scripts/verify_environment.sh --evidence-dir "$PHASE1_EVIDENCE_ROOT"

required=(
  acceptance_run_id.txt
  documentation-gate.log
  host-audit.json
  install-host.log
  install-state.env
  install-complete.env
  apt-candidates.tsv
  apt-sources-before/inventory.tsv
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
  resource-downloads.tsv
  gpu.txt
  egl.log
  forbidden-packages.txt
  disk-memory.txt
  colcon-build.log
  colcon-test.log
  colcon-test-result.log
  frontend-build.log
  result.json
  SHA256SUMS
)
for name in "${required[@]}"; do
  test -s "$PHASE1_EVIDENCE_ROOT/$name"
done
test -f "$PHASE1_EVIDENCE_ROOT/host-install-new-packages.txt"
test "$(tail -n1 "$PHASE1_EVIDENCE_ROOT/install-host.log")" = 'install-host: PASS'
if test -e "$PHASE1_EVIDENCE_ROOT/install-resume.env"; then
  grep -Fx 'state=REBOOT_REQUIRED' "$PHASE1_EVIDENCE_ROOT/install-resume.env"
fi

python3 - "$PHASE1_EVIDENCE_ROOT/result.json" <<'PY'
import json
import sys
from pathlib import Path
result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
required = {"schema_version", "acceptance_run_id", "git_commit", "started_at", "completed_at", "commands", "exit_codes", "thresholds", "measurements", "artifacts", "status", "failures"}
assert required <= result.keys()
assert result["status"] == "passed"
assert result["failures"] == []
expected_ids = {
    "documentation-gate", "host-audit", "tracked-lock", "version-checks",
    "ai-environment", "gateway-environment", "ai-lock", "gateway-lock",
    "resource-lock", "ros-workspace", "web-environment", "node-lock",
    "npm-ci", "frontend-build", "headless-egl",
}
records = result["commands"]
assert {record["id"] for record in records} == expected_ids
assert result["exit_codes"] == ({command_id: 0 for command_id in expected_ids} | {"verify_environment": 0})
for record in records:
    assert record["argv"]
    assert record["started_at"].endswith("Z")
    assert record["completed_at"].endswith("Z")
    assert record["exit_code"] == record["capture_exit_code"] == 0
    log_path = Path(sys.argv[1]).parent / record["log"]
    assert log_path.is_file()
    assert log_path.stat().st_size > 0
PY

(cd "$PHASE1_EVIDENCE_ROOT" && sha256sum -c SHA256SUMS)
grep -F '  apt-sources-before/inventory.tsv' "$PHASE1_EVIDENCE_ROOT/SHA256SUMS"
grep -F '  commands/documentation-gate.json' "$PHASE1_EVIDENCE_ROOT/SHA256SUMS"
(cd artifacts/environment && sha256sum -c SHA256SUMS)
cmp artifacts/environment/dpkg-packages.tsv "$PHASE1_EVIDENCE_ROOT/dpkg-packages.tsv"
cmp artifacts/environment/ai-pip-freeze.txt "$PHASE1_EVIDENCE_ROOT/ai-pip-freeze.txt"
cmp artifacts/environment/gateway-pip-freeze.txt "$PHASE1_EVIDENCE_ROOT/gateway-pip-freeze.txt"
cmp artifacts/environment/node-npm-versions.txt "$PHASE1_EVIDENCE_ROOT/node-npm-versions.txt"
cmp artifacts/environment/resource-downloads.tsv "$PHASE1_EVIDENCE_ROOT/resource-downloads.tsv"

failure_run_id="phase1-verifier-failure-$(python3 -c 'import uuid; print(uuid.uuid4())')"
failure_run_root="/var/lib/substation/evidence/acceptance/$failure_run_id"
test ! -e "$failure_run_root"
install -d -m 0750 "$failure_run_root"
cleanup_failure_fixture() {
  case "$failure_run_root" in
    /var/lib/substation/evidence/acceptance/phase1-verifier-failure-*) ;;
    *) return 1 ;;
  esac
  find "$failure_run_root" -depth -delete
}
trap cleanup_failure_fixture EXIT
failure_evidence_dir="$failure_run_root/01-environment"
failure_bin="$failure_run_root/bin"
install -d -m 0750 "$failure_evidence_dir" "$failure_bin"
cp -a -- "$PHASE1_EVIDENCE_ROOT/." "$failure_evidence_dir/"
printf '%s\n' "$failure_run_id" > "$failure_evidence_dir/acceptance_run_id.txt"
cat > "$failure_bin/bash" <<'SH'
#!/usr/bin/bash
if test "${1-}" = scripts/verify_documentation_gate.sh; then
  printf '%s\n' 'injected-documentation-gate-failure' >&2
  exit 23
fi
exec /usr/bin/bash "$@"
SH
chmod 0750 "$failure_bin/bash"

set +e
PATH="$failure_bin:$PATH" /usr/bin/bash scripts/verify_environment.sh \
  --evidence-dir "$failure_evidence_dir" \
  > "$failure_run_root/verify-failure.log" 2>&1
failure_rc=$?
set -e
test "$failure_rc" -eq 23
test ! -e "$failure_evidence_dir/SHA256SUMS"
python3 - "$failure_evidence_dir/result.json" "$failure_evidence_dir/commands/documentation-gate.json" <<'PY'
import json
import sys
from pathlib import Path

result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
record = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
assert result["status"] == "failed"
assert result["commands"] == [record]
assert result["exit_codes"] == {"documentation-gate": 23, "verify_environment": 23}
assert record["id"] == "documentation-gate"
assert record["argv"] == ["bash", "scripts/verify_documentation_gate.sh"]
assert record["exit_code"] == 23
assert record["capture_exit_code"] == 0
assert record["log"] == "documentation-gate.log"
PY
trap - EXIT
cleanup_failure_fixture
printf '%s\n' 'verify-environment-test: PASS'
```

Run:

```bash
chmod +x tests/environment/test_verify_environment.sh
bash tests/environment/test_verify_environment.sh
```

Expected: exit nonzero because the capture script, canonical verifier, and tracked environment lock do not exist.

- [ ] **Step 2: Implement the reviewed environment-lock capture**

Create `scripts/capture_environment_lock.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

if test "$#" -ne 2 || test "$1" != --evidence-dir; then
  printf '%s\n' 'usage: bash scripts/capture_environment_lock.sh --evidence-dir /var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment' >&2
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

install -d -m 0755 artifacts/environment
dpkg-query -W -f='${Package}\t${Version}\n' | LC_ALL=C sort > artifacts/environment/dpkg-packages.tsv
install -m 0644 "$evidence_dir/ai-pip-freeze.txt" artifacts/environment/ai-pip-freeze.txt
install -m 0644 "$evidence_dir/gateway-pip-freeze.txt" artifacts/environment/gateway-pip-freeze.txt
install -m 0644 "$evidence_dir/node-npm-versions.txt" artifacts/environment/node-npm-versions.txt
install -m 0644 "$evidence_dir/resource-downloads.tsv" artifacts/environment/resource-downloads.tsv

manifest_work="$(mktemp --tmpdir=/tmp)"
cleanup() {
  test ! -e "$manifest_work" || unlink -- "$manifest_work"
}
trap cleanup EXIT
for name in \
  ai-pip-freeze.txt \
  dpkg-packages.tsv \
  gateway-pip-freeze.txt \
  node-npm-versions.txt \
  resource-downloads.tsv; do
  (cd artifacts/environment && sha256sum -- "$name") >> "$manifest_work"
done
install -m 0644 "$manifest_work" artifacts/environment/SHA256SUMS
(cd artifacts/environment && sha256sum -c SHA256SUMS)
trap - EXIT
cleanup
printf '%s\n' 'capture-environment-lock: PASS'
```

This capture is deliberately explicit. It cannot update an approved baseline unnoticed because the resulting Git diff must be reviewed and committed in this task; any later change requires the version/ADR synchronization rule.

- [ ] **Step 3: Implement the canonical failure-closed verifier**

Create `scripts/verify_environment.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

if test "$#" -ne 2 || test "$1" != --evidence-dir; then
  printf '%s\n' 'usage: bash scripts/verify_environment.sh --evidence-dir /var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment' >&2
  exit 2
fi

evidence_dir="$2"
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
source scripts/lib/environment_common.sh
environment_require_evidence_dir "$evidence_dir"

started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
acceptance_run_id="$(basename "$(dirname "$evidence_dir")")"
git_commit="$(git rev-parse HEAD)"
commands_dir="$evidence_dir/commands"

write_failed_result() {
  local rc="$1"
  local line="$2"
  trap - ERR
  python3 - "$evidence_dir/result.json" "$acceptance_run_id" "$git_commit" "$started_at" "$rc" "$line" "$commands_dir" <<'PY'
import datetime
import json
import sys
from pathlib import Path

path, run_id, commit, started, rc, line, commands_dir = sys.argv[1:]
records = []
for record_path in sorted(Path(commands_dir).glob("*.json")):
    records.append(json.loads(record_path.read_text(encoding="utf-8")))
result = {
    "schema_version": 1,
    "acceptance_run_id": run_id,
    "git_commit": commit,
    "started_at": started,
    "completed_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "commands": records,
    "exit_codes": {record["id"]: record["exit_code"] for record in records} | {"verify_environment": int(rc)},
    "thresholds": {"disk_free_bytes_min": 80 * 1024**3, "memory_bytes_min": 16 * 1024**3, "nvidia_driver_min": "560.35.05"},
    "measurements": {},
    "artifacts": [],
    "status": "failed",
    "failures": [f"verify_environment failed at shell line {line} with exit {rc}"],
}
Path(path).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  exit "$rc"
}
trap 'write_failed_result "$?" "$LINENO"' ERR

install -d -m 0750 "$commands_dir"
command_ids=(
  documentation-gate host-audit tracked-lock version-checks ai-environment
  gateway-environment ai-lock gateway-lock resource-lock ros-workspace
  web-environment node-lock npm-ci frontend-build headless-egl
)
for command_id in "${command_ids[@]}"; do
  if test -e "$commands_dir/$command_id.json"; then
    unlink -- "$commands_dir/$command_id.json"
  fi
done
if test -e "$evidence_dir/SHA256SUMS"; then
  unlink -- "$evidence_dir/SHA256SUMS"
fi

run_recorded() {
  local command_id="$1"
  local log_relative="$2"
  shift 2
  test "$1" = --
  shift
  [[ "$command_id" =~ ^[a-z0-9-]+$ ]]
  [[ "$log_relative" != /* && "$log_relative" != *..* ]]
  local log_path="$evidence_dir/$log_relative"
  local record_path="$commands_dir/$command_id.json"
  local command_started command_completed command_rc capture_rc saved_err_trap
  local -a pipeline_status
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
  python3 - "$record_path" "$command_id" "$log_relative" "$command_started" "$command_completed" "$command_rc" "$capture_rc" "$@" <<'PY'
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
Path(record_path).write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  if test "$command_rc" -ne 0; then
    return "$command_rc"
  fi
  if test "$capture_rc" -ne 0; then
    return "$capture_rc"
  fi
}

installer_required=(
  acceptance_run_id.txt
  documentation-gate.log
  host-audit.json
  install-host.log
  install-state.env
  install-complete.env
  apt-candidates.tsv
  apt-sources-before/inventory.tsv
  managed-files-after.tsv
  host-install-version-changes.tsv
  ros-archive-key.sha256
  gazebo-archive-key.sha256
  dpkg-before.tsv
  dpkg-after.tsv
)
for relative_path in "${installer_required[@]}"; do
  test -s "$evidence_dir/$relative_path" || {
    printf 'missing-mandatory-installer-artifact: %s\n' "$relative_path" >&2
    false
  }
done
test -f "$evidence_dir/host-install-new-packages.txt"
test "$(<"$evidence_dir/acceptance_run_id.txt")" = "$acceptance_run_id"
test "$(tail -n1 "$evidence_dir/install-host.log")" = 'install-host: PASS'
grep -Fxq 'state=INITIAL_INSTALL_STARTED' "$evidence_dir/install-state.env"
grep -Fxq 'state=PASS' "$evidence_dir/install-complete.env"
if test -e "$evidence_dir/install-resume.env"; then
  test -s "$evidence_dir/install-resume.env"
  grep -Fxq 'state=REBOOT_REQUIRED' "$evidence_dir/install-resume.env"
fi
grep -Eq '^nginx_unit_present_before=[01]$' "$evidence_dir/install-state.env"
grep -Eq '^nginx_active_before=(absent|[a-z-]+)$' "$evidence_dir/install-state.env"
grep -Eq '^nginx_enabled_before=(absent|[a-z-]+)$' "$evidence_dir/install-state.env"
python3 - "$evidence_dir/apt-sources-before/inventory.tsv" "$evidence_dir/managed-files-after.tsv" <<'PY'
import csv
import hashlib
import sys
from pathlib import Path

inventory_path, after_path = map(Path, sys.argv[1:])
expected_paths = {
    "/etc/apt/sources.list.d/ros2.list",
    "/etc/apt/sources.list.d/gazebo-stable.list",
    "/usr/share/keyrings/ros-archive-keyring.gpg",
    "/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg",
    "/etc/default/locale",
    "/etc/ros/rosdep/sources.list.d/20-default.list",
}
with inventory_path.open(encoding="utf-8", newline="") as handle:
    inventory = list(csv.DictReader(handle, delimiter="\t"))
assert {row["source_path"] for row in inventory} == expected_paths
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
    path = Path(row["source_path"])
    if row["existed_after"] == "1":
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
        assert f"{path.stat().st_mode & 0o777:o}" == row["mode"]
    else:
        assert row["existed_after"] == "0"
        assert not path.exists()
        assert row["mode"] == row["sha256"] == "-"
PY
python3 - "$evidence_dir/dpkg-before.tsv" "$evidence_dir/dpkg-after.tsv" "$evidence_dir/host-install-version-changes.tsv" "$evidence_dir/host-install-new-packages.txt" <<'PY'
import csv
import sys
from pathlib import Path

before_path, after_path, changes_path, additions_path = map(Path, sys.argv[1:])
def versions(path):
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        package, version = line.split("\t", 1)
        rows[package] = version
    return rows

before = versions(before_path)
after = versions(after_path)
expected = []
for package in sorted(set(before) | set(after)):
    old = before.get(package)
    new = after.get(package)
    if old == new:
        continue
    change = "added" if old is None else "removed" if new is None else "version-changed"
    expected.append({
        "package": package,
        "before_version": old or "-",
        "after_version": new or "-",
        "change": change,
    })
with changes_path.open(encoding="utf-8", newline="") as handle:
    actual = list(csv.DictReader(handle, delimiter="\t"))
assert actual == expected
additions = additions_path.read_text(encoding="utf-8").splitlines()
assert additions == [row["package"] for row in expected if row["change"] == "added"]
PY
grep -E $'^ros-jazzy-ros-gz\t1\.0\.23-1\t1\.0\.23-1([^0-9].*)?$' "$evidence_dir/apt-candidates.tsv"
grep -E $'^ros-jazzy-navigation2\t1\.3\.12-1\t1\.3\.12-1([^0-9].*)?$' "$evidence_dir/apt-candidates.tsv"
grep -E $'^ros-jazzy-nav2-bringup\t1\.3\.12-1\t1\.3\.12-1([^0-9].*)?$' "$evidence_dir/apt-candidates.tsv"
grep -E $'^ros-jazzy-slam-toolbox\t2\.8\.5-1\t2\.8\.5-1([^0-9].*)?$' "$evidence_dir/apt-candidates.tsv"
grep -E $'^ros-jazzy-turtlebot3\t2\.3\.6-1\t2\.3\.6-1([^0-9].*)?$' "$evidence_dir/apt-candidates.tsv"
grep -E $'^ros-jazzy-turtlebot3-simulations\t2\.3\.7-1\t2\.3\.7-1([^0-9].*)?$' "$evidence_dir/apt-candidates.tsv"
if systemctl is-active --quiet nginx.service; then
  printf '%s\n' 'nginx must remain stopped during the environment baseline' >&2
  false
fi
nginx_enabled="$(systemctl is-enabled nginx.service 2>/dev/null || true)"
test "$nginx_enabled" = disabled
printf 'nginx.service=inactive\nnginx.enabled=%s\n' "$nginx_enabled" > "$evidence_dir/service-state.txt"
grep -F 'deb [arch=' /etc/apt/sources.list.d/ros2.list >/dev/null
grep -F 'http://packages.ros.org/ros2/ubuntu noble main' /etc/apt/sources.list.d/ros2.list >/dev/null
grep -F 'http://packages.osrfoundation.org/gazebo/ubuntu-stable noble main' /etc/apt/sources.list.d/gazebo-stable.list >/dev/null

verify_tracked_lock() {
  local output_dir="$1"
  dpkg-query -W -f='${Package}\t${Version}\n' | LC_ALL=C sort > "$output_dir/dpkg-packages.tsv"
  cmp artifacts/environment/dpkg-packages.tsv "$output_dir/dpkg-packages.tsv"
  (cd artifacts/environment && sha256sum -c SHA256SUMS)
  printf '%s\n' 'tracked-environment-lock: PASS'
}

verify_versions() {
  local output_dir="$1"
  source /opt/ros/jazzy/setup.bash
  test "$ROS_DISTRO" = jazzy
  dpkg-query -W -f='${Package}\t${Version}\n' ros-jazzy-ros-gz \
    | grep -E $'^ros-jazzy-ros-gz\t1\.0\.23-1([^0-9].*)?$'
  dpkg-query -W -f='${Package}\t${Version}\n' ros-jazzy-navigation2 ros-jazzy-nav2-bringup \
    | tee "$output_dir/navigation2-packages.txt"
  grep -E $'^ros-jazzy-navigation2\t1\.3\.12-1([^0-9].*)?$' "$output_dir/navigation2-packages.txt"
  grep -E $'^ros-jazzy-nav2-bringup\t1\.3\.12-1([^0-9].*)?$' "$output_dir/navigation2-packages.txt"
  dpkg-query -W -f='${Version}\n' ros-jazzy-slam-toolbox \
    | grep -E '^2\.8\.5-1([^0-9].*)?$'
  dpkg-query -W -f='${Package}\t${Version}\n' ros-jazzy-turtlebot3 ros-jazzy-turtlebot3-simulations \
    | tee "$output_dir/turtlebot3-packages.txt"
  grep -E $'^ros-jazzy-turtlebot3\t2\.3\.6-1([^0-9].*)?$' "$output_dir/turtlebot3-packages.txt"
  grep -E $'^ros-jazzy-turtlebot3-simulations\t2\.3\.7-1([^0-9].*)?$' "$output_dir/turtlebot3-packages.txt"
  gz sim --versions | tee "$output_dir/gazebo-version.txt"
  grep -E '(^|[^0-9])8\.[0-9]' "$output_dir/gazebo-version.txt"
  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader \
    | tee "$output_dir/gpu.txt"
  local driver_version
  driver_version="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -n1)"
  dpkg --compare-versions "$driver_version" ge 560.35.05
  printf '%s\n' 'locked-version-checks: PASS'
}

capture_ai_lock() {
  local output_dir="$1"
  .venv/bin/python -m pip freeze --all | LC_ALL=C sort > "$output_dir/ai-pip-freeze.txt"
  cmp artifacts/environment/ai-pip-freeze.txt "$output_dir/ai-pip-freeze.txt"
  printf '%s\n' 'ai-freeze-lock: PASS'
}

capture_gateway_lock() {
  local output_dir="$1"
  .venv-web/bin/python -m pip freeze --all | LC_ALL=C sort > "$output_dir/gateway-pip-freeze.txt"
  cmp artifacts/environment/gateway-pip-freeze.txt "$output_dir/gateway-pip-freeze.txt"
  printf '%s\n' 'gateway-freeze-lock: PASS'
}

verify_resources() {
  local output_dir="$1"
  bash scripts/download_phase1_resources.sh --resource all --evidence-dir "$output_dir"
  cmp artifacts/environment/resource-downloads.tsv "$output_dir/resource-downloads.tsv"
  printf '%s\n' 'resource-lock-check: PASS'
}

capture_node_lock() {
  local output_dir="$1"
  {
    node --version
    npm --version
    node -p 'require("./web/frontend/package.json").packageManager'
  } > "$output_dir/node-npm-versions.txt"
  cmp artifacts/environment/node-npm-versions.txt "$output_dir/node-npm-versions.txt"
  printf '%s\n' 'node-npm-lock: PASS'
}

run_recorded documentation-gate documentation-gate.log -- bash scripts/verify_documentation_gate.sh
run_recorded host-audit host-audit.json -- bash scripts/audit_host.sh

python3 - "$evidence_dir/host-audit.json" "$evidence_dir/disk-memory.txt" <<'PY'
import json
import sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert data["status"] == "passed"
Path(sys.argv[2]).write_text(
    f"disk_free_bytes={data['disk_free_bytes']}\nmemory_bytes={data['memory_bytes']}\n",
    encoding="utf-8",
)
PY

python3 - "$evidence_dir/host-audit.json" "$evidence_dir/forbidden-packages.txt" <<'PY'
import json
import sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
packages = data["forbidden_packages"]
Path(sys.argv[2]).write_text(
    "forbidden-packages: none\n" if not packages else "\n".join(packages) + "\n",
    encoding="utf-8",
)
assert not packages
PY

run_recorded tracked-lock tracked-lock-check.log -- verify_tracked_lock "$evidence_dir"
run_recorded version-checks version-checks.log -- verify_versions "$evidence_dir"
run_recorded ai-environment test-ai-environment.log -- bash tests/environment/test_ai_environment.sh
run_recorded gateway-environment test-gateway-environment.log -- bash tests/environment/test_gateway_environment.sh
run_recorded ai-lock ai-lock-check.log -- capture_ai_lock "$evidence_dir"
run_recorded gateway-lock gateway-lock-check.log -- capture_gateway_lock "$evidence_dir"
run_recorded resource-lock resource-lock-check.log -- verify_resources "$evidence_dir"
run_recorded ros-workspace verify-ros-workspace.log -- bash scripts/setup_ros_workspace.sh --evidence-dir "$evidence_dir"
run_recorded web-environment test-web-environment.log -- bash tests/environment/test_web_environment.sh
run_recorded node-lock node-lock-check.log -- capture_node_lock "$evidence_dir"
run_recorded npm-ci npm-ci.log -- npm --prefix web/frontend ci
run_recorded frontend-build frontend-build.log -- npm --prefix web/frontend run build
run_recorded headless-egl verify-headless-egl.log -- bash scripts/smoke_headless_egl.sh --evidence-dir "$evidence_dir"

python3 - "$commands_dir" "$evidence_dir" <<'PY'
import json
import sys
from pathlib import Path

commands_dir, evidence_dir = map(Path, sys.argv[1:])
expected = {
    "documentation-gate": "documentation-gate.log",
    "host-audit": "host-audit.json",
    "tracked-lock": "tracked-lock-check.log",
    "version-checks": "version-checks.log",
    "ai-environment": "test-ai-environment.log",
    "gateway-environment": "test-gateway-environment.log",
    "ai-lock": "ai-lock-check.log",
    "gateway-lock": "gateway-lock-check.log",
    "resource-lock": "resource-lock-check.log",
    "ros-workspace": "verify-ros-workspace.log",
    "web-environment": "test-web-environment.log",
    "node-lock": "node-lock-check.log",
    "npm-ci": "npm-ci.log",
    "frontend-build": "frontend-build.log",
    "headless-egl": "verify-headless-egl.log",
}
records = {}
for path in commands_dir.glob("*.json"):
    record = json.loads(path.read_text(encoding="utf-8"))
    records[record["id"]] = record
assert set(records) == set(expected)
for command_id, log_relative in expected.items():
    record = records[command_id]
    assert record["schema_version"] == 1
    assert record["argv"]
    assert record["started_at"].endswith("Z")
    assert record["completed_at"].endswith("Z")
    assert record["exit_code"] == 0
    assert record["capture_exit_code"] == 0
    assert record["log"] == log_relative
    log_path = evidence_dir / log_relative
    assert log_path.is_file()
    assert log_path.stat().st_size > 0
PY

python3 - "$evidence_dir/environment.json" "$evidence_dir/host-audit.json" "$git_commit" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

output, audit_path, commit = sys.argv[1:]
audit = json.loads(Path(audit_path).read_text(encoding="utf-8"))
def command(*args):
    return subprocess.run(args, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
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
Path(output).write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

completed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 - "$evidence_dir/result.json" "$acceptance_run_id" "$git_commit" "$started_at" "$completed_at" "$evidence_dir/host-audit.json" "$commands_dir" <<'PY'
import json
import sys
from pathlib import Path

output, run_id, commit, started, completed, audit_path, commands_dir = sys.argv[1:]
audit = json.loads(Path(audit_path).read_text(encoding="utf-8"))
records = [
    json.loads(path.read_text(encoding="utf-8"))
    for path in sorted(Path(commands_dir).glob("*.json"))
]
root = Path(output).parent
artifacts = sorted(
    str(path.relative_to(root))
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
    "exit_codes": {record["id"]: record["exit_code"] for record in records} | {"verify_environment": 0},
    "thresholds": {"disk_free_bytes_min": 80 * 1024**3, "memory_bytes_min": 16 * 1024**3, "nvidia_driver_min": "560.35.05"},
    "measurements": {"disk_free_bytes": audit["disk_free_bytes"], "memory_bytes": audit["memory_bytes"], "driver_version": audit["gpu"]["driver_version"]},
    "artifacts": artifacts,
    "status": "passed",
    "failures": [],
}
Path(output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

final_required=(
  acceptance_run_id.txt
  documentation-gate.log
  host-audit.json
  install-host.log
  install-state.env
  install-complete.env
  apt-candidates.tsv
  apt-sources-before/inventory.tsv
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
  resource-downloads.tsv
  gpu.txt
  egl.log
  forbidden-packages.txt
  disk-memory.txt
  colcon-build.log
  colcon-test.log
  colcon-test-result.log
  frontend-build.log
  result.json
)
for relative_path in "${final_required[@]}"; do
  test -s "$evidence_dir/$relative_path" || {
    printf 'missing-mandatory-final-artifact: %s\n' "$relative_path" >&2
    false
  }
done
test -f "$evidence_dir/host-install-new-packages.txt"
test "$(tail -n1 "$evidence_dir/install-host.log")" = 'install-host: PASS'

acceptance_root="$evidence_dir"
checksum_found_nul=
checksum_expected_nul=
checksum_expected_lines=
checksum_work=
checksum_actual_unsorted=
checksum_actual_lines=
checksum_install_work=
checksum_cleanup() {
  local cleanup_path
  for cleanup_path in \
    "$checksum_found_nul" \
    "$checksum_expected_nul" \
    "$checksum_expected_lines" \
    "$checksum_work" \
    "$checksum_actual_unsorted" \
    "$checksum_actual_lines" \
    "$checksum_install_work"; do
    if test -n "$cleanup_path" && test -e "$cleanup_path"; then
      unlink -- "$cleanup_path"
    fi
  done
}
trap checksum_cleanup EXIT

checksum_found_nul="$(mktemp --tmpdir=/tmp)"
checksum_expected_nul="$(mktemp --tmpdir=/tmp)"
checksum_expected_lines="$(mktemp --tmpdir=/tmp)"
checksum_work="$(mktemp --tmpdir=/tmp)"
checksum_actual_unsorted="$(mktemp --tmpdir=/tmp)"
checksum_actual_lines="$(mktemp --tmpdir=/tmp)"

find "$acceptance_root" -type f ! -path "$acceptance_root/SHA256SUMS" -printf '%P\0' \
  > "$checksum_found_nul"
LC_ALL=C sort -z "$checksum_found_nul" > "$checksum_expected_nul"
mapfile -d '' -t checksum_paths < "$checksum_expected_nul"

for relative_path in "${checksum_paths[@]}"; do
  if [[ "$relative_path" == *$'\n'* || "$relative_path" == *'\'* ]]; then
    printf 'checksum: unsupported newline or backslash in path: %q\n' "$relative_path" >&2
    false
  fi
  printf '%s\n' "$relative_path" >> "$checksum_expected_lines"
  (cd "$acceptance_root" && sha256sum -- "$relative_path") >> "$checksum_work"
done

LC_ALL=C awk '
  length($0) < 66 || substr($0, 65, 2) != "  " {
    print "checksum: malformed SHA256SUMS entry" > "/dev/stderr"
    exit 1
  }
  { print substr($0, 67) }
' "$checksum_work" > "$checksum_actual_unsorted"
LC_ALL=C sort "$checksum_actual_unsorted" > "$checksum_actual_lines"

checksum_expected_count="$(wc -l < "$checksum_expected_lines")"
checksum_actual_count="$(wc -l < "$checksum_actual_lines")"
printf 'checksum-expected-count=%s\n' "$checksum_expected_count"
printf 'checksum-actual-count=%s\n' "$checksum_actual_count"
if test "$checksum_expected_count" -ne "$checksum_actual_count"; then
  printf '%s\n' 'checksum: expected and actual entry counts differ' >&2
  false
fi
if ! cmp --silent "$checksum_expected_lines" "$checksum_actual_lines"; then
  diff -u "$checksum_expected_lines" "$checksum_actual_lines" >&2 || true
  printf '%s\n' 'checksum: expected and actual path sets differ' >&2
  false
fi

(cd "$acceptance_root" && sha256sum -c "$checksum_work")
checksum_install_dir="$(dirname -- "$acceptance_root")"
checksum_install_work="$(mktemp --tmpdir="$checksum_install_dir")"
install -m 0640 "$checksum_work" "$checksum_install_work"
mv -f -- "$checksum_install_work" "$acceptance_root/SHA256SUMS"
checksum_install_work=
if ! (cd "$acceptance_root" && sha256sum -c SHA256SUMS); then
  unlink -- "$acceptance_root/SHA256SUMS"
  false
fi

trap - EXIT
checksum_cleanup

trap - ERR
printf '%s\n' 'verify-environment: PASS'
```

- [ ] **Step 4: Capture and review the proposed tracked lock**

Run:

```bash
chmod +x scripts/capture_environment_lock.sh scripts/verify_environment.sh tests/environment/test_verify_environment.sh
source .phase1-run.env
bash scripts/capture_environment_lock.sh --evidence-dir "$PHASE1_EVIDENCE_ROOT"
git diff -- artifacts/environment
(cd artifacts/environment && sha256sum -c SHA256SUMS)
```

Expected: `capture-environment-lock: PASS`; five `OK` checksum lines; the Debian snapshot reflects the approved current server and does not contain a forbidden package. Review every version change before proceeding.

- [ ] **Step 5: Run the canonical verifier and the focused test**

```bash
source .phase1-run.env
bash scripts/verify_environment.sh --evidence-dir "$PHASE1_EVIDENCE_ROOT"
bash tests/environment/test_verify_environment.sh
```

Expected: final lines `verify-environment: PASS` and `verify-environment-test: PASS`; every required artifact is present (and non-empty except the explicitly allowed empty new-package list); both SHA manifests verify; `result.json.status` is `passed`; failures is empty. Fifteen child-command records each contain exact argv, log path, start/end UTC, command exit code, and capture exit code; `result.json.exit_codes` has those fifteen zero entries plus `verify_environment: 0`, rather than one aggregate value. The canonical command is not piped to a file inside the tree while that tree is being hashed. Any intermediate error removes the prior SHA manifest, records the failed command metadata and a failed `result.json`, and exits nonzero.

Evidence: the complete required final evidence set listed in the file map, rooted at `$PHASE1_EVIDENCE_ROOT`, plus the reviewed six-file tracked lock under `artifacts/environment`.

Safe rollback: preserve the full acceptance directory. Do not replace the prior approved environment lock. If this is the first baseline and review rejects it, move exactly `artifacts/environment` to `artifacts/environment.rejected-$PHASE1_RUN_ID` with `git mv`, record the reason, and revert Task 10. Roll back the underlying task that caused the mismatch rather than editing captured versions by hand.

- [ ] **Step 6: Commit Task 10, then re-verify that exact commit**

```bash
git add scripts/capture_environment_lock.sh scripts/verify_environment.sh tests/environment/test_verify_environment.sh artifacts/environment
git diff --cached --check
git commit -m "test: verify phase one environment baseline"
verified_commit="$(git rev-parse HEAD)"
source .phase1-run.env
bash scripts/verify_environment.sh --evidence-dir "$PHASE1_EVIDENCE_ROOT"
test "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["git_commit"])' "$PHASE1_EVIDENCE_ROOT/result.json")" = "$verified_commit"
```

Expected: the post-commit verifier prints `verify-environment: PASS`, and evidence `git_commit` equals the Task 10 commit exactly.

---

### Task 11: Project Status and Handoff Update

**Files:**
- Modify: `docs/PROJECT_STATUS.md`
- Modify: `docs/HANDOFF.md`

**Interfaces:**
- Consumes: the immutable Task 10 implementation verification record, `$PHASE1_EVIDENCE_ROOT/result.json`, `$PHASE1_EVIDENCE_ROOT/SHA256SUMS`, all verification commands, current Git status, and service state.
- Produces: a documentation-only synchronization commit that names the earlier verified implementation commit and a deterministic Phase 2 resume entry. It does not rewrite the immutable environment result to pretend that the later documentation commit was environment-tested.

- [ ] **Step 1: Capture the exact dynamic values before editing**

```bash
source .phase1-run.env
verified_commit="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["git_commit"])' "$PHASE1_EVIDENCE_ROOT/result.json")"
verified_at="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["completed_at"])' "$PHASE1_EVIDENCE_ROOT/result.json")"
verified_status="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "$PHASE1_EVIDENCE_ROOT/result.json")"
repo_root="$(git rev-parse --show-toplevel)"
branch_name="$(git branch --show-current)"
verification_command="$(printf 'bash scripts/verify_environment.sh --evidence-dir %q' "$PHASE1_EVIDENCE_ROOT")"
status_commit_command='git log -1 --format=%H -- docs/PROJECT_STATUS.md docs/HANDOFF.md'
resume_command="$(printf 'cd %q && source .phase1-run.env && (cd %q && sha256sum -c SHA256SUMS)' "$repo_root" "$PHASE1_EVIDENCE_ROOT")"
printf 'verified_commit=%s\nverified_at=%s\nverified_status=%s\nrepo_root=%s\nbranch=%s\nevidence=%s\nverification_command=%s\nstatus_commit_command=%s\nresume_command=%s\n' \
  "$verified_commit" "$verified_at" "$verified_status" "$repo_root" "$branch_name" "$PHASE1_EVIDENCE_ROOT" "$verification_command" "$status_commit_command" "$resume_command"
test "$verified_status" = passed
test "$(git rev-parse HEAD)" = "$verified_commit"
(cd "$PHASE1_EVIDENCE_ROOT" && sha256sum -c SHA256SUMS)
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
- Last successful command: the exact `verification_command` line printed in Step 1.
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
verified_commit="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["git_commit"])' "$PHASE1_EVIDENCE_ROOT/result.json")"
rg -n 'Phase 1|environment baseline|环境基线|verify_environment.sh|result.json|SHA256SUMS|Phase 2|Gazebo' docs/PROJECT_STATUS.md docs/HANDOFF.md
rg -n -F "$PHASE1_EVIDENCE_ROOT" docs/PROJECT_STATUS.md docs/HANDOFF.md
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
verified_commit="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["git_commit"])' "$PHASE1_EVIDENCE_ROOT/result.json")"
status_commit="$(git rev-parse HEAD)"
evidence_commit="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["git_commit"])' "$PHASE1_EVIDENCE_ROOT/result.json")"
test "$evidence_commit" = "$verified_commit"
test "$status_commit" != "$verified_commit"
test "$(git diff --name-only "$verified_commit" "$status_commit" | LC_ALL=C sort)" = $'docs/HANDOFF.md\ndocs/PROJECT_STATUS.md'
(cd "$PHASE1_EVIDENCE_ROOT" && sha256sum -c SHA256SUMS)
bash scripts/verify_documentation_gate.sh
git status --short
```

Expected: environment evidence still refers exactly to the Task 10 implementation commit and all checksums pass without rewriting any evidence. The current HEAD differs only by the two status documents, and the documentation gate passes at that documentation-only HEAD. Only unrelated pre-existing changes, if any, remain.

Evidence: the immutable `$PHASE1_EVIDENCE_ROOT/result.json`, `$PHASE1_EVIDENCE_ROOT/SHA256SUMS`, the literal Git diff between implementation and status commits, and the two committed current-state documents.

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
    "scripts/download_phase1_resources.sh",
    "scripts/setup_ros_workspace.sh",
    "scripts/setup_python_env.sh",
    "scripts/setup_gateway_env.sh",
    "scripts/setup_web_env.sh",
    "scripts/smoke_headless_egl.sh",
    "scripts/verify_environment.sh",
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
scan_pattern='T''BD|T''ODO|F''IXME|X''XX|PLACE''HOLDER|待''定|待''补|以后再''定'
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

Run final Markdown and diff checks:

```bash
git diff --check
git diff -- docs/plans/PHASE-01-ENVIRONMENT.md
```

Expected: `git diff --check` has no output; the diff contains only this Phase 1 plan during plan authoring. During implementation, each task's diff contains only that task's declared paths.

## Completion Conditions

Phase 1 is complete only when all eleven task commits exist, the Task 10 implementation commit has an immutable verifier result with `result.json.status` equal to `passed`, both environment SHA manifests verify, no forbidden package is installed, the exact versions match `docs/VERSION_MATRIX.md`, CUDA is available, the colcon commands pass, the frontend production build passes, and a Gazebo RGB frame is proven with `DISPLAY` removed. The later Task 11 HEAD must differ from that verified implementation commit only by `docs/PROJECT_STATUS.md` and `docs/HANDOFF.md`; those documents must explicitly distinguish the two commits and truthfully identify Phase 2 as next.

Do not continue directly into product-world code from an unreviewed working tree. The next session first writes and approves the Phase 2 Gazebo world implementation plan, then implements it test-first against the locked environment produced here.
