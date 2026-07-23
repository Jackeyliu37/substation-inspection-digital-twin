#!/usr/bin/env bash
set -euo pipefail

if test "$#" -eq 3 && test "$1" = --plan && test "$2" = --evidence-dir; then
  mode=plan
  evidence_dir="$3"
  confirm_run_id=
elif test "$#" -eq 5 && test "$1" = --apply && test "$2" = --evidence-dir && test "$4" = --confirm-run-id; then
  mode=apply
  evidence_dir="$3"
  confirm_run_id="$5"
else
  printf '%s\n' 'usage: bash scripts/rollback_host.sh --plan --evidence-dir DIR | --apply --evidence-dir DIR --confirm-run-id RUN_ID' >&2
  exit 2
fi

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
source scripts/lib/environment_common.sh
environment_require_evidence_dir "$evidence_dir"

state_file="$evidence_dir/install-state.env"
before_packages="$evidence_dir/dpkg-before.tsv"
after_packages="$evidence_dir/dpkg-after.tsv"
additions="$evidence_dir/host-install-new-packages.txt"
managed_manifest="$evidence_dir/install-managed-files.tsv"
for required in "$state_file" "$before_packages" "$after_packages" "$managed_manifest"; do test -s "$required"; done
test -f "$additions"

state_values="$(python3 - "$state_file" <<'PY'
import re
import sys
from pathlib import Path

expected = {
    "run_id", "implementation_commit", "package_manifest_sha256",
    "policy_existed_before", "policy_mode_before", "policy_sha_before",
    "nginx_present_before", "nginx_enabled_before", "nginx_active_before",
}
values = {}
for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    if not re.fullmatch(r"[a-z_]+=[A-Za-z0-9_.:+-]+", line):
        raise SystemExit("unsafe install-state line")
    key, value = line.split("=", 1)
    if key in values:
        raise SystemExit("duplicate install-state key")
    values[key] = value
if set(values) != expected:
    raise SystemExit("install-state key set changed")
if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", values["run_id"]):
    raise SystemExit("invalid run id")
if values["policy_existed_before"] not in {"0", "1"} or values["nginx_present_before"] not in {"0", "1"}:
    raise SystemExit("invalid state boolean")
if values["nginx_present_before"] == "1":
    if values["nginx_enabled_before"] not in {"enabled", "disabled", "masked"}:
        raise SystemExit("invalid nginx enabled state")
    if values["nginx_active_before"] != "inactive":
        raise SystemExit("invalid nginx active state")
print("\t".join(values[key] for key in ("run_id", "nginx_present_before", "nginx_enabled_before", "nginx_active_before")))
PY
)"
IFS=$'\t' read -r run_id nginx_present_before nginx_enabled_before nginx_active_before <<<"$state_values"
test "$run_id" = "$(basename "$(dirname "$evidence_dir")")"

allowed_managed_paths=(
  /usr/share/keyrings/ros-archive-keyring.gpg
  /etc/apt/sources.list.d/ros2.list
  /usr/share/keyrings/gazebo-archive-keyring.gpg
  /etc/apt/sources.list.d/gazebo-stable.list
  /etc/ros/rosdep/sources.list.d/20-default.list
)
python3 - "$managed_manifest" "${allowed_managed_paths[@]}" <<'PY'
import csv
import re
import sys
from pathlib import Path

rows = list(csv.DictReader(Path(sys.argv[1]).open(encoding="utf-8"), delimiter="\t"))
allowed = set(sys.argv[2:])
seen = set()
if not rows:
    raise SystemExit("empty managed-file manifest")
for row in rows:
    path = row["path"]
    if path not in allowed or path in seen:
        raise SystemExit(f"managed path rejected: {path}")
    seen.add(path)
    if row["existed_before"] not in {"0", "1"}:
        raise SystemExit("invalid existed flag")
    if not re.fullmatch(r"[0-9a-f]{64}", row["sha256_after"]):
        raise SystemExit("invalid after sha")
    if row["existed_before"] == "0":
        if row["sha256_before"] != "-":
            raise SystemExit("created file has before sha")
    elif row["sha256_before"] != row["sha256_after"]:
        raise SystemExit("pre-existing managed file changed")
PY

current_packages="$(mktemp --tmpdir=/tmp rollback-current.XXXXXX)"
simulated_removals="$(mktemp --tmpdir=/tmp rollback-removals.XXXXXX)"
cleanup() { unlink -- "$current_packages" "$simulated_removals" 2>/dev/null || true; }
trap cleanup EXIT
dpkg-query -W -f='${db:Status-Abbrev}\t${binary:Package}\t${Version}\n' 2>/dev/null \
  | awk -F '\t' '$1 == "ii " {print $2 "\t" $3}' | LC_ALL=C sort > "$current_packages"

