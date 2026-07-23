#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

test -x scripts/verify_documentation_gate.sh
output="$(bash scripts/verify_documentation_gate.sh)"
grep -Fx 'documentation-gate: PASS' <<<"$output"

grep -Fq '公开训练数据下载和模型微调由用户在本仓库外完成' docs/DATA_AND_MODELS.md
grep -Fq '官方 `yolo11n.pt` 仅作为开发占位/base weight' docs/DATA_AND_MODELS.md
grep -Fq '用户发布的不可变 GitHub release 或固定 commit' docs/DATA_AND_MODELS.md
grep -Fq '接收并验证用户训练产物' 基于数字孪生与多模态风险感知的变电站智能巡检系统_项目计划.md
! grep -Fq '| 4. 数据与 YOLO11n | 第 4～5 周 | 下载、许可清单、格式转换、合成仪表数据、分模型训练和评估 |' 基于数字孪生与多模态风险感知的变电站智能巡检系统_项目计划.md

printf '%s\n' 'model-training-boundary: PASS'
