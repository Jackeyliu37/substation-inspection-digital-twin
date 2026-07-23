#!/usr/bin/env bash
set -euo pipefail

environment_repo_root() {
  git rev-parse --show-toplevel
}

environment_require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'missing-command: %s\n' "$1" >&2
    return 1
  }
}

environment_require_evidence_dir() {
  local evidence_dir="$1"
  local evidence_run_id
  if [[ "$evidence_dir" =~ ^/var/lib/substation/evidence/acceptance/([0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})/01-environment\.staging$ ]]; then
    evidence_run_id="${BASH_REMATCH[1]}"
  else
    printf 'invalid-evidence-dir: %s\n' "$evidence_dir" >&2
    return 1
  fi
  test -n "$evidence_run_id"
  test -d "$evidence_dir" || {
    printf 'missing-evidence-dir: %s\n' "$evidence_dir" >&2
    return 1
  }
}

environment_require_final_evidence_target() {
  local evidence_dir="$1"
  case "$evidence_dir" in
    /var/lib/substation/evidence/acceptance/*/01-environment) ;;
    *)
      printf 'invalid-final-evidence-target: %s\n' "$evidence_dir" >&2
      return 1
      ;;
  esac
}

environment_prepare_owned_directory() {
  local manifest="$1"
  local path="$2"
  local expected_mode="$3"
  local expected_owner="$4"
  local expected_group="$5"
  local parent actual_mode actual_owner actual_group device inode
  expected_mode="${expected_mode#0}"
  test "${path#/}" != "$path"
  test "$path" != /
  if test -L "$path"; then
    printf 'refusing-symlink-directory: %s\n' "$path" >&2
    return 1
  fi
  if test -e "$path"; then
    test -d "$path"
    actual_mode="$(stat -c '%a' "$path")"
    actual_owner="$(stat -c '%U' "$path")"
    actual_group="$(stat -c '%G' "$path")"
    device="$(stat -c '%d' "$path")"
    inode="$(stat -c '%i' "$path")"
    printf '%s\t1\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t0\n' \
      "$path" "$actual_mode" "$actual_owner" "$actual_group" "$device" "$inode" \
      "$expected_mode" "$expected_owner" "$expected_group" >> "$manifest"
    test "$actual_mode" = "$expected_mode"
    test "$actual_owner" = "$expected_owner"
    test "$actual_group" = "$expected_group"
    return
  fi
  parent="$(dirname -- "$path")"
  test -d "$parent"
  test ! -L "$parent"
  printf '%s\t0\t-\t-\t-\t-\t-\t%s\t%s\t%s\t1\n' \
    "$path" "$expected_mode" "$expected_owner" "$expected_group" >> "$manifest"
  if test -w "$parent" \
    && test "$expected_owner" = "$(id -un)" \
    && test "$expected_group" = "$(id -gn)"; then
    install -d -m "$expected_mode" "$path"
  else
    sudo install -d -m "$expected_mode" -o "$expected_owner" -g "$expected_group" "$path"
  fi
}

environment_sha256() {
  sha256sum -- "$1" | awk '{print $1}'
}
