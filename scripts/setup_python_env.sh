#!/usr/bin/env bash
set -euo pipefail

if test "$#" -ne 2 || test "$1" != --evidence-dir; then
  printf '%s\n' 'usage: bash scripts/setup_python_env.sh --evidence-dir /var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment.staging' >&2
  exit 2
fi

evidence_dir="$2"
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
source scripts/lib/environment_common.sh
environment_require_evidence_dir "$evidence_dir"
set +u
source /opt/ros/jazzy/setup.bash
set -u
test "$ROS_DISTRO" = jazzy
python3 -c 'import sys; assert sys.version_info[:2] == (3, 12)'
test -s requirements.lock

stage=".venv.staging-$(python3 -c 'import uuid; print(uuid.uuid4())')"
cleanup() {
  if test -e "$stage"; then
    case "$stage" in .venv.staging-*) find "$stage" -depth -delete ;; *) return 1 ;; esac
  fi
}
trap cleanup EXIT
if test -e .venv; then
  test -d .venv
  test ! -L .venv
  python3 scripts/lib/venv_provenance.py verify --kind ai --venv .venv --lock requirements.lock
else
  test ! -e "$stage"
  python3 -m venv --system-site-packages "$stage"
  grep -Fxq 'include-system-site-packages = true' "$stage/pyvenv.cfg"
  python_wheel_dir="/var/lib/substation/downloads/python-wheels/torch-2.12.1-cu126"
  if test -f "$python_wheel_dir/torch-2.12.1+cu126-cp312-cp312-manylinux_2_28_x86_64.whl" \
    && test -f "$python_wheel_dir/torchvision-0.27.1+cu126-cp312-cp312-manylinux_2_28_x86_64.whl"; then
    "$stage/bin/python" -m pip install --disable-pip-version-check --no-deps \
      "$python_wheel_dir/torch-2.12.1+cu126-cp312-cp312-manylinux_2_28_x86_64.whl" \
      "$python_wheel_dir/torchvision-0.27.1+cu126-cp312-cp312-manylinux_2_28_x86_64.whl"
    install_lock="$stage/requirements.lock"
    python3 - "$install_lock" "$python_wheel_dir" <<'PY'
from pathlib import Path
import sys

output = Path(sys.argv[1])
wheel_dir = Path(sys.argv[2])
lock = Path("requirements.lock").read_text(encoding="utf-8")
lock = lock.replace(
    "https://download.pytorch.org/whl/cu126/torch-2.12.1%2Bcu126-cp312-cp312-manylinux_2_28_x86_64.whl",
    (wheel_dir / "torch-2.12.1+cu126-cp312-cp312-manylinux_2_28_x86_64.whl").as_uri(),
)
lock = lock.replace(
    "https://download.pytorch.org/whl/cu126/torchvision-0.27.1%2Bcu126-cp312-cp312-manylinux_2_28_x86_64.whl",
    (wheel_dir / "torchvision-0.27.1+cu126-cp312-cp312-manylinux_2_28_x86_64.whl").as_uri(),
)
output.write_text(lock, encoding="utf-8")
PY
  else
    install_lock="requirements.lock"
  fi
  "$stage/bin/python" -m pip install --disable-pip-version-check --require-hashes -r "$install_lock"
  "$stage/bin/python" - <<'PY'
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
PY
  python3 scripts/lib/venv_provenance.py write --kind ai --venv "$stage" --lock requirements.lock
  mv -- "$stage" .venv
fi

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
print(torch.__version__, torch.version.cuda, torch.cuda.get_device_name(0))
PY

.venv/bin/python -m pip freeze --all | LC_ALL=C sort > "$evidence_dir/ai-pip-freeze.txt"
python3 scripts/lib/venv_provenance.py verify --kind ai --venv .venv --lock requirements.lock
trap - EXIT
cleanup
printf '%s\n' 'setup-python-env: PASS'
