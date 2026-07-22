# 测试与验收合同

## 1. 目的、状态与总原则

本文是项目验证方法的唯一入口，固定测试层、命令、输入、阈值、失败判据和证据目录。没有实际命令输出、退出码、日志或产物校验值，不得把功能、阶段或项目标记完成。

当前仓库处于 **Phase 0 文档门槛**：只有第 4 节静态检查可立即运行。第 5 节及之后的命令是后续阶段必须按指定路径实现的验收入口；在对应脚本、功能包、服务、数据和模型尚未创建时，它们是合同而不是当前可运行声明。Phase 0 期间不得为了试跑未来命令而安装依赖、创建 ROS 2 功能包、下载数据/模型、启动 Gazebo/Nav2/Web 服务或修改服务器配置。

所有测试遵循以下规则：

1. 单项通过要求命令退出码为 0、所有硬阈值满足、必需 artifact 存在且 SHA-256 可校验。只满足其中一部分仍为失败。
2. 跳过、`xfail`、重试后隐藏首次失败、缺日志、缺样本、缺指标、人工口头观察或静态推测不得计为通过。允许的跳过必须由阶段计划明确列为不适用，且不能属于本阶段交付范围。
3. 使用 `use_sim_time=true` 的 ROS 节点以 `/clock` 为 ROS 时间；持续时间、超时与性能测量使用单调时钟。测试报告同时记录墙钟 UTC 和 ROS 时间。
4. 自动验收不得向感知链提供 `/simulation/scenario_truth`。真值只用于期望值比较和证据，不得成为被测系统输入。
5. 产品浏览器的状态和控制只经 FastAPI Gateway 的 `/api/v1`、`/ws/telemetry`、`/ws/events`、`/ws/camera`。浏览器不得直连 DDS。Foxglove Web 只经服务器 Foxglove Bridge 进行只读开发诊断，不能发布 Topic、调用 Service 或发送 Action goal，也不能替代产品 UI、Gateway 或证据系统。

## 2. 统一命令与证据约定

除 Phase 0 文档报告外，后续验收先创建唯一证据根目录：

```bash
acceptance_run_id="$(python3 -c 'import uuid; print(uuid.uuid4())')"
acceptance_root="/var/lib/substation/evidence/acceptance/${acceptance_run_id}"
install -d -m 0750 "$acceptance_root"
printf '%s\n' "$acceptance_run_id" > "$acceptance_root/acceptance_run_id.txt"
git rev-parse HEAD > "$acceptance_root/git_commit.txt"
```

每条测试命令必须把 stdout/stderr、开始/结束 UTC、退出码和参数写入对应层目录。层目录固定为：

```text
00-phase0-docs/
01-environment/
02-unit/
03-ros-integration/
04-gazebo-scenarios/
05-navigation-risk/
06-models/
07-gateway/
08-web-e2e/
09-performance/
10-reports/
11-final/
```

最终执行：

```bash
find "$acceptance_root" -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > "$acceptance_root/SHA256SUMS"
sha256sum -c "$acceptance_root/SHA256SUMS"
```

每层的 `result.json` 至少包含 `schema_version`、`acceptance_run_id`、`git_commit`、`started_at`、`completed_at`、`commands`、`exit_codes`、`thresholds`、`measurements`、`artifacts`、`status` 和 `failures`。`status` 只允许 `passed` 或 `failed`；不存在以 `pending` 代替失败的最终记录。

## 3. 测试层总表