python3 - "$before_packages" "$after_packages" "$current_packages" "$additions" <<'PY'
import re
import sys
from pathlib import Path

def load(path):
    return dict(line.split("\t", 1) for line in Path(path).read_text(encoding="utf-8").splitlines())

before, after, current = load(sys.argv[1]), load(sys.argv[2]), load(sys.argv[3])
recorded = [line for line in Path(sys.argv[4]).read_text(encoding="utf-8").splitlines() if line]
expected = sorted(after.keys() - before.keys())
if recorded != expected:
    raise SystemExit("new-package evidence does not match captured before/after state")
changed_after = [package for package in before.keys() & after.keys() if before[package] != after[package]]
if changed_after:
    raise SystemExit(f"captured install changed pre-existing packages: {changed_after}")
if any(not re.fullmatch(r"[a-z0-9][a-z0-9+.-]*(?::[a-z0-9]+)?", package) for package in recorded):
    raise SystemExit("invalid derived package name")
changed_current = [package for package in before if current.get(package) != before[package]]
missing_added = [package for package in recorded if current.get(package) != after[package]]
if changed_current or missing_added:
    raise SystemExit(f"live package state diverged: pre-existing={changed_current} additions={missing_added}")
PY
mapfile -t added_packages < "$additions"

if test "${#added_packages[@]}" -gt 0; then
  apt-get --simulate remove --no-auto-remove --yes "${added_packages[@]}" \
    | awk '$1 == "Remv" {print $2}' | LC_ALL=C sort -u > "$simulated_removals"
  cmp "$additions" "$simulated_removals"
fi

printf 'run_id=%s\n' "$run_id"
printf '%s\n' 'packages-to-remove:'
sed 's/^/  /' "$additions"
printf '%s\n' 'task-created-files-to-remove:'
awk -F '\t' 'NR > 1 && $2 == "0" {print "  " $1}' "$managed_manifest"
printf '%s\n' 'rollback-host-plan: PASS'
if test "$mode" = plan; then exit 0; fi

test "$confirm_run_id" = "$run_id"
sudo -v
if test "${#added_packages[@]}" -gt 0; then
  sudo apt-get remove --no-auto-remove --yes "${added_packages[@]}"
fi

while IFS=$'\t' read -r path existed_before _ sha_after; do
  test "$path" != path || continue
  if test "$existed_before" = 0; then
    case "$path" in
      /usr/share/keyrings/ros-archive-keyring.gpg|/etc/apt/sources.list.d/ros2.list|/usr/share/keyrings/gazebo-archive-keyring.gpg|/etc/apt/sources.list.d/gazebo-stable.list|/etc/ros/rosdep/sources.list.d/20-default.list) ;;
      *) printf 'rollback-host: unmanaged path rejected: %s\n' "$path" >&2; exit 1 ;;
    esac
    test "$(sudo sha256sum "$path" | awk '{print $1}')" = "$sha_after"
    sudo unlink -- "$path"
  fi
done < "$managed_manifest"

sudo apt-get update
if test "$nginx_present_before" = 1 && systemctl list-unit-files --type=service --no-legend 2>/dev/null | grep -q '^nginx\.service'; then
  case "$nginx_enabled_before" in
    enabled) sudo systemctl enable nginx.service ;;
    disabled) sudo systemctl disable nginx.service ;;
    masked) sudo systemctl mask nginx.service ;;
  esac
  if test "$nginx_active_before" = inactive; then sudo systemctl stop nginx.service; fi
fi

dpkg-query -W -f='${db:Status-Abbrev}\t${binary:Package}\t${Version}\n' 2>/dev/null \
  | awk -F '\t' '$1 == "ii " {print $2 "\t" $3}' | LC_ALL=C sort > "$current_packages"
python3 - "$before_packages" "$current_packages" "$additions" <<'PY'
import sys
from pathlib import Path

def load(path):
    return dict(line.split("\t", 1) for line in Path(path).read_text(encoding="utf-8").splitlines())

before, current = load(sys.argv[1]), load(sys.argv[2])
additions = {line for line in Path(sys.argv[3]).read_text(encoding="utf-8").splitlines() if line}
changed = [package for package in before if current.get(package) != before[package]]
remaining = sorted(additions & current.keys())
if changed or remaining:
    raise SystemExit(f"rollback verification failed: pre-existing={changed} remaining={remaining}")
PY
printf 'state=PASS\nrun_id=%s\nrolled_back_at=%s\n' "$run_id" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$evidence_dir/rollback-complete.env"
printf '%s\n' 'rollback-host-apply: PASS'
