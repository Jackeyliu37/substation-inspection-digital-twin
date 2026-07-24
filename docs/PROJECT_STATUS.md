# 项目状态

## 当前结论

- 当前阶段：Phase 9 集成前收口。Phase 1～3 已有 immutable live evidence；Phase 4 仍为 `in_progress / production model artifacts blocked`；Phase 5～8 已完成受限开发实现与契约验证，但尚不是生产交付。
- Phase 5～6 live acceptance：`passed`；实现提交 `7b7ffc4`，run ID `2f9e16bc-0ce8-4025-a50c-195998fac49f`，immutable evidence 为 `/var/lib/substation/evidence/acceptance/2f9e16bc-0ce8-4025-a50c-195998fac49f/05-risk-mission`。它在真实 Gazebo 场景中触发 `combined-risk-obstacle`，确认 transformer-01 风险为 68 分 / ALERT，任务队列重排到 transformer-01 首位，证据 SHA-256 全部通过且无残留进程。
- Phase 7 Gateway 开发检查点：`d61a7fb`。FastAPI Gateway 已覆盖 health/readiness、资产/任务/地图/报告/诊断快照、命令幂等、telemetry/events/camera WebSocket 契约，并有可供 systemd 使用的 `python -m substation_web_gateway` 启动入口；未接入真实 rclpy 订阅、Service/Action 调用或持久报告索引时 readiness fail-closed。
- Phase 8 前端开发检查点：`df30574`。八工作区和 REST/WebSocket-only 边界已实现；`npm test` 和 `npm run build` 已通过。主机没有可用 Chrome，尚未进行 Playwright 截图或浏览器端到端验收。
- Phase 6 任务持久化检查点：`e73f60a`。`substation_mission` 现在以单写者方式把任务队列、机器人模式、全局 state revision 和紧急停止锁存写入 `/var/lib/substation/sqlite/mission.sqlite3`；同 run 恢复完整快照，新 run 保留锁存并推进 revision。包级重建与测试为 `11 tests, 0 errors, 0 failures, 0 skipped`；直接对安装后的 `task_manager` 发送 SIGTERM 的 smoke 得到 SQLite `state_revision=1`、`emergency_stop_latched=0`，日志无 `Traceback/ERROR/FATAL/RCLError` 且无残留节点进程。
- Phase 6 Nav2 执行链检查点：`bea53a7`。任务管理器把同 revision 完整队列发到 `/mission/execute_inspection`，执行器顺序调用标准 `/navigate_to_pose`；风险重排会取消当前普通目标并提交新队首，紧停会取消活动 Nav2 goal，不可达任务按 `continue_on_unreachable` 跳过或失败。显式 launch 与无 Nav2 fail-closed smoke 已验证；`ExecuteInspection` goal 缺失的 `schema_version` 契约字段已补齐。pause/resume/stop 全生命周期、任务 terminal 状态和速度仲裁仍待实现。
- reporting ROS 检查点：`2f8847a`。新增 9 个 schema 1 Service、`evidence_store` 与 `report_generator` 节点；`evidence.sqlite3` 和内容寻址对象由 evidence store 单写，RunContext/revision、canonical metadata、SHA-256、JPEG freeze、Range、ROS-time→UTC 映射及 readiness fail-closed 已验证。报告节点只写 `/var/lib/substation/reports/.work` 并经 `/reporting/store_evidence` 提交 HTML/PDF/evidence ZIP/诊断 ZIP；缺 implementation commit 时不发布生成 Service。为消除 HTML 无法经 evidence store 提交的契约冲突，`text/html` 已仅对 report generator 加入 allowlist。独立 report/diagnostic 索引和 Gateway 下载映射仍待实现。
- 本轮全量软件验证：`colcon build --symlink-install && colcon test && colcon test-result --all --verbose` 为 `164 tests, 0 errors, 0 failures, 0 skipped`；顶层 Phase 5～6 interface contract 另为 `2 passed`，documentation gate 通过，world/navigation/perception/synthetic/Gateway/deployment 的既有检查点仍有效。
- Phase 2 已验证实现提交：`eeffd2e6ad26247987c9b3f9c922979089a90f41`。
- Phase 3 已验证实现提交：`5044ce56f66288beb0bd20563261c44bc1778996`（包含 `b25c99b` 地面支撑修复、`445539c` 本地代价地图窗口修复和 `5044ce5` 动态障碍探针修复）。
- 已验证环境实现提交：`993213026fef37f7e77741fd757caf8f684e0fd9`。
- Phase 1 验证完成时间：`2026-07-23T11:05:21Z`。
- Phase 2 验证完成时间：`2026-07-23T12:17:08Z`。
- Phase 2 验证结果：`passed`；run ID 为 `170b0adb-9553-4ce4-a304-c8425cfc156d`，`result.json` 和 `SHA256SUMS` 均已验证。
- 仪表数据生成器提交：`be1bc2fcfd13ed42c6d3b3f5deeb273f2fb8c01c`；ROS 包测试为 `53 tests, 0 errors, 0 failures, 0 skipped`。
- 全量数据生成结果：`passed`；run ID `8d51ced9-df63-430b-b7e4-0944fc2f0e96`，generation ID `a1532e097446a27c63654fb8159f7835955a41c1dc47008e04ace43eac1a82d2`，完成时间 `2026-07-23T15:05:27Z`。
- Phase 3 live acceptance 结果：`passed`；run ID `6e4c7d62-4e9c-4698-b789-d7fa40f32d82`，完成时间 `2026-07-23T17:21:23Z`；immutable evidence 为 `/var/lib/substation/evidence/acceptance/6e4c7d62-4e9c-4698-b789-d7fa40f32d82/03-navigation`。
- Phase 4 占位运行时已验证实现提交：`ff87d7d43a712e2549e4d36571fad01e6d8cf1eb`；live smoke `passed`，run ID `e2e3c709-63ee-4c7d-a41e-f099547acced`，完成时间 `2026-07-23T19:02:45Z`，immutable evidence 为 `/var/lib/substation/evidence/acceptance/e2e3c709-63ee-4c7d-a41e-f099547acced/04-perception-placeholder`。
- 当前阻塞项：Phase 4 正式 safety、equipment、fault 和 meter 模块的生产映射与最终验收等待用户发布四个不可变训练 artifact；该阻塞不否定已通过的开发占位链路。
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
- Phase 4 新建 `substation_perception`，包含不可变模型身份校验、CUDA 强制的延迟 Ultralytics 后端、有界 `Detection2DArray` 转换、最新帧背压、开发专用 Topic、带框 `rgb8` 图像和诊断。`colcon test --packages-select substation_perception` 为 `59 tests, 0 errors, 0 failures, 0 skipped`；顶层 smoke 合同测试另有 `2 passed`。
- Phase 4 首次占位 run `ceeacc8d-3c3e-4435-9704-1945a5dd6aa8` 保留 staging 证据；相机正常但系统 Python 找不到锁定的 Ultralytics，已由 `6b62963f8dd12742fc84649320204567f8ad6098` 接入锁定 AI 环境。最终实现 `456e824e21c7fff8ede1b89675b95be843793498` 强制 CUDA `device=0`、启动期身份错误诊断和 setsid 进程组清理；`bc7ee57b11c78d9d8037b84599d1bd1d33cfccf3` 再修复根目录与 `ros2_ws/install` 两种安装布局的绝对 `.venv` 解释器解析，并以 live smoke 回归验证。
- Phase 4 占位 live smoke 命令：`bash tests/perception/run_placeholder_smoke.sh --expected-commit ff87d7d43a712e2549e4d36571fad01e6d8cf1eb`。结果为 `passed`；官方权重 SHA-256 `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`、大小 `5613764` 字节，GPU 为 NVIDIA GeForce RTX 3060 Ti / driver `595.71.05`。
- Phase 4 占位 probe 收到 74 个相机样本、14 个开发检测消息和 13 个开发带框图像；14 个 detection header、13 个 annotated header 与源帧匹配，`frames_processed=14`、`frames_replaced=58`、`frames_failed=0`、`backend_ready=true`、`inference_device=cuda:0`。只读证据复核命令为 `(cd /var/lib/substation/evidence/acceptance/e2e3c709-63ee-4c7d-a41e-f099547acced/04-perception-placeholder && sha256sum -c SHA256SUMS)`；验收后无残留 Gazebo/ROS 进程。
- 该检查点只证明 `development_placeholder`，且 `production_ready=false`。输出只位于 `/perception/development/detections` 和 `/perception/development/annotated_image`，不进入正式聚合、数字孪生、风险、Gateway、报告或证据链；不得用它满足 Phase 4 生产模型或 300 秒 15 FPS 最终验收。

