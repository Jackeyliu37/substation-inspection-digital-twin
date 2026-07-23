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
environment_require_evidence_dir "$evidence_dir"
test ! -e "$evidence_dir/SHA256SUMS"

for command_name in apt-cache apt-get curl dpkg dpkg-query gpg nvidia-smi python3 sha256sum sudo systemctl; do
  environment_require_command "$command_name"
done

LC_ALL=C sort -c config/environment/apt-packages.txt
test "$(uniq -d config/environment/apt-packages.txt | wc -l)" -eq 0
! awk '/^ros-/ && $0 !~ /^ros-jazzy-/ {bad=1} END {exit bad ? 0 : 1}' config/environment/apt-packages.txt
! grep -Eq '^(ros-jazzy-(desktop|desktop-full)|ubuntu-desktop|xorg|xserver-xorg.*|nomachine|xvfb|virtualgl|nvidia-cuda-toolkit)$' config/environment/apt-packages.txt

initial_artifacts=(
  install-state.env
  install-complete.env
  dpkg-before.tsv
  dpkg-after.tsv
  install-managed-files.tsv
  apt-candidates.tsv
  apt-policy-origins.tsv
  apt-install-simulation.txt
  host-install-new-packages.txt
  host-install-version-changes.tsv
  nvidia-packages-before.tsv
  nvidia-packages-after.tsv
  nvidia-smi-before.txt
  nvidia-smi-after.txt
)
for artifact in "${initial_artifacts[@]}"; do
  test ! -e "$evidence_dir/$artifact" || {
    printf 'install-host: incomplete or completed evidence already exists: %s\n' "$evidence_dir/$artifact" >&2
    exit 1
  }
done

bash scripts/audit_host.sh --preflight > "$evidence_dir/host-audit-before-install.json"
sudo -v

run_id="$(<"$evidence_dir/acceptance_run_id.txt")"
test -n "$run_id"
test "$run_id" = "$(basename "$(dirname "$evidence_dir")")"
implementation_commit="$(git rev-parse HEAD)"
package_manifest_sha256="$(sha256sum config/environment/apt-packages.txt | awk '{print $1}')"
nvidia_package_regex='^(nvidia-|libnvidia-|libcuda1-|linux-(modules|objects|signatures)-nvidia-|xserver-xorg-video-nvidia-)'

dpkg-query -W -f='${db:Status-Abbrev}\t${binary:Package}\t${Version}\n' 2>/dev/null \
  | awk -F '\t' '$1 == "ii " {print $2 "\t" $3}' | LC_ALL=C sort > "$evidence_dir/dpkg-before.tsv"
awk -F '\t' -v pattern="$nvidia_package_regex" '$1 ~ pattern {print}' "$evidence_dir/dpkg-before.tsv" > "$evidence_dir/nvidia-packages-before.tsv"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader > "$evidence_dir/nvidia-smi-before.txt"

nginx_present_before=0
nginx_enabled_before=absent
nginx_active_before=absent
if systemctl list-unit-files --type=service --no-legend 2>/dev/null | grep -q '^nginx\.service'; then
  nginx_present_before=1
  nginx_enabled_before="$(systemctl is-enabled nginx.service 2>/dev/null || true)"
  nginx_active_before="$(systemctl is-active nginx.service 2>/dev/null || true)"
  case "$nginx_enabled_before" in enabled|disabled|masked) ;; *) printf 'unsupported nginx enabled state: %s\n' "$nginx_enabled_before" >&2; exit 1 ;; esac
  test "$nginx_active_before" = inactive || {
    printf 'nginx must be inactive before Phase 1 install: %s\n' "$nginx_active_before" >&2
    exit 1
  }
fi

work_dir="$(mktemp -d --tmpdir=/tmp substation-host-install.XXXXXX)"
policy_path=/usr/sbin/policy-rc.d
policy_backup="$evidence_dir/policy-rc.d.before"
policy_existed_before=0
policy_mode_before=-
policy_sha_before=-
policy_blocker_sha=-
policy_active=0

capture_partial_packages() {
  test -s "$evidence_dir/dpkg-before.tsv" || return 0
  if test ! -e "$evidence_dir/dpkg-after.tsv"; then
    dpkg-query -W -f='${db:Status-Abbrev}\t${binary:Package}\t${Version}\n' 2>/dev/null \
      | awk -F '\t' '$1 == "ii " {print $2 "\t" $3}' | LC_ALL=C sort > "$evidence_dir/dpkg-after.tsv" || true
  fi
  if test -s "$evidence_dir/dpkg-after.tsv" && test ! -e "$evidence_dir/host-install-new-packages.txt"; then
    comm -13 <(cut -f1 "$evidence_dir/dpkg-before.tsv") <(cut -f1 "$evidence_dir/dpkg-after.tsv") \
      > "$evidence_dir/host-install-new-packages.txt" || true
  fi
}

