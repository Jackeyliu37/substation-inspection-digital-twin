#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

test -f ros2_ws/src/.gitkeep
test -x scripts/setup_ros_workspace.sh
set +u
source /opt/ros/jazzy/setup.bash
set -u
test "$ROS_DISTRO" = jazzy
test "$(find ros2_ws/src -mindepth 1 -maxdepth 1 ! -name .gitkeep | wc -l)" -eq 0
