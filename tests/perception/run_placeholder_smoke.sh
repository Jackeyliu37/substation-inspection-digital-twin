#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf '%s\n' 'usage: bash tests/perception/run_placeholder_smoke.sh --expected-commit 40-hex-git-sha' >&2
  exit 2
}

test "$#" -eq 2 || usage
test "$1" = --expected-commit || usage
expected_commit="$2"
if [[ ! "$expected_commit" =~ ^[0-9a-f]{40}$ ]]; then
  usage
fi

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
test "$(git rev-parse HEAD)" = "$expected_commit"
test -z "$(git status --porcelain --untracked-files=no)"
test -f install/setup.bash

run_id="$(python3 -c 'import uuid; print(uuid.uuid4())')"
evidence_parent="/var/lib/substation/evidence/acceptance/$run_id"
evidence_dir="$evidence_parent/04-perception-placeholder.staging"
final_dir="${evidence_dir%.staging}"
install -d -m 0750 "$evidence_dir"
test ! -L "$evidence_dir"
test -z "$(find "$evidence_dir" -mindepth 1 -maxdepth 1 -print -quit)"
test ! -e "$final_dir"
free_bytes="$(stat -f -c '%a*%S' "$evidence_dir" | awk -F\* '{print $1*$2}')"
test "$free_bytes" -ge 21474836480

partition="phase4-placeholder-$run_id"
started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'run_id=%s\nimplementation_commit=%s\nstarted_at=%s\npartition=%s\nfree_bytes=%s\n' \
  "$run_id" "$expected_commit" "$started_at" "$partition" "$free_bytes" \
  > "$evidence_dir/run.env"
git status --short --branch > "$evidence_dir/git-status.txt"
sha256sum \
  ros2_ws/src/substation_perception/launch/placeholder_perception.launch.py \
  ros2_ws/src/substation_perception/substation_perception/model_identity.py \
  ros2_ws/src/substation_perception/substation_perception/yolo_backend.py \
  ros2_ws/src/substation_perception/substation_perception/detection_contract.py \
  ros2_ws/src/substation_perception/substation_perception/placeholder_node.py \
  > "$evidence_dir/input-sha256.txt"
model_path='/var/lib/substation/models/base/0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1/yolo11n.pt'
sha256sum "$model_path" > "$evidence_dir/model-sha256.txt"
stat --printf='size_bytes=%s\n' "$model_path" > "$evidence_dir/model-size.txt"
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader > "$evidence_dir/gpu.txt"

set +u
source /opt/ros/jazzy/setup.bash
source install/setup.bash
set -u
export ROS_LOCALHOST_ONLY=1
export GZ_PARTITION="$partition"

world_pid=""
perception_pid=""
stop_group() {
  local pid="$1"
  test -n "$pid" || return 0
  if kill -0 -- "-$pid" 2>/dev/null; then
    kill -TERM -- "-$pid" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 -- "-$pid" 2>/dev/null || break
      sleep 0.25
    done
    if kill -0 -- "-$pid" 2>/dev/null; then
      kill -KILL -- "-$pid" 2>/dev/null || true
    fi
  fi
  if kill -0 "$pid" 2>/dev/null; then
    wait "$pid" 2>/dev/null || true
  fi
}
cleanup() {
  stop_group "$perception_pid"
  stop_group "$world_pid"
}
trap cleanup EXIT INT TERM

setsid env -u DISPLAY ROS_LOCALHOST_ONLY=1 GZ_PARTITION="$partition" \
  ros2 launch substation_gazebo substation_world.launch.py \
  run_id:="$run_id" gz_partition:="$partition" \
  > "$evidence_dir/world-launch.log" 2>&1 &
world_pid=$!

setsid env -u DISPLAY ROS_LOCALHOST_ONLY=1 GZ_PARTITION="$partition" \
  ros2 launch substation_perception placeholder_perception.launch.py \
  gz_partition:="$partition" \
  > "$evidence_dir/perception-launch.log" 2>&1 &
perception_pid=$!

timeout 90s python3 tests/perception/probe_placeholder_pipeline.py \
  --output "$evidence_dir/probe.json" \
  > "$evidence_dir/probe.log" 2>&1

printf 'pid\tppid\targs\n' > "$evidence_dir/processes.tsv"
for pid in "$world_pid" "$perception_pid"; do
  ps -o pid=,ppid=,args= -p "$pid" >> "$evidence_dir/processes.tsv"
  tr '\0' '\n' < "/proc/$pid/environ" > "$evidence_dir/$pid.environ"
  grep -Fxq "GZ_PARTITION=$partition" "$evidence_dir/$pid.environ"
  if grep -q '^DISPLAY=' "$evidence_dir/$pid.environ"; then
    printf '%s\n' 'process unexpectedly has DISPLAY' >&2
    exit 1
  fi
done

cleanup
trap - EXIT INT TERM
if kill -0 -- "-$world_pid" 2>/dev/null || kill -0 -- "-$perception_pid" 2>/dev/null; then
  printf '%s\n' 'owned launch process remained after cleanup' >&2
  exit 1
fi

completed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 - "$evidence_dir/result.json" "$run_id" "$expected_commit" "$completed_at" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
path.write_text(json.dumps({
    "phase": "04-perception-placeholder",
    "status": "passed",
    "run_id": sys.argv[2],
    "implementation_commit": sys.argv[3],
    "completed_at": sys.argv[4],
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
(
  cd "$evidence_dir"
  find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
  sha256sum -c SHA256SUMS >/dev/null
)
mv -- "$evidence_dir" "$final_dir"
printf '%s\n' "placeholder-smoke: PASS: $final_dir"
