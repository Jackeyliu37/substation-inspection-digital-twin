#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

test -x scripts/setup_gateway_env.sh
test -s requirements-web.lock
grep -q -- '--hash=sha256:' requirements-web.lock
set +u
source /opt/ros/jazzy/setup.bash
set -u
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
print("gateway-environment: PASS")
PY
python3 scripts/lib/venv_provenance.py verify --kind gateway --venv .venv-web --lock requirements-web.lock
