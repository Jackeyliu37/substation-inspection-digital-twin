#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf '%s\n' 'usage: bash tests/navigation/run_phase3_acceptance.sh --run-id UUID --evidence-dir /var/lib/substation/evidence/acceptance/UUID/03-navigation.staging' >&2
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
expected="/var/lib/substation/evidence/acceptance/$run_id/03-navigation.staging"
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
implementation_commit="$(git rev-parse HEAD)"
started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
partition="phase3-$run_id"
map_path="ros2_ws/src/substation_gazebo/maps/substation.pgm"
map_sha256_before="$(sha256sum "$map_path" | awk '{print $1}')"

printf 'run_id=%s\nimplementation_commit=%s\nstarted_at=%s\npartition=%s\n' \
  "$run_id" "$implementation_commit" "$started_at" "$partition" \
  > "$evidence_dir/run.env"
git status --short --branch > "$evidence_dir/git-status.txt"
sha256sum \
  configs/devices.yaml \
  ros2_ws/src/substation_gazebo/config/nav2_params.yaml \
  ros2_ws/src/substation_gazebo/config/slam_toolbox.yaml \
  ros2_ws/src/substation_gazebo/maps/substation.pgm \
  ros2_ws/src/substation_gazebo/maps/substation.yaml \
  ros2_ws/src/substation_gazebo/worlds/substation_world.sdf \
  > "$evidence_dir/input-sha256.txt"

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
    for _ in $(seq 1 40); do
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
  ros2 launch substation_gazebo substation_navigation.launch.py \
  run_id:="$run_id" gz_partition:="$partition" \
  > "$evidence_dir/launch.log" 2>&1 &
launch_pid=$!
launch_group="$launch_pid"

timeout 300s python3 tests/navigation/probe_phase3_navigation.py \
  --run-id "$run_id" \
  --devices configs/devices.yaml \
  --map ros2_ws/src/substation_gazebo/maps/substation.yaml \
  --output "$evidence_dir/navigation-probe.json" \
  > "$evidence_dir/navigation-probe.log" 2>&1

ps -eo pid=,ppid=,pgid=,args= | awk -v pgid="$launch_pid" \
  'BEGIN {print "pid\tppid\tpgid\targs"} $3 == pgid {print}' \
  > "$evidence_dir/process-group.tsv"
tr '\0' '\n' < "/proc/$launch_pid/environ" > "$evidence_dir/launch-environ.txt"
grep -Fxq "GZ_PARTITION=$partition" "$evidence_dir/launch-environ.txt"
grep -Fxq 'ROS_LOCALHOST_ONLY=1' "$evidence_dir/launch-environ.txt"
if grep -q '^DISPLAY=' "$evidence_dir/launch-environ.txt"; then
  printf '%s\n' 'Phase 3 launch unexpectedly has DISPLAY' >&2
  exit 1
fi

cleanup
launch_pid=""
if kill -0 -- "-$launch_group" 2>/dev/null; then
  printf '%s\n' 'Phase 3 process group remained after cleanup' >&2
  exit 1
fi

map_sha256_after="$(sha256sum "$map_path" | awk '{print $1}')"
test "$map_sha256_after" = "$map_sha256_before"
completed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 - "$evidence_dir/navigation-probe.json" "$evidence_dir/result.json" \
  "$implementation_commit" "$started_at" "$completed_at" "$map_sha256_after" <<'PY'
import json
from pathlib import Path
import sys

probe = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if probe.get("status") != "passed":
    raise SystemExit("navigation probe did not pass")
probe.update(
    {
        "phase": "03-navigation",
        "implementation_commit": sys.argv[3],
        "started_at": sys.argv[4],
        "completed_at": sys.argv[5],
        "static_map_sha256": sys.argv[6],
    }
)
Path(sys.argv[2]).write_text(
    json.dumps(probe, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
PY
printf '%s\n' '<?xml version="1.0" encoding="UTF-8"?><testsuite name="phase3-navigation" tests="2" failures="0"><testcase name="static-amcl-nav2-goal"/><testcase name="dynamic-obstacle-local-costmap"/></testsuite>' \
  > "$evidence_dir/junit.xml"

(
  cd "$evidence_dir"
  find . -maxdepth 1 -type f ! -name SHA256SUMS -printf '%f\n' \
    | LC_ALL=C sort \
    | xargs sha256sum > SHA256SUMS
  sha256sum -c SHA256SUMS
)
mv -- "$evidence_dir" "$final_dir"
printf '%s\n' 'phase3-navigation-probe: PASS'
printf '%s\n' 'phase3-acceptance: PASS'
