#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

test -x scripts/download_phase1_resources.sh
test -x scripts/verify_phase1_resources.sh
test -s config/environment/resource-sources.tsv
grep -F $'node-linux-x64\tphase1\t24.18.0' config/environment/resource-sources.tsv
grep -F $'yolo11n-base\tphase1\tultralytics-assets-v8.4.0' config/environment/resource-sources.tsv
bash scripts/download_phase1_resources.sh --list | grep -Fx node-linux-x64
bash scripts/download_phase1_resources.sh --list | grep -Fx yolo11n-base
! git ls-files | grep -E '\.(pt|onnx|engine|tar\.xz|zip)$'
if rg -n 'npm install|pip install|apt-get|systemctl start|gz sim|colcon' scripts/download_phase1_resources.sh scripts/verify_phase1_resources.sh; then
  exit 1
fi

printf '%s\n' 'phase1-resource-static-test: PASS'
