#!/usr/bin/env bash
set -euo pipefail

if test "$#" -ne 2 || test "$1" != --evidence-dir; then
  printf '%s\n' 'usage: bash scripts/check_environment_seal.sh --evidence-dir /var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment' >&2
  exit 2
fi

evidence_dir="$2"
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
source scripts/lib/environment_common.sh
test_root="${SUBSTATION_VERIFY_TEST_ROOT:-}"
if test -n "$test_root"; then
  case "$test_root" in /tmp/phase1-seal-fixture-*) ;; *) exit 2 ;; esac
  case "$evidence_dir" in "$test_root"/acceptance/**/01-environment) ;; *) exit 2 ;; esac
else
  environment_require_final_evidence_target "$evidence_dir"
fi

test -d "$evidence_dir"
test ! -L "$evidence_dir"
test ! -e "$evidence_dir.staging"
test -s "$evidence_dir/SHA256SUMS"
python3 - "$evidence_dir" <<'PY'
import hashlib
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
manifest = root / "SHA256SUMS"
entries = {}
for line in manifest.read_text(encoding="utf-8").splitlines():
    if len(line) < 67 or line[64:66] != "  ":
        raise SystemExit(f"malformed SHA256SUMS entry: {line!r}")
    digest, relative = line[:64], line[66:]
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise SystemExit(f"invalid SHA-256: {digest!r}")
    if not relative or relative.startswith("/") or "\\" in relative or "\n" in relative:
        raise SystemExit(f"unsafe checksum path: {relative!r}")
    path = Path(relative)
    if ".." in path.parts or relative in entries:
        raise SystemExit(f"duplicate or escaping checksum path: {relative!r}")
    entries[relative] = digest

actual = set()
for path in root.rglob("*"):
    if path.is_symlink():
        raise SystemExit(f"symlink forbidden in sealed evidence: {path}")
    if path.is_file() and path.name != "SHA256SUMS":
        actual.add(path.relative_to(root).as_posix())
    elif not path.is_dir() and not path.is_file():
        raise SystemExit(f"unsupported evidence entry: {path}")
if set(entries) != actual:
    raise SystemExit(
        f"checksum path set mismatch: missing={sorted(actual - set(entries))}, "
        f"extra={sorted(set(entries) - actual)}"
    )
for relative, expected in entries.items():
    digest = hashlib.sha256((root / relative).read_bytes()).hexdigest()
    if digest != expected:
        raise SystemExit(f"checksum mismatch: {relative}")

result = json.loads((root / "result.json").read_text(encoding="utf-8"))
required = {
    "schema_version", "acceptance_run_id", "git_commit", "started_at",
    "completed_at", "commands", "exit_codes", "thresholds", "measurements",
    "artifacts", "status", "failures",
}
if not required <= result.keys():
    raise SystemExit("result.json schema keys missing")
if result["status"] != "passed" or result["failures"] != []:
    raise SystemExit("sealed result is not passed")
if not re.fullmatch(r"[0-9a-f]{40}", result["git_commit"]):
    raise SystemExit("result git_commit is not a full commit")
if result["acceptance_run_id"] != root.parent.name:
    raise SystemExit("acceptance run id does not match evidence parent")
expected_artifacts = sorted(actual - {"result.json"})
if result["artifacts"] != expected_artifacts:
    raise SystemExit("result artifact inventory does not match sealed files")
records = result["commands"]
if len({record["id"] for record in records}) != len(records):
    raise SystemExit("duplicate command ids")
if result["exit_codes"] != (
    {record["id"]: record["exit_code"] for record in records}
    | {"verify_environment": 0}
):
    raise SystemExit("exit-code map does not match command records")
for record in records:
    if record["exit_code"] != 0 or record["capture_exit_code"] != 0:
        raise SystemExit(f"nonzero sealed command record: {record['id']}")
    if not (root / record["log"]).is_file():
        raise SystemExit(f"missing sealed command log: {record['log']}")
PY

printf '%s\n' 'check-environment-seal: PASS'
