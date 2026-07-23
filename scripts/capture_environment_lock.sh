#!/usr/bin/env bash
set -euo pipefail

if test "$#" -ne 2 || test "$1" != --evidence-dir; then
  printf '%s\n' 'usage: bash scripts/capture_environment_lock.sh --evidence-dir /var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment.staging' >&2
  exit 2
fi

evidence_dir="$2"
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
source scripts/lib/environment_common.sh
environment_require_evidence_dir "$evidence_dir"

for name in ai-pip-freeze.txt gateway-pip-freeze.txt node-npm-versions.txt resource-downloads.tsv; do
  test -s "$evidence_dir/$name"
done

target=artifacts/environment
run_id="$(basename "$(dirname "$evidence_dir")")"
stage="artifacts/.environment-capture-$run_id"
candidate=
cleanup() {
  local path
  for path in "$stage" "$candidate"; do
    test -n "$path" || continue
    if test -e "$path"; then
      case "$path" in
        artifacts/.environment-capture-*|/tmp/phase1-environment-lock-*) ;;
        *) return 1 ;;
      esac
      find "$path" -depth -delete
    fi
  done
}
trap cleanup EXIT

build_candidate() {
  local destination="$1"
  install -d -m 0755 "$destination"
  dpkg-query -W -f='${Package}\t${Version}\n' | LC_ALL=C sort \
    > "$destination/dpkg-packages.tsv"
  install -m 0644 "$evidence_dir/ai-pip-freeze.txt" "$destination/ai-pip-freeze.txt"
  install -m 0644 "$evidence_dir/gateway-pip-freeze.txt" "$destination/gateway-pip-freeze.txt"
  install -m 0644 "$evidence_dir/node-npm-versions.txt" "$destination/node-npm-versions.txt"
  install -m 0644 "$evidence_dir/resource-downloads.tsv" "$destination/resource-downloads.tsv"
  (
    cd "$destination"
    for name in \
      ai-pip-freeze.txt \
      dpkg-packages.tsv \
      gateway-pip-freeze.txt \
      node-npm-versions.txt \
      resource-downloads.tsv; do
      sha256sum -- "$name"
    done > SHA256SUMS
    sha256sum -c SHA256SUMS
  )
}

tracked_files=(
  artifacts/environment/dpkg-packages.tsv
  artifacts/environment/ai-pip-freeze.txt
  artifacts/environment/gateway-pip-freeze.txt
  artifacts/environment/node-npm-versions.txt
  artifacts/environment/resource-downloads.tsv
  artifacts/environment/SHA256SUMS
)

if test -e "$target"; then
  test -d "$target"
  test ! -L "$target"
  test -z "$(git status --porcelain=v1 --untracked-files=all -- "$target")" || {
    printf 'refusing-dirty-tracked-baseline: %s\n' "$target" >&2
    exit 1
  }
  candidate="/tmp/phase1-environment-lock-$(python3 -c 'import uuid; print(uuid.uuid4())')"
  test ! -e "$candidate"
  install -d -m 0700 "$candidate"
  build_candidate "$candidate"
  baseline_complete=1
  for path in "${tracked_files[@]}"; do
    name="${path##*/}"
    if test -e "$path"; then
      test -f "$path"
      test ! -L "$path"
      git ls-files --error-unmatch "$path" >/dev/null
      cmp -- "$path" "$candidate/$name"
    else
      baseline_complete=0
    fi
  done
  if test "$baseline_complete" -eq 1; then
    printf '%s\n' 'capture-environment-lock: PASS: tracked-baseline-unchanged'
  else
    for path in "${tracked_files[@]}"; do
      name="${path##*/}"
      install -m 0644 "$candidate/$name" "$path"
    done
    printf '%s\n' 'capture-environment-lock: PASS: first-baseline-created'
  fi
  trap - EXIT
  cleanup
  exit 0
fi

test ! -e "$stage"
install -d -m 0755 artifacts
build_candidate "$stage"
mv -T -- "$stage" "$target"
stage=
printf '%s\n' 'capture-environment-lock: PASS: first-baseline-created'
trap - EXIT
cleanup
