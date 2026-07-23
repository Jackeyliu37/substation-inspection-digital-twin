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
set +u
source /opt/ros/jazzy/setup.bash
set -u
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
