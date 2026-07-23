#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
source scripts/lib/environment_common.sh

if test "$#" -eq 1 && test "$1" = --list; then
  printf '%s\n' node-linux-x64 yolo11n-base
  exit 0
fi
if test "$#" -ne 4 || test "$1" != --resource || test "$3" != --evidence-dir; then
  printf '%s\n' 'usage: bash scripts/download_phase1_resources.sh --resource node-linux-x64|yolo11n-base|all --evidence-dir DIR' >&2
  exit 2
fi

selection="$2"
evidence_dir="$4"
case "$selection" in
  node-linux-x64|yolo11n-base|all) ;;
  *) printf 'unknown-resource: %s\n' "$selection" >&2; exit 2 ;;
esac
environment_require_evidence_dir "$evidence_dir"

manifest="$evidence_dir/resource-downloads.tsv"
mkdir -p /var/lib/substation/downloads/node/24.18.0
mkdir -p /var/lib/substation/models/base

tmp_manifest="$(mktemp --tmpdir=/tmp)"
download_tmp=
cleanup() {
  test ! -e "$tmp_manifest" || unlink -- "$tmp_manifest"
  test -z "$download_tmp" || test ! -e "$download_tmp" || unlink -- "$download_tmp"
}
trap cleanup EXIT
printf 'resource_id\trevision\tsha256\tsize_bytes\tsource_url\tserver_path\n' > "$tmp_manifest"

manifest_row() {
  local resource_id="$1"
  awk -F '\t' -v id="$resource_id" '$1 == id {print; exit}' "$manifest" 2>/dev/null || true
}

download_file() {
  local source_url="$1"
  local output_path="$2"
  curl --http1.1 -fL --retry 5 --retry-delay 3 --retry-all-errors \
    --connect-timeout 20 --speed-limit 1024 --speed-time 30 \
    "$source_url" -o "$output_path"
}

download_official_yolo_asset() {
  local output_path="$1"
  local api_asset_url=https://api.github.com/repos/ultralytics/assets/releases/assets/340060970
  curl --http1.1 -fL --retry 5 --retry-delay 3 --retry-all-errors \
    --connect-timeout 20 --max-time 900 \
    -H 'Accept: application/octet-stream' \
    "$api_asset_url" -o "$output_path"
}

