#!/usr/bin/env python3
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected(kind: str, venv: Path, lock: Path) -> dict:
    cfg = venv / "pyvenv.cfg"
    python = venv / "bin/python"
    if not cfg.is_file() or not python.is_file():
        raise SystemExit(f"not a complete virtual environment: {venv}")
    values = {}
    for line in cfg.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    if values.get("include-system-site-packages") != "true":
        raise SystemExit(f"system-site-packages is not enabled: {venv}")
    version = subprocess.run(
        [str(python), "-c", "import platform; print(platform.python_version())"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    if not version.startswith("3.12."):
        raise SystemExit(f"unexpected Python version: {version}")
    return {
        "schema_version": 1,
        "owner": "phase1-environment",
        "kind": kind,
        "python_version": version,
        "system_site_packages": True,
        "lock_path": lock.name,
        "lock_sha256": sha256(lock),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "verify"))
    parser.add_argument("--kind", choices=("ai", "gateway"), required=True)
    parser.add_argument("--venv", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    args = parser.parse_args()
    marker = args.venv / ".substation-environment.json"
    document = expected(args.kind, args.venv, args.lock)
    if args.action == "write":
        if marker.exists():
            raise SystemExit(f"refusing to overwrite provenance marker: {marker}")
        marker.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        if not marker.is_file():
            raise SystemExit(f"foreign virtual environment without provenance: {args.venv}")
        actual = json.loads(marker.read_text(encoding="utf-8"))
        if actual != document:
            raise SystemExit(f"virtual environment provenance mismatch: {args.venv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
