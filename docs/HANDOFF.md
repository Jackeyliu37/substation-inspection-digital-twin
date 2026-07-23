# 工作交接与恢复入口

## 当前恢复快照

- Repository：`/home/jackeyliu37/substation-inspection-digital-twin`。
- Branch：`main`。
- 当前阶段：Phase 1 环境基线已完成；Phase 2 Gazebo world 规划是下一项工作。
- 已验证环境实现提交：`993213026fef37f7e77741fd757caf8f684e0fd9`。
- 状态同步提交：使用 `git log -1 --format=%H -- docs/PROJECT_STATUS.md docs/HANDOFF.md` 查询；它只修改文档，并晚于环境实现提交。
- 验证结果：`passed`，完成时间 `2026-07-23T11:05:21Z`。
- immutable evidence：`/var/lib/substation/evidence/acceptance/d9748529-dada-4699-b738-8aa1b90fdaf1/01-environment`；`result.json` 为 passed，`SHA256SUMS` 已验证。
- 当前运行的项目服务：无。

## 验证与恢复命令

- Canonical one-shot verifier 已执行：`bash scripts/verify_environment.sh --evidence-dir /var/lib/substation/evidence/acceptance/d9748529-dada-4699-b738-8aa1b90fdaf1/01-environment`。不得为此 acceptance run 再次执行。
- 最后成功的只读命令：`bash scripts/check_environment_seal.sh --evidence-dir /var/lib/substation/evidence/acceptance/d9748529-dada-4699-b738-8aa1b90fdaf1/01-environment`。
- 首次恢复命令：`cd /home/jackeyliu37/substation-inspection-digital-twin && source .phase1-run.env && bash scripts/check_environment_seal.sh --evidence-dir /var/lib/substation/evidence/acceptance/d9748529-dada-4699-b738-8aa1b90fdaf1/01-environment`。

## 本地状态

- `.phase1-run.env`、`.venv`、`.venv-web`、ROS build/install/log、Node toolchain、`node_modules` 和 `.next` 均被 Git 忽略或位于仓库外。
- Node archive 和官方 `yolo11n.pt` 位于 Git 外，其身份记录在 `artifacts/environment/resource-downloads.tsv`。
- `git status --short` 在交接提交前仅显示预先存在的未跟踪文件 `.phase1-run.failed-a9ab99ee-a85e-4c6f-a9bd-65b421efc8ca.env`；未修改或删除它。
- 失败的旧 acceptance run `c2d99d10-058f-4033-aa33-89917bf74590` 按一次性封存契约保留为未封存失败证据；当前 passed run 为 `d9748529-dada-4699-b738-8aa1b90fdaf1`。

## 固定边界

- 浏览器只通过 Nginx 和 FastAPI REST/WebSocket，不直连 ROS DDS。
- 不启动或宣称已部署 Nginx、Gateway、前端、Gazebo 或 ROS 应用服务。
- 公开训练数据下载和模型微调由用户在仓库外完成；仓库中的官方 YOLO11n 仅为非生产占位。
- 下一实现动作是先创建并审查零上下文 Phase 2 Gazebo world 计划，再添加 ROS package 或产品 world。