restore_policy() {
  test "$policy_active" -eq 1 || return 0
  if test "$policy_existed_before" -eq 1; then
    test "$(sha256sum "$policy_backup" | awk '{print $1}')" = "$policy_sha_before"
    sudo install -m "$policy_mode_before" "$policy_backup" "$policy_path"
  else
    if sudo test -e "$policy_path"; then
      test "$(sudo sha256sum "$policy_path" | awk '{print $1}')" = "$policy_blocker_sha"
      sudo unlink -- "$policy_path"
    fi
  fi
  policy_active=0
}

cleanup() {
  local rc=$?
  set +e
  capture_partial_packages
  restore_policy
  find "$work_dir" -depth -delete 2>/dev/null
  return "$rc"
}
trap cleanup EXIT

if test -e "$policy_path"; then
  test -f "$policy_path"
  test ! -L "$policy_path"
  policy_existed_before=1
  policy_mode_before="$(sudo stat -c '%a' "$policy_path")"
  policy_sha_before="$(sudo sha256sum "$policy_path" | awk '{print $1}')"
  sudo install -m 0600 "$policy_path" "$policy_backup"
  sudo chown "$(id -u):$(id -g)" "$policy_backup"
fi
printf '#!/bin/sh\nexit 101\n' > "$work_dir/policy-rc.d"
policy_blocker_sha="$(sha256sum "$work_dir/policy-rc.d" | awk '{print $1}')"
sudo install -m 0755 "$work_dir/policy-rc.d" "$policy_path"
policy_active=1

cat > "$evidence_dir/install-state.env" <<EOF
run_id=$run_id
implementation_commit=$implementation_commit
package_manifest_sha256=$package_manifest_sha256
policy_existed_before=$policy_existed_before
policy_mode_before=$policy_mode_before
policy_sha_before=$policy_sha_before
nginx_present_before=$nginx_present_before
nginx_enabled_before=$nginx_enabled_before
nginx_active_before=$nginx_active_before
EOF

managed_manifest="$evidence_dir/install-managed-files.tsv"
printf 'path\texisted_before\tsha256_before\tsha256_after\n' > "$managed_manifest"
install_managed_file() {
  local source_file="$1" target_file="$2" mode="$3"
  local before_sha=- after_sha existed=0
  case "$target_file" in
    /usr/share/keyrings/ros-archive-keyring.gpg|/etc/apt/sources.list.d/ros2.list|/usr/share/keyrings/gazebo-archive-keyring.gpg|/etc/apt/sources.list.d/gazebo-stable.list) ;;
    *) printf 'install-host: unmanaged target rejected: %s\n' "$target_file" >&2; return 1 ;;
  esac
  test ! -L "$target_file"
  after_sha="$(sha256sum "$source_file" | awk '{print $1}')"
  if test -e "$target_file"; then
    test -f "$target_file"
    existed=1
    before_sha="$(sudo sha256sum "$target_file" | awk '{print $1}')"
    test "$before_sha" = "$after_sha" || {
      printf 'install-host: incompatible existing file: %s\n' "$target_file" >&2
      return 1
    }
  else
    sudo install -D -m "$mode" "$source_file" "$target_file"
    test "$(sudo sha256sum "$target_file" | awk '{print $1}')" = "$after_sha"
  fi
  printf '%s\t%s\t%s\t%s\n' "$target_file" "$existed" "$before_sha" "$after_sha" >> "$managed_manifest"
}

curl --fail --location --silent --show-error https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o "$work_dir/ros.key"
gpg --batch --yes --dearmor --output "$work_dir/ros-archive-keyring.gpg" "$work_dir/ros.key"
install_managed_file "$work_dir/ros-archive-keyring.gpg" /usr/share/keyrings/ros-archive-keyring.gpg 0644

architecture="$(dpkg --print-architecture)"
codename="$(. /etc/os-release && printf '%s' "$VERSION_CODENAME")"
test "$architecture" = amd64
test "$codename" = noble
printf 'deb [arch=%s signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] https://packages.ros.org/ros2/ubuntu %s main\n' "$architecture" "$codename" > "$work_dir/ros2.list"
install_managed_file "$work_dir/ros2.list" /etc/apt/sources.list.d/ros2.list 0644

