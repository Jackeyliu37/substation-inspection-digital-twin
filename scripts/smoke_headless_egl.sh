#!/usr/bin/env bash
set -euo pipefail

if test "$#" -ne 2 || test "$1" != --evidence-dir; then
  printf '%s\n' 'usage: bash scripts/smoke_headless_egl.sh --evidence-dir /var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment.staging' >&2
  exit 2
fi
evidence_dir="$2"
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
source scripts/lib/environment_common.sh
environment_require_evidence_dir "$evidence_dir"
world=tests/environment/fixtures/headless_camera.sdf
test -s "$world"
frame_log="$evidence_dir/egl-frame.txt"
topic_log="$evidence_dir/egl-topics.txt"
: > "$evidence_dir/egl.log"
: > "$frame_log"
printf 'DISPLAY-present-before-unset=%s\n' "${DISPLAY+x}" >> "$evidence_dir/egl.log"
printf '%s\n' 'command=env -u DISPLAY gz sim -s -r --headless-rendering tests/environment/fixtures/headless_camera.sdf' >> "$evidence_dir/egl.log"
env -u DISPLAY gz sim -s -r --headless-rendering "$world" >> "$evidence_dir/egl.log" 2>&1 &
gz_pid=$!
cleanup() {
  if kill -0 "$gz_pid" >/dev/null 2>&1; then kill "$gz_pid"; wait "$gz_pid" || true; fi
}
trap cleanup EXIT
topic_ready=0
for _ in $(seq 1 30); do
  if ! kill -0 "$gz_pid" >/dev/null 2>&1; then printf '%s\n' 'gazebo exited before camera topic became ready' >&2; exit 1; fi
  env -u DISPLAY gz topic -l > "$topic_log"
  if grep -Fxq '/phase1/camera' "$topic_log"; then topic_ready=1; break; fi
  sleep 1
done
test "$topic_ready" -eq 1
set +e
env -u DISPLAY timeout 8s gz topic -e -t /phase1/camera > "$frame_log" 2>> "$evidence_dir/egl.log"
frame_rc=$?
set -e
test "$frame_rc" -eq 0 || test "$frame_rc" -eq 124
grep -Eq '^width: 64$' "$frame_log"
grep -Eq '^height: 48$' "$frame_log"
grep -Eq 'pixel_format_type: RGB_INT8|pixel_format: RGB_INT8|pixel_format_type: 3' "$frame_log"
printf '%s\n' 'camera-topic=/phase1/camera' >> "$evidence_dir/egl.log"
grep -m1 -E '^width:|^height:|pixel_format' "$frame_log" >> "$evidence_dir/egl.log"
printf '%s\n' 'headless-egl: PASS' >> "$evidence_dir/egl.log"
trap - EXIT
cleanup
printf '%s\n' 'headless-egl: PASS'
