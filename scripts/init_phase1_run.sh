#!/usr/bin/env bash
set -euo pipefail

if test "$#" -ne 2 || test "$1" != --gate-log; then
  printf '%s\n' 'usage: bash scripts/init_phase1_run.sh --gate-log /tmp/documentation-gate.log' >&2
  exit 2
fi

gate_log="$2"
test -f "$gate_log"
grep -Fxq 'documentation-gate: PASS' "$gate_log"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
source scripts/lib/environment_common.sh
test ! -e .phase1-run.env || {
  printf '%s\n' '.phase1-run.env already exists; source it instead of creating a second run' >&2
  exit 1
}

phase1_run_id="$(python3 -c 'import uuid; print(uuid.uuid4())')"
phase1_acceptance_root="/var/lib/substation/evidence/acceptance/${phase1_run_id}"
phase1_evidence_root="$phase1_acceptance_root/01-environment.staging"
phase1_evidence_final="$phase1_acceptance_root/01-environment"
operator_user="$(id -un)"
operator_group="$(id -gn)"

test ! -e "$phase1_evidence_final"
metadata_work="$(mktemp --tmpdir=/tmp)"
cleanup() {
  test ! -e "$metadata_work" || unlink -- "$metadata_work"
}
trap cleanup EXIT
printf 'path\texisted_before\tmode_before\towner_before\tgroup_before\tdevice\tinode\texpected_mode\texpected_owner\texpected_group\tcreated_by_task\n' > "$metadata_work"
environment_prepare_owned_directory "$metadata_work" /var/lib/substation 0750 "$operator_user" "$operator_group"
environment_prepare_owned_directory "$metadata_work" /var/lib/substation/evidence 0750 "$operator_user" "$operator_group"
environment_prepare_owned_directory "$metadata_work" /var/lib/substation/evidence/acceptance 0750 "$operator_user" "$operator_group"
environment_prepare_owned_directory "$metadata_work" "$phase1_acceptance_root" 0750 "$operator_user" "$operator_group"
environment_prepare_owned_directory "$metadata_work" "$phase1_evidence_root" 0750 "$operator_user" "$operator_group"
environment_prepare_owned_directory "$metadata_work" /opt/substation 0755 root root
environment_prepare_owned_directory "$metadata_work" /opt/substation/toolchains 0755 root root
install -m 0640 "$metadata_work" "$phase1_evidence_root/storage-paths-before.tsv"
unlink -- "$metadata_work"
metadata_work=
install -m 0640 "$gate_log" "$phase1_evidence_root/documentation-gate.log"
printf '%s\n' "$phase1_run_id" > "$phase1_evidence_root/acceptance_run_id.txt"
git rev-parse HEAD > "$phase1_evidence_root/git_commit.txt"

umask 077
printf 'export PHASE1_RUN_ID=%q\n' "$phase1_run_id" > .phase1-run.env
printf 'export PHASE1_EVIDENCE_ROOT=%q\n' "$phase1_evidence_root" >> .phase1-run.env
printf 'export PHASE1_EVIDENCE_FINAL=%q\n' "$phase1_evidence_final" >> .phase1-run.env

printf 'PHASE1_RUN_ID=%s\n' "$phase1_run_id"
printf 'PHASE1_EVIDENCE_ROOT=%s\n' "$phase1_evidence_root"
printf 'PHASE1_EVIDENCE_FINAL=%s\n' "$phase1_evidence_final"

trap - EXIT
cleanup
