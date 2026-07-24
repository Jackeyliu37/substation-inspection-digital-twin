#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 [--output-root ABSOLUTE_PATH]" >&2
  exit 2
}

output_root="/var/lib/substation/releases-staging"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-root) output_root="${2:-}"; shift 2 ;;
    *) usage ;;
  esac
done
[[ "$output_root" = /* ]] || usage

repository="$(git rev-parse --show-toplevel)"
cd "$repository"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "build-release: repository must be clean" >&2
  exit 1
fi
commit="$(git rev-parse --verify HEAD^{commit})"
[[ "$commit" =~ ^[0-9a-f]{40}$ ]]

for required in .venv .venv-web web/frontend/node_modules; do
  if [[ ! -d "$repository/$required" ]]; then
    echo "build-release: missing runtime dependency: $required" >&2
    exit 1
  fi
done

mkdir -p -- "$output_root"
final="$output_root/$commit"
staging="$output_root/.$commit.staging"
[[ ! -e "$final" && ! -e "$staging" ]] || {
  echo "build-release: candidate already exists for $commit" >&2
  exit 1
}
available_kib="$(df -Pk "$output_root" | awk 'NR == 2 {print $4}')"
if ((available_kib < 20 * 1024 * 1024)); then
  echo "build-release: less than 20 GiB free" >&2
  exit 1
fi

mkdir -p -- "$staging"
git archive --format=tar "$commit" | tar -xf - -C "$staging"
cp -a --reflink=auto "$repository/.venv" "$staging/.venv"
cp -a --reflink=auto "$repository/.venv-web" "$staging/.venv-web"
cp -a --reflink=auto \
  "$repository/web/frontend/node_modules" \
  "$staging/web/frontend/node_modules"

build_root="$(mktemp -d "$output_root/.build-$commit.XXXXXX")"
cleanup() {
  case "$build_root" in "$output_root"/.build-"$commit".*) rm -rf -- "$build_root" ;; esac
}
trap cleanup EXIT

set +u
source /opt/ros/jazzy/setup.bash
set -u
colcon --log-base "$build_root/log" build \
  --base-paths "$staging/ros2_ws/src" \
  --build-base "$build_root/build" \
  --install-base "$staging/install" \
  --merge-install \
  --event-handlers console_direct+

node_root="/opt/substation/toolchains/node-current/bin"
PATH="$node_root:$PATH" npm --prefix "$staging/web/frontend" run build

commit_time="$(git show -s --format=%cI "$commit")"
python3 - "$staging/release-manifest.json" "$commit" "$commit_time" <<'PY'
import json
from pathlib import Path
import sys

target = Path(sys.argv[1])
payload = {
    "schema_version": 1,
    "git_commit": sys.argv[2],
    "source_commit_time": sys.argv[3],
    "runtime_components": [
        "ros2-install",
        "ai-venv",
        "gateway-venv",
        "nextjs-production",
        "deployment-config",
    ],
}
target.write_text(
    json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

(
  cd "$staging"
  find . -type f ! -name release-SHA256SUMS -printf '%P\0' \
    | LC_ALL=C sort -z \
    | xargs -0 sha256sum -- \
    > release-SHA256SUMS
  sha256sum -c release-SHA256SUMS
)
mv -- "$staging" "$final"
trap - EXIT
cleanup
echo "build-release: PASS: $final"
