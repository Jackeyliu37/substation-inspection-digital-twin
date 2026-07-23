# 工作交接与恢复入口

## 当前恢复快照

- Repository：`/home/jackeyliu37/substation-inspection-digital-twin`。
- Branch：`main`。
- 当前阶段：Phase 9 集成前收口。Phase 4 官方 `yolo11n.pt` 开发占位运行时已通过 live smoke；生产集成仍等待用户在 AutoDL 训练的 safety、equipment、fault 和 meter 四个独立 artifact。
- Phase 5～6 live acceptance：`passed`；实现提交 `7b7ffc4`，run ID `2f9e16bc-0ce8-4025-a50c-195998fac49f`，immutable evidence `/var/lib/substation/evidence/acceptance/2f9e16bc-0ce8-4025-a50c-195998fac49f/05-risk-mission`。复核命令为 `(cd /var/lib/substation/evidence/acceptance/2f9e16bc-0ce8-4025-a50c-195998fac49f/05-risk-mission && sha256sum -c SHA256SUMS)`。
- Phase 7 Gateway 开发检查点：`d61a7fb`，Gateway 契约测试和部署契约共 13 passed；`python -m substation_web_gateway --host 127.0.0.1 --port 8001` 已 loopback 冒烟。它仍是 state seam，未连接真实 rclpy 控制面，因而 `/readyz` fail-closed。
- Phase 8 前端开发检查点：`df30574`，`npm test` 与 `npm run build` 已通过；没有 Chrome，因此没有 Playwright 浏览器证据。
- 当前软件验证：ROS workspace `138 tests, 0 errors, 0 failures, 0 skipped`；world/navigation/perception/synthetic/phase5_6/Gateway/deployment 和 documentation gate 均已通过。
- Phase 2 已验证实现提交：`eeffd2e6ad26247987c9b3f9c922979089a90f41`。
- Phase 3 已验证实现提交：`5044ce56f66288beb0bd20563261c44bc1778996`。
- 已验证环境实现提交：`993213026fef37f7e77741fd757caf8f684e0fd9`。
- 状态同步提交：使用 `git log -1 --format=%H -- docs/PROJECT_STATUS.md docs/HANDOFF.md` 查询；它只修改文档，并晚于环境实现提交。
- Phase 1 验证结果：`passed`，完成时间 `2026-07-23T11:05:21Z`；immutable evidence 为 `/var/lib/substation/evidence/acceptance/d9748529-dada-4699-b738-8aa1b90fdaf1/01-environment`。
- Phase 2 验证结果：`passed`，run ID `170b0adb-9553-4ce4-a304-c8425cfc156d`，完成时间 `2026-07-23T12:17:08Z`；immutable evidence 为 `/var/lib/substation/evidence/acceptance/170b0adb-9553-4ce4-a304-c8425cfc156d/02-gazebo-world`。
- 仪表数据生成器提交：`be1bc2fcfd13ed42c6d3b3f5deeb273f2fb8c01c`；ROS 包测试为 `53 tests, 0 errors, 0 failures, 0 skipped`。
- 全量数据已通过：run ID `8d51ced9-df63-430b-b7e4-0944fc2f0e96`，generation ID `a1532e097446a27c63654fb8159f7835955a41c1dc47008e04ace43eac1a82d2`，ZIP 路径 `/var/lib/substation/datasets/synthetic/gazebo-meter/a1532e097446a27c63654fb8159f7835955a41c1dc47008e04ace43eac1a82d2/gazebo-meter-locator-v1.zip`，SHA-256 `0f22438f4fa1baacdb06c7f64be65b08f78fd1b83f0891ac14f2c28c6ca0af4f`，大小 100,338,006 字节。
- Phase 3 验收结果：`passed`；run ID `6e4c7d62-4e9c-4698-b789-d7fa40f32d82`，immutable evidence `/var/lib/substation/evidence/acceptance/6e4c7d62-4e9c-4698-b789-d7fa40f32d82/03-navigation`。`result.json` 记录静态/动态目标成功、`dynamic_obstacle_costmap_seen=true`；静态地图 SHA-256 `28d2643b517bfb3a691e74bec19889247815454baaeaa908256135765e639dc7`。
- Phase 4 占位运行时实现提交：`ff87d7d43a712e2549e4d36571fad01e6d8cf1eb`；run ID `e2e3c709-63ee-4c7d-a41e-f099547acced`，结果 `passed`，immutable evidence `/var/lib/substation/evidence/acceptance/e2e3c709-63ee-4c7d-a41e-f099547acced/04-perception-placeholder`。该结果明确为 `development_placeholder`、`production_ready=false`，不是 Phase 4 生产验收。
- 当前运行的项目服务：无。

