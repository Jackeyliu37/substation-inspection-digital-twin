#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

test -x scripts/setup_python_env.sh
grep -Fq 'python_wheel_dir' scripts/setup_python_env.sh
test -s requirements.lock
grep -q -- '--hash=sha256:' requirements.lock
test -s artifacts/environment/pytorch-cu126-wheels.tsv
grep -Fq 'https://download.pytorch.org/whl/cu126/torch-2.12.1%2Bcu126-cp312-cp312-manylinux_2_28_x86_64.whl' artifacts/environment/pytorch-cu126-wheels.tsv
grep -Fq 'https://download.pytorch.org/whl/cu126/torchvision-0.27.1%2Bcu126-cp312-cp312-manylinux_2_28_x86_64.whl' artifacts/environment/pytorch-cu126-wheels.tsv
grep -Fq 'torch @ https://download.pytorch.org/whl/cu126/torch-2.12.1%2Bcu126-cp312-cp312-manylinux_2_28_x86_64.whl' requirements.lock
grep -Fq 'torchvision @ https://download.pytorch.org/whl/cu126/torchvision-0.27.1%2Bcu126-cp312-cp312-manylinux_2_28_x86_64.whl' requirements.lock
set +u
source /opt/ros/jazzy/setup.bash
set -u
.venv/bin/python - <<'PY'
import cv2
import numpy
import rclpy
import torch
import torchvision
import ultralytics

assert torch.__version__.split("+")[0] == "2.12.1"
assert torchvision.__version__.split("+")[0] == "0.27.1"
assert ultralytics.__version__ == "8.4.104"
assert numpy.__version__ == "1.26.4"
assert cv2.__version__ == "4.11.0"
assert torch.cuda.is_available()
assert torch.version.cuda == "12.6"
print("ai-environment: PASS")
PY
python3 scripts/lib/venv_provenance.py verify --kind ai --venv .venv --lock requirements.lock

fixture_root="/tmp/phase1-venv-fixture-$(python3 -c 'import uuid; print(uuid.uuid4())')"
case "$fixture_root" in /tmp/phase1-venv-fixture-*) ;; *) exit 1 ;; esac
install -d -m 0700 "$fixture_root/foreign/bin"
printf '%s\n' 'include-system-site-packages = true' > "$fixture_root/foreign/pyvenv.cfg"
ln -s "$(command -v python3)" "$fixture_root/foreign/bin/python"
set +e
python3 scripts/lib/venv_provenance.py verify --kind ai --venv "$fixture_root/foreign" --lock requirements.lock
foreign_rc=$?
set -e
test "$foreign_rc" -ne 0
case "$fixture_root" in /tmp/phase1-venv-fixture-*) find "$fixture_root" -depth -delete ;; *) exit 1 ;; esac
