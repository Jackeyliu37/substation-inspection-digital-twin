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
      policy-rc.d-state.tsv
      host-install-version-changes.tsv
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
    set +u
    source /opt/ros/jazzy/setup.bash
    set -u
    test "$ROS_DISTRO" = jazzy
    dpkg-query -W -f='${Package}\t${Version}\n' ros-jazzy-ros-gz \
      | grep -E $'^ros-jazzy-ros-gz\t1\.0\.22-1([^0-9].*)?$'
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
    set +u
    source /opt/ros/jazzy/setup.bash
    set -u
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
disk_free_bytes = min(item["free_bytes"] for item in data["disks"])
disk_path.write_text(
    f"disk_free_bytes={disk_free_bytes}\n"
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
disk_free_bytes = min(item["free_bytes"] for item in audit["disks"])

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
    "disk_free_bytes": disk_free_bytes,
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
    "disk_free_bytes": min(item["free_bytes"] for item in audit["disks"]),
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
    policy-rc.d-state.tsv
    host-install-version-changes.tsv
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
