#!/usr/bin/env bash
set -euo pipefail

if test "$#" -ne 2 || test "$1" != --evidence-dir; then
  printf '%s\n' 'usage: bash scripts/verify_phase1_resources.sh --evidence-dir DIR' >&2
  exit 2
fi

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
source scripts/lib/environment_common.sh
evidence_dir="$2"
environment_require_evidence_dir "$evidence_dir"
manifest="$evidence_dir/resource-downloads.tsv"
test -s "$manifest"

python3 - "$manifest" <<'PY'
import csv
import hashlib
import json
import sys
from pathlib import Path

fields = ["resource_id", "revision", "sha256", "size_bytes", "source_url", "server_path"]
with Path(sys.argv[1]).open(encoding="utf-8", newline="") as handle:
    reader = csv.DictReader(handle, delimiter="\t")
    assert reader.fieldnames == fields
    rows = list(reader)
assert rows
assert [row["resource_id"] for row in rows] == sorted(row["resource_id"] for row in rows)
assert len(rows) == len({row["resource_id"] for row in rows})
for row in rows:
    path = Path(row["server_path"])
    assert path.is_absolute()
    assert path.is_file()
    payload = path.read_bytes()
    assert len(payload) == int(row["size_bytes"])
    assert hashlib.sha256(payload).hexdigest() == row["sha256"]
    marker = json.loads((path.parent / ".substation-resource.json").read_text(encoding="utf-8"))
    assert marker["owner"] == "phase1-resource"
    assert marker["resource_id"] == row["resource_id"]
    assert marker["revision"] == row["revision"]
    assert marker["sha256"] == row["sha256"]
    assert marker["size_bytes"] == int(row["size_bytes"])
    assert marker["source_url"] == row["source_url"]
    if row["resource_id"] == "node-linux-x64":
        assert row["revision"] == "24.18.0"
        assert path == Path("/var/lib/substation/downloads/node/24.18.0/node-v24.18.0-linux-x64.tar.xz")
        sums = (path.parent / "SHASUMS256.txt").read_text(encoding="utf-8").splitlines()
        assert any(line.split()[0] == row["sha256"] and line.split()[1] == path.name for line in sums if len(line.split()) >= 2)
    elif row["resource_id"] == "yolo11n-base":
        assert row["revision"] == "v8.4.0"
        assert path == Path(f"/var/lib/substation/models/base/{row['sha256']}/yolo11n.pt")
        source = json.loads((path.parent / "source.json").read_text(encoding="utf-8"))
        assert source == {key: value for key, value in marker.items() if key != "owner"}
    else:
        raise AssertionError(row["resource_id"])
PY

printf '%s\n' 'verify-phase1-resources: PASS'