## 验证与恢复命令

- Canonical one-shot verifier 已执行：`bash scripts/verify_environment.sh --evidence-dir /var/lib/substation/evidence/acceptance/d9748529-dada-4699-b738-8aa1b90fdaf1/01-environment`。不得为此 acceptance run 再次执行。
- 最后成功的只读命令：`bash scripts/check_environment_seal.sh --evidence-dir /var/lib/substation/evidence/acceptance/d9748529-dada-4699-b738-8aa1b90fdaf1/01-environment`。
- 首次恢复命令：`cd /home/jackeyliu37/substation-inspection-digital-twin && source .phase1-run.env && bash scripts/check_environment_seal.sh --evidence-dir /var/lib/substation/evidence/acceptance/d9748529-dada-4699-b738-8aa1b90fdaf1/01-environment`。
- Phase 2 最新检查点：`python3 -m pytest -q tests/world/test_world_contract.py`，结果 `5 passed in 0.03s`。该检查点还通过两包 `colcon build/test/test-result`、SDF `gz sdf -k` 和 `check_urdf`。
- Phase 2 运行时非 live 门：两包构建成功，`ros2 pkg prefix` 可解析两个 workspace 包，`colcon test-result --verbose` 为 `22 tests, 0 errors, 0 failures, 0 skipped`，顶层 world/launch/acceptance 契约为 `15 passed`，`git diff --check` 通过。
- 失败的首次 live run `4fe34eba-b7c6-4029-ac09-0423b8e3bd3b` 保留为 staging 证据；其 `launch.log` 证明原 manifest 邮箱非法使 workspace 包未进入 ament 索引。该问题已由 `a58e92f61a7e982e9e2ca7bb8d0e58e7db21f9e6` 修复，禁止复用旧 run ID。
- 失败的第二次 live run `06c181e5-b401-4050-a687-383e41f3b78e` 同样保留 staging 证据；其 `launch.log` 证明资产 TF 节点因 Jazzy logger API 误用退出。该问题已由 `695643e0455280f1a4019adb939e296eab7bd8e2` 修复，禁止复用旧 run ID。
- 失败的第三次 live run `c3179573-892e-4e6f-b12c-72dd0e52e472` 同样保留 staging 证据；短时诊断证明全部 topic 与字段有效，仅 LaserScan 的 `0.12` 经 `float32` 传输成为 `0.11999999731779099`。该问题已由 `9a56f6a380563479ded178f7b6e20405ea0c0bf1` 修复，禁止复用旧 run ID。
- 失败的第四次 live run `ef5489db-02fb-4948-b162-4fbb9d8ec87b` 同样保留 staging 证据；baseline、触发和幂等 revision 已通过，probe 仅因把幂等重放的 `applying` 事件误当终态而过早 reset。该问题已由 `ce25f96c2b263c078843d345c08e6ed96ceedaf3` 修复，禁止复用旧 run ID。
- Phase 2 一次性 acceptance 已执行：`bash tests/world/run_phase2_acceptance.sh --run-id 170b0adb-9553-4ce4-a304-c8425cfc156d --evidence-dir /var/lib/substation/evidence/acceptance/170b0adb-9553-4ce4-a304-c8425cfc156d/02-gazebo-world.staging`；不得复用该 run ID 或 staging 命令。
- Phase 2 只读恢复检查：`(cd /var/lib/substation/evidence/acceptance/170b0adb-9553-4ce4-a304-c8425cfc156d/02-gazebo-world && sha256sum -c SHA256SUMS)`；全部证据哈希通过，`result.json.implementation_commit` 为 `eeffd2e6ad26247987c9b3f9c922979089a90f41`，无残留 Phase 2 进程。
- Phase 3 只读恢复检查：`(cd /var/lib/substation/evidence/acceptance/6e4c7d62-4e9c-4698-b789-d7fa40f32d82/03-navigation && sha256sum -c SHA256SUMS)`；全部 10 个证据文件通过，`result.json.implementation_commit` 为 `5044ce56f66288beb0bd20563261c44bc1778996`，无残留 Phase 3 ROS/Gazebo 进程。
- Phase 3 一次性 acceptance 已执行：`bash tests/navigation/run_phase3_acceptance.sh --run-id 6e4c7d62-4e9c-4698-b789-d7fa40f32d82 --evidence-dir /var/lib/substation/evidence/acceptance/6e4c7d62-4e9c-4698-b789-d7fa40f32d82/03-navigation.staging`；不得复用该 run ID 或 staging 命令。
- Phase 4 占位 smoke 已执行：`bash tests/perception/run_placeholder_smoke.sh --expected-commit ff87d7d43a712e2549e4d36571fad01e6d8cf1eb`；probe 为 `backend_ready=true`、`inference_device=cuda:0`，相机/检测/带框图像计数为 74/14/13，14/13 个输出 header 分别匹配源帧，14 帧成功、58 帧被最新帧背压替换、0 帧失败。
- Phase 4 占位证据只读复核：`(cd /var/lib/substation/evidence/acceptance/e2e3c709-63ee-4c7d-a41e-f099547acced/04-perception-placeholder && sha256sum -c SHA256SUMS)`。官方权重 SHA-256 为 `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`、大小 `5613764` 字节；验收后无残留项目进程。
- Phase 4 首次失败 run `ceeacc8d-3c3e-4435-9704-1945a5dd6aa8` 保留 staging 证据；根因是系统 Python 没有锁定的 Ultralytics。最终修复强制 CUDA `device=0`、在身份校验失败时发布诊断、通过绝对 `.venv` 解释器运行，并按 setsid 进程组清理。
- 本文档提交晚于已验证实现提交，仅记录 acceptance 结果；不得把文档提交冒充为经过 Gazebo live acceptance 的实现提交。
- 当前 ROS 恢复命令：`cd /home/jackeyliu37/substation-inspection-digital-twin && set +u && source /opt/ros/jazzy/setup.bash && source install/setup.bash && set -u && export ROS_LOCALHOST_ONLY=1 && colcon build --symlink-install && colcon test --event-handlers console_direct+ && colcon test-result --all --verbose`。源代码在 `ros2_ws/src`，但本仓库从根目录执行 colcon，当前产物在根 `build/`、`install/`；不要 source 旧的 `ros2_ws/install/setup.bash`。

