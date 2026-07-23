#!/usr/bin/env bash
set -euo pipefail

mode=preflight
if test "$#" -eq 1 && test "$1" = --report-only; then
  mode=report-only
elif test "$#" -eq 1 && test "$1" = --preflight; then
  mode=preflight
elif test "$#" -ne 0; then
  printf '%s\n' 'usage: bash scripts/audit_host.sh [--report-only|--preflight]' >&2
  exit 2
fi

repo_root="$(git rev-parse --show-toplevel)"
export PHASE1_AUDIT_MODE="$mode"
export PHASE1_AUDIT_REPO_ROOT="$repo_root"

python3 - <<'PY'
import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path

repo = Path(os.environ["PHASE1_AUDIT_REPO_ROOT"])
mode = os.environ["PHASE1_AUDIT_MODE"]


def run(command):
    return subprocess.run(command, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


os_release = {}
for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
    if "=" in line:
        key, value = line.split("=", 1)
        os_release[key] = value.strip().strip('"')

meminfo = {}
for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
    if ":" in line:
        key, value = line.split(":", 1)
        fields = value.strip().split()
        if fields and fields[0].isdigit():
            meminfo[key] = int(fields[0]) * 1024

disk_paths = {
    "repository": repo,
    "/var/lib/substation": Path("/var/lib/substation"),
    "/opt/substation": Path("/opt/substation"),
}
disks = []
for label, path in disk_paths.items():
    usage = shutil.disk_usage(path)
    disks.append(
        {
            "path": label,
            "probe_path": str(path),
            "free_bytes": usage.free,
            "required_phase1_residual_free_bytes": 20 * 1024**3,
            "meets_phase1_residual_floor": usage.free >= 20 * 1024**3,
        }
    )

patterns = [
    re.compile(line)
    for line in (repo / "config/environment/forbidden-packages.regex").read_text(encoding="utf-8").splitlines()
    if line.strip()
]
installed_packages = []
dpkg = run(["dpkg-query", "-W", "-f=${db:Status-Abbrev}\t${binary:Package}\n"])
if dpkg.returncode == 0:
    for line in dpkg.stdout.splitlines():
        try:
            status, package = line.split("\t", 1)
        except ValueError:
            continue
        if status == "ii ":
            installed_packages.append(package)
forbidden_packages = sorted(
    {
        package
        for package in installed_packages
        if any(pattern.fullmatch(package) for pattern in patterns)
    }
)

gpu_name = None
driver_version = None
nvidia = run(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"])
if nvidia.returncode == 0 and nvidia.stdout.strip():
    gpu_name, driver_version = [part.strip() for part in nvidia.stdout.splitlines()[0].split(",", 1)]


def version_tuple(value):
    if value is None:
        return ()
    return tuple(int(part) for part in value.split(".") if part.isdigit())


project_units = [
    "nginx.service",
    "substation-gazebo.service",
    "substation-core.service",
    "substation-web-gateway.service",
    "substation-web-frontend.service",
    "substation-foxglove-bridge.service",
]
active_project_services = []
for unit in project_units:
    completed = run(["systemctl", "is-active", unit])
    state = completed.stdout.strip()
    if state == "active":
        active_project_services.append(unit)

graphics_process_names = {
    "Xorg",
    "Xwayland",
    "gnome-shell",
    "plasmashell",
    "gdm3",
    "sddm",
    "lightdm",
    "Xvfb",
    "nxserver",
    "nxnode",
}
active_graphics_processes = []
ps = run(["ps", "-eo", "comm="])
if ps.returncode == 0:
    active_graphics_processes = sorted(
        {name for name in ps.stdout.splitlines() if name in graphics_process_names}
    )

checks = {
    "ubuntu_24_04": os_release.get("ID") == "ubuntu" and os_release.get("VERSION_ID") == "24.04",
    "architecture_x86_64": platform.machine() == "x86_64",
    "physical_memory_at_least_15_gib": meminfo.get("MemTotal", 0) >= 15 * 1024**3,
    "all_storage_paths_keep_20_gib_phase1_residual": all(item["meets_phase1_residual_floor"] for item in disks),
    "nvidia_gpu_present": driver_version is not None,
    "nvidia_driver_floor_560_35_05": version_tuple(driver_version) >= version_tuple("560.35.05"),
    "no_forbidden_packages": not forbidden_packages,
    "no_active_project_services": not active_project_services,
    "no_active_graphics_processes": not active_graphics_processes,
}

document = {
    "schema_version": 1,
    "status": "passed" if all(checks.values()) else "failed",
    "os": {
        "id": os_release.get("ID"),
        "version_id": os_release.get("VERSION_ID"),
        "pretty_name": os_release.get("PRETTY_NAME"),
    },
    "architecture": platform.machine(),
    "memory_bytes": meminfo.get("MemTotal", 0),
    "disks": disks,
    "gpu": {
        "present": driver_version is not None,
        "name": gpu_name,
        "driver_version": driver_version,
        "required_driver_floor": "560.35.05",
    },
    "forbidden_packages": forbidden_packages,
    "active_project_services": active_project_services,
    "active_graphics_processes": active_graphics_processes,
    "checks": checks,
}
print(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True))
if mode != "report-only" and document["status"] != "passed":
    raise SystemExit(1)
PY