| 层 | 当前状态 | 唯一入口 | 核心产物 |
|---|---|---|---|
| Phase 0 文档 | 当前可运行 | 第 4 节列出的 shell 检查 | `.superpowers/sdd/task-4-report.md` 与 Git diff |
| Phase 1 主机/环境 | 未来 Phase 1 | `bash scripts/verify_environment.sh --evidence-dir "$acceptance_root/01-environment"` | 环境 JSON、Debian/Python/npm 清单、GPU/EGL 日志 |
| 单元 | 对应包创建后 | `bash scripts/run_unit_tests.sh --evidence-dir "$acceptance_root/02-unit"` | JUnit、colcon test-result、覆盖率和日志 |
| ROS 集成 | ROS 包创建后 | `bash tests/integration/run_ros_integration.sh --evidence-dir "$acceptance_root/03-ros-integration"` | launch 日志、Topic/QoS/TF/状态机断言、rosbag2 |
| Gazebo 场景 | 世界与场景创建后 | `bash tests/scenarios/run_gazebo_scenarios.sh --evidence-dir "$acceptance_root/04-gazebo-scenarios"` | 场景真值、传感器统计、截图/帧、rosbag2、JUnit |
| 导航/风险闭环 | 风险任务闭环创建后 | `bash tests/scenarios/run_navigation_risk_acceptance.sh --evidence-dir "$acceptance_root/05-navigation-risk" --normal-runs 20` | 20 次运行记录、风险与目标时间线、路径和任务差异 |
| 模型 | 数据/模型就绪后 | `.venv/bin/python scripts/evaluate_models.py --dataset-manifest datasets/manifest.yaml --model-manifest models/manifest.yaml --evidence-dir "$acceptance_root/06-models"` | 指标 JSON、混淆矩阵、逐类指标、FPS、摘要 |
| Gateway | Gateway 创建后 | `.venv-web/bin/python -m pytest tests/integration/gateway -q --junitxml="$acceptance_root/07-gateway/junit.xml" --log-file="$acceptance_root/07-gateway/pytest.log"` | JUnit、OpenAPI、REST/WS transcript、SQLite 检查 |
| Web / Playwright | 前端创建后 | `bash tests/web-e2e/run.sh --base-url http://ros-server/ --evidence-dir "$acceptance_root/08-web-e2e"` | Playwright HTML/JUnit、trace、截图、视频、下载报告 |
| 性能 | 全栈就绪后 | `.venv/bin/python scripts/run_performance_acceptance.py --base-url http://ros-server/ --duration-s 300 --evidence-dir "$acceptance_root/09-performance"` | 原始样本、分位数、FPS、资源曲线和结果 JSON |
| 报告追溯 | 报告链就绪后 | `.venv/bin/python scripts/verify_report_traceability.py --acceptance-root "$acceptance_root" --evidence-dir "$acceptance_root/10-reports"` | 报告/证据包摘要、关联图、rosbag2 metadata |
| 最终验收 | 全部交付完成后 | `bash scripts/run_acceptance.sh --profile final --base-url http://ros-server/ --evidence-dir "$acceptance_root/11-final"` | 汇总 JSON/Markdown、全部层摘要、签名清单 |

未来阶段激活后，入口脚本缺失、不可执行或没有生成规定产物本身就是失败；不得换用临时命令后声称合同入口通过。

## 4. Phase 0 文档门槛（当前可运行）

### 4.1 文件与基线聚焦检查

```bash
test -s docs/VERSION_MATRIX.md
test -s docs/DATA_AND_MODELS.md
test -s docs/TEST_ACCEPTANCE.md
rg -n 'Ubuntu 24.04|ROS 2 Jazzy|Gazebo Harmonic|2.12.1|8.4.104|24.18.0|16.2.11|0.139.2' docs/VERSION_MATRIX.md
rg -n 'c63ed3c7f5ea33ac8e9024c467a70a62b849b2ad|4bf9c31b18fadcd44d5f0b6d66f82bc56fa5e328|CC BY-NC 3.0|2,000|500' docs/DATA_AND_MODELS.md
rg -n '15 FPS|0.75|20|90%|2 seconds|500 ms|1 second|5 seconds' docs/TEST_ACCEPTANCE.md
```

通过：三个文件非空，三个 `rg` 命令均退出 0，且命中内容与根项目计划一致。失败：任一命令非零、版本/数据 revision/许可/样本数/阈值缺失或含义改变。

