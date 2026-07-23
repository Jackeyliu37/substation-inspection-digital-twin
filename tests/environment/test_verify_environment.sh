#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

test -x scripts/verify_environment.sh
test -x scripts/check_environment_seal.sh
rg -F 'unsafe install-state line' scripts/verify_environment.sh
! rg -n 'source .*install-state|source "\$state_file"' \
  scripts/verify_environment.sh scripts/rollback_host.sh

fixture_root="/tmp/phase1-seal-fixture-$(python3 -c 'import uuid; print(uuid.uuid4())')"
case "$fixture_root" in /tmp/phase1-seal-fixture-*) ;; *) exit 2 ;; esac
test ! -e "$fixture_root"
install -d -m 0750 "$fixture_root/acceptance"
cleanup() {
  case "$fixture_root" in /tmp/phase1-seal-fixture-*) ;; *) return 1 ;; esac
  if test -e "$fixture_root"; then
    find "$fixture_root" -depth -delete
  fi
}
trap cleanup EXIT

create_staging() {
  local run_id="$1"
  local staging="$fixture_root/acceptance/$run_id/01-environment.staging"
  install -d -m 0750 "$staging"
  printf '%s\n' "$run_id" > "$staging/acceptance_run_id.txt"
  printf '%s\n' "seed=$run_id" > "$staging/fixture-seed.txt"
  printf '%s\n' "$staging"
}

snapshot_tree() {
  local root="$1"
  local output="$2"
  (
    cd "$root"
    find . -printf '%y\t%m\t%p\n' | LC_ALL=C sort
    find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum
  ) > "$output"
}
success_run=seal-success
success_staging="$(create_staging "$success_run")"
success_final="$fixture_root/acceptance/$success_run/01-environment"
SUBSTATION_VERIFY_TEST_ROOT="$fixture_root" \
  bash scripts/verify_environment.sh --evidence-dir "$success_final"
test ! -e "$success_staging"
test -d "$success_final"
test -s "$success_final/SHA256SUMS"
SUBSTATION_VERIFY_TEST_ROOT="$fixture_root" \
  bash scripts/check_environment_seal.sh --evidence-dir "$success_final"

before_snapshot="$fixture_root/success-before.tsv"
after_snapshot="$fixture_root/success-after.tsv"
snapshot_tree "$success_final" "$before_snapshot"
set +e
SUBSTATION_VERIFY_TEST_ROOT="$fixture_root" \
  bash scripts/verify_environment.sh --evidence-dir "$success_final" \
  > "$fixture_root/existing-final-refusal.log" 2>&1
existing_rc=$?
set -e
test "$existing_rc" -ne 0
snapshot_tree "$success_final" "$after_snapshot"
cmp "$before_snapshot" "$after_snapshot"
SUBSTATION_VERIFY_TEST_ROOT="$fixture_root" \
  bash scripts/check_environment_seal.sh --evidence-dir "$success_final"

failure_run=seal-failure
failure_staging="$(create_staging "$failure_run")"
failure_final="$fixture_root/acceptance/$failure_run/01-environment"
set +e
SUBSTATION_VERIFY_TEST_ROOT="$fixture_root" \
SUBSTATION_VERIFY_TEST_FAILURE=23 \
  bash scripts/verify_environment.sh --evidence-dir "$failure_final" \
  > "$fixture_root/failure.log" 2>&1
failure_rc=$?
set -e
test "$failure_rc" -eq 23
test ! -e "$failure_final"
test -d "$failure_staging"
test ! -e "$failure_staging/SHA256SUMS"
test -s "$failure_staging/result.json"
test -s "$failure_staging/commands/fixture-check.json"
python3 - "$failure_staging/result.json" <<'PY'
import json
import sys
from pathlib import Path

result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert result["status"] == "failed"
assert result["failures"]
assert result["exit_codes"] == {"fixture-check": 23, "verify_environment": 23}
assert result["commands"][0]["id"] == "fixture-check"
assert result["commands"][0]["exit_code"] == 23
PY

failed_snapshot="$fixture_root/failure-before-rerun.tsv"
failed_after="$fixture_root/failure-after-rerun.tsv"
snapshot_tree "$failure_staging" "$failed_snapshot"
set +e
SUBSTATION_VERIFY_TEST_ROOT="$fixture_root" \
  bash scripts/verify_environment.sh --evidence-dir "$failure_final" \
  > "$fixture_root/failed-staging-refusal.log" 2>&1
rerun_rc=$?
set -e
test "$rerun_rc" -ne 0
snapshot_tree "$failure_staging" "$failed_after"
cmp "$failed_snapshot" "$failed_after"

printf '%s\n' 'verify-environment-test: PASS'