curl --fail --location --silent --show-error https://packages.osrfoundation.org/gazebo.gpg -o "$work_dir/gazebo.gpg"
gpg --batch --yes --dearmor --output "$work_dir/gazebo-archive-keyring.gpg" "$work_dir/gazebo.gpg"
install_managed_file "$work_dir/gazebo-archive-keyring.gpg" /usr/share/keyrings/gazebo-archive-keyring.gpg 0644
printf 'deb [arch=%s signed-by=/usr/share/keyrings/gazebo-archive-keyring.gpg] https://packages.osrfoundation.org/gazebo/ubuntu-stable %s main\n' "$architecture" "$codename" > "$work_dir/gazebo-stable.list"
install_managed_file "$work_dir/gazebo-stable.list" /etc/apt/sources.list.d/gazebo-stable.list 0644

sudo apt-get update
mapfile -t requested_packages < config/environment/apt-packages.txt
apt-get --simulate install --no-install-recommends "${requested_packages[@]}" > "$evidence_dir/apt-install-simulation.txt"
! grep -Eq '^Remv ' "$evidence_dir/apt-install-simulation.txt"
! grep -Eq '^Inst .*\[[^]]+\]' "$evidence_dir/apt-install-simulation.txt"
if grep -Eq "^(Inst|Remv) ${nvidia_package_regex#^}" "$evidence_dir/apt-install-simulation.txt"; then
  printf '%s\n' 'install-host: NVIDIA package transaction rejected' >&2
  exit 1
fi

python3 - config/environment/apt-packages.txt "$evidence_dir/apt-install-simulation.txt" "$evidence_dir/apt-candidates.tsv" "$evidence_dir/apt-policy-origins.tsv" <<'PY'
import re
import subprocess
import sys
from pathlib import Path

requested_path, simulation_path, candidates_path, origins_path = map(Path, sys.argv[1:])
requested = {line for line in requested_path.read_text(encoding="utf-8").splitlines() if line}
planned = set(re.findall(r"^Inst\s+(\S+)", simulation_path.read_text(encoding="utf-8"), re.MULTILINE))
packages = sorted(requested | planned)

ubuntu = {"http://archive.ubuntu.com/ubuntu", "http://security.ubuntu.com/ubuntu", "https://archive.ubuntu.com/ubuntu", "https://security.ubuntu.com/ubuntu"}
ros = {"http://packages.ros.org/ros2/ubuntu", "https://packages.ros.org/ros2/ubuntu"}
gazebo = {"http://packages.osrfoundation.org/gazebo/ubuntu-stable", "https://packages.osrfoundation.org/gazebo/ubuntu-stable"}
locked = {
    "ros-jazzy-ros-gz": "1.0.23-1",
    "ros-jazzy-navigation2": "1.3.12-1",
    "ros-jazzy-nav2-bringup": "1.3.12-1",
    "ros-jazzy-slam-toolbox": "2.8.5-1",
    "ros-jazzy-turtlebot3": "2.3.6-1",
    "ros-jazzy-turtlebot3-simulations": "2.3.7-1",
}

def allowed_for(package):
    base = package.split(":", 1)[0]
    if base.startswith("ros-jazzy-"):
        return ros
    if re.match(r"^(gz-|libgz-|sdformat|libsdformat|ignition-|libignition-)", base):
        return gazebo
    return ubuntu

candidate_rows = []
origin_rows = []
for package in packages:
    completed = subprocess.run(["apt-cache", "policy", package], check=True, text=True, stdout=subprocess.PIPE)
    match = re.search(r"^\s*Candidate:\s*(\S+)", completed.stdout, re.MULTILINE)
    if not match or match.group(1) == "(none)":
        raise SystemExit(f"missing candidate: {package}")
    candidate = match.group(1)
    candidate_rows.append((package, candidate))
    target = False
    origins = set()
    for line in completed.stdout.splitlines():
        version = re.match(r"^\s*(?:\*\*\*\s+)?(\S+)\s+\d+\s*$", line)
        if version:
            target = version.group(1) == candidate
            continue
        if target:
            origin = re.match(r"^\s+\d+\s+(https?://\S+)\s+", line)
            if origin:
                origins.add(origin.group(1).rstrip("/"))
    allowed = allowed_for(package)
    if not origins or not origins <= allowed:
        raise SystemExit(f"candidate origin rejected: {package}: {sorted(origins)}")
    origin_rows.append((package, candidate, ",".join(sorted(origins))))
    base = package.split(":", 1)[0]
    if base in locked:
        prefix = locked[base]
        suffix = candidate[len(prefix):] if candidate.startswith(prefix) else ""
        if not candidate.startswith(prefix) or (suffix and suffix[0].isdigit()):
            raise SystemExit(f"locked candidate mismatch: {base}: {candidate}")

