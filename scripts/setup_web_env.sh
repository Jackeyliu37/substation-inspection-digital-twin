#!/usr/bin/env bash
set -euo pipefail

if test "$#" -ne 2 || test "$1" != --evidence-dir; then
  printf '%s\n' 'usage: bash scripts/setup_web_env.sh --evidence-dir /var/lib/substation/evidence/acceptance/$PHASE1_RUN_ID/01-environment.staging' >&2
  exit 2
fi
evidence_dir="$2"
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
source scripts/lib/environment_common.sh
environment_require_evidence_dir "$evidence_dir"
test -s "$evidence_dir/resource-downloads.tsv"
node_archive="$(awk -F '\t' '$1 == "node-linux-x64" {print $6}' "$evidence_dir/resource-downloads.tsv")"
node_sha="$(awk -F '\t' '$1 == "node-linux-x64" {print $3}' "$evidence_dir/resource-downloads.tsv")"
test -f "$node_archive"
test "$(environment_sha256 "$node_archive")" = "$node_sha"
toolchain_root=/opt/substation/toolchains
node_root="$toolchain_root/node-v24.18.0"
stage_root="$toolchain_root/.node-v24.18.0-${PHASE1_RUN_ID:?}"
marker="$node_root/.substation-toolchain.json"
node_current="$toolchain_root/node-current"
node_current_before="$evidence_dir/node-current-before.tsv"
link_work=
cleanup() {
  if test -n "$link_work" && test -e "$link_work"; then sudo unlink -- "$link_work"; fi
  if test -e "$stage_root"; then sudo find "$stage_root" -depth -delete; fi
}
trap cleanup EXIT
test -d "$toolchain_root"
test ! -L "$toolchain_root"
test "$(stat -c '%a:%U:%G' "$toolchain_root")" = 755:root:root
if test -e "$node_current" && test ! -L "$node_current"; then printf 'refusing-foreign-node-current: %s\n' "$node_current" >&2; exit 1; fi
if test -e "$node_root"; then
  test -d "$node_root"; test ! -L "$node_root"; test -s "$marker"
  python3 - "$marker" "$node_sha" <<'PY'
import json, sys
from pathlib import Path
assert json.loads(Path(sys.argv[1]).read_text()) == {"archive_sha256": sys.argv[2], "owner": "phase1-environment", "schema_version": 1, "toolchain": "node", "version": "24.18.0"}
PY
else
  sudo install -d -m 0755 "$stage_root"
  sudo tar -xJf "$node_archive" -C "$stage_root" --strip-components=1 --no-same-owner --owner=root --group=root
  marker_work="$(mktemp --tmpdir=/tmp)"
  python3 - "$marker_work" "$node_sha" <<'PY'
import json, sys
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps({"archive_sha256": sys.argv[2], "owner": "phase1-environment", "schema_version": 1, "toolchain": "node", "version": "24.18.0"}, indent=2, sort_keys=True) + "\n")
PY
  sudo install -m 0644 "$marker_work" "$stage_root/.substation-toolchain.json"
  unlink -- "$marker_work"
  sudo mv -- "$stage_root" "$node_root"
fi
"$node_root/bin/node" --version | grep -Fx v24.18.0
for command_name in node npm npx corepack; do
  command_target="$node_root/bin/$command_name"; command_link="/usr/local/bin/$command_name"; test -x "$command_target"
  if test -L "$command_link"; then test "$(readlink -- "$command_link")" = "$command_target"; elif test -e "$command_link"; then printf 'refusing-to-overwrite-command: %s\n' "$command_link" >&2; exit 1; else sudo ln -s "$command_target" "$command_link"; fi
done
if test ! -e "$node_current_before"; then
  if test -L "$node_current"; then printf 'path\texisted_before\ttarget_before\n%s\t1\t%s\n' "$node_current" "$(readlink -- "$node_current")" > "$node_current_before"; elif test -e "$node_current"; then exit 1; else printf 'path\texisted_before\ttarget_before\n%s\t0\t-\n' "$node_current" > "$node_current_before"; fi
else test -L "$node_current"; test "$(readlink -f "$node_current")" = "$node_root"; fi
if test ! -L "$node_current" || test "$(readlink -f "$node_current")" != "$node_root"; then
  link_work="$toolchain_root/.node-current-${PHASE1_RUN_ID:?}"; sudo ln -s "$node_root" "$link_work"; sudo mv -Tf "$link_work" "$node_current"; link_work=
fi
npm_version="$(npm --version)"
npm_registry=https://registry.npmmirror.com
python3 scripts/write_frontend_manifest.py --npm-version "$npm_version" --output web/frontend/package.json
if test ! -e web/frontend/package-lock.json; then npm --prefix web/frontend install --package-lock-only --ignore-scripts --registry "$npm_registry"; fi
test "$(node -p 'require("./web/frontend/package-lock.json").lockfileVersion')" = 3
npm --prefix web/frontend ci --registry "$npm_registry"
npm --prefix web/frontend run build 2>&1 | tee "$evidence_dir/frontend-build.log"
test "${PIPESTATUS[0]}" -eq 0
{ node --version; npm --version; node -p 'require("./web/frontend/package.json").packageManager'; } > "$evidence_dir/node-npm-versions.txt"
trap - EXIT
cleanup
printf '%s\n' 'setup-web-env: PASS'