## 本地状态

- `.phase1-run.env`、`.venv`、`.venv-web`、ROS build/install/log、Node toolchain、`node_modules` 和 `.next` 均被 Git 忽略或位于仓库外。
- Node archive 和官方 `yolo11n.pt` 位于 Git 外，其身份记录在 `artifacts/environment/resource-downloads.tsv`。
- `git status --short` 在交接提交前仅显示预先存在的未跟踪文件 `.phase1-run.failed-a9ab99ee-a85e-4c6f-a9bd-65b421efc8ca.env`；未修改或删除它。
- 失败的旧 acceptance run `c2d99d10-058f-4033-aa33-89917bf74590` 按一次性封存契约保留为未封存失败证据；Phase 1 当前 passed run 为 `d9748529-dada-4699-b738-8aa1b90fdaf1`，Phase 3 当前 passed run 为 `6e4c7d62-4e9c-4698-b789-d7fa40f32d82`。

## 固定边界

- 浏览器只通过 Nginx 和 FastAPI REST/WebSocket，不直连 ROS DDS。
- 不启动或宣称已部署 Nginx、Gateway、前端、Gazebo 或 ROS 应用服务。
- 公开训练数据下载和模型微调由用户在仓库外完成；仓库中的官方 YOLO11n 仅为非生产占位。
- 占位结果只发布到 `/perception/development/detections` 和 `/perception/development/annotated_image`；正式聚合、数字孪生、风险、Gateway、报告和证据链不得消费它们。
- 下一实现动作：优先接收用户四个训练结果 ZIP，以不可变 GitHub release 或固定 commit 导入并校验；随后补报告 ROS Service、Nav2 `ExecuteInspection` 执行器/持久化、真实 Gateway ROS adapter、Playwright/Windows/Nginx/ Foxglove 集成证据。Phase 4 占位运行时已经通过，但 Phase 4 与最终交付尚未完成。
