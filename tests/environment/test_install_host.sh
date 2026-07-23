#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

test -s config/environment/apt-packages.txt
LC_ALL=C sort -c config/environment/apt-packages.txt
test "$(uniq -d config/environment/apt-packages.txt | wc -l)" -eq 0

test -x scripts/install_host.sh
test -x scripts/rollback_host.sh

plan="$(bash scripts/install_host.sh --plan)"
for package in \
  gz-harmonic \
  ros-jazzy-ros-base \
  ros-jazzy-ros-gz \
  ros-jazzy-navigation2 \
  ros-jazzy-nav2-bringup \
  ros-jazzy-slam-toolbox \
  ros-jazzy-turtlebot3 \
  ros-jazzy-turtlebot3-simulations \
  ros-jazzy-vision-msgs; do
  grep -Fxq "$package" <<<"$plan"
done

! grep -E 'ros-.*-desktop|ubuntu-desktop|xorg|nomachine|xvfb|virtualgl|nvidia-cuda-toolkit' <<<"$plan"
! awk '/^ros-/ && $0 !~ /^ros-jazzy-/ {bad=1} END {exit bad ? 0 : 1}' config/environment/apt-packages.txt

grep -Fq 'http://packages.ros.org/ros.key' scripts/install_host.sh
grep -Fq '3a4c8d59e3a0fbb2acf338994b6102c5baa17071c4cc97f520b482a697f8a4fe' scripts/install_host.sh
grep -Fq 'curl --ipv4' scripts/install_host.sh
grep -Fq -- '--connect-timeout 10' scripts/install_host.sh
grep -Fq -- '--max-time 120' scripts/install_host.sh
grep -Fq 'install-host: downloading ROS key' scripts/install_host.sh
grep -Fq 'install-host: refreshing apt indexes' scripts/install_host.sh
grep -Fq 'install-host: installing packages' scripts/install_host.sh
grep -Fq 'ros_apt_uri=http://packages.ros.org/ros2/ubuntu' scripts/install_host.sh
grep -Fq 'https://packages.osrfoundation.org/gazebo.gpg' scripts/install_host.sh
grep -Fq 'https://packages.osrfoundation.org/gazebo/ubuntu-stable' scripts/install_host.sh
grep -Fq 'scripts/audit_host.sh' scripts/install_host.sh
grep -Fq '/usr/sbin/policy-rc.d' scripts/install_host.sh
grep -Fq 'dpkg-before.tsv' scripts/install_host.sh
grep -Fq 'dpkg-after.tsv' scripts/install_host.sh
grep -Fq 'host-install-new-packages.txt' scripts/install_host.sh
grep -Fq 'host-install-version-changes.tsv' scripts/install_host.sh
grep -Fq 'apt-candidates.tsv' scripts/install_host.sh
grep -Fq 'apt-policy-origins.tsv' scripts/install_host.sh
grep -Fq 'apt-install-simulation.txt' scripts/install_host.sh
grep -Fq 'apt-get --simulate install' scripts/install_host.sh
grep -Fq 'nvidia-packages-before.tsv' scripts/install_host.sh
grep -Fq 'nvidia-packages-after.tsv' scripts/install_host.sh
grep -Fq 'nvidia-smi-before.txt' scripts/install_host.sh
grep -Fq 'nvidia-smi-after.txt' scripts/install_host.sh
grep -Fq 'nvidia_package_regex=' scripts/install_host.sh
grep -Fq 'libcuda1-' scripts/install_host.sh
grep -Fq 'linux-(modules|objects|signatures)-nvidia-' scripts/install_host.sh
grep -Fq '${db:Status-Abbrev}' scripts/install_host.sh
grep -Fq 'new_packages_sha256=' scripts/install_host.sh
grep -Fq 'policy_mode_before=' scripts/install_host.sh
grep -Fq '/etc/ros/rosdep/sources.list.d/20-default.list' scripts/install_host.sh
grep -Fq 'nginx_enabled_before=' scripts/install_host.sh
grep -Fq 'nginx_active_before=' scripts/install_host.sh
grep -Fq 'nginx must be inactive before Phase 1 install' scripts/install_host.sh
grep -Fq 'systemctl disable --now nginx.service' scripts/install_host.sh
! grep -Eq 'ubuntu-drivers|NVIDIA-Linux|apt-get.*nvidia-driver' scripts/install_host.sh

grep -Fq -- '--confirm-run-id' scripts/rollback_host.sh
grep -Fq 'apt-get --simulate remove' scripts/rollback_host.sh
grep -Fq 'apt-get remove --no-auto-remove' scripts/rollback_host.sh
grep -Fq 'host-install-new-packages.txt' scripts/rollback_host.sh
grep -Fq 'dpkg-after.tsv' scripts/rollback_host.sh
grep -Fq '${db:Status-Abbrev}' scripts/rollback_host.sh
grep -Fq 'allowed_managed_paths' scripts/rollback_host.sh
grep -Fq 'managed_fields = ["path", "existed_before", "sha256_before", "sha256_after"]' scripts/rollback_host.sh
if grep -Fq 'empty managed-file manifest' scripts/rollback_host.sh; then exit 1; fi
grep -Fq 'nginx_enabled_before' scripts/rollback_host.sh
grep -Fq 'nginx_active_before' scripts/rollback_host.sh
grep -Fq '[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}' scripts/rollback_host.sh
grep -Fq '[a-z0-9_]+=' scripts/rollback_host.sh
grep -Fq 'evidence_run_id' scripts/lib/environment_common.sh

printf '%s\n' 'install-host-static-test: PASS'
