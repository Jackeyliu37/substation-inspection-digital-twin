#!/usr/bin/env bash
set -euo pipefail

test "$#" -eq 4 || { printf '%s\n' 'usage: bash tests/phase5_6/run_phase5_6_acceptance.sh --run-id UUID --evidence-dir /var/lib/substation/evidence/acceptance/UUID/05-risk-mission.staging' >&2; exit 2; }
test "$1" = --run-id && run_id="$2"
test "$3" = --evidence-dir && evidence_dir="$4"
[[ "$run_id" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$ ]]
expected="/var/lib/substation/evidence/acceptance/$run_id/05-risk-mission.staging"
test "$evidence_dir" = "$expected"
test -d "$evidence_dir" && test -z "$(find "$evidence_dir" -mindepth 1 -maxdepth 1 -print -quit)"
final_dir="${evidence_dir%.staging}"
test ! -e "$final_dir"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
set +u
source /opt/ros/jazzy/setup.bash
source install/setup.bash
set -u
export ROS_LOCALHOST_ONLY=1
partition="phase5-6-$run_id"
printf 'run_id=%s\nimplementation_commit=%s\npartition=%s\nstarted_at=%s\n' \
  "$run_id" "$(git rev-parse HEAD)" "$partition" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$evidence_dir/run.env"
git status --short --branch > "$evidence_dir/git-status.txt"

world_pid=""
core_pid=""
cleanup() {
  for pid in "$core_pid" "$world_pid"; do
    if test -n "$pid" && kill -0 -- "-$pid" 2>/dev/null; then
      kill -TERM -- "-$pid" 2>/dev/null || true
      for _ in $(seq 1 30); do kill -0 -- "-$pid" 2>/dev/null || break; sleep 0.25; done
      kill -KILL -- "-$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
}
trap cleanup EXIT INT TERM

setsid env -u DISPLAY ROS_LOCALHOST_ONLY=1 GZ_PARTITION="$partition" \
  ros2 launch substation_gazebo substation_world.launch.py \
  run_id:="$run_id" gz_partition:="$partition" > "$evidence_dir/world-launch.log" 2>&1 &
world_pid=$!
sleep 8
setsid env ROS_LOCALHOST_ONLY=1 \
  ros2 launch "$repo_root/ros2_ws/src/substation_mission/launch/substation_core.launch.py" run_id:="$run_id" \
  > "$evidence_dir/core-launch.log" 2>&1 &
core_pid=$!

timeout 150s python3 tests/phase5_6/probe_phase5_6_pipeline.py \
  --run-id "$run_id" --output "$evidence_dir/probe.json" \
  > "$evidence_dir/probe.log" 2>&1

cleanup
trap - EXIT INT TERM
test ! -e "/proc/$world_pid" && test ! -e "/proc/$core_pid"
printf '%s\n' 'phase5-6-processes: stopped' > "$evidence_dir/processes.txt"
printf '%s\n' '<?xml version="1.0" encoding="UTF-8"?><testsuite name="phase5-6-risk-mission" tests="1" failures="0"><testcase name="risk-confirmation-and-mission-replan"/></testsuite>' > "$evidence_dir/junit.xml"
python3 - "$evidence_dir/result.json" "$run_id" "$(git rev-parse HEAD)" <<'PY'
import json
import pathlib
import sys

pathlib.Path(sys.argv[1]).write_text(json.dumps({
    "phase": "05-risk-mission",
    "status": "passed",
    "run_id": sys.argv[2],
    "implementation_commit": sys.argv[3],
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
(
  cd "$evidence_dir"
  find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
  sha256sum -c SHA256SUMS >/dev/null
)
mv -- "$evidence_dir" "$final_dir"
printf '%s\n' 'phase5-6-acceptance: PASS'
