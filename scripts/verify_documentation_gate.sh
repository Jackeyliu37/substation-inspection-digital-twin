#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

required_files=(
  AGENTS.md
  README.md
  基于数字孪生与多模态风险感知的变电站智能巡检系统_项目计划.md
  docs/ARCHITECTURE.md
  docs/DEPLOYMENT.md
  docs/INTERFACES.md
  docs/TEST_ACCEPTANCE.md
  docs/VERSION_MATRIX.md
  docs/DATA_AND_MODELS.md
  docs/PROJECT_STATUS.md
  docs/HANDOFF.md
  docs/plans/PHASE-01-ENVIRONMENT.md
  docs/adr/0001-headless-gazebo.md
  docs/adr/0002-server-web-deployment.md
  docs/adr/0003-multimodel-perception.md
  docs/adr/0004-nvidia-headless-packaging.md
)

for path in "${required_files[@]}"; do
  test -s "$path" || {
    printf 'documentation-gate: missing-or-empty: %s\n' "$path" >&2
    exit 1
  }
  git ls-files --error-unmatch "$path" >/dev/null
done

python3 - <<'PY'
import re
import subprocess
from pathlib import Path

contract = Path("docs/TEST_ACCEPTANCE.md").read_text(encoding="utf-8")
try:
    phase0_full_gate = contract.split("### 4.4 完整可重复 Phase 0 gate", 1)[1].split(
        "## 5. Phase 1 主机与环境验收（当前活动阶段；入口逐项激活）", 1
    )[0]
except IndexError as error:
    raise SystemExit("documentation-gate: Phase 0 full gate section not found") from error

blocks = re.findall(r"```bash\n(.*?)\n```", phase0_full_gate, flags=re.DOTALL)
if len(blocks) != 1:
    raise SystemExit(
        f"documentation-gate: expected exactly one Phase 0 full-gate Bash block, found {len(blocks)}"
    )
completed = subprocess.run(["bash", "-c", blocks[0]], text=True)
if completed.returncode != 0:
    raise SystemExit(
        f"documentation-gate: TEST_ACCEPTANCE section 4.4 failed with exit {completed.returncode}"
    )
PY

printf '%s\n' 'documentation-gate: PASS'
