# 项目状态

## 当前结论

- 当前阶段：Phase 3 SLAM/Nav2 已完成 live acceptance；Phase 2 Gazebo 世界和 Phase 4 仪表数据准备检查点也已完成。下一步等待用户上传 AutoDL 训练好的 `meter_locator` 模型并进入 Phase 4 集成。
- Phase 2 已验证实现提交：`eeffd2e6ad26247987c9b3f9c922979089a90f41`。
- Phase 3 已验证实现提交：`5044ce56f66288beb0bd20563261c44bc1778996`（包含 `b25c99b` 地面支撑修复、`445539c` 本地代价地图窗口修复和 `5044ce5` 动态障碍探针修复）。
- 已验证环境实现提交：`993213026fef37f7e77741fd757caf8f684e0fd9`。
- Phase 1 验证完成时间：`2026-07-23T11:05:21Z`。
- Phase 2 验证完成时间：`2026-07-23T12:17:08Z`。
- Phase 2 验证结果：`passed`；run ID 为 `170b0adb-9553-4ce4-a304-c8425cfc156d`，`result.json` 和 `SHA256SUMS` 均已验证。
- 仪表数据生成器提交：`be1bc2fcfd13ed42c6d3b3f5deeb273f2fb8c01c`；ROS 包测试为 `53 tests, 0 errors, 0 failures, 0 skipped`。
- 全量数据生成结果：`passed`；run ID `8d51ced9-df63-430b-b7e4-0944fc2f0e96`，generation ID `a1532e097446a27c63654fb8159f7835955a41c1dc47008e04ace43eac1a82d2`，完成时间 `2026-07-23T15:05:27Z`。
- Phase 3 live acceptance 结果：`passed`；run ID `6e4c7d62-4e9c-4698-b789-d7fa40f32d82`，完成时间 `2026-07-23T17:21:23Z`；immutable evidence 为 `/var/lib/substation/evidence/acceptance/6e4c7d62-4e9c-4698-b789-d7fa40f32d82/03-navigation`。
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
- Phase 2 运行时源码检查点验证：两包 `colcon build` 成功，`ros2 pkg prefix` 可解析两个 workspace 包，`colcon test-result --verbose` 为 `22 tests, 0 errors, 0 failures, 0 skipped`；`python3 -m pytest -q tests/world/test_world_contract.py tests/world/test_launch_contract.py tests/world/test_acceptance_contract.py` 为 `15 passed`；`git diff --check` 通过。
- 首次 live run `4fe34eba-b7c6-4029-ac09-0423b8e3bd3b` 已失败并保留 staging 证据；根因是原 manifest 邮箱非法导致包被降级识别为普通 Python 包，修复提交和回归测试已验证，下一次验收必须使用新 run ID。
- 第二次 live run `06c181e5-b401-4050-a687-383e41f3b78e` 已失败并保留 staging 证据；根因是资产 TF 节点调用了 Jazzy 不支持的多参数 logger API，修复提交和回归测试已验证。
- 第三次 live run `c3179573-892e-4e6f-b12c-72dd0e52e472` 已失败并保留 staging 证据；诊断证明全部 topic 与字段均有效，唯一根因是 probe 对 ROS `float32` 的 LiDAR 最小量程做精确相等比较，修复提交和现场值回归测试已验证。
- 第四次 live run `ef5489db-02fb-4948-b162-4fbb9d8ec87b` 已失败并保留 staging 证据；baseline、触发和幂等 revision 已通过，根因是 probe 把幂等重放的 `applying` 事件误当终态并过早发送 reset，终态等待修复和 race 回归测试已验证。
- Phase 2 最终 live acceptance：`bash tests/world/run_phase2_acceptance.sh --run-id 170b0adb-9553-4ce4-a304-c8425cfc156d --evidence-dir /var/lib/substation/evidence/acceptance/170b0adb-9553-4ce4-a304-c8425cfc156d/02-gazebo-world.staging`，结果依次为 `phase2-topic-probe: PASS` 和 `phase2-acceptance: PASS`。
- Phase 2 immutable evidence：`/var/lib/substation/evidence/acceptance/170b0adb-9553-4ce4-a304-c8425cfc156d/02-gazebo-world`。只读复核命令为 `(cd /var/lib/substation/evidence/acceptance/170b0adb-9553-4ce4-a304-c8425cfc156d/02-gazebo-world && sha256sum -c SHA256SUMS)`；全部 12 个证据文件通过，且没有残留 Phase 2 ROS/Gazebo 进程。
- 仪表数据 live smoke 已在 `/var/lib/substation/datasets/synthetic/gazebo-meter/b68b5a49cce51c8625cfc18282b789e07202a27b09b36131e80524f77a8ca905` 原子发布；包含 12 张图像和标签，train/val/test 各覆盖两种仪表，ZIP SHA-256 为 `4cb11ef6ea56b0e1a961cfe87e7f74d6287dc13869601e2e131db2554131b448`，运行后无残留 ROS/Gazebo 进程。
- 全量数据已在 `/var/lib/substation/datasets/synthetic/gazebo-meter/a1532e097446a27c63654fb8159f7835955a41c1dc47008e04ace43eac1a82d2` 原子发布；共 2,000 张 640x480 图像和标签，train/val/test 为 1600/200/200，油位/压力仪表各 1,000 张。ZIP 为 `gazebo-meter-locator-v1.zip`，SHA-256 `0f22438f4fa1baacdb06c7f64be65b08f78fd1b83f0891ac14f2c28c6ca0af4f`，大小 100,338,006 字节；逐文件校验、ZIP 测试和外层证据校验均通过，且无残留 ROS/Gazebo 进程。
- Phase 3 导航实现：静态地图、AMCL/Nav2、MPPI 控制器和 `/scan` 运行时障碍层已锁定；静态地图 SHA-256 为 `28d2643b517bfb3a691e74bec19889247815454baaeaa908256135765e639dc7`。
- Phase 3 一次性 acceptance 命令：`bash tests/navigation/run_phase3_acceptance.sh --run-id 6e4c7d62-4e9c-4698-b789-d7fa40f32d82 --evidence-dir /var/lib/substation/evidence/acceptance/6e4c7d62-4e9c-4698-b789-d7fa40f32d82/03-navigation.staging`；该 run ID 和 staging 命令不得复用。
- Phase 3 验收 JSON 显示静态目标和动态目标均成功，`map_to_odom=1`，`dynamic_obstacle_costmap_seen=true`，局部代价地图消息数为 `109`；证据目录内 `sha256sum -c SHA256SUMS` 全部通过，验收结束无残留进程。
- Phase 3 失败 run `e90c98da-99f4-463d-9df8-ccfd93bb7f0c` 保留 staging 证据；根因是探针只检查动态障碍中心附近 `0.1 m`，未覆盖 0.8 m 方箱表面的致命单元，已由 `5044ce5` 添加 `0.5 m` 米制搜索半径和回归测试修复。
- 本状态提交晚于并且只记录 Phase 3 已验证实现提交 `5044ce56f66288beb0bd20563261c44bc1778996`，不得把后续文档提交冒充为经过 Gazebo live acceptance 的实现提交。

## 下一步

用户按 `datasets/README.md` 将 ZIP 上传到 AutoDL，训练 `meter_locator`，并按约定交付权重、训练配置、类别映射和指标摘要；收到后进入 Phase 4 模型加载、仪表定位和 Gateway 集成验收。
