#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

test -x scripts/verify_documentation_gate.sh
output="$(bash scripts/verify_documentation_gate.sh)"
grep -Fx 'documentation-gate: PASS' <<<"$output"
