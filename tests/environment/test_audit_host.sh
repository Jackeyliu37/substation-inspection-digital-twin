#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

test -x scripts/audit_host.sh
test -s config/environment/forbidden-packages.regex

audit_json="$(bash scripts/audit_host.sh --report-only)"
AUDIT_JSON="$audit_json" python3 - <<'PY'
import json
import os
import sys

data = json.loads(os.environ["AUDIT_JSON"])
required = {
    "schema_version",
    "status",
    "os",
    "architecture",
    "memory_bytes",
    "disks",
    "gpu",
    "forbidden_packages",
    "active_project_services",
    "active_graphics_processes",
    "checks",
}
missing = required - data.keys()
assert not missing, missing
assert data["schema_version"] == 1
assert data["architecture"]
assert {item["path"] for item in data["disks"]} == {
    "repository",
    "/var/lib/substation",
    "/opt/substation",
}
assert "ubuntu_24_04" in data["checks"]
assert "physical_memory_at_least_15_gib" in data["checks"]
assert "all_storage_paths_keep_20_gib_phase1_residual" in data["checks"]
assert "nvidia_gpu_present" in data["checks"]
assert "no_forbidden_packages" in data["checks"]
assert "no_active_project_services" in data["checks"]
PY

if rg -n 'apt-get|apt install|curl|wget|npm|pip install|colcon|gz sim|systemctl start|systemctl enable' scripts/audit_host.sh; then
  exit 1
fi

printf '%s\n' 'audit-host-light-test: PASS'
