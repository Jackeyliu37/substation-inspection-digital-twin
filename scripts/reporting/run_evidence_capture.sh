#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 --run-id UUID --output-dir PATH [--duration-s SECONDS]" >&2
}

run_id=""
output_dir=""
duration_s="300"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-id) run_id="${2:-}"; shift 2 ;;
    --output-dir) output_dir="${2:-}"; shift 2 ;;
    --duration-s) duration_s="${2:-}"; shift 2 ;;
    *) usage; exit 2 ;;
  esac
done

if [[ ! "$run_id" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$ ]]; then
  echo "evidence-capture: invalid UUIDv4 run id" >&2
  exit 2
fi
if [[ -z "$output_dir" || ! "$duration_s" =~ ^[1-9][0-9]*$ ]]; then
  usage
  exit 2
fi

bag_dir="$output_dir/rosbag2"
if [[ -e "$bag_dir" ]]; then
  echo "evidence-capture: target already exists: $bag_dir" >&2
  exit 1
fi
mkdir -p -- "$output_dir"

topics=(
  /system/run_context
  /camera/image_raw
  /perception/detections
  /perception/meters/readings
  /digital_twin/assets
  /risk/assets
  /risk/alerts
  /mission/inspection_tasks
  /odom
  /plan
  /diagnostics
)

set +e
timeout --foreground --signal=INT --kill-after=10s "${duration_s}s" \
  ros2 bag record --disable-keyboard-controls --storage sqlite3 \
    --output "$bag_dir" --topics "${topics[@]}"
record_status=$?
set -e
if [[ "$record_status" -ne 0 && "$record_status" -ne 124 ]]; then
  echo "evidence-capture: rosbag2 exited with status $record_status" >&2
  exit "$record_status"
fi
if [[ ! -s "$bag_dir/metadata.yaml" ]]; then
  echo "evidence-capture: metadata.yaml missing" >&2
  exit 1
fi
message_count="$(awk '/^  message_count:/ {print $2; exit}' "$bag_dir/metadata.yaml")"
if [[ ! "$message_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "evidence-capture: rosbag2 contains no messages" >&2
  exit 1
fi
install -m 0644 "$bag_dir/metadata.yaml" "$output_dir/metadata.yaml"
printf 'run_id=%s\nduration_s=%s\nrosbag_metadata=%s\n' \
  "$run_id" "$duration_s" "$bag_dir/metadata.yaml" \
  > "$output_dir/capture.env"
echo "evidence-capture: PASS: $bag_dir"
