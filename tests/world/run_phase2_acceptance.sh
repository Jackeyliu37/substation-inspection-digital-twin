#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf '%s\n' 'usage: bash tests/world/run_phase2_acceptance.sh --run-id UUID --evidence-dir /var/lib/substation/evidence/acceptance/UUID/02-gazebo-world.staging' >&2
  exit 2
}

test "$#" -eq 4 || usage
test "$1" = --run-id || usage
run_id="$2"
test "$3" = --evidence-dir || usage
evidence_dir="$4"
if [[ ! "$run_id" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$ ]]; then
  printf 'invalid-run-id: %s\n' "$run_id" >&2
  exit 2
fi
expected="/var/lib/substation/evidence/acceptance/$run_id/02-gazebo-world.staging"
test "$evidence_dir" = "$expected" || {
  printf 'invalid-evidence-dir: %s\n' "$evidence_dir" >&2
  exit 2
}
test -d "$evidence_dir"
test ! -L "$evidence_dir"
test -z "$(find "$evidence_dir" -mindepth 1 -maxdepth 1 -print -quit)"
final_dir="${evidence_dir%.staging}"
test ! -e "$final_dir"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
test -z "$(git status --porcelain --untracked-files=no)"
test -f ros2_ws/install/setup.bash
free_bytes="$(stat -f -c '%a*%S' "$evidence_dir" | awk -F\* '{print $1*$2}')"
test "$free_bytes" -ge 21474836480
implementation_commit="$(git rev-parse HEAD)"
completed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
partition="phase2-$run_id"

printf 'run_id=%s\nimplementation_commit=%s\nstarted_at=%s\npartition=%s\nfree_bytes=%s\n' \
  "$run_id" "$implementation_commit" "$completed_at" "$partition" "$free_bytes" \
  > "$evidence_dir/run.env"
git status --short --branch > "$evidence_dir/git-status.txt"
sha256sum \
  configs/devices.yaml \
  ros2_ws/src/substation_description/urdf/inspection_robot.urdf.xacro \
  ros2_ws/src/substation_gazebo/config/bridge.yaml \
  ros2_ws/src/substation_gazebo/config/scenarios.yaml \
  ros2_ws/src/substation_gazebo/models/inspection_robot/model.sdf \
  ros2_ws/src/substation_gazebo/worlds/substation_world.sdf \
  > "$evidence_dir/input-sha256.txt"
if test -f .phase1-run.env; then
  source .phase1-run.env
  printf 'phase1_run_id=%s\nphase1_evidence_final=%s\n' \
    "$PHASE1_RUN_ID" "$PHASE1_EVIDENCE_FINAL" > "$evidence_dir/phase1-identity.env"
  bash scripts/check_environment_seal.sh --evidence-dir "$PHASE1_EVIDENCE_FINAL" \
    > "$evidence_dir/phase1-seal-check.log"
fi

set +u
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
set -u
export ROS_LOCALHOST_ONLY=1
export GZ_PARTITION="$partition"

launch_pid=""
cleanup() {
  if test -n "$launch_pid" && kill -0 "$launch_pid" 2>/dev/null; then
    kill -TERM -- "-$launch_pid" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "$launch_pid" 2>/dev/null || break
      sleep 0.25
    done
    if kill -0 "$launch_pid" 2>/dev/null; then
      kill -KILL -- "-$launch_pid" 2>/dev/null || true
    fi
    wait "$launch_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

setsid env -u DISPLAY ROS_LOCALHOST_ONLY=1 GZ_PARTITION="$partition" \
  ros2 launch substation_gazebo substation_world.launch.py \
  run_id:="$run_id" gz_partition:="$partition" \
  > "$evidence_dir/launch.log" 2>&1 &
launch_pid=$!

timeout 120s python3 tests/world/probe_phase2_topics.py \
  --run-id "$run_id" \
  --output "$evidence_dir/topic-probe.json" \
  > "$evidence_dir/topic-probe.log" 2>&1

descendants=("$launch_pid")
frontier=("$launch_pid")
while test "${#frontier[@]}" -gt 0; do
  next=()
  for parent in "${frontier[@]}"; do
    while IFS= read -r child; do
      test -n "$child" || continue
      descendants+=("$child")
      next+=("$child")
    done < <(ps -eo pid=,ppid= | awk -v parent="$parent" '$2 == parent {print $1}')
  done
  frontier=("${next[@]}")
done
printf 'pid\tppid\targs\n' > "$evidence_dir/process-tree.tsv"
gz_pid=""
for pid in "${descendants[@]}"; do
  test -r "/proc/$pid/environ" || continue
  ps -o pid=,ppid=,args= -p "$pid" >> "$evidence_dir/process-tree.tsv"
  args="$(ps -o args= -p "$pid")"
  if [[ "$args" == *"gz sim"*"substation_world.sdf"* ]]; then
    gz_pid="$pid"
  fi
done
test -n "$gz_pid"
tr '\0' '\n' < "/proc/$gz_pid/environ" > "$evidence_dir/gazebo-environ.txt"
grep -Fxq "GZ_PARTITION=$partition" "$evidence_dir/gazebo-environ.txt"
if grep -q '^DISPLAY=' "$evidence_dir/gazebo-environ.txt"; then
  printf '%s\n' 'Gazebo process unexpectedly has DISPLAY' >&2
  exit 1
fi
grep -F -- '--headless-rendering' "$evidence_dir/process-tree.tsv" >/dev/null

cleanup
trap - EXIT INT TERM
if kill -0 -- "-$launch_pid" 2>/dev/null; then
  printf '%s\n' 'Phase 2 process group remained after cleanup' >&2
  exit 1
fi

printf '%s\n' '<?xml version="1.0" encoding="UTF-8"?><testsuite name="phase2-gazebo-world" tests="1" failures="0"><testcase name="headless-topic-and-scenario-contract"/></testsuite>' \
  > "$evidence_dir/junit.xml"
python3 - "$evidence_dir/result.json" "$run_id" "$implementation_commit" "$completed_at" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
path.write_text(json.dumps({
    "phase": "02-gazebo-world",
    "status": "passed",
    "run_id": sys.argv[2],
    "implementation_commit": sys.argv[3],
    "completed_at": sys.argv[4],
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
(
  cd "$evidence_dir"
  find . -type f ! -name SHA256SUMS -print0 \
    | sort -z \
    | xargs -0 sha256sum > SHA256SUMS
  sha256sum -c SHA256SUMS >/dev/null
)
mv -- "$evidence_dir" "$final_dir"
printf '%s\n' 'phase2-topic-probe: PASS'
printf '%s\n' 'phase2-acceptance: PASS'
