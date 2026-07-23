#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

test -x scripts/setup_web_env.sh
grep -Fq 'npm_registry=https://registry.npmmirror.com' scripts/setup_web_env.sh
node --version | grep -Fx v24.18.0
npm_spec="$(node -p 'require("./web/frontend/package.json").packageManager')"
[[ "$npm_spec" =~ ^npm@[0-9]+\.[0-9]+\.[0-9]+$ ]]
test "$(npm --prefix web/frontend --version)" = "${npm_spec#npm@}"
test "$(node -p 'require("./web/frontend/package-lock.json").lockfileVersion')" = 3
npm --prefix web/frontend ls next --depth=0 | grep -F 'next@16.2.11'
npm --prefix web/frontend ls react react-dom --depth=0 | grep -F 'react@19.2.8'
npm --prefix web/frontend ls react react-dom --depth=0 | grep -F 'react-dom@19.2.8'
npm --prefix web/frontend ls typescript --depth=0 | grep -F 'typescript@6.0.3'
npm --prefix web/frontend ls tailwindcss --depth=0 | grep -F 'tailwindcss@4.3.3'
npm --prefix web/frontend ls three --depth=0 | grep -F 'three@0.185.1'
npm --prefix web/frontend ls @react-three/fiber --depth=0 | grep -F '@react-three/fiber@9.6.1'
npm --prefix web/frontend ls echarts --depth=0 | grep -F 'echarts@6.1.0'
web/frontend/node_modules/.bin/playwright --version | grep -Fx 'Version 1.61.1'
test -L /opt/substation/toolchains/node-current
test "$(readlink -f /opt/substation/toolchains/node-current)" = /opt/substation/toolchains/node-v24.18.0
python3 - /opt/substation/toolchains/node-v24.18.0/.substation-toolchain.json <<'PY'
import json, sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert data["owner"] == "phase1-environment"
assert data["toolchain"] == "node"
assert data["version"] == "24.18.0"
assert len(data["archive_sha256"]) == 64
PY