### 4.2 未填标记、边界与一致性扫描

```bash
scan_pattern='T''BD|T''ODO|F''IXME|X''XX|PLACE''HOLDER|待''定|待''补|以后再''定'
! rg -n -i "$scan_pattern" docs/VERSION_MATRIX.md docs/DATA_AND_MODELS.md docs/TEST_ACCEPTANCE.md
rg -n '/camera/image_raw|/perception/detections|/digital_twin/assets|/risk/assets|/mission/inspection_tasks|/navigate_to_pose|/api/v1|/ws/telemetry|/ws/events|/ws/camera|substation.v1' \
  docs/INTERFACES.md docs/TEST_ACCEPTANCE.md
rg -n 'FastAPI.*Gateway|浏览器不得直连 DDS|Foxglove Web.*只读|不能发布 Topic|不能.*Service|不能.*Action' \
  AGENTS.md docs/ARCHITECTURE.md docs/DEPLOYMENT.md docs/INTERFACES.md docs/TEST_ACCEPTANCE.md
git diff --check
```

通过：未填标记扫描无输出且取反后退出 0；接口名和边界扫描同时覆盖接口合同与本文；`git diff --check` 无输出。未来命令中的环境变量和 schema 元变量是已定义语法，不属于未填写内容。

### 4.3 Phase 0 完成判据

只有以下条件全部满足，最终文档门槛任务才可宣布 Phase 0 通过：AGENTS、README、项目计划、架构、部署、接口、版本、数据/模型、测试、三个 ADR、Phase 1 计划、PROJECT_STATUS 和 HANDOFF 全部存在；链接/路径/命令经复核；无规范冲突；检查输出被记录。Task 4 自身只负责前三份专项规范，不提前创建或更新由最终门槛任务集中维护的状态与交接文档。

## 5. Phase 1 主机与环境验收（未来）

### 5.1 唯一命令

```bash
bash scripts/verify_environment.sh --evidence-dir "$acceptance_root/01-environment"
source /opt/ros/jazzy/setup.bash
colcon build --base-paths ros2_ws/src --build-base build --install-base install --log-base log --event-handlers console_direct+
colcon test --base-paths ros2_ws/src --build-base build --install-base install --log-base log --event-handlers console_direct+ --return-code-on-test-failure
colcon test-result --test-result-base build --all --verbose
```

### 5.2 硬判据

- `/etc/os-release` 为 Ubuntu 24.04；ROS 2 为 Jazzy；Gazebo 为 Harmonic `gz-sim 8.x`；`ros_gz`、Nav2、SLAM Toolbox 和 TurtleBot3 与 [VERSION_MATRIX](VERSION_MATRIX.md) 一致。
- NVIDIA 驱动版本不低于 `560.35.05`；`nvidia-smi` 成功；`.venv` 中 `torch.cuda.is_available() == True`；PyTorch/TorchVision 使用 CUDA 12.6 wheel。
- `colcon build`、`colcon test` 和 `colcon test-result` 均无错误和失败测试。
- 在清除 `DISPLAY` 的会话中 OGRE2/EGL 官方/最小 headless 渲染探针成功；不得安装 Ubuntu Desktop、GNOME/KDE、Xorg、显示管理器、NoMachine、Xvfb 或 VirtualGL。包清单命中任一禁用组件即失败。
- `.venv`、`.venv-web`、`requirements.lock`、`requirements-web.lock`、`package-lock.json` 和 Debian 环境清单的解析版本/摘要一致；禁止全局 `sudo pip` 和额外 CUDA 工具链。
- 项目分区可用空间不少于 80 GiB。16 GiB 内存是目标单机预算；低于该预算时不得声称满足计划资源基线。

必需产物：`environment.json`、`dpkg-packages.tsv`、两个 `pip-freeze.txt`、`node-npm-versions.txt`、`gpu.txt`、`egl.log`、`forbidden-packages.txt`、`disk-memory.txt`、colcon 日志与 `SHA256SUMS`。