## 下一步

### 与项目计划的收口差异

| 计划项 | 当前事实 | 后续条件 |
|---|---|---|
| Phase 4 四模型、15 FPS、指标报告 | 官方 `yolo11n.pt` 占位 smoke 已通过；生产模型未导入 | 用户交付四个不可变训练 ZIP/Release，随后校验 SHA-256、类别、训练摘要与指标 |
| Phase 5 证据与报告 ROS 服务 | reporting Service、RunContext 时间映射、内容寻址证据、Range、HTML/PDF/evidence/diagnostic 生成与 evidence store 提交已验证 | 补 rosbag2、report/diagnostic 索引、告警/轨迹/模型完整快照与正式报告验收 |
| Phase 6 Nav2 巡检执行 | 风险确认、队列重排、SQLite 恢复及 `ExecuteInspection`→Nav2 目标替换/紧停取消已验证 | 补 pause/resume/stop terminal 状态、任务状态持久化、手动速度仲裁和正式 live acceptance |
| Phase 7 Gateway 真实控制面 | REST/WS/SQLite 命令契约已实现 | 用 rclpy 接权威 Topic/Service/Action，完成报告 Range 下载、命令终态与真实相机帧 |
| Phase 8 浏览器验收 | 八个工作区、契约测试和生产构建通过 | 安装/提供 Chromium 后执行 Playwright；真实 Gateway/ROS/Nginx 联调 |
| Phase 9 部署、Windows、Foxglove、演示 | systemd/Nginx/Foxglove 配置和静态契约已提交 | 以 `/opt/substation` release 实测、Windows LAN 验收、只读 Foxglove、900 s 闭环、报告/截图/演示视频 |

用户在 AutoDL 完成 safety、equipment、fault 和 meter 四个独立模型后，按已约定的精简交付把四个训练结果 ZIP 发布到不可变 GitHub release 或固定 commit。本仓库收到后校验权重、训练过程摘要、类别映射和指标，导入生产映射并继续正式模型、仪表 OpenCV 下游和全栈验收。
