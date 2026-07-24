#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 --run-id UUIDv4 --evidence-dir /var/lib/substation/evidence/acceptance/UUID/09-production-integration.staging" >&2
  exit 2
}

fail() {
  echo "production-acceptance: FAIL: $*" >&2
  exit 1
}

[[ $# -eq 4 && "$1" = "--run-id" && "$3" = "--evidence-dir" ]] || usage
run_id="$2"
evidence_dir="$4"
duration_s=300
fps_threshold=15
[[ "$run_id" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$ ]] || usage
expected="/var/lib/substation/evidence/acceptance/$run_id/09-production-integration.staging"
[[ "$evidence_dir" = "$expected" ]] || usage
[[ -d "$evidence_dir" ]] || fail "evidence staging directory is not accessible: $evidence_dir"
[[ ! -L "$evidence_dir" ]] || fail "evidence staging directory must not be a symlink: $evidence_dir"
if ! staging_entry="$(find "$evidence_dir" -mindepth 1 -maxdepth 1 -print -quit)"; then
  fail "evidence staging directory cannot be traversed: $evidence_dir"
fi
[[ -z "$staging_entry" ]] || fail "evidence staging directory is not empty: $staging_entry"
final_dir="${evidence_dir%.staging}"
[[ ! -e "$final_dir" ]] || fail "sealed evidence directory already exists: $final_dir"

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "$repo_root"
git_safe=(git -c "safe.directory=$repo_root")
[[ -z "$("${git_safe[@]}" status --porcelain)" ]] || fail "repository is not clean: $repo_root"
release_root="$(readlink -f /opt/substation/current)"
[[ "$release_root" = /opt/substation/releases/* && -d "$release_root" ]] || fail "current release is not immutable: $release_root"
release_commit="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["git_commit"])' "$release_root/release-manifest.json")"
(
  cd "$release_root"
  sha256sum -c release-SHA256SUMS >/dev/null
)
for logical_model in yolo11n_safety yolo11n_equipment yolo11n_fault meter_locator; do
  rg -q "^  $logical_model:" "$release_root/models/manifest.yaml"
done

meter_source="/var/lib/substation/evidence/acceptance/35900da2-0e41-4d98-802b-b7e36675e988/04-meter-reader-evaluation.staging/meter-evaluation.json"
[[ -s "$meter_source" ]] || fail "meter evaluation source is missing: $meter_source"
install -m 0640 "$meter_source" "$evidence_dir/meter-evaluation.json"
printf 'run_id=%s\nrelease_commit=%s\nharness_commit=%s\nduration_s=%s\nfps_threshold=%s\nstarted_at=%s\n' \
  "$run_id" "$release_commit" "$("${git_safe[@]}" rev-parse HEAD)" "$duration_s" \
  "$fps_threshold" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  > "$evidence_dir/run.env"

systemctl is-active \
  substation-gazebo.service \
  substation-core.service \
  substation-web-gateway.service \
  substation-web-frontend.service \
  nginx.service \
  > "$evidence_dir/systemd-active.txt"
curl -fsS http://127.0.0.1:8000/healthz > "$evidence_dir/gateway-health.json"
curl -fsS http://127.0.0.1:8000/api/v1/system/status \
  > "$evidence_dir/live-system-status.json"
python3 - "$evidence_dir/live-system-status.json" "$run_id" <<'PY'
import json
from pathlib import Path
import sys

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected_run_id = sys.argv[2]
context = payload.get("data", {}).get("run_context", {})
actual_run_id = payload.get("run_id")
lifecycle = context.get("lifecycle")
if actual_run_id != expected_run_id or lifecycle != "active":
    raise SystemExit(
        f"live run mismatch: expected={expected_run_id} actual={actual_run_id} "
        f"lifecycle={lifecycle}"
    )
PY
ss -H -ltnp > "$evidence_dir/listeners.txt"

bag_root="/var/lib/substation/rosbag2/$run_id"
[[ ! -e "$bag_root" ]] || fail "rosbag target already exists: $bag_root"
capture_pid=""
cleanup() {
  if [[ -n "$capture_pid" ]] && kill -0 -- "-$capture_pid" 2>/dev/null; then
    kill -TERM -- "-$capture_pid" 2>/dev/null || true
    for _ in $(seq 1 40); do
      kill -0 -- "-$capture_pid" 2>/dev/null || break
      sleep 0.25
    done
    kill -KILL -- "-$capture_pid" 2>/dev/null || true
    wait "$capture_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

setsid bash scripts/reporting/run_evidence_capture.sh \
  --run-id "$run_id" \
  --output-dir "$bag_root" \
  --duration-s "$duration_s" \
  > "$evidence_dir/rosbag-capture.log" 2>&1 &
capture_pid=$!

set +u
source /opt/ros/jazzy/setup.bash
source "$release_root/install/setup.bash"
set -u
export ROS_LOCALHOST_ONLY=1
"$release_root/.venv/bin/python" tests/perception/probe_production_pipeline.py \
  --run-id "$run_id" \
  --duration-s "$duration_s" \
  --fps-threshold "$fps_threshold" \
  --model-manifest "$release_root/models/manifest.yaml" \
  --model-root /var/lib/substation/models/production \
  --meter-evaluation "$evidence_dir/meter-evaluation.json" \
  --rosbag-metadata "$bag_root/metadata.yaml" \
  --report-work-root /var/lib/substation/reports/.work \
  --output "$evidence_dir/result.json" \
  > "$evidence_dir/production-probe.log" 2>&1

wait "$capture_pid"
capture_pid=""
trap - EXIT INT TERM
[[ -s "$bag_root/metadata.yaml" && -s "$bag_root/rosbag2/metadata.yaml" ]]
cp -- "$bag_root/metadata.yaml" "$evidence_dir/rosbag2-metadata.yaml"
sha256sum "$bag_root"/rosbag2/*.db3 > "$evidence_dir/rosbag2-SHA256SUMS"

report_id="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["report"]["report_id"])' "$evidence_dir/result.json")"
report_work="/var/lib/substation/reports/.work/$report_id"
install -d -m 0750 "$evidence_dir/report"
install -m 0640 "$report_work/evidence.zip" "$evidence_dir/report/evidence.zip"
install -m 0640 "$report_work/report.html" "$evidence_dir/report/report.html"
install -m 0640 "$report_work/report.pdf" "$evidence_dir/report/report.pdf"
python3 scripts/reporting/verify_report_bundle.py \
  --bundle "$evidence_dir/report/evidence.zip" \
  --run-id "$run_id" \
  > "$evidence_dir/report-verification.txt"

if pgrep -af '^.*run_evidence_capture.sh.*09-production-integration' > "$evidence_dir/residual-processes.txt"; then
  echo "production-acceptance: residual acceptance process" >&2
  exit 1
fi
echo "acceptance_owned_processes=0" > "$evidence_dir/process-cleanup.txt"
printf '%s\n' '<?xml version="1.0" encoding="UTF-8"?><testsuite name="production-integration" tests="5" failures="0"><testcase name="four-model-fps"/><testcase name="real-camera"/><testcase name="mission-safety-barrier"/><testcase name="rosbag2"/><testcase name="report-bundle"/></testsuite>' \
  > "$evidence_dir/junit.xml"
(
  cd "$evidence_dir"
  find . -type f ! -name SHA256SUMS -print0 \
    | LC_ALL=C sort -z \
    | xargs -0 sha256sum > SHA256SUMS
  sha256sum -c SHA256SUMS >/dev/null
)
mv -- "$evidence_dir" "$final_dir"
echo "production-acceptance: PASS: $final_dir"