## 6. 单元测试（未来）

```bash
bash scripts/run_unit_tests.sh --evidence-dir "$acceptance_root/02-unit"
source /opt/ros/jazzy/setup.bash
colcon test --base-paths ros2_ws/src --build-base build --install-base install --log-base log --event-handlers console_direct+ --return-code-on-test-failure
colcon test-result --test-result-base build --all --verbose
.venv/bin/python -m pytest tests/unit -q --junitxml="$acceptance_root/02-unit/python-junit.xml"
cd web/frontend
npm test -- --run
cd ../..
```

入口脚本必须执行并记录上述 ROS/C++、Python 和 TypeScript 原生命令；Web 的 `test` script 必须使用 `--run` 一次性退出而非 watch 模式。最低必测单元：

- 接口 schema version、UUID、ID 正则、单位、有限数、frame、四元数和 QoS 配置；
- 风险公式 `100 × (0.30V + 0.25T + 0.20S + 0.10G + 0.15C)`、等级边界 `[0,30)`、`[30,60)`、`[60,80)`、`[80,100]`、连续帧确认、滑动平均和滞回；
- 任务优先级公式、稳定排序、冷却、不可达重试/替代观察点/跳过；
- `RunContext` gating、revision 单调性、IDLE 空快照、证据幂等和冲突；
- 手动速度 monotonic deadline、模式仲裁、松键/失焦/断线取消与自动归零；
- Gateway JSON gate 顺序、RFC 8785 摘要、幂等键、错误码、命令状态机、camera 64-byte framing；
- Web snapshot/revision/sequence 恢复、5 秒断线禁控、相机坏帧处理和报告下载 Range；
- 数据 manifest、split 隔离、类别映射、SHA-256 和模型 artifact 晋升。

通过：所有用例通过，0 skipped/xfail（阶段计划明确不适用者除外），JUnit 可解析。覆盖率是诊断指标；根项目计划未授权统一数值门槛，因此不得虚构百分比，但每个上述行为都必须有直接测试。任何关键安全行为只由间接测试覆盖即失败。

## 7. ROS 集成与接口合同（未来）

```bash
bash tests/integration/run_ros_integration.sh --evidence-dir "$acceptance_root/03-ros-integration"
```

测试必须以 `docs/INTERFACES.md` schema 1 为逐字段 oracle，至少验证：

- `/clock`、`/system/run_context`、`/camera/image_raw`、`/camera/camera_info`、`/scan`、`/simulation/environment/temperature_raw`、`/simulation/environment/smoke_raw`、`/simulation/environment/gas_raw`、`/simulation/scenario_truth`、`/perception/safety/detections`、`/perception/equipment/detections`、`/perception/defects/detections`、`/perception/meters/readings`、`/perception/detections`、`/perception/annotated_image`、`/environment/temperature`、`/environment/smoke`、`/environment/gas`、`/digital_twin/assets`、`/risk/assets`、`/risk/alerts`、`/mission/inspection_tasks`、`/map`、`/odom`、`/battery_state`、`/tf`、`/tf_static`、`/plan`、`/local_plan`、`/cmd_vel_nav`、`/cmd_vel_manual`、`/mission/manual_velocity_status`、`/cmd_vel`、`/diagnostics` 和 `/simulation/scenario_state` 的精确类型、发布者唯一性、速率与 QoS；
- `/mission/manage`、`/mission/queue_navigation_goal`、`/mission/emergency_stop`、`/mission/emergency_stop_reset` 和 `/scenario_manager/set_parameters_atomically`；
- `/mission/execute_inspection` 以及标准 `/navigate_to_pose`。Gateway 不得直接调用 `/navigate_to_pose`，Nav2 与 Gateway 都不得直接发布最终 `/cmd_vel`；
- TF 树 `map -> odom -> base_footprint -> base_link -> camera_link -> camera_optical_frame`、`base_link -> laser_frame` 和 `map -> asset/<asset_id>` 的唯一所有者、时间容差与失败降级；
- ACTIVE/ENDING/ENDED/IDLE gating、旧 run/revision 拒绝、源时间戳保留、证据 ID 幂等、QoS late joiner 和进程重启恢复。

