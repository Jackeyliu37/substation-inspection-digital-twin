#!/usr/bin/env bash
set -euo pipefail

if test "$#" -ne 2 || test "$1" != --evidence-dir; then
  printf '%s\n' 'usage: bash scripts/setup_gateway_env.sh --evidence-dir /var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment.staging' >&2
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
test -s requirements-web.lock

stage=".venv-web.staging-$(python3 -c 'import uuid; print(uuid.uuid4())')"
cleanup() {
  if test -e "$stage"; then
    case "$stage" in .venv-web.staging-*) find "$stage" -depth -delete ;; *) return 1 ;; esac
  fi
}
trap cleanup EXIT
if test -e .venv-web; then
  test -d .venv-web
  test ! -L .venv-web
  python3 scripts/lib/venv_provenance.py verify --kind gateway --venv .venv-web --lock requirements-web.lock
else
  test ! -e "$stage"
  python3 -m venv --system-site-packages "$stage"
  grep -Fxq 'include-system-site-packages = true' "$stage/pyvenv.cfg"
  "$stage/bin/python" -m pip install --disable-pip-version-check --require-hashes -r requirements-web.lock
  "$stage/bin/python" - <<'PY'
import fastapi
import pydantic
import rclpy
import uvicorn
import websockets

assert fastapi.__version__ == "0.139.2"
assert uvicorn.__version__ == "0.51.0"
assert pydantic.__version__ == "2.13.4"
assert websockets.__version__ == "16.1.1"
PY
  python3 scripts/lib/venv_provenance.py write --kind gateway --venv "$stage" --lock requirements-web.lock
  mv -- "$stage" .venv-web
fi

.venv-web/bin/python - <<'PY'
import fastapi
import pydantic
import rclpy
import uvicorn
import websockets

assert fastapi.__version__ == "0.139.2"
assert uvicorn.__version__ == "0.51.0"
assert pydantic.__version__ == "2.13.4"
assert websockets.__version__ == "16.1.1"
print(fastapi.__version__, uvicorn.__version__, pydantic.__version__, websockets.__version__)
PY

.venv-web/bin/python -m pip freeze --all | LC_ALL=C sort > "$evidence_dir/gateway-pip-freeze.txt"
python3 scripts/lib/venv_provenance.py verify --kind gateway --venv .venv-web --lock requirements-web.lock
trap - EXIT
cleanup
printf '%s\n' 'setup-gateway-env: PASS'