candidates_path.write_text("package\tcandidate\n" + "".join(f"{p}\t{v}\n" for p, v in candidate_rows), encoding="utf-8")
origins_path.write_text("package\tcandidate\torigins\n" + "".join(f"{p}\t{v}\t{o}\n" for p, v, o in origin_rows), encoding="utf-8")
PY

sudo DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends --no-upgrade "${requested_packages[@]}"

rosdep_path=/etc/ros/rosdep/sources.list.d/20-default.list
rosdep_existed=0
rosdep_before=-
if test -e "$rosdep_path"; then
  test -f "$rosdep_path"
  rosdep_existed=1
  rosdep_before="$(sudo sha256sum "$rosdep_path" | awk '{print $1}')"
else
  sudo rosdep init
fi
rosdep_after="$(sudo sha256sum "$rosdep_path" | awk '{print $1}')"
if test "$rosdep_existed" -eq 1; then test "$rosdep_before" = "$rosdep_after"; fi
printf '%s\t%s\t%s\t%s\n' "$rosdep_path" "$rosdep_existed" "$rosdep_before" "$rosdep_after" >> "$managed_manifest"
rosdep update --rosdistro jazzy

if systemctl list-unit-files --type=service --no-legend 2>/dev/null | grep -q '^nginx\.service'; then
  sudo systemctl disable --now nginx.service
fi

dpkg-query -W -f='${db:Status-Abbrev}\t${binary:Package}\t${Version}\n' 2>/dev/null \
  | awk -F '\t' '$1 == "ii " {print $2 "\t" $3}' | LC_ALL=C sort > "$evidence_dir/dpkg-after.tsv"
comm -13 <(cut -f1 "$evidence_dir/dpkg-before.tsv") <(cut -f1 "$evidence_dir/dpkg-after.tsv") > "$evidence_dir/host-install-new-packages.txt"
python3 - "$evidence_dir/dpkg-before.tsv" "$evidence_dir/dpkg-after.tsv" "$evidence_dir/host-install-version-changes.tsv" <<'PY'
import sys
from pathlib import Path

def load(path):
    return dict(line.split("\t", 1) for line in Path(path).read_text(encoding="utf-8").splitlines())

before, after = load(sys.argv[1]), load(sys.argv[2])
changes = [(package, before[package], after[package]) for package in sorted(before.keys() & after.keys()) if before[package] != after[package]]
Path(sys.argv[3]).write_text("package\tbefore_version\tafter_version\n" + "".join(f"{p}\t{b}\t{a}\n" for p, b, a in changes), encoding="utf-8")
if changes:
    raise SystemExit("pre-existing package versions changed; rollback review required")
PY

awk -F '\t' -v pattern="$nvidia_package_regex" '$1 ~ pattern {print}' "$evidence_dir/dpkg-after.tsv" > "$evidence_dir/nvidia-packages-after.tsv"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader > "$evidence_dir/nvidia-smi-after.txt"
cmp "$evidence_dir/nvidia-packages-before.tsv" "$evidence_dir/nvidia-packages-after.tsv"
cmp "$evidence_dir/nvidia-smi-before.txt" "$evidence_dir/nvidia-smi-after.txt"

source /opt/ros/jazzy/setup.bash
test "$ROS_DISTRO" = jazzy
gz sim --versions > "$evidence_dir/gazebo-versions.txt"
grep -Eq '(^|[^0-9])8\.[0-9]' "$evidence_dir/gazebo-versions.txt"

restore_policy
printf 'path\texisted_before\tmode_before\tsha256_before\trestored\n%s\t%s\t%s\t%s\t1\n' \
  "$policy_path" "$policy_existed_before" "$policy_mode_before" "$policy_sha_before" > "$evidence_dir/policy-rc.d-state.tsv"
printf 'state=PASS\ninstall_state_sha256=%s\nmanaged_files_sha256=%s\nnew_packages_sha256=%s\ndpkg_after_sha256=%s\n' \
  "$(sha256sum "$evidence_dir/install-state.env" | awk '{print $1}')" \
  "$(sha256sum "$managed_manifest" | awk '{print $1}')" \
  "$(sha256sum "$evidence_dir/host-install-new-packages.txt" | awk '{print $1}')" \
  "$(sha256sum "$evidence_dir/dpkg-after.tsv" | awk '{print $1}')" > "$evidence_dir/install-complete.env"

printf '%s\n' 'install-host: PASS'