接口名、类型、字段、单位、QoS、frame、枚举、错误码、所有权或安全 gating 任一不符即失败。产物包括 `ros-graph.json`、`topic-info/`、`qos.json`、`tf-tree.yaml`、JUnit、launch 日志和覆盖关键转换的 rosbag2。

## 8. Gazebo 无头场景验收（未来）

### 8.1 启动与传感器

```bash
env -u DISPLAY gz sim -s -r --headless-rendering substation_world.sdf
bash tests/scenarios/run_gazebo_scenarios.sh --evidence-dir "$acceptance_root/04-gazebo-scenarios"
```

项目 launch 可替代第一条命令，但必须记录等价的 `headless:=true`、OGRE2/EGL 和无 `DISPLAY` 环境。相机、CameraInfo、LiDAR、温度、烟雾、气体、里程计、时钟和 TF 必须持续发布；相机帧须为 `rgb8`、CameraInfo 同 stamp 且标定非零。任何依赖 X11/虚拟显示、渲染传感器停止、frame/QoS 错误或真值进入感知订阅图均失败。

### 8.2 固定场景集合

| `scenario_id` 类别 | 必验证行为 | 证据 |
|---|---|---|
| normal | 无伪告警；完整传感与基础巡检 | truth、检测、风险、任务、轨迹、rosbag2 |
| PPE | person/hardhat/no_hardhat 独立检测；单帧误检不触发紧急任务 | 原图、带框帧、连续帧和告警时间线 |
| fire-smoke | fire/smoke 连续帧确认并进入风险融合 | 场景参数、检测、风险分量和告警 |
| temperature-high | 温度测量进入数字孪生和风险，不伪装视觉类 | 原始/归一化测量、资产快照、风险 |
| gas-high | gas ppm 进入数字孪生和风险 | 原始/归一化测量、资产快照、风险 |
| meter-limit | 仅 Gazebo 生成仪表输入，读数、单位和 evidence_id 正确 | 自动真值、读数、误差和证据帧 |
| unreachable | 合法不可达目标触发重试、替代观察点或跳过并记录原因 | Nav2 结果、任务 revision、报告原因 |

场景命令必须经产品 Gateway 的 `POST /api/v1/simulation/scenario`，并由 `/simulation/scenario_state` 中 matching `command_id` 确认；测试工具不得直接写感知 Topic 绕过产品链。

## 9. 导航与风险闭环（未来）

```bash
bash tests/scenarios/run_navigation_risk_acceptance.sh \
  --evidence-dir "$acceptance_root/05-navigation-risk" \
  --normal-runs 20
```

硬阈值与失败判据：

- 正常场景必须恰好执行 **20** 次独立巡检，成功率不低于 **90%**，即至少 18/20 成功。少于 20 次、分母排除失败 run 或重用同一 run_id 均失败。
- 验收观察器首次收到风险达到 60 分的样本，到任务队列优先级更新并向 Nav2 提交新合法目标，两项的单调时钟延迟都必须在 **2 seconds** 内；相应 ROS stamp 的 `/clock` 差值也不得超过 2 秒。只改变 Web 颜色、只重排队列未提交目标或只提交目标未保存 revision 均失败。
- 新目标必须在 `map` 内、可通行、不在设备膨胀碰撞体或危险区内，并使用配置的安全观察距离。紧急风险可取消普通目标；普通目标不得抢占紧急任务。
- 不可达目标必须执行配置允许的重试、替代观察点或跳过，且稳定错误码/原因进入任务快照和最终报告。
- 每个 run 保存风险阈值 crossing、`risk_revision`、`queue_revision`、Nav2 goal/结果、路径、TF、任务状态和 rosbag2；缺任一关联字段即失败。

