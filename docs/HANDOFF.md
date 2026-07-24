# 工作交接与恢复入口

## 当前恢复快照

### 最新恢复重点（2026-07-24）

- 训练 run 的 GitHub 归档路径固定为 `artifacts/phase4/substation_yolo_runs.zip`；其 SHA-256 为 `fae3721cbe65b9fa09f24972ab36a5c45df54d0a9f97fa7e9d5cb87e619235ce`。不展开提交 run 目录。
- 生产感知已经修复 release merged-install 路径解析；本地 overlay 和 immutable release 均会找到当前 release 内的 `.venv/bin/python`。
- `scripts/deployment/install_release.sh` 现在会把 `substation` 加入 `render`/`video` 组。root 安装前不要把 systemd 生产部署写成完成。
- 最新开发探针证明：相机和四模块输出真实存在；当前未安装 release，因此 15 FPS/300 秒正式证据仍为空，不能用短时开发探针替代。

- Repository：`/home/jackeyliu37/substation-inspection-digital-twin`。
- Branch：`main`。
- 当前阶段：Phase 9 集成收口。Phase 4 四个用户训练 artifact 已导入；上传 ZIP、模型哈希、训练 metrics 和已接受的 safety waiver 记录在 `artifacts/phase4/` 与 `models/manifest.yaml`。操作员决定不重新训练，生产感知、仪表、release、报告和安全边界验收正在落实。
- Phase 5～6 live acceptance：`passed`；实现提交 `7b7ffc4`，run ID `2f9e16bc-0ce8-4025-a50c-195998fac49f`，immutable evidence `/var/lib/substation/evidence/acceptance/2f9e16bc-0ce8-4025-a50c-195998fac49f/05-risk-mission`。复核命令为 `(cd /var/lib/substation/evidence/acceptance/2f9e16bc-0ce8-4025-a50c-195998fac49f/05-risk-mission && sha256sum -c SHA256SUMS)`。
- Phase 7 Gateway ROS 适配检查点：`82d70fc`。独立 rclpy executor 已接权威 RunContext、数字孪生、风险、任务、地图/增量、diagnostics 和 reporting readiness；严格同 run/revision gate、时间映射、幂等 Web revision、mission Service 受理 gate 及 evidence metadata/Range 下载已通过真实 rclpy 与 ASGI 测试。安装后进程 smoke 为 `/healthz=200`、缺 ROS 图 `/readyz=503`，SIGINT 正常退出且无残留。
- Phase 8 前端检查点：`ec927c1`（基于 `df30574`）。本轮 `npm test` 与 `npm run build` 均退出码 0；按操作员决定改用 Windows 浏览器人工验收，不把 Playwright 作为交付前置条件。
- Phase 9 部署检查点：Gateway/接口/部署回归本轮 `49 passed`，documentation gate `PASS`；Nginx 片段经临时完整配置包装后 `nginx -t` 成功。immutable release 构建与五服务依赖已完成；尚未启动产品服务，root 安装、Windows LAN、Foxglove 和人工 Web 验收仍待现场执行。
- Phase 6 任务持久化检查点：`e73f60a`。`mission.sqlite3` 由任务管理器单写，保存任务队列、机器人模式、state/queue/latch revisions 和紧急停止锁存；同 run 恢复快照，新 run 不会隐式解除锁存。
- Phase 6 Nav2 执行链检查点：`bea53a7`。任务管理器是 `/mission/execute_inspection` 客户端，巡检执行器是其 Action server 和标准 `/navigate_to_pose` 唯一项目客户端；真实 rclpy 集成测试覆盖完整队列、风险重排目标替换、不可达策略和紧停取消。
- Phase 6 mission 生命周期检查点：`19a983d`。`/mission/manage` pause/resume/stop 与 stop 后 start 已接通；Action feedback/result 回写 task/mission terminal、RunContext 和 SQLite，风险重排不会重跑 terminal task。Gateway 只有在 matching transition_command_id 权威快照后才把 command 标为 succeeded。
- Phase 6 速度仲裁检查点：`4268803` + production integration closure。任务模块单写最终 `/cmd_vel`，在 autonomous/manual 间严格选择 Nav2 或带 RunContext 的手动命令；monotonic deadline、限速、锁存、frame、去重、ACCEPTED→APPLIED、IDLE→START 和 0.5 s/无活动 goal motion barrier 均已实现并测试。
- Phase 7 Gateway 控制面检查点：`c78f1ad`。mode/manual-velocity/emergency-stop/reset REST 已接入 ROS；紧停路径独立于 readiness，manual 仅发送带 run/context 的 `ManualVelocityCommand`，输入校验和幂等已通过。
- Phase 7 Gateway 机器人状态检查点：`e0578d0` + production perception closure。`/odom` 按消息 stamp 精确查询 `map←odom`，合法四元数/位姿/速度映射到 `/api/v1/robot/state`；`/battery_state` 由 0～1 转换为百分数，mission 模式/锁存/active task 同步进入快照。0.5 秒 stale 使用 ROS time，普通手动移动在 HTTP 和 ROS 发布边界双重 fail-closed；真实相机 JPEG 与四模块生产 Topic 已接入并有聚焦测试。
- Phase 7 Gateway 命令终态检查点：`db2b089`。CommandStore 保存受理 payload/Service 最小 revision；mission transition、mode/e-stop latch、ManualVelocityStatus terminal 和固定 timeout 均写入不可逆命令终态。`command.status` 在 SQLite 提交后进入事件流，`/ws/events` 可重放；ROS 终态先于 HTTP 记录的竞态由缓存/回放处理。Gateway/部署/接口回归 `41 passed`，ROS workspace `174` 项全绿。
- reporting index 检查点：`EvidenceStore.list_evidence`、schema 1 `/reporting/list_reporting_artifacts` 及 Gateway report/diagnostic 索引已接入。Gateway 通过 reporting Service 读取 canonical entries，按 group/format 生成列表，并把下载复用 evidence 的 Range、ETag、SHA-256 和 200/206/304/400/416 语义；不直接读文件或 SQLite。report generator metadata 已带 group/format/run/mission/created_at。
- 当前 reporting 增量验证：reporting tests `18 passed`、Gateway tests `42 passed`；完整 workspace、部署/接口 contract 与 documentation gate 在提交前复跑。
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
- Phase 4 导入摘要：archive SHA-256 `fae3721cbe65b9fa09f24972ab36a5c45df54d0a9f97fa7e9d5cb87e619235ce`；safety/equipment/fault/meter 最佳指标分别为 `0.69297/0.84187/0.99673/0.99500`。安全指标低于文档阈值，按用户明确要求记录 operator-approved waiver，不应在后续报告中隐去。
- 当前运行的项目服务：无；所有开发探针均已清理项目进程。
- 根目录未跟踪的 `.phase1-run.failed-*.env` 已移出仓库并保留在 `/tmp/phase1-run.failed-a9ab99ee-a85e-4c6f-a9bd-65b421efc8ca.env`，权限 `600`；恢复入口不依赖该文件。

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
- 任务持久化验证命令：`source /opt/ros/jazzy/setup.bash && colcon build --symlink-install --packages-select substation_mission && colcon test --packages-select substation_mission --event-handlers console_direct+ && colcon test-result --test-result-base build/substation_mission --all --verbose`，结果为 `11 tests, 0 errors, 0 failures, 0 skipped`。SIGTERM smoke 必须直接 timeout `install/substation_mission/lib/substation_mission/task_manager`；不要 timeout `ros2 run` 包装进程，否则包装层退出后可能短暂留下子节点。
- Nav2 执行链最新验证命令：`source /opt/ros/jazzy/setup.bash && colcon build --symlink-install && colcon test --event-handlers console_direct+ && colcon test-result --all --verbose && python3 -m pytest tests/phase5_6/test_interfaces_contract.py -q`，结果为 ROS workspace `153 tests, 0 errors, 0 failures, 0 skipped` 和顶层 `2 passed`。`inspection_executor` 单节点 smoke 还确认 Action 类型为 `substation_interfaces/action/ExecuteInspection`、日志无 `Traceback/ERROR/FATAL/RCLError` 且无残留进程。
- reporting 最新验证命令：`source /opt/ros/jazzy/setup.bash && colcon build --symlink-install && colcon test --event-handlers console_direct+ && colcon test-result --all --verbose && python3 -m pytest tests/phase5_6/test_interfaces_contract.py -q && bash scripts/verify_documentation_gate.sh`，结果为 ROS workspace `164 tests, 0 errors, 0 failures, 0 skipped`、顶层 `2 passed` 和 documentation gate `PASS`。直接启动两个安装后节点的 smoke 确认 9 个 `/reporting/*` Service 全部出现、日志无 `Traceback/ERROR/FATAL/RCLError` 且无残留进程；不要用外层 `ros2 launch` PID 代替两个节点 PID 做 smoke 清理。
- Gateway ROS 适配验证命令：`source /opt/ros/jazzy/setup.bash && source install/setup.bash && colcon build --symlink-install && colcon test --event-handlers console_direct+ && colcon test-result --all --verbose && .venv-web/bin/python -m pytest tests/gateway tests/integration/test_deployment_contract.py tests/phase5_6/test_interfaces_contract.py -q && bash scripts/verify_documentation_gate.sh`，结果为 ROS workspace `174 tests, 0 errors, 0 failures, 0 skipped`、顶层 `41 passed` 和 documentation gate `PASS`。安装后 Gateway smoke 另确认私有 executor 启动、health 200、无权威图 ready 503、正常 shutdown 且无残留；机器人状态与命令终态集成测试另确认真实 TF/odom/battery、mission/manual terminal 可进入 ASGI/WS。
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
- 下一实现动作：root 安装最新 immutable release 后执行 300 秒/15 FPS 生产验收，封存 rosbag2/report bundle 并启动五服务联调；浏览器部分由操作员人工验收，训练 run 固定归档在 `artifacts/phase4/substation_yolo_runs.zip`。
