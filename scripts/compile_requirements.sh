#!/usr/bin/env bash
set -euo pipefail

if test "$#" -ne 2 || test "$1" != --profile; then
  printf '%s\n' 'usage: bash scripts/compile_requirements.sh --profile ai|gateway' >&2
  exit 2
fi

case "$2" in
  ai) input=requirements.in; output=requirements.lock ;;
  gateway) input=requirements-web.in; output=requirements-web.lock ;;
  *) printf 'unknown-profile: %s\n' "$2" >&2; exit 2 ;;
esac

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
test -s "$input"

resolver_dir="$(mktemp -d --tmpdir=/tmp)"
cleanup() {
  if test -d "$resolver_dir"; then
    python3 - "$resolver_dir" <<'PY'
import shutil
import sys
shutil.rmtree(sys.argv[1])
PY
  fi
}
trap cleanup EXIT

python3 -m venv "$resolver_dir"
"$resolver_dir/bin/python" -m pip install --disable-pip-version-check pip-tools==7.4.1
"$resolver_dir/bin/pip-compile" \
  --resolver=backtracking \
  --generate-hashes \
  --strip-extras \
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
  --output-file "$output" \
  "$input"
grep -q -- '--hash=sha256:' "$output"
printf 'requirements-lock: PASS: %s\n' "$output"
