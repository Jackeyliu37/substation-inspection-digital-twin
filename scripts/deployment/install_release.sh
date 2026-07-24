#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 --candidate ABSOLUTE_PATH --run-id UUIDv4" >&2
  exit 2
}

candidate=""
run_id=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --candidate) candidate="${2:-}"; shift 2 ;;
    --run-id) run_id="${2:-}"; shift 2 ;;
    *) usage ;;
  esac
done
if ((EUID != 0)); then
  echo "install-release: root is required" >&2
  exit 1
fi
[[ "$candidate" = /* && -d "$candidate" ]] || usage
if [[ ! "$run_id" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$ ]]; then
  usage
fi

commit="$(python3 - "$candidate/release-manifest.json" <<'PY'
import json
from pathlib import Path
import sys

print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["git_commit"])
PY
)"
[[ "$commit" =~ ^[0-9a-f]{40}$ ]]
candidate="$(readlink -f -- "$candidate")"
(
  cd "$candidate"
  sha256sum -c release-SHA256SUMS
)

if ! getent passwd substation >/dev/null; then
  useradd --system --home-dir /var/lib/substation --shell /usr/sbin/nologin substation
fi
# Gazebo OGRE2/EGL needs direct access to the NVIDIA render nodes.  Keep this
# limited to the existing device groups; no display session or X server is
# introduced by the production service.
if getent group render >/dev/null; then
  usermod -aG "render" substation
fi
if getent group video >/dev/null; then
  usermod -aG "video" substation
fi
install -d -m 0755 /opt/substation /opt/substation/releases /opt/substation/config
install -d -m 0750 /var/lib/substation
chgrp substation /var/lib/substation
chmod 0750 /var/lib/substation
install -d -m 0750 -o substation -g substation \
  /var/lib/substation/.ros \
  /var/lib/substation/.gz/rendering \
  /var/lib/substation/.gz/sim/log \
  /var/lib/substation/.cache \
  /var/lib/substation/.config \
  /var/lib/substation/sqlite \
  /var/lib/substation/evidence \
  /var/lib/substation/reports \
  /var/lib/substation/diagnostics \
  /var/lib/substation/rosbag2 \
  /var/log/substation

target="/opt/substation/releases/$commit"
[[ ! -e "$target" ]] || {
  echo "install-release: immutable target already exists: $target" >&2
  exit 1
}
mv -- "$candidate" "$target"
chown -R root:root "$target"
chmod -R a-w "$target"

runtime_tmp="/opt/substation/config/.runtime.env.$commit"
printf 'SUBSTATION_RUN_ID=%s\nSUBSTATION_IMPLEMENTATION_COMMIT=%s\nSUBSTATION_ROSBAG_METADATA_PATH=/var/lib/substation/rosbag2/%s/metadata.yaml\n' \
  "$run_id" "$commit" "$run_id" > "$runtime_tmp"
chmod 0644 "$runtime_tmp"
mv -T "$runtime_tmp" /opt/substation/config/runtime.env

for unit in \
  substation-gazebo.service \
  substation-core.service \
  substation-web-gateway.service \
  substation-web-frontend.service \
  substation-foxglove-bridge.service; do
  install -m 0644 "$target/deploy/systemd/$unit" "/etc/systemd/system/$unit"
done
install -m 0644 "$target/deploy/nginx/substation.conf" \
  /etc/nginx/sites-available/substation.conf
ln -sfn /etc/nginx/sites-available/substation.conf \
  /etc/nginx/sites-enabled/substation.conf

new_link="/opt/substation/.current-$commit"
ln -s "$target" "$new_link"
mv -Tf "$new_link" /opt/substation/current
systemctl daemon-reload
nginx -t
systemctl enable \
  substation-gazebo.service \
  substation-core.service \
  substation-web-gateway.service \
  substation-web-frontend.service \
  nginx.service
systemctl disable substation-foxglove-bridge.service >/dev/null 2>&1 || true
echo "install-release: PASS: $target"
