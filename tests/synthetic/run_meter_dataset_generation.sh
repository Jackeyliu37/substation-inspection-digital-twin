#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf '%s\n' 'usage: bash tests/synthetic/run_meter_dataset_generation.sh --mode smoke|full --run-id UUID --output-dir /var/lib/substation/datasets/synthetic/gazebo-meter/GENERATION_ID.staging' >&2
  exit 2
}

test "$#" -eq 6 || usage
test "$1" = --mode || usage
mode="$2"
test "$mode" = smoke || test "$mode" = full || usage
test "$3" = --run-id || usage
run_id="$4"
test "$5" = --output-dir || usage
output_dir="$6"
[[ "$run_id" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$ ]] || usage
[[ "$output_dir" = /* ]] || usage
[[ "$output_dir" = /var/lib/substation/datasets/synthetic/gazebo-meter/*.staging ]] || usage
test -d "$output_dir"
test ! -L "$output_dir"
test -z "$(find "$output_dir" -mindepth 1 -maxdepth 1 -print -quit)"
final_dir="${output_dir%.staging}"
test ! -e "$final_dir"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
test -z "$(git status --porcelain --untracked-files=no)"
test -f ros2_ws/install/setup.bash
free_bytes="$(stat -f -c '%a*%S' "$output_dir" | awk -F\* '{print $1*$2}')"
test "$free_bytes" -ge 21474836480
source .phase1-run.env
bash scripts/check_environment_seal.sh --evidence-dir "$PHASE1_EVIDENCE_FINAL" \
  > "$output_dir/phase1-seal-check.log"

set +u
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
set -u
implementation_commit="$(git rev-parse HEAD)"
generation_id="$(python3 -m substation_gazebo.meter_dataset_package identity \
  --config "$repo_root/configs/meter_dataset_generation.yaml" \
  --registry "$repo_root/configs/devices.yaml" --mode "$mode")"
test "$(basename "$output_dir")" = "$generation_id.staging" || {
  printf 'generation-id-mismatch: expected=%s actual=%s\n' \
    "$generation_id.staging" "$(basename "$output_dir")" >&2
  exit 2
}

capture_root="$output_dir/gazebo-meter-locator-v1.staging"
dataset_root="$output_dir/dataset/gazebo-meter-locator-v1"
install -d -m 0750 "$capture_root"
partition="meter-dataset-$run_id"
started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'run_id=%s\nmode=%s\ngeneration_id=%s\nimplementation_commit=%s\nstarted_at=%s\npartition=%s\nfree_bytes=%s\n' \
  "$run_id" "$mode" "$generation_id" "$implementation_commit" "$started_at" \
  "$partition" "$free_bytes" > "$output_dir/run.env"
git status --short --branch > "$output_dir/git-status.txt"
sha256sum \
  configs/devices.yaml \
  configs/meter_dataset_generation.yaml \
  ros2_ws/src/substation_gazebo/models/synthetic_meter/model.sdf \
  ros2_ws/src/substation_gazebo/worlds/meter_dataset_world.sdf \
  > "$output_dir/input-sha256.txt"
printf '{"generation_id":"%s","generator_git_commit":"%s","run_id":"%s","sample_mode":"%s"}\n' \
  "$generation_id" "$implementation_commit" "$run_id" "$mode" \
  > "$output_dir/provenance.json"

launch_pid=""
cleanup() {
  if test -n "$launch_pid" && kill -0 -- "-$launch_pid" 2>/dev/null; then
    kill -TERM -- "-$launch_pid" 2>/dev/null || true
    for _attempt in $(seq 1 40); do
      kill -0 -- "-$launch_pid" 2>/dev/null || break
      sleep 0.25
    done
    if kill -0 -- "-$launch_pid" 2>/dev/null; then
      kill -KILL -- "-$launch_pid" 2>/dev/null || true
    fi
    wait "$launch_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

setsid env -u DISPLAY ROS_LOCALHOST_ONLY=1 GZ_PARTITION="$partition" \
  ros2 launch substation_gazebo meter_dataset.launch.py \
  run_id:="$run_id" output_dir:="$capture_root" \
  generation_config:="$repo_root/configs/meter_dataset_generation.yaml" \
  registry_path:="$repo_root/configs/devices.yaml" \
  expected_commit:="$implementation_commit" sample_mode:="$mode" \
  gz_partition:="$partition" > "$output_dir/launch.log" 2>&1 &
launch_pid=$!

deadline=$((SECONDS + 2700))
while test ! -s "$capture_root/generation-result.json"; do
  if ! kill -0 "$launch_pid" 2>/dev/null; then
    printf '%s\n' 'meter dataset launch exited before writing generation result' >&2
    exit 1
  fi
  test "$SECONDS" -lt "$deadline" || {
    printf '%s\n' 'meter dataset generation exceeded 45 minutes' >&2
    exit 1
  }
  sleep 1
done

printf 'pid\tppid\tpgid\targs\n' > "$output_dir/process-tree.tsv"
ps -eo pid=,ppid=,pgid=,args= | awk -v pgid="$launch_pid" '$3 == pgid' \
  >> "$output_dir/process-tree.tsv"
gz_pid="$(awk '/gz sim/ {print $1; exit}' "$output_dir/process-tree.tsv")"
test -n "$gz_pid"
tr '\0' '\n' < "/proc/$gz_pid/environ" > "$output_dir/gazebo-environ.txt"
grep -Fxq "GZ_PARTITION=$partition" "$output_dir/gazebo-environ.txt"
! grep -q '^DISPLAY=' "$output_dir/gazebo-environ.txt"

python3 - "$capture_root/generation-result.json" <<'PY'
import json
import sys
from pathlib import Path

result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if result.get("status") != "accepted":
    raise SystemExit(f"generation did not complete: {result}")
PY

cleanup
trap - EXIT INT TERM
! kill -0 -- "-$launch_pid" 2>/dev/null

install -d -m 0750 "$output_dir/dataset"
mv -- "$capture_root" "$dataset_root"
python3 -m substation_gazebo.meter_dataset_package package \
  --dataset-root "$dataset_root" \
  --config "$repo_root/configs/meter_dataset_generation.yaml" \
  --registry "$repo_root/configs/devices.yaml" --mode "$mode" \
  --provenance-json "$output_dir/provenance.json" \
  --zip-output "$output_dir/gazebo-meter-locator-v1.zip" \
  > "$output_dir/package.log"
grep -Fxq 'meter-dataset-package: PASS' "$output_dir/package.log"
(cd "$dataset_root" && sha256sum -c SHA256SUMS) > "$output_dir/checksums.log"
python3 - "$output_dir/gazebo-meter-locator-v1.zip" \
  > "$output_dir/zip-test.log" <<'PY'
import sys
import zipfile
from pathlib import Path

archive_path = Path(sys.argv[1])
with zipfile.ZipFile(archive_path) as archive:
    corrupt = archive.testzip()
    if corrupt is not None:
        raise SystemExit(f"corrupt ZIP member: {corrupt}")
    print(f"zip-test: PASS: {len(archive.infolist())} files")
PY

completed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s\n' '<?xml version="1.0" encoding="UTF-8"?><testsuite name="meter-dataset" tests="1" failures="0"><testcase name="generation-package-contract"/></testsuite>' \
  > "$output_dir/junit.xml"
python3 - "$output_dir/result.json" "$run_id" "$mode" "$generation_id" \
  "$implementation_commit" "$started_at" "$completed_at" <<'PY'
import json
import sys
from pathlib import Path

Path(sys.argv[1]).write_text(json.dumps({
    "schema_version": 1,
    "status": "passed",
    "run_id": sys.argv[2],
    "sample_mode": sys.argv[3],
    "generation_id": sys.argv[4],
    "generator_git_commit": sys.argv[5],
    "started_at": sys.argv[6],
    "completed_at": sys.argv[7],
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
(
  cd "$output_dir"
  find . -type f ! -path ./SHA256SUMS -print0 \
    | sort -z | xargs -0 sha256sum > SHA256SUMS
)
mv -- "$output_dir" "$final_dir"
printf 'meter-dataset-%s: PASS\n' "$mode"
printf '%s\n' 'meter-dataset-package: PASS'