## 10. 模型与数据验收（未来）

```bash
.venv/bin/python scripts/verify_data_and_models.py \
  --dataset-manifest datasets/manifest.yaml \
  --model-manifest models/manifest.yaml \
  --data-root /var/lib/substation/datasets \
  --model-root /var/lib/substation/models \
  --report "$acceptance_root/06-models/governance.json"
.venv/bin/python scripts/evaluate_models.py \
  --dataset-manifest datasets/manifest.yaml \
  --model-manifest models/manifest.yaml \
  --evidence-dir "$acceptance_root/06-models"
```

硬门槛：

- 仪表合成图至少 2,000 张；每个启用的合成异常类至少 500 张；split、许可、revision、类别映射和逐文件 SHA-256 完整。
- 安全与设备模型在各自冻结公开 test split 上总体 `mAP50 >= 0.75`，并报告所有类别 AP。未报告某类即失败，不以总体均值掩盖。
- 缺陷模型必须报告 Balanced Accuracy、逐类召回率和混淆矩阵；仪表模块必须报告定位 AP、有效读数率、绝对误差分布与分组结果。项目计划未给这两类数值下限，故不虚构阈值；缺指标、非有限值、数据泄漏或类别不一致仍失败。
- 三个视觉模型和仪表后处理独立加载、独立输出、独立评估。任一合并模型替代多个模块即失败。
- 640×640 输入下，服务器端从 ROS 图像订阅、预处理、推理、后处理到 ROS 检测发布的完整管线稳定吞吐至少 **15 FPS**。测量持续 300 秒，报告总帧、丢帧和 P50/P95 处理延迟；预先读取图片的裸模型 benchmark 不计入该阈值。
- 每个模型文件、基础 `yolo11n.pt`、metrics、训练配置和数据 manifest 的 SHA-256 匹配；每条检测可追溯到图像、ROS 时间戳、模型/数据版本和 evidence_id。

## 11. Gateway、REST 与 WebSocket 合同（未来）

```bash
.venv-web/bin/python -m pytest tests/integration/gateway -q \
  --junitxml="$acceptance_root/07-gateway/junit.xml" \
  --log-file="$acceptance_root/07-gateway/pytest.log"
.venv-web/bin/python scripts/export_openapi.py \
  --output "$acceptance_root/07-gateway/openapi.json"
```

### 11.1 REST

必须覆盖 `/healthz`、`/readyz`、全部 `/api/v1` 快照、mission 控制、导航、手动速度、紧停/复位、场景、命令查询和报告 Range 下载。验证媒体类型/64 KiB/JSON/Idempotency-Key gate 顺序、RFC 8785 同请求重放、RFC 7807、ETag、revision、稳定排序、未知字段拒绝及 SQLite 持久化顺序。

所有合法控制请求必须在 **1 second** 内返回 `command_id` 和受理结果；这只证明受理，不得当成业务成功。endpoint 权威终态和超时固定为：mission start 30 s，pause/resume/stop 各 10 s，return-home 300 s，navigation goal 300 s，manual velocity 1 s，emergency stop 2 s，reset 5 s，scenario 30 s。提前凭 ROS accepted/HTTP 202 标记 succeeded、超时后改写 terminal 或不匹配 command/revision 终结命令均失败。

### 11.2 WebSocket

