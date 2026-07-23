# 工作交接与恢复入口

## 当前恢复快照

- Repository：`/home/jackeyliu37/substation-inspection-digital-twin`。
- Branch：`main`。
- 当前阶段：Phase 2 Gazebo world 开发中；场景运行时、纯无头 launch 和 acceptance 工具已通过非 live 门，Gazebo live acceptance 是下一项工作。
- Phase 2 当前已验证运行时源码提交：`9a56f6a380563479ded178f7b6e20405ea0c0bf1`。
- 已验证环境实现提交：`993213026fef37f7e77741fd757caf8f684e0fd9`。
- 状态同步提交：使用 `git log -1 --format=%H -- docs/PROJECT_STATUS.md docs/HANDOFF.md` 查询；它只修改文档，并晚于环境实现提交。
- 验证结果：`passed`，完成时间 `2026-07-23T11:05:21Z`。
- immutable evidence：`/var/lib/substation/evidence/acceptance/d9748529-dada-4699-b738-8aa1b90fdaf1/01-environment`；`result.json` 为 passed，`SHA256SUMS` 已验证。
- 当前运行的项目服务：无。

## 验证与恢复命令

- Canonical one-shot verifier 已执行：`bash scripts/verify_environment.sh --evidence-dir /var/lib/substation/evidence/acceptance/d9748529-dada-4699-b738-8aa1b90fdaf1/01-environment`。不得为此 acceptance run 再次执行。
- 最后成功的只读命令：`bash scripts/check_environment_seal.sh --evidence-dir /var/lib/substation/evidence/acceptance/d9748529-dada-4699-b738-8aa1b90fdaf1/01-environment`。
- 首次恢复命令：`cd /home/jackeyliu37/substation-inspection-digital-twin && source .phase1-run.env && bash scripts/check_environment_seal.sh --evidence-dir /var/lib/substation/evidence/acceptance/d9748529-dada-4699-b738-8aa1b90fdaf1/01-environment`。
- Phase 2 最新检查点：`python3 -m pytest -q tests/world/test_world_contract.py`，结果 `5 passed in 0.03s`。该检查点还通过两包 `colcon build/test/test-result`、SDF `gz sdf -k` 和 `check_urdf`。
- Phase 2 运行时非 live 门：两包构建成功，`ros2 pkg prefix` 可解析两个 workspace 包，`colcon test-result --verbose` 为 `22 tests, 0 errors, 0 failures, 0 skipped`，顶层 world/launch/acceptance 契约为 `14 passed`，`git diff --check` 通过。
- 失败的首次 live run `4fe34eba-b7c6-4029-ac09-0423b8e3bd3b` 保留为 staging 证据；其 `launch.log` 证明原 manifest 邮箱非法使 workspace 包未进入 ament 索引。该问题已由 `a58e92f61a7e982e9e2ca7bb8d0e58e7db21f9e6` 修复，禁止复用旧 run ID。
- 失败的第二次 live run `06c181e5-b401-4050-a687-383e41f3b78e` 同样保留 staging 证据；其 `launch.log` 证明资产 TF 节点因 Jazzy logger API 误用退出。该问题已由 `695643e0455280f1a4019adb939e296eab7bd8e2` 修复，禁止复用旧 run ID。
- 失败的第三次 live run `c3179573-892e-4e6f-b12c-72dd0e52e472` 同样保留 staging 证据；短时诊断证明全部 topic 与字段有效，仅 LaserScan 的 `0.12` 经 `float32` 传输成为 `0.11999999731779099`。该问题已由 `9a56f6a380563479ded178f7b6e20405ea0c0bf1` 修复，禁止复用旧 run ID。
- Phase 2 恢复命令：`cd /home/jackeyliu37/substation-inspection-digital-twin && set +u && source /opt/ros/jazzy/setup.bash && set -u && export ROS_LOCALHOST_ONLY=1 && cd ros2_ws && colcon build --symlink-install --packages-select substation_description substation_gazebo && source install/setup.bash && colcon test --packages-select substation_description substation_gazebo --event-handlers console_direct+ && colcon test-result --verbose`。

## 本地状态

- `.phase1-run.env`、`.venv`、`.venv-web`、ROS build/install/log、Node toolchain、`node_modules` 和 `.next` 均被 Git 忽略或位于仓库外。
- Node archive 和官方 `yolo11n.pt` 位于 Git 外，其身份记录在 `artifacts/environment/resource-downloads.tsv`。
- `git status --short` 在交接提交前仅显示预先存在的未跟踪文件 `.phase1-run.failed-a9ab99ee-a85e-4c6f-a9bd-65b421efc8ca.env`；未修改或删除它。
- 失败的旧 acceptance run `c2d99d10-058f-4033-aa33-89917bf74590` 按一次性封存契约保留为未封存失败证据；当前 passed run 为 `d9748529-dada-4699-b738-8aa1b90fdaf1`。

## 固定边界

- 浏览器只通过 Nginx 和 FastAPI REST/WebSocket，不直连 ROS DDS。
- 不启动或宣称已部署 Nginx、Gateway、前端、Gazebo 或 ROS 应用服务。
- 公开训练数据下载和模型微调由用户在仓库外完成；仓库中的官方 YOLO11n 仅为非生产占位。
- 下一实现动作：提交并推送运行时检查点状态，然后按 `docs/superpowers/plans/2026-07-23-gazebo-substation-world.md` 在干净固定提交上运行无 `DISPLAY` Gazebo live acceptance；Phase 3 尚未开始。
