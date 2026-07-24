#!/usr/bin/env bash
set -Eeuo pipefail

if ((EUID != 0)); then
  echo "repair-current-readiness: root is required (run with sudo)" >&2
  exit 1
fi

runtime_env=/opt/substation/config/runtime.env
[[ -f "$runtime_env" ]] || {
  echo "repair-current-readiness: missing $runtime_env" >&2
  exit 1
}
source "$runtime_env"
run_id="${SUBSTATION_RUN_ID:-}"
if [[ ! "$run_id" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$ ]]; then
  echo "repair-current-readiness: runtime run ID is invalid" >&2
  exit 1
fi

helper="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/ensure_time_mapping.py"
runuser -u substation -- env -u DISPLAY ROS_LOCALHOST_ONLY=1 \
  bash -c 'source /opt/ros/jazzy/setup.bash; source /opt/substation/current/install/setup.bash; exec /usr/bin/python3 "$1" --run-id "$2"' \
  _ "$helper" "$run_id"

deadline=$((SECONDS + 30))
while ((SECONDS < deadline)); do
  if curl -fsS --max-time 3 http://127.0.0.1:8000/readyz >/dev/null 2>&1; then
    echo "repair-current-readiness: PASS: /readyz=200"
    exit 0
  fi
  sleep 1
done

echo "repair-current-readiness: /readyz did not become ready" >&2
curl -sS http://127.0.0.1:8000/readyz >&2 || true
exit 1