- 只接受子协议 `substation.v1`，否则 HTTP 426；文本外壳字段、RFC 3339 UTC、sequence、stream_epoch、snapshot_revision 和 replay 与 [INTERFACES](INTERFACES.md) 一致。
- 应用 heartbeat 每 1 秒、protocol Ping 每 2 秒。客户端在最后一条合法应用消息后恰好 5 秒时可保持当前状态，但一旦单调时钟超过 **5 seconds** 必须禁用除紧急停止外的普通控制、选择/发送零手动速度并开始重连；服务器超过 10 秒无 Pong 关闭 1001。
- telemetry 缺口执行四个 REST 快照后重连；events 在窗口内 replay，超窗发 `WS_RESYNC_REQUIRED` 并 4009 关闭；camera 不 replay。
- camera 固定 64-byte header、`SSCF` magic、big-endian、JPEG 长度/尺寸/SOI/EOI 校验；连续 3 个坏帧关闭 1003 并产生 `CAMERA_FRAME_INVALID`。
- 积压时只保留每个 telemetry type 最新值和最新 camera 帧，事件必须先持久化；视频积压不得延迟紧停和基础控制。

### 11.3 安全与边界

Gateway/前端只监听回环地址，Nginx 是 LAN 唯一产品入口。浏览器网络记录中不得出现 DDS 或直接 ROS Service/Action/Topic 连接。Foxglove Bridge 关闭发布、Service 调用和 Action goal 能力；以下未来检查必须通过：

```bash
bash scripts/verify_network_boundaries.sh --base-url http://ros-server/ --evidence-dir "$acceptance_root/07-gateway"
bash scripts/verify_foxglove_read_only.sh --evidence-dir "$acceptance_root/07-gateway"
```

Foxglove 不可用不影响产品验收；但最终交付必须至少完成一次地图、TF、路径和 `/diagnostics` 的只读显示验证。任何通过 Foxglove 发布命令/Topic、浏览器直连 DDS 或把 Foxglove 当控制恢复路径的配置均为失败。

## 12. Web 构建与 Playwright E2E（未来）

```bash
cd web/frontend
npm ci
npm run build
cd ../..
bash tests/web-e2e/run.sh \
  --base-url http://ros-server/ \
  --evidence-dir "$acceptance_root/08-web-e2e"
```

一台未安装 ROS、Gazebo、Python 和 Node.js 的 Windows 客户端必须只访问 `http://ros-server/` 完成日常功能。Playwright 至少覆盖：

- 综合驾驶舱、三维孪生、感知、任务、风险、场景、报告和系统状态八个页面打开且无致命 console/page error；
- 启动、暂停、继续巡检，地图设点，场景触发，紧急停止、显式复位和报告下载；
- 202 只显示 accepted/executing，随后依据 `/ws/events` 或命令查询显示 terminal；失败/超时可追溯；
- WebSocket 断线超过 5 seconds 后普通控制禁用，REST 四快照恢复后再续流；紧急停止 HTTP 按钮不依赖 WebSocket；
- 手动控制松键、窗口失焦或断线立即选择零速度；紧急停止取消 Nav2、最终 `/cmd_vel` 为零并保持锁存，复位后不自动恢复旧任务/速度；
- camera 坏帧、连接重启、sequence 缺口、stale pose、依赖降级和报告 Range 下载；
- 浏览器只连接 Nginx 产品地址；不得直连 `127.0.0.1:8000`、`127.0.0.1:3000` 或 DDS。

`npm ci`、生产构建或任一 Playwright 用例失败，八页缺页，关键流程只用 mock 而未经过真实 Gateway/ROS 集成，或缺 trace/截图/下载文件摘要，均失败。单元组件测试可 mock；最终 E2E 不可用 mock 替代系统闭环。

## 13. 性能与资源验收（未来）

```bash
.venv/bin/python scripts/run_performance_acceptance.py \
  --base-url http://ros-server/ \
  --duration-s 300 \
  --evidence-dir "$acceptance_root/09-performance"
```

在 Gazebo、ROS 核心、推理、Gateway、前端和 Nginx 同时运行、局域网 Windows 浏览器实际订阅的条件下测量 300 秒：