download_node() {
  local resource_id=node-linux-x64
  local revision=24.18.0
  local archive=node-v24.18.0-linux-x64.tar.xz
  local source_url="https://nodejs.org/dist/v24.18.0/$archive"
  local target_dir=/var/lib/substation/downloads/node/24.18.0
  local target="$target_dir/$archive"
  local sums="$target_dir/SHASUMS256.txt"
  local marker="$target_dir/.substation-resource.json"
  local prior actual expected size
  prior="$(manifest_row "$resource_id")"
  if test -n "$prior"; then
    printf '%s\n' "$prior" >> "$tmp_manifest"
    return
  fi
  if test -s "$target" && test -s "$sums" && test -s "$marker"; then
    expected="$(awk -v file="$archive" '$2 == file {print $1}' "$sums")"
    test -n "$expected"
    actual="$(environment_sha256 "$target")"
    test "$actual" = "$expected"
    size="$(stat -c '%s' "$target")"
    python3 - "$marker" "$resource_id" "$revision" "$actual" "$size" "$source_url" <<'PY'
import json
import sys
from pathlib import Path

path, resource_id, revision, digest, size, source_url = sys.argv[1:]
data = json.loads(Path(path).read_text(encoding="utf-8"))
assert data == {
    "owner": "phase1-resource",
    "resource_id": resource_id,
    "revision": revision,
    "schema_version": 1,
    "sha256": digest,
    "size_bytes": int(size),
    "source_url": source_url,
}
PY
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$resource_id" "$revision" "$actual" "$size" "$source_url" "$target" >> "$tmp_manifest"
    return
  fi
  download_file "$source_url" "$target.tmp"
  download_file "https://nodejs.org/dist/v24.18.0/SHASUMS256.txt" "$sums.tmp"
  expected="$(awk -v file="$archive" '$2 == file {print $1}' "$sums.tmp")"
  test -n "$expected"
  actual="$(environment_sha256 "$target.tmp")"
  test "$actual" = "$expected"
  mv "$target.tmp" "$target"
  mv "$sums.tmp" "$sums"
  size="$(stat -c '%s' "$target")"
  python3 - "$marker" "$resource_id" "$revision" "$actual" "$size" "$source_url" <<'PY'
import json
import sys
from pathlib import Path

path, resource_id, revision, digest, size, source_url = sys.argv[1:]
Path(path).write_text(json.dumps({
    "owner": "phase1-resource",
    "resource_id": resource_id,
    "revision": revision,
    "schema_version": 1,
    "sha256": digest,
    "size_bytes": int(size),
    "source_url": source_url,
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$resource_id" "$revision" "$actual" "$size" "$source_url" "$target" >> "$tmp_manifest"
}

download_yolo() {
  local resource_id=yolo11n-base
  local revision=v8.4.0
  local source_url=https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt
  local prior digest size target_dir target marker source_json
  prior="$(manifest_row "$resource_id")"
  if test -n "$prior"; then
    printf '%s\n' "$prior" >> "$tmp_manifest"
    return
  fi
  download_tmp="$(mktemp --tmpdir=/tmp)"
  download_official_yolo_asset "$download_tmp"
  digest="$(environment_sha256 "$download_tmp")"
  size="$(stat -c '%s' "$download_tmp")"
  target_dir="/var/lib/substation/models/base/$digest"
  target="$target_dir/yolo11n.pt"
  marker="$target_dir/.substation-resource.json"
  source_json="$target_dir/source.json"
  test ! -e "$target_dir" || {
    printf 'resource target exists without locked manifest: %s\n' "$target_dir" >&2
    exit 1
  }
  mkdir -p "$target_dir"
  mv "$download_tmp" "$target"
  download_tmp=
  python3 - "$marker" "$source_json" "$resource_id" "$revision" "$digest" "$size" "$source_url" <<'PY'
import json
import sys
from pathlib import Path

marker, source_json, resource_id, revision, digest, size, source_url = sys.argv[1:]
common = {
    "resource_id": resource_id,
    "revision": revision,
    "schema_version": 1,
    "sha256": digest,
    "size_bytes": int(size),
    "source_url": source_url,
}
Path(marker).write_text(json.dumps(common | {"owner": "phase1-resource"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
Path(source_json).write_text(json.dumps(common, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$resource_id" "$revision" "$digest" "$size" "$source_url" "$target" >> "$tmp_manifest"
}

if test "$selection" = node-linux-x64 || test "$selection" = all; then
  download_node
fi
if test "$selection" = yolo11n-base || test "$selection" = all; then
  download_yolo
fi

python3 - "$manifest" "$tmp_manifest" <<'PY'
import csv
import os
import sys
from pathlib import Path

fields = ["resource_id", "revision", "sha256", "size_bytes", "source_url", "server_path"]
manifest = Path(sys.argv[1])
incoming = Path(sys.argv[2])

def rows(path):
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames != fields:
            raise SystemExit(f"resource manifest header changed: {reader.fieldnames}")
        return list(reader)

merged = {row["resource_id"]: row for row in rows(manifest)}
for row in rows(incoming):
    old = merged.get(row["resource_id"])
    if old is not None and old != row:
        raise SystemExit(f"resource identity changed: {row['resource_id']}")
    merged[row["resource_id"]] = row

tmp = manifest.with_suffix(".tsv.tmp")
with tmp.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    for key in sorted(merged):
        writer.writerow(merged[key])
os.replace(tmp, manifest)
PY

bash scripts/verify_phase1_resources.sh --evidence-dir "$evidence_dir"
trap - EXIT
cleanup
printf 'phase1-resources: PASS: %s\n' "$selection"
