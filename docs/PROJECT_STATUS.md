# 项目状态

## 当前结论

- 当前阶段：Phase 9 集成前收口。Phase 1～3 已有 immutable live evidence；Phase 4 四个训练 artifact 已按用户授权导入并建立 production 映射，但 safety 的 `mAP50=0.69297` 低于文档硬门槛 `0.75`，本轮以显式 operator waiver 记录；Phase 5～9 的受限实现、契约和构建验证已完成，但尚不是严格生产交付。
- Phase 5～6 live acceptance：`passed`；实现提交 `7b7ffc4`，run ID `2f9e16bc-0ce8-4025-a50c-195998fac49f`，immutable evidence 为 `/var/lib/substation/evidence/acceptance/2f9e16bc-0ce8-4025-a50c-195998fac49f/05-risk-mission`。它在真实 Gazebo 场景中触发 `combined-risk-obstacle`，确认 transformer-01 风险为 68 分 / ALERT，任务队列重排到 transformer-01 首位，证据 SHA-256 全部通过且无残留进程。
- Phase 7 Gateway ROS 适配检查点：`82d70fc`。独立 rclpy executor 已接入权威 RunContext、数字孪生、风险、任务、地图/增量和 diagnostics；同 run/revision 校验、ROS-time→UTC、float32 Web 规范化、Web snapshot revision 幂等及 reporting readiness 均 fail-closed。mission POST 只有 `/mission/manage` 实际接受后才写 accepted；evidence metadata 与 200/206/304/400/416 Range 下载只经 reporting Service。生产入口会加载 ROS/colcon 环境，安装后进程 smoke 为 `/healthz=200`、缺权威 ROS 图时 `/readyz=503`。
- Phase 8 前端检查点：`ec927c1`（基于 `df30574`）。八工作区和 REST/WebSocket-only 边界已实现；本轮重新执行 `npm test`（`frontend contract: PASS (8 views, REST/WS boundary locked)`）和 `npm run build`（Next.js 16.2.11，退出码 0）。按操作员决定，本项目采用 Windows 浏览器人工验收，不把 Playwright 作为交付前置条件。
- Phase 9 部署检查点：systemd、Nginx、Foxglove 和 safe-stop 契约已重新验证；Gateway/接口/部署回归为 `49 passed`，documentation gate 为 `PASS`。Nginx 片段通过临时 `events/http` 包装配置的 `nginx -t` 语法检查；产品服务未启动，`/opt/substation/current` release、Windows LAN、真实 Foxglove 和演示闭环仍待现场验收。
- Phase 6 任务持久化检查点：`e73f60a`。`substation_mission` 现在以单写者方式把任务队列、机器人模式、全局 state revision 和紧急停止锁存写入 `/var/lib/substation/sqlite/mission.sqlite3`；同 run 恢复完整快照，新 run 保留锁存并推进 revision。包级重建与测试为 `11 tests, 0 errors, 0 failures, 0 skipped`；直接对安装后的 `task_manager` 发送 SIGTERM 的 smoke 得到 SQLite `state_revision=1`、`emergency_stop_latched=0`，日志无 `Traceback/ERROR/FATAL/RCLError` 且无残留节点进程。
- Phase 6 Nav2 执行链检查点：`bea53a7`。任务管理器把同 revision 完整队列发到 `/mission/execute_inspection`，执行器顺序调用标准 `/navigate_to_pose`；风险重排会取消当前普通目标并提交新队首，紧停会取消活动 Nav2 goal，不可达任务按 `continue_on_unreachable` 跳过或失败。显式 launch 与无 Nav2 fail-closed smoke 已验证；`ExecuteInspection` goal 缺失的 `schema_version` 契约字段已补齐。
- Phase 6 mission 生命周期检查点：`19a983d`。`/mission/manage` 已实现 pause/resume/stop 和 stop 后 start 新 run；Action feedback/result 将 active/succeeded/skipped/failed/cancelled task、mission terminal、RunContext lifecycle 与 transition command 原子写回 `mission.sqlite3`。风险重排会把被取消的 ACTIVE task 安全重排回 QUEUED，已完成任务不重复执行；Gateway command 仅在 matching 权威 mission 快照后从 accepted 转 succeeded。
- Phase 6 速度仲裁检查点：`4268803`。任务模块现在是最终 `/cmd_vel` 单一项目发布者：autonomous 只接受 `/cmd_vel_nav`，manual 只接受带 run/context 的 `/cmd_vel_manual`；手动命令使用进程 monotonic deadline，校验模式、紧停、frame、限速和 duration，按 ACCEPTED→APPLIED 发布状态并到期归零，重复 command 不重放。`/mission/set_robot_mode` 使用 state/latch revision CAS，切 manual 会取消 Nav2 并先发零速度。冷启动 IDLE→START 与紧停复位 0.5 s/无活动 goal 完整 barrier 仍待收口。
- Phase 7 Gateway 控制面检查点：`c78f1ad`。新增 `/api/v1/robot/mode`、`/api/v1/robot/manual-velocity`、`/api/v1/robot/emergency-stop` 和 `/api/v1/robot/emergency-stop/reset`；所有命令经真实 ROS Service/Topic adapter，紧停不依赖 readiness，manual endpoint 只发布 `ManualVelocityCommand`。参数、Idempotency-Key、uint64 revision、速度/时长/deadman 和 fail-closed 错误均已测试。
- Phase 7 Gateway 机器人状态检查点：`e0578d0`。Gateway 使用显式契约 QoS 订阅 `/odom`、`/battery_state` 和 tf2，在 odom 样本的精确 stamp 查询 `map←odom`，验证 frame/有限数/四元数后组成 map pose，并把标准 0～1 电量换算成百分数。mission 模式、锁存 revision 和 active task 与机器人快照原子同步；pose 超过 0.5 秒或时钟异常即 stale，HTTP gate 与 ROS 发布边界均拒绝普通手动移动，紧停路径不受影响。真实 rclpy TF/odom/battery→ASGI `/api/v1/robot/state` 集成测试已通过；命令终态与 reporting 索引/下载已接入，真实相机帧仍待收口。
- Phase 7 Gateway 命令终态检查点：`db2b089`。CommandStore 保存每次受理命令的 payload 与 Service 最小 revision，只有 matching mission transition、robot mode/latch/revision 或 `ManualVelocityStatus` terminal 才写入 succeeded/failed/timed_out/cancelled；HTTP 202、Service accepted 和 ManualVelocityStatus.ACCEPTED 不再伪造成功。固定 timeout 会将未完成命令终结为 timed_out，终态在 SQLite 提交后写入 `command.status` 事件并由 `/ws/events` 重放；ROS 先于 HTTP 记录到达的 mission/manual 状态可回放。Gateway 回归已覆盖这些正负终态与竞态。
- reporting ROS 检查点：`2f8847a` → reporting index checkpoint。`EvidenceStore.list_evidence` 和 schema 1 `/reporting/list_reporting_artifacts` 以 metadata 建立 report/diagnostic artifact 索引，Gateway 通过该 Service 分组 `/api/v1/reports`、`/api/v1/diagnostics`，并将 HTML/PDF/evidence/diagnostic 下载映射到同一 reporting Range/ETag/SHA-256 读取边界；Gateway 不读文件或 SQLite。报告节点提交 metadata 的 group/format/run/mission/created_at 字段。
- 本轮 reporting index 验证：reporting tests `18 passed`，Gateway tests `42 passed`；ROS 接口/节点包已重建。完整 workspace、部署/接口 contract 与 documentation gate 将在本检查点提交前复跑。
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
- Phase 4 模型 handoff：用户上传的 `artifacts/phase4/substation_yolo_runs.zip` SHA-256 为 `fae3721cbe65b9fa09f24972ab36a5c45df54d0a9f97fa7e9d5cb87e619235ce`、大小 `83,036,921` 字节；四个 `best.pt` 的 task、类别顺序、训练配置和 metrics 已校验，导入报告为 `artifacts/phase4/model-import-report.json`，生产副本位于 `/var/lib/substation/models/production/<sha256>/`。安全模型最佳 mAP50 为 `0.69297`，按用户明确要求以 waiver 计入；严格验收仍需重新训练或撤销 waiver。
- 正在运行的项目服务：无。Gazebo、ROS 项目节点、Gateway、前端、Foxglove Bridge 和 Nginx 均未作为产品服务运行。
- 仓库根目录不再保留 `.phase1-run.failed-*.env` 未跟踪文件；原文件已安全移至 `/tmp/phase1-run.failed-a9ab99ee-a85e-4c6f-a9bd-65b421efc8ca.env`（权限 `600`），未写入 Git。

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
| Phase 4 四模型、15 FPS、指标报告 | 四模型已导入，task/类别/训练摘要/指标可追溯；安全 mAP50 低于 0.75，按用户授权 waiver 记录 | 仍需真实四模块 ROS 管线 15 FPS/300 s、meter OpenCV 读数和严格安全指标复验 |
| Phase 5 证据与报告 ROS 服务 | reporting Service、RunContext 时间映射、内容寻址证据、Range、HTML/PDF/evidence/diagnostic 生成、artifact 索引与 Gateway 下载已验证 | 补 rosbag2、告警/轨迹/模型完整快照与正式报告验收 |
| Phase 6 Nav2 巡检执行 | 风险重排、SQLite 恢复、mission/task terminal、Nav2 执行及手动/自动速度仲裁已验证 | 补冷启动 IDLE→START、紧停复位完整 barrier 和正式 live acceptance |
| Phase 7 Gateway 真实控制面 | 权威状态、mission/evidence/reporting、mode/manual/e-stop、精确 TF/odom pose、电量、命令终态、report/diagnostic 索引下载已接入 | 补真实相机帧 |
| Phase 8 浏览器验收 | 八个工作区、契约测试和生产构建通过 | 操作员人工执行 Windows 浏览器验收；真实 Gateway/ROS/Nginx 联调 |
| Phase 9 部署、Windows、Foxglove、演示 | systemd/Nginx/Foxglove 配置和静态契约已提交 | 以 `/opt/substation` release 实测、Windows LAN 验收、只读 Foxglove、900 s 闭环、报告/截图/演示视频 |

用户在 AutoDL 完成 safety、equipment、fault 和 meter 四个独立模型后，按已约定的精简交付把四个训练结果 ZIP 发布到不可变 GitHub release 或固定 commit。本仓库收到后校验权重、训练过程摘要、类别映射和指标，导入生产映射并继续正式模型、仪表 OpenCV 下游和全栈验收。
