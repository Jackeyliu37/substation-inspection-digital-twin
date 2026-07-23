# 项目状态

## 当前结论

- 当前阶段：Phase 2 Gazebo 变电站世界开发中；场景运行时、纯无头 launch 和 live acceptance 工具已完成非 live 验证，等待固定提交上的 Gazebo live acceptance。
- Phase 2 当前已验证运行时源码提交：`695643e0455280f1a4019adb939e296eab7bd8e2`。
- 已验证环境实现提交：`993213026fef37f7e77741fd757caf8f684e0fd9`。
- 验证完成时间：`2026-07-23T11:05:21Z`。
- 验证结果：`passed`；`result.json` 和 `SHA256SUMS` 均已验证。
- 当前阻塞项：无。
- 正在运行的项目服务：无。Gazebo、ROS 项目节点、Gateway、前端、Foxglove Bridge 和 Nginx 均未作为产品服务运行。

## Phase 1 验证记录

- 一次性验证命令：`bash scripts/verify_environment.sh --evidence-dir /var/lib/substation/evidence/acceptance/d9748529-dada-4699-b738-8aa1b90fdaf1/01-environment`。该 acceptance run 已封存，不得再次运行此命令。
- 后续只读检查：`bash scripts/check_environment_seal.sh --evidence-dir /var/lib/substation/evidence/acceptance/d9748529-dada-4699-b738-8aa1b90fdaf1/01-environment`。
- immutable evidence：`/var/lib/substation/evidence/acceptance/d9748529-dada-4699-b738-8aa1b90fdaf1/01-environment`。
- `result.json.git_commit` 有意指向已验证的 Task 10 环境实现提交 `993213026fef37f7e77741fd757caf8f684e0fd9`。后续状态/交接提交只修改文档，不冒充经过环境验证的实现提交。
- 状态文档提交使用 `git log -1 --format=%H -- docs/PROJECT_STATUS.md docs/HANDOFF.md` 查询；本文不嵌入自身哈希。

## 已完成范围

- 文档 gate、轻量只读主机审计、官方主机依赖安装和资源校验。
- ROS 2 Jazzy 空工作区及 colcon build/test/test-result 基线。
- PyTorch CUDA 12.6 AI 环境、FastAPI Gateway 环境及其哈希锁和 provenance。
- Node.js 24.18.0、npm 11.16.0、Next.js 前端锁文件和生产构建。
- 无 `DISPLAY` 的 Gazebo Harmonic OGRE2/EGL 64×48 RGB camera probe。
- 受审查的环境快照、一次性 verifier 和 immutable evidence seal。
- 官方 `yolo11n.pt` 仅作开发占位；公开训练数据和模型微调仍由用户在仓库外完成。
- Phase 2 已建立 `substation_description`、`substation_gazebo`、10 个稳定资产（8 类规范设备和 2 个仪表）、TurtleBot3 Waffle Pi 尺寸机器人、OGRE2 传感器、静态世界和 ROS bridge 配置。
- Phase 2 静态检查点验证：`python3 -m pytest -q tests/world/test_world_contract.py`，结果 `5 passed`；两包 `colcon build/test/test-result` 为 `6 tests, 0 errors, 0 failures`，SDF 与 URDF 解析通过。
- Phase 2 运行时源码检查点验证：两包 `colcon build` 成功，`ros2 pkg prefix` 可解析两个 workspace 包，`colcon test-result --verbose` 为 `22 tests, 0 errors, 0 failures, 0 skipped`；`python3 -m pytest -q tests/world/test_world_contract.py tests/world/test_launch_contract.py tests/world/test_acceptance_contract.py` 为 `13 passed`；`git diff --check` 通过。
- 首次 live run `4fe34eba-b7c6-4029-ac09-0423b8e3bd3b` 已失败并保留 staging 证据；根因是原 manifest 邮箱非法导致包被降级识别为普通 Python 包，修复提交和回归测试已验证，下一次验收必须使用新 run ID。
- 第二次 live run `06c181e5-b401-4050-a687-383e41f3b78e` 已失败并保留 staging 证据；根因是资产 TF 节点调用了 Jazzy 不支持的多参数 logger API，修复提交和回归测试已验证。

## Phase 2 当前工作

1. 提交并推送当前运行时检查点状态。
2. 对干净固定提交运行无 `DISPLAY` Gazebo live acceptance 并生成 Phase 2 immutable evidence。
3. live evidence 通过后封存 Phase 2 状态并转入 Phase 3 设计；在此之前不声明 Phase 2 完成。
