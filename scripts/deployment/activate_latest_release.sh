#!/usr/bin/env bash
set -Eeuo pipefail

if ((EUID != 0)); then
  echo "activate-latest-release: root is required (run with sudo)" >&2
  exit 1
fi

staging_root=/var/lib/substation/releases-staging
latest_candidate=""
latest_mtime=-1
shopt -s nullglob
for manifest in "$staging_root"/*/release-manifest.json; do
  candidate="$(dirname -- "$manifest")"
  commit="$(basename -- "$candidate")"
  [[ "$commit" =~ ^[0-9a-f]{40}$ ]] || continue
  mtime="$(stat -c %Y -- "$manifest")"
  if ((mtime > latest_mtime)); then
    latest_candidate="$candidate"
    latest_mtime="$mtime"
  fi
done
[[ -n "$latest_candidate" ]] || {
  echo "activate-latest-release: no immutable candidate found in $staging_root" >&2
  exit 1
}

run_id="$(cat /proc/sys/kernel/random/uuid)"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
echo "activate-latest-release: selected $latest_candidate"
exec bash "$script_dir/activate_release.sh" \
  --candidate "$latest_candidate" \
  --run-id "$run_id"