| 指标 | 硬阈值 | 起止点 |
|---|---:|---|
| 完整 ROS 图像推理管线 | 至少 15 FPS | `/camera/image_raw` 采集到 `/perception/detections` 发布 |
| 位姿/任务/风险浏览器更新 | P95 不超过 **500 ms** | 服务器源 ROS 时间对应事件到浏览器状态提交 |
| 带框视频端到端 | P95 不超过 **1 second** | 图像采集到浏览器完成该 JPEG 帧解码/绘制 |
| 控制同步受理 | P95 且每个样本不超过 **1 second** | 浏览器发出请求到收到 command_id/accepted 或同步拒绝 |
| WebSocket 失联禁控 | 单调时间超过 **5 seconds** 即禁用 | 最后一条合法应用消息到 UI 状态转换 |

样本数少于 100、测试不足 300 秒、排除失败/超时样本、使用服务器与浏览器未同步的墙钟直接相减、只报告平均值、训练与验收同时争用 GPU、或任一阈值超限均失败。保存原始 CSV/JSON、时钟映射、P50/P95/P99、CPU/内存/GPU/显存/磁盘曲线和服务日志。视频可在拥塞时降至 10～15 FPS，但不得影响事件、紧停或基础控制；降帧不能用于掩盖完整 ROS 推理管线低于 15 FPS。

## 14. 报告、证据与追溯验收（未来）

```bash
.venv/bin/python scripts/verify_report_traceability.py \
  --acceptance-root "$acceptance_root" \
  --evidence-dir "$acceptance_root/10-reports"
```

每个验收 run 的 `run_id` 必须由 `substation_mission` 的 `/system/run_context` 唯一生成，并贯穿任务、风险、证据、rosbag2、报告和 Web 快照。最终报告至少包含：巡检轨迹、设备状态、最高风险、告警证据、任务变更、不可达原因、模型 artifact SHA-256、数据 manifest SHA-256、Git commit、接口 schema、ROS/UTC 时间映射和 rosbag2 URI/metadata。

校验必须从报告中的每个 `evidence_id` 反查不可变文件和 content SHA-256，从任务/告警反查 ROS 时间线，从生产模型反查训练/数据/环境 manifest；HTML、PDF 和 evidence ZIP 的摘要必须与 `GET /api/v1/reports` 及下载 header 一致。断链、重复 ID 对应不同内容、旧 run 混入、新生成报告缺 rosbag2、摘要不符或 Range 返回错误字节均失败。

## 15. 最终项目验收（未来）

```bash
bash scripts/run_acceptance.sh \
  --profile final \
  --base-url http://ros-server/ \
  --evidence-dir "$acceptance_root/11-final"
```

最终入口必须汇总而不是替代前述层。项目仅在以下条件同时满足时通过：

1. Phase 0 文档门槛和一台新 Ubuntu 24.04 服务器重建均有记录；版本、锁文件、manifest 与清单一致。
2. Gazebo Harmonic OGRE2/EGL 无头、ROS 2 Jazzy、YOLO11n、风险融合、任务管理和 Nav2 构成实际闭环；高风险在 2 seconds 内改变优先级并提交新合法目标。
3. 20 次正常巡检至少 18 次成功，安全/设备 mAP50、15 FPS 和 Web 性能硬阈值全部满足。
4. Windows 只通过 `http://ros-server/` 完成八页日常功能和全部指定控制；浏览器不直连 DDS，全部产品状态/命令经过 Gateway。
5. Three.js Web 孪生、二维地图、带框画面与风险共享同一运行时间线；断线、手动 deadman、紧停锁存和恢复通过真实 E2E。
6. 自研 Web、Foxglove Web 只读诊断和无 `DISPLAY` Gazebo 各至少有一次实际验证。Foxglove 不能发布 Topic、调用 Service/Action 或承担产品控制。
7. 每个结果可追溯到版本、时间戳、数据/模型 SHA-256、rosbag2、证据和报告；全部交付物、链接、命令、版本和路径复核，无未填写标记。
8. 汇总 `result.json` 为 `passed`，所有子层为 `passed`，`SHA256SUMS` 全部校验成功。任一子层失败、缺失、过期于被验收 Git commit 或由不同锁定环境产生，最终状态必须为 `failed`。
