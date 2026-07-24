#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  echo "usage: $0 --candidate ABSOLUTE_PATH --run-id UUIDv4" >&2
  exit 2
}

candidate=""
run_id=""
health_timeout_s=120
while [[ $# -gt 0 ]]; do
  case "$1" in
    --candidate) candidate="${2:-}"; shift 2 ;;
    --run-id) run_id="${2:-}"; shift 2 ;;
    *) usage ;;
  esac
done

if ((EUID != 0)); then
  echo "activate-release: root is required (run with sudo)" >&2
  exit 1
fi
[[ "$candidate" = /* && -d "$candidate" ]] || usage
if [[ ! "$run_id" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$ ]]; then
  usage
fi

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
candidate="$(readlink -f -- "$candidate")"
commit="$(python3 - "$candidate/release-manifest.json" <<'PY'
import json
from pathlib import Path
import sys

print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["git_commit"])
PY
)"
[[ "$commit" =~ ^[0-9a-f]{40}$ ]] || {
  echo "activate-release: invalid git_commit in release manifest" >&2
  exit 1
}
target="/opt/substation/releases/$commit"

services=(
  substation-gazebo.service
  substation-core.service
  substation-web-gateway.service
  substation-web-frontend.service
  nginx.service
)

diagnostics() {
  set +e
  echo "=== service status ===" >&2
  systemctl --no-pager --full status "${services[@]}" >&2
  echo "=== recent service logs ===" >&2
  journalctl --no-pager -n 80 \
    -u substation-gazebo.service \
    -u substation-core.service \
    -u substation-web-gateway.service \
    -u substation-web-frontend.service \
    -u nginx.service >&2
}

on_error() {
  local status="$1"
  local line="$2"
  trap - ERR
  echo "activate-release: FAIL at line $line (status $status)" >&2
  diagnostics
  exit "$status"
}
trap 'on_error "$?" "$LINENO"' ERR

exec 9>/run/substation-release-activation.lock
flock -n 9 || {
  echo "activate-release: another activation is already running" >&2
  exit 1
}

echo "activate-release: candidate $commit"
if curl -fsS --max-time 3 http://127.0.0.1:8000/healthz >/dev/null 2>&1; then
  idempotency_key="$(cat /proc/sys/kernel/random/uuid)"
  echo "activate-release: latching emergency stop"
  curl -fsS --max-time 10 \
    -X POST \
    -H 'Content-Type: application/json' \
    -H "Idempotency-Key: $idempotency_key" \
    -d "{\"reason\":\"activate release $commit\"}" \
    http://127.0.0.1:8000/api/v1/robot/emergency-stop >/dev/null
else
  echo "activate-release: gateway is not reachable; treating activation as a cold start"
fi

echo "activate-release: stopping current services"
systemctl stop substation-web-frontend.service
systemctl stop substation-core.service substation-gazebo.service
systemctl stop substation-web-gateway.service

echo "activate-release: installing immutable release"
bash "$repo_root/scripts/deployment/install_release.sh" \
  --candidate "$candidate" \
  --run-id "$run_id"

[[ "$(readlink -f -- /opt/substation/current)" == "$target" ]]

echo "activate-release: starting services"
systemctl start substation-gazebo.service
systemctl start substation-core.service substation-web-gateway.service substation-web-frontend.service
systemctl reload nginx.service

echo "activate-release: waiting for health and readiness (up to ${health_timeout_s}s)"
deadline=$((SECONDS + health_timeout_s))
while ((SECONDS < deadline)); do
  if curl -fsS --max-time 3 http://127.0.0.1:8000/healthz >/dev/null 2>&1 && \
     curl -fsS --max-time 3 http://127.0.0.1:8000/readyz >/dev/null 2>&1; then
    systemctl is-active --quiet "${services[@]}"
    [[ "$(readlink -f -- /opt/substation/current)" == "$target" ]]
    trap - ERR
    echo "activate-release: PASS: $target"
    exit 0
  fi
  sleep 2
done

echo "activate-release: health/readiness timeout after ${health_timeout_s}s" >&2
false
