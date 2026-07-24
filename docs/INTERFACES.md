# ROS、TF、REST 与 WebSocket 接口契约

## 1. 范围与不变边界

本文固定 ROS 2 Topic/Service/Action、TF、FastAPI REST 和 WebSocket 的跨组件契约。组件状态所有权遵循 [ARCHITECTURE](ARCHITECTURE.md)：数字孪生唯一拥有资产语义状态，风险模块唯一拥有风险分数与等级，任务模块唯一拥有任务队列、机器人模式、紧急停止锁存和 Nav2 目标，Gateway 只做适配、校验、限频、命令跟踪与 Web 编码。

产品浏览器只调用 Nginx 代理的 `/api/` 和 `/ws/`；它不连接 ROS DDS，不发布 Topic，也不直接调用 ROS Service/Action。Foxglove Web 仅通过服务器 Foxglove Bridge 订阅 ROS 诊断数据，是与本文产品 API 分离的只读开发诊断旁路；Bridge 和浏览器均不得发布 Topic、调用控制 Service/Action，且 Foxglove 不得成为操作员入口、命令恢复通道或证据系统。

项目计划要求优先使用标准接口。因此图像、激光、检测、导航、环境测量、数字孪生快照和诊断复用标准消息；`substation_interfaces` 只包含第 4 节列出的风险、巡检任务、跨模块运行上下文及任务安全控制接口，不为感知或数字孪生另建专有载荷。Gazebo 场景控制复用标准参数服务，不另建场景自定义消息。

## 2. 跨接口基础规则

### 2.1 名称与标识符

| 名称 | 格式与所有权 |
|---|---|
| `run_id` | `substation_mission` 任务管理器在一次 operational run 开始时生成的 UUID，并通过 `/system/run_context` 唯一发布；同一证据链、rosbag2、报告和 Web 快照共享该值。Gateway 和其他节点不得生成、替换或猜测 operational run_id。空字符串只允许出现在本文明确规定的 IDLE/no-run 完整状态快照中。 |
| `mission_id` | 任务模块生成的 UUID；一轮任务队列一个值。 |
| `task_id` | 任务模块生成的 UUID；任务重排不改变已有任务的值，创建替代任务时生成新值。 |
| `command_id` | Gateway 在媒体类型、大小、JSON 语法和 Idempotency-Key gate 全部通过后，为每个控制尝试生成的 UUID，包括之后被业务校验拒绝的请求；用于 REST 查询和事件关联。 |
| `alert_id` | 风险模块生成的 UUID；一次从较低等级进入告警/紧急等级的事件一个值，清除事件引用同一值。 |
| `evidence_id` | 产出不可变证据内容的源节点生成的 UUID；每个冻结帧、检测裁剪或其他证据对象一个值。证据存储按调用方提供的 ID 幂等持久化，不垄断 ID 分配。 |
| `asset_id` | `substation_description` 配置拥有的稳定字符串；正则为 `^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$`，长度 1～64，同一站点永久不复用。 |
| `route_id`、`scenario_id`、`sensor_id` | 配置拥有的稳定字符串，使用与 `asset_id` 相同的正则和长度规则。 |
| `report_id` | 报告模块生成的 UUID。 |

所有 UUID 在 ROS 自定义字段和 Web JSON 中均使用小写、带连字符的 RFC 4122/9562 规范字符串 `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`；生成方使用随机 UUIDv4。接收方不得依赖 UUID 的排序含义。ROS Topic、Service、Action 和 TF frame 使用本文件的绝对名称；ROS 消息内的 `frame_id` 不以 `/` 开头。

### 2.2 时间、时钟与排序

- ROS 内全部时间字段使用 `builtin_interfaces/Time` 或 `std_msgs/Header.stamp`，并在仿真运行中统一设置 `use_sim_time=true`，以 `/clock` 为唯一 ROS 时间源。传感器消息使用采集时间，派生消息使用计算所依据的最新输入时间；不得用发布时刻覆盖源时间。
- Gateway 在首次观察到任务管理器发布的 ACTIVE `RunContext` 后，必须调用 `substation_reporting/evidence_store` 的 `/reporting/record_run_time_mapping`，以原子持久化 `(run_id, context_revision, anchor_ros_sec, anchor_ros_nanosec, anchor_utc)`；`anchor_ros_*` 是该 Gateway 回调所见的 `RunContext.header.stamp`，`anchor_utc` 是同一回调以 UTC 读取的墙钟。一个 run 只能有一个映射：重复相同值是幂等成功，不同值返回 `TIME_MAPPING_CONFLICT`。Gateway 重启时必须先经 `/reporting/query_run_time_mapping` 取回该记录，缺记录时不得把当前墙钟伪装为历史时间，而应使依赖该转换的快照/证据请求返回 `TIME_MAPPING_UNAVAILABLE`。同一 run 内 ROS 时间到 UTC 的唯一换算是 `anchor_utc + (source_ros_time - anchor_ros_time)`；仿真 ROS 时间倒退、跨 run 或缺失映射均不能换算。Web 中所有名称以 `_at` 结尾的时间均是 RFC 3339 UTC 字符串，固定六位小数和 `Z`，例如 `2026-07-22T14:03:05.123456Z`。若需要审计原始 ROS 时间，另给 `source_ros_time: {"sec": int32, "nanosec": uint32}`，它不是 Web 业务排序主键。
- 同一 ROS 发布者不得倒退消息时间；同一 Web 流以 `stream_epoch` 加 `sequence` 排序，不能用墙钟时间替代序号。系统墙钟回拨不改变已分配的 `sequence` 或 `snapshot_revision`。
- `duration`、超时和速率使用单调时钟计算。零值 ROS 时间只表示“未发生/不适用”，不得表示当前时间。

### 2.3 单位与数值范围

默认使用 SI：位置/距离为 m，线速度为 m/s，角度为 rad，角速度为 rad/s，持续时间为 s，压力为 Pa。例外只有温度 `°C`、气体浓度 `ppm`、名称明确以 `_percent` 结尾的 0～100 百分数，以及名称明确以 `_0_1`/`_0_100` 结尾的闭区间归一化值。检测置信度和风险公式的 `V/T/S/G/C` 分量使用 0～1，最终风险分数使用 0～100，模拟电量使用 0～100 percent。文件/内存/帧长度属于数字计数，统一使用 byte 并以 `_bytes` 或 framing 表中的 byte offset/length 明示。

所有浮点输入必须有限，禁止 `NaN` 和正负无穷。Web 中二维导航姿态以 `x_m`、`y_m`、`yaw_rad` 表示；ROS 中使用标准 pose/quaternion，四元数范数必须在 `[0.999, 1.001]`，否则拒绝。角度规范化到 `[-pi, pi]`。

### 2.4 版本规则

- REST 的破坏性版本由路径 `/api/v1` 固定；Web JSON 的 `schema_version` 初值为字符串 `"1.0"`。同一主版本只能新增可选字段或新事件类型，不能删除字段、改变单位、缩窄既有合法范围或复用枚举值。客户端必须拒绝未知主版本，可忽略同一主版本的未知字段。
- WebSocket 子协议固定为 `substation.v1`。握手未协商该子协议时，服务器返回 HTTP 426；消息仍携带 `schema_version`，以便存档和离线验证。
- `substation_interfaces` 每个自定义定义包含 `SCHEMA_VERSION=1` 和实例字段 `schema_version`。发布者必须写 `1`，消费者遇到其他值必须拒绝该样本并上报 `INTERFACE_VERSION_UNSUPPORTED`。
- ROS 自定义定义一经进入验收基线不得原地做破坏性修改。破坏性变化必须先按项目规则新增 ADR，再创建 `V2` 类型和新 Topic/Service/Action 名称；不得在相同 ROS 类型名下悄然改变字段语义。
- 枚举值只追加不复用。持久化记录同时保存 Git commit、Web `schema_version`、ROS `schema_version` 和配置/模型校验值。

### 2.5 快照修订号

Gateway 为每个权威 `run_id` 维护单调递增的无符号 64 位 `snapshot_revision`。任何会改变 `/api/v1/system/status`、`/api/v1/robot/state`、`/api/v1/assets` 或 `/api/v1/missions/current` 聚合结果的提交只增加一次修订号；同一原子提交产生的多个快照使用同一值。新 `run_id` 可从 1 重新开始，因此比较键是 `(run_id, snapshot_revision)`；无 run 时使用 `(null, system_snapshot_revision)`，该系统 revision 不能冒充 RunContext revision。

所有快照 REST 响应使用第 7.1 节的统一外壳，并返回弱 ETag `W/"<run_id-or-none>:<snapshot_revision>"`。匹配的 `If-None-Match` 返回 304 且无响应体。WebSocket 数据消息携带它所基于的 `snapshot_revision`；客户端发现 run 变化、修订号倒退或不可恢复的序号缺口时，必须重新读取 REST 快照，而不是猜测差量。

### 2.5.1 Web 中的 `uint64` 编码

ROS `uint64` 绝不能以 JSON number 传给浏览器，以免 JavaScript 精度丢失。REST、WebSocket 文本 envelope、WebSocket camera metadata、RFC 7807 `violations` 和 JSON 请求体中的每一个 ROS `uint64`，以及 Gateway 自己的 `snapshot_revision`、`map_revision`、事件 `sequence` 和二进制 header 对应的 JSON 镜像值，都使用十进制字符串。合法语法为 `^(0|[1-9][0-9]{0,19})$`，并且实现必须在 uint64 范围 `[0,18446744073709551615]` 内解析；禁止前导 `+`、前导零、空白、小数、指数或负数。该规则覆盖 `context_revision`、`state_revision`、`queue_revision`、`risk_revision`、`alert_revision`、`emergency_stop_latch_revision`、`snapshot_revision`、`map_revision`、`scenario_revision`、`sequence`、`after_sequence`、二进制 camera `sequence`/`snapshot_revision` 的 metadata 副本及所有 `*_revision` 新字段。二进制 camera 64-byte header 继续是网络序 uint64，不改为文本。`uint32` 计数、ROS `Time.sec` 和 `Time.nanosec` 保持 JSON number。

### 2.6 ROS 枚举到 Web 字符串

Gateway 只做下表无损映射，不自行推导状态。未知 ROS 枚举不得映射为 normal/idle，而应拒绝该样本并上报 `INTERFACE_VERSION_UNSUPPORTED`。

| 语义 | ROS uint8 → Web string |
|---|---|
| RunContext 生命周期 | `0 → idle`，`1 → starting`，`2 → active`，`3 → ending`，`4 → ended` |
| 风险等级 | `0 → normal`，`1 → attention`，`2 → alert`，`3 → emergency` |
| 风险事件 | `0 → opened`，`1 → level_changed`，`2 → cleared` |
| Mission 状态 | `0 → idle`，`1 → ready`，`2 → running`，`3 → paused`，`4 → stopping`，`5 → succeeded`，`6 → failed`，`7 → stopped` |
| 机器人模式 | `0 → autonomous`，`1 → manual`，`2 → estop` |
| 任务类型 | `0 → inspect_asset`，`1 → navigation_goal`，`2 → return_home` |
| 任务状态 | `0 → queued`，`1 → active`，`2 → succeeded`，`3 → skipped`，`4 → failed`，`5 → cancelled` |
| 数字孪生资产状态 | `DiagnosticStatus.level 0 → normal`，`1 → attention`，`2 → fault`，`3 → stale` |
| 巡检 Action 结果 | `0 → succeeded`，`1 → stopped`，`2 → failed`，`3 → cancelled` |

## 3. ROS 2 接口

### 3.1 QoS 配置文件

下表中的 QoS 均固定 history、depth、reliability 和 durability；未列出的 deadline/lifespan 表示未设置，liveliness 均为 `AUTOMATIC`。

| 名称 | History / depth | Reliability | Durability | 额外约束 |
|---|---|---|---|---|
| `Q_CLOCK` | `KEEP_LAST / 1` | `BEST_EFFORT` | `VOLATILE` | 只用于 `/clock`。 |
| `Q_IMAGE` | `KEEP_LAST / 2` | `BEST_EFFORT` | `VOLATILE` | 允许丢旧帧，不积压图像。 |
| `Q_SENSOR` | `KEEP_LAST / 5` | `BEST_EFFORT` | `VOLATILE` | 激光和高频原始测量。 |
| `Q_STREAM` | `KEEP_LAST / 10` | `RELIABLE` | `VOLATILE` | 派生流式状态。 |
| `Q_STATE` | `KEEP_LAST / 1` | `RELIABLE` | `TRANSIENT_LOCAL` | 最新完整快照；新订阅者立即取得一份。 |
| `Q_EVENT` | `KEEP_LAST / 100` | `RELIABLE` | `VOLATILE` | 事件必须由证据存储另行持久化；DDS depth 不是历史库。 |
| `Q_CONTROL` | `KEEP_LAST / 1` | `RELIABLE` | `VOLATILE` | deadline 0.1 s，lifespan 0.25 s；lifespan 只限制 DDS 交付前的运输陈旧度，手动命令执行时限严格使用仲裁器进程单调时钟。 |
| `Q_TF_DYNAMIC` | `KEEP_LAST / 100` | `RELIABLE` | `VOLATILE` | 与 tf2 动态广播/监听配置一致。 |
| `Q_TF_STATIC` | `KEEP_LAST / 1` | `RELIABLE` | `TRANSIENT_LOCAL` | 与 tf2 静态广播/监听配置一致。 |
| `Q_MAP` | `KEEP_LAST / 1` | `RELIABLE` | `TRANSIENT_LOCAL` | 完整占据地图。 |
| `Q_DIAGNOSTIC` | `KEEP_LAST / 10` | `RELIABLE` | `VOLATILE` | 1 Hz 健康状态。 |

Service 和 Action 使用 ROS 2 默认的 reliable/volatile request-response QoS；Action 状态 Topic 使用 `KEEP_LAST / 10`、`RELIABLE`、`TRANSIENT_LOCAL`。发布/订阅两端必须兼容本表，不得用全局“system default”代替测试中可检查的显式配置。

### 3.2 Topic、Service 与 Action 总表

“速率”是仿真运行时名义发布率；`事件`表示状态变化时立即发布且不轮询，`事件 + N Hz` 表示变化立即发布并以 N Hz 重发当前状态。所有节点名是逻辑所有者，实际可组合进同一进程但不能改变所有权。表内简写固定映射为：数字孪生=`substation_digital_twin`，风险=`substation_risk`，任务=`substation_mission`，报告=`substation_reporting`，Gateway=`substation_web_gateway`，证据采集/存储=架构中证据存储拥有的采集节点，检测聚合器=`substation_perception/detection_aggregator`。

`/system/run_context` 的订阅与 gating 义务只适用于项目自有、会产生或消费 run-scoped 派生状态、证据或控制命令的节点。发布标准基础设施/原始流的 bridge、第三方组件及 Nav2/SLAM——包括 `/clock`、`/tf`、`/tf_static`、`/odom`、`/map`、`/scan`、相机原始 Topic、`/plan`、`/local_plan` 和 `/cmd_vel_nav`——持续按自身生命周期发布，不订阅 `/system/run_context`，即使由项目 launch 启动也不改变这一规则；其标准消息本身不获得 run 归属。项目自有消费者和 Gateway 可持续消费这些原始输入用于 readiness、定位和安全判断；只有在形成带 run 归属的派生输出、证据、Web 快照或命令时，才以最新 RunContext 校验、归属或抑制样本。

| 域 | ROS 名称 | 发布者 / Server | 订阅者 / Client | 精确类型 | 速率 | QoS |
|---|---|---|---|---|---:|---|
| 时钟 | `/clock` | Gazebo `ros_gz_bridge` | 所有 `use_sim_time` 节点 | `rosgraph_msgs/msg/Clock` | 100 Hz | `Q_CLOCK` |
| 运行上下文 | `/system/run_context` | `substation_mission/task_manager`（唯一发布者） | 项目自有 run-scoped 生产/消费节点、Gateway、报告和证据存储；不含标准基础设施/原始流 bridge、第三方组件、SLAM 或 Nav2 | `substation_interfaces/msg/RunContext` | 状态变化立即发布；`Q_STATE` 为后加入者保留最新值 | `Q_STATE` |
| 原始 RGB | `/camera/image_raw` | `substation_gazebo` 相机桥 | 四个独立感知模块、证据采集 | `sensor_msgs/msg/Image` | 15 Hz | `Q_IMAGE` |
| 相机标定 | `/camera/camera_info` | `substation_gazebo` 相机桥 | 四个独立感知模块 | `sensor_msgs/msg/CameraInfo` | 15 Hz，与图像同 stamp | `Q_SENSOR` |
| 原始 LiDAR | `/scan` | `substation_gazebo` 激光桥 | SLAM、Nav2 costmap | `sensor_msgs/msg/LaserScan` | 10 Hz | `Q_SENSOR` |
| 原始环境 | `/simulation/environment/temperature_raw` | `substation_gazebo` | `substation_perception/environment_normalizer` | `diagnostic_msgs/msg/DiagnosticArray` | 2 Hz | `Q_SENSOR` |
| 原始环境 | `/simulation/environment/smoke_raw` | `substation_gazebo` | `substation_perception/environment_normalizer` | `diagnostic_msgs/msg/DiagnosticArray` | 2 Hz | `Q_SENSOR` |
| 原始环境 | `/simulation/environment/gas_raw` | `substation_gazebo` | `substation_perception/environment_normalizer` | `diagnostic_msgs/msg/DiagnosticArray` | 2 Hz | `Q_SENSOR` |
| 仿真真值 | `/simulation/scenario_truth` | `substation_gazebo` | 仅场景验收与证据记录 | `diagnostic_msgs/msg/DiagnosticArray` | 事件 + 1 Hz | `Q_EVENT` |
| 开发占位检测 | `/perception/development/detections` | `substation_perception/placeholder_detector` | 仅开发维护与只读诊断；检测聚合器、数字孪生、风险、任务、Gateway 和证据采集不得订阅 | `vision_msgs/msg/Detection2DArray` | 最高 15 Hz | `Q_STREAM` |
| 开发占位带框图像 | `/perception/development/annotated_image` | `substation_perception/placeholder_detector` | 仅开发维护与只读诊断；Gateway 和证据采集不得订阅 | `sensor_msgs/msg/Image` | 最高 15 Hz | `Q_IMAGE` |
| 安全检测 | `/perception/safety/detections` | `substation_perception/safety_detector` | 检测聚合器、风险、证据采集 | `vision_msgs/msg/Detection2DArray` | 15 Hz | `Q_STREAM` |
| 设备检测 | `/perception/equipment/detections` | `substation_perception/equipment_detector` | 检测聚合器、数字孪生、证据采集 | `vision_msgs/msg/Detection2DArray` | 15 Hz | `Q_STREAM` |
| 缺陷分类 | `/perception/defects/detections` | `substation_perception/defect_classifier` | 检测聚合器、数字孪生、风险、证据采集 | `vision_msgs/msg/Detection2DArray` | 15 Hz | `Q_STREAM` |
| 仪表读数 | `/perception/meters/readings` | `substation_perception/meter_reader` | 数字孪生、风险、证据采集 | `diagnostic_msgs/msg/DiagnosticArray` | 5 Hz | `Q_STREAM` |
| 聚合检测 | `/perception/detections` | `substation_perception/detection_aggregator`（只合并、不重新推理） | 数字孪生、风险、Gateway、证据采集 | `vision_msgs/msg/Detection2DArray` | 15 Hz | `Q_STREAM` |
| 带框图像 | `/perception/annotated_image` | `substation_perception/detection_aggregator` | Gateway JPEG 编码、证据采集 | `sensor_msgs/msg/Image` | 15 Hz | `Q_IMAGE` |
| 规范化环境 | `/environment/temperature` | `substation_perception/environment_normalizer` | 数字孪生、风险、Gateway、报告 | `diagnostic_msgs/msg/DiagnosticArray` | 2 Hz | `Q_STREAM` |
| 规范化环境 | `/environment/smoke` | `substation_perception/environment_normalizer` | 数字孪生、风险、Gateway、报告 | `diagnostic_msgs/msg/DiagnosticArray` | 2 Hz | `Q_STREAM` |
| 规范化环境 | `/environment/gas` | `substation_perception/environment_normalizer` | 数字孪生、风险、Gateway、报告 | `diagnostic_msgs/msg/DiagnosticArray` | 2 Hz | `Q_STREAM` |
| 数字孪生 | `/digital_twin/assets` | `substation_digital_twin` | 风险、任务、报告、Gateway | `diagnostic_msgs/msg/DiagnosticArray` | 事件 + 2 Hz | `Q_STATE` |
| 资产风险 | `/risk/assets` | `substation_risk` | 任务、报告、Gateway | `substation_interfaces/msg/AssetRiskArray` | 事件 + 5 Hz | `Q_STATE` |
| 风险事件 | `/risk/alerts` | `substation_risk` | 任务、报告、Gateway、证据存储 | `substation_interfaces/msg/RiskAlert` | 事件 | `Q_EVENT` |
| 告警确认 | `/risk/alert_acknowledgements` | `substation_risk` | 任务、报告、Gateway、证据存储 | `substation_interfaces/msg/AlertAcknowledgement` | 事件 | `Q_EVENT` |
| 巡检队列 | `/mission/inspection_tasks` | `substation_mission` | 报告、Gateway、证据存储 | `substation_interfaces/msg/InspectionTaskArray` | 事件 + 2 Hz | `Q_STATE` |
| 地图 | `/map` | SLAM / map server（二者按运行模式二选一） | Nav2、任务目标校验、Gateway | `nav_msgs/msg/OccupancyGrid` | 事件 + 1 Hz | `Q_MAP` |
| 地图增量 | `/map_updates` | 与 `/map` 相同的唯一地图发布者 | Gateway | `map_msgs/msg/OccupancyGridUpdate` | 变化时 | `Q_STREAM` |
| 里程计 | `/odom` | `substation_gazebo` 底盘桥/里程计 | 定位、Nav2、任务、Gateway | `nav_msgs/msg/Odometry` | 30 Hz | `Q_SENSOR` |
| 模拟电量 | `/battery_state` | `substation_gazebo` 电源模拟器 | 任务、Gateway、报告 | `sensor_msgs/msg/BatteryState` | 1 Hz | `Q_STREAM` |
| 动态 TF | `/tf` | 第 5 节指定的唯一 frame 所有者 | 定位、Nav2、感知、数字孪生、Gateway、Foxglove 只读 | `tf2_msgs/msg/TFMessage` | 10～30 Hz | `Q_TF_DYNAMIC` |
| 静态 TF | `/tf_static` | `robot_state_publisher` 与资产静态广播器，各自拥有不重叠子 frame | 全部 TF 消费者、Foxglove 只读 | `tf2_msgs/msg/TFMessage` | 启动/配置变化 | `Q_TF_STATIC` |
| 全局路径 | `/plan` | Nav2 planner/controller server | 任务、Gateway、证据存储 | `nav_msgs/msg/Path` | 事件，最高 5 Hz | `Q_STREAM` |
| 局部路径 | `/local_plan` | Nav2 controller server | 任务、Gateway | `nav_msgs/msg/Path` | 5 Hz | `Q_STREAM` |
| Nav2 速度 | `/cmd_vel_nav` | Nav2 controller server | 任务安全速度仲裁器 | `geometry_msgs/msg/Twist` | 最高 20 Hz | `Q_CONTROL` |
| 手动速度请求 | `/cmd_vel_manual` | Gateway | 任务安全速度仲裁器 | `substation_interfaces/msg/ManualVelocityCommand` | 0～10 Hz | `Q_CONTROL` |
| 手动速度确认 | `/mission/manual_velocity_status` | 任务安全速度仲裁器 | Gateway、证据存储 | `substation_interfaces/msg/ManualVelocityStatus` | 每个 command 状态变化时发布 | `Q_EVENT` |
| 底盘速度 | `/cmd_vel` | 任务安全速度仲裁器（唯一发布者） | Gazebo 底盘控制器 | `geometry_msgs/msg/Twist` | 最高 20 Hz；停止时立即发零并以 10 Hz 保持 0.5 s | `Q_CONTROL` |
| 系统诊断 | `/diagnostics` | 所有核心组件，经诊断聚合器汇总 | Gateway、证据存储、Foxglove 只读 | `diagnostic_msgs/msg/DiagnosticArray` | 事件 + 1 Hz | `Q_DIAGNOSTIC` |
| 场景状态 | `/simulation/scenario_state` | `substation_gazebo/scenario_manager` | Gateway、证据存储 | `diagnostic_msgs/msg/DiagnosticArray` | 事件 + 1 Hz | `Q_STATE` |
| 巡检执行 | `/mission/execute_inspection` | `substation_mission/inspection_executor` Action server | `substation_mission/task_manager` Action client | `substation_interfaces/action/ExecuteInspection` | 按 Action 反馈/结果 | Action 默认 QoS |
| 导航执行 | `/navigate_to_pose` | Nav2 `NavigateToPose` Action server | 仅 `substation_mission` Action client | `nav2_msgs/action/NavigateToPose` | 按 Action 反馈/结果 | Action 默认 QoS |
| 任务控制 | `/mission/manage` | `substation_mission` Service server | Gateway | `substation_interfaces/srv/ManageMission` | 请求触发 | Service 默认 QoS |
| 合法目标 | `/mission/queue_navigation_goal` | `substation_mission` Service server | Gateway | `substation_interfaces/srv/QueueNavigationGoal` | 请求触发 | Service 默认 QoS |
| 紧急停止 | `/mission/emergency_stop` | `substation_mission` Service server | Gateway | `substation_interfaces/srv/EmergencyStop` | 请求触发 | Service 默认 QoS |
| 紧停复位 | `/mission/emergency_stop_reset` | `substation_mission` Service server | Gateway | `substation_interfaces/srv/ResetEmergencyStop` | 请求触发 | Service 默认 QoS |
| 机器人模式 | `/mission/set_robot_mode` | `substation_mission` Service server | Gateway | `substation_interfaces/srv/SetRobotMode` | 请求触发 | Service 默认 QoS |
| 资产优先巡检 | `/mission/prioritize_asset` | `substation_mission` Service server | Gateway | `substation_interfaces/srv/PrioritizeAsset` | 请求触发 | Service 默认 QoS |
| 编辑巡检任务 | `/mission/edit_inspection_task` | `substation_mission` Service server | Gateway | `substation_interfaces/srv/EditInspectionTask` | 请求触发 | Service 默认 QoS |
| 显式重规划 | `/mission/replan` | `substation_mission` Service server | Gateway | `substation_interfaces/srv/ReplanMission` | 请求触发 | Service 默认 QoS |
| 资产复检 | `/mission/request_reinspection` | `substation_mission` Service server | Gateway | `substation_interfaces/srv/RequestReinspection` | 请求触发 | Service 默认 QoS |
| 告警确认 | `/risk/acknowledge_alert` | `substation_risk` Service server | Gateway | `substation_interfaces/srv/AcknowledgeAlert` | 请求触发 | Service 默认 QoS |
| 非关键服务重连 | `/maintenance/reconnect_noncritical_service` | `substation_system/maintenance_supervisor` Service server | Gateway | `substation_interfaces/srv/ReconnectNoncriticalService` | 请求触发 | Service 默认 QoS |
| 记录时间映射 | `/reporting/record_run_time_mapping` | `substation_reporting/evidence_store` Service server | Gateway、任务管理器 | `substation_interfaces/srv/RecordRunTimeMapping` | 请求触发 | Service 默认 QoS |
| 查询时间映射 | `/reporting/query_run_time_mapping` | `substation_reporting/evidence_store` Service server | Gateway、报告生成器 | `substation_interfaces/srv/QueryRunTimeMapping` | 请求触发 | Service 默认 QoS |
| 存储证据 | `/reporting/store_evidence` | `substation_reporting/evidence_store` Service server | 感知、风险、任务、Gateway、报告生成器 | `substation_interfaces/srv/StoreEvidence` | 请求触发 | Service 默认 QoS |
| 冻结证据 | `/reporting/freeze_evidence` | `substation_reporting/evidence_store` Service server | Gateway | `substation_interfaces/srv/FreezeEvidence` | 请求触发 | Service 默认 QoS |
| 查询/读取证据 | `/reporting/query_evidence`、`/reporting/read_evidence_chunk` | `substation_reporting/evidence_store` Service server | Gateway、报告生成器 | `substation_interfaces/srv/QueryEvidence`、`substation_interfaces/srv/ReadEvidenceChunk` | 请求触发 | Service 默认 QoS |
| 报告就绪 | `/reporting/readiness` | `substation_reporting/evidence_store` Service server | Gateway、任务管理器、报告生成器 | `substation_interfaces/srv/GetReportingReadiness` | 请求触发 | Service 默认 QoS |
| 报告/诊断生成 | `/reporting/generate_report`、`/reporting/generate_diagnostic_bundle` | `substation_reporting/report_generator` Service server | Gateway、任务管理器 | `substation_interfaces/srv/GenerateReport`、`substation_interfaces/srv/GenerateDiagnosticBundle` | 请求触发 | Service 默认 QoS |
| 场景控制 | `/scenario_manager/set_parameters_atomically` | `substation_gazebo/scenario_manager` 标准参数 Service server | Gateway | `rcl_interfaces/srv/SetParametersAtomically` | 请求触发 | Service 默认 QoS |

`/navigate_to_pose` 必须使用标准 Nav2 `NavigateToPose`，Gateway 不得成为其客户端。任务模块先根据 `map`、资产碰撞体、危险区和安全观察距离验证/排序目标，再调用 Nav2。`/cmd_vel_nav` 是 Nav2 输出重映射；Nav2 和 Gateway 都不得直接发布最终 `/cmd_vel`。

### 3.3 RunContext 生命周期与 gating

任务管理器是 operational run 的唯一创建者和状态机所有者。它先把新上下文与 mission 初始快照原子持久化，再发布 `RunContext`；订阅该 Topic 的项目自有节点只能消费，不能另行发布或改写。第 3.2 节列出的标准基础设施/原始流 bridge、第三方组件、SLAM 和 Nav2 不参与此状态机并持续发布。合法生命周期为 `IDLE -> STARTING -> ACTIVE -> ENDING -> ENDED -> IDLE`，每次转换严格增加持久化的 `context_revision`，任务管理器重启后也不得倒退。

- `IDLE` 明确表示当前没有 run：`run_id=""`，started/ended time 为零，reason_code=`NO_ACTIVE_RUN`。空字符串只在该状态合法，不是 UUID 占位符。
- `STARTING` 首次携带新 UUID run_id；只允许任务管理器准备 route、mission、审计和执行器，其他项目自有 run-scoped 生产者不得产生派生结果或证据。上述标准基础设施/原始流与导航发布者继续发布。
- `ACTIVE` 允许项目自有 run-scoped 生产者产生带 run 归属的派生状态和证据。所有显式 `run_id` 字段必须逐字等于最新 RunContext；携带 context revision 的命令还必须精确匹配最新 revision，不匹配时拒绝并报 `RUN_CONTEXT_MISMATCH`。
- `ENDING` 禁止项目自有节点创建新任务和新的传感/检测证据，只允许取消导航、归零、完成既有证据写入，并由报告/清单生产者生成终态证据完成封口；`ENDED` 表示这些 barrier 已完成并保留结束 run_id 供消费者提交最终状态。上述标准基础设施/原始流与导航发布者不因这些转换停发。
- 从 `ENDED` 转为 `IDLE` 后，标准第三方基础设施与原始传感器仍可发布，项目自有消费者也可将其用于 readiness 和安全诊断；但不得分配 evidence_id、形成 run-scoped 派生输出或将样本计入某个 run。其余项目自有 run-scoped publisher 抑制输出。

Gateway 启动或重启时先取得 transient-local `/system/run_context`，再取得同一 run_id 的 transient-local `/mission/inspection_tasks`。二者 revision 均有效且 run_id/lifecycle 一致后，Gateway 才建立 REST/WS 快照；此前 `/readyz` 为 503 `NOT_READY`。Gateway 从这两份权威完整快照恢复 run_id、mission、route、模式、锁存和任务状态，不从 SQLite 副本或客户端缓存重建业务真值。

### 3.4 标准消息的项目内字段约束

#### 图像与检测

- `/camera/image_raw`：`header.frame_id="camera_optical_frame"`，`encoding="rgb8"`；同一帧的 CameraInfo 具有相同 stamp，标定矩阵非零且 width/height 一致。
- `/perception/development/detections` 和 `/perception/development/annotated_image` 只允许在显式 `runtime_mode=development_placeholder` 且 `production_ready=false` 时发布。检测 `class_id` 固定使用 `placeholder/coco/<normalized-class>`，`Detection2D.id` 只是单帧开发关联 ID，不是 production `evidence_id`；两个 Topic 都逐字保留输入图像 header，带框图像固定为 `rgb8`。这些样本不得进入检测聚合器、数字孪生、风险、任务、Gateway、报告或证据链，也不得映射到任何正式感知 Topic。
- 三个独立视觉检测 Topic 和 `/perception/detections`：`header.frame_id="camera_optical_frame"`；源检测节点在发布前生成 `Detection2D.id` 作为该检测证据的 `evidence_id`；每个 `ObjectHypothesis.class_id` 使用 `<module>/<class>`，其中 module 只能是 `safety`、`equipment` 或 `defect`，score 为 `confidence_0_1`。聚合器保留来源前缀和证据 ID，不合并四个模型，也不重新分配 evidence_id。
- `/perception/annotated_image`：`encoding="rgb8"`，stamp 与生成它的原始帧一致；若一帧推理未完成则丢弃该带框帧，不得复制旧框到新图像。
- `/battery_state`：使用标准 `BatteryState.percentage` 的 0～1 比例；Gateway 只在 Web 边界换算为 `battery_percent = 100 × percentage`。其余未知电池字段使用该标准消息定义的 NaN 语义，但 Gateway 不得把 NaN 输出到 JSON。

#### 标准导航消息 frame_id

| Topic | 固定 frame 语义 |
|---|---|
| `/odom` | `header.frame_id="odom"`、`child_frame_id="base_footprint"`；pose 表达在 odom，twist 表达在 child frame。 |
| `/map` | `header.frame_id="map"`；占据栅格 origin 也表达在 map。 |
| `/plan` | `Path.header.frame_id="map"`，每个 `PoseStamped.header.frame_id="map"`；各 pose stamp 为路径计算 stamp。 |
| `/local_plan` | `Path.header.frame_id="odom"`，每个 `PoseStamped.header.frame_id="odom"`；Gateway 在 Path stamp 处变换到 map 后才对 Web 发布。 |
| `/battery_state` | `header.frame_id="base_link"`。 |

任何不符合表中 frame 的样本都以 `FRAME_ID_INVALID` 拒绝，不能由 Gateway 根据 Topic 名猜 frame。`/cmd_vel_nav`、`/cmd_vel` 是标准 `Twist`，没有 header；它们的线/角速度按 `base_link` 约定解释。手动速度的 frame 由 `ManualVelocityCommand.header.frame_id` 明示；header stamp 只供审计与关联，不能用于执行时限。

#### `DiagnosticArray` 测量编码

环境和仪表 Topic 的 `header.stamp` 是采样时间。每个 `DiagnosticStatus` 表示一个资产上的一个传感器：`name=asset_id`，`hardware_id=sensor_id`；`level` 只表示数据质量（0 OK、1 WARN/降级、2 ERROR/无效、3 STALE），不能借用为风险等级；`message` 是稳定原因短语。`values` 必须恰好包含下表键，ACTIVE 时 `run_id` 必须是当前 RunContext UUID。只有 `/simulation/environment/*_raw` readiness 样本可在 IDLE 使用空 run_id，且 normalizer 必须抑制对应派生输出。数值使用十进制点和无单位字符串表示，接收方拒绝缺键、重复键或无法解析的样本。

| Topic | 必需 `KeyValue.key` | 约束 |
|---|---|---|
| `*/temperature*` | `run_id`、`value_celsius`、`confidence_0_1`、`valid` | `valid` 为 `true`/`false`；有效时温度有限、confidence 在 0～1。 |
| `*/smoke*` | `run_id`、`value_0_1`、`confidence_0_1`、`valid` | 两个数均在 0～1。 |
| `*/gas*` | `run_id`、`value_ppm`、`confidence_0_1`、`valid` | ppm 非负。 |
| `/perception/meters/readings` | `run_id`、`reading`、`unit`、`confidence_0_1`、`valid`、`evidence_id` | `unit` 必须来自资产配置，不由模型自由生成；meter_reader 在发布前生成 evidence_id。 |

`/simulation/scenario_truth` 使用 `name=scenario_id`、`hardware_id="gazebo"`，并含 `run_id`、`active`、`scenario_revision`、`started_ros_sec`、`started_ros_nanosec`；它只供验收和证据，感知、数字孪生和风险节点不得订阅。`/simulation/scenario_state` 也使用 `name=scenario_id`、`hardware_id="gazebo"`，其 values 必须恰好含 `run_id`、`command_id`、`action`、`status`、`active`、`scenario_revision`、`applied_ros_sec`、`applied_ros_nanosec`、`error_code`；status 为 `applying|applied|failed`。它是控制确认状态而非感知输入，scenario manager 按 command_id 幂等执行并为每次实际应用增加 revision。

#### 数字孪生快照编码

`/digital_twin/assets` 的 `header.frame_id="map"`。每个 `DiagnosticStatus.name=asset_id`，`hardware_id=category`；level 表示资产语义状态：0 `NORMAL`、1 `ATTENTION`、2 `FAULT`、3 `STALE`。每个 status 的 `values` 必须恰好含以下键；IDLE 时发布 statuses 为空的完整快照：

`run_id`、`category`、`state`、`pose_x_m`、`pose_y_m`、`pose_z_m`、`orientation_x`、`orientation_y`、`orientation_z`、`orientation_w`、`temperature_celsius`、`smoke_0_1`、`gas_ppm`、`meter_reading`、`meter_unit`、`last_observed_ros_sec`、`last_observed_ros_nanosec`、`latest_evidence_id`。

没有测量的可空值编码为空字符串；`latest_evidence_id` 为空或 UUID；`state` 必须等于第 2.6 节中 level 对应的小写字符串。pose 来自 `substation_description` 的 `map` 坐标且不能被观测节点改写。未知键在 schema 1 中视为错误，以防不同模块对同名状态作不同解释。

#### Evidence ID 分配与持久化

源节点在内容形成时分配 UUIDv4 evidence_id：视觉/仪表节点分配检测与读数证据，Gateway 分配操作者冻结帧，风险/报告节点分配各自生成的派生证据或清单。证据存储接收 `(evidence_id, run_id, media_type, content_sha256, metadata, bytes)`，在同一事务中验证 RunContext 后按调用方 ID 持久化：

- 首次出现的 ID 写入内容、元数据和索引；存储不得替换成新 ID。
- 同一 ID、相同 content SHA-256、media type 和 canonical metadata 的重试返回原记录，视为成功的幂等重放。
- 同一 ID 对应不同内容、media type 或 metadata 时拒绝写入、保留原对象并报告 `EVIDENCE_ID_CONFLICT`；禁止覆盖、合并或静默重新编号。
- 非 ACTIVE/ENDING RunContext、run_id 不匹配或无效 UUID 的写入分别返回 `RUN_CONTEXT_MISMATCH` 或 `VALIDATION_FAILED`。ENDING 只允许完成 ACTIVE 已创建的对象，以及由报告/清单生产者新建终态证据；感知与 Gateway 不得在 ENDING 分配新 evidence_id。

标准 `sensor_msgs/Image`、`vision_msgs/Detection2DArray`、`diagnostic_msgs/DiagnosticArray`、`nav_msgs/OccupancyGrid` 和 `nav_msgs/Path` 没有项目 `run_id` 字段，因而不得靠“当前 Gateway run”作不可审计的猜测归属。每次 `StoreEvidence`/`FreezeEvidence` 必须同时写入并由 evidence store 不可变保存：ACTIVE `RunContext.run_id` 与 `context_revision`、`source_topic`、完整 `source_header_stamp(sec,nanosec)`、`source_header_frame_id`、源消息类型、源图像 SHA-256（适用时）、该标准消息的 RFC 8785 canonical JSON SHA-256（适用时）和 source sequence/index。视觉检测还保存 `Detection2D.id=evidence_id`、数组 header、检测在数组中的 zero-based index；仪表读数保存对应 `DiagnosticArray` header、status index 和 `evidence_id` key。写入时 evidence store 以记录的 run/revision 精确核对其已持久化 RunContext registry；不匹配、IDLE、STARTING、结束后新增感知证据或缺任一 source 字段一律拒绝。验收必须能够用 rosbag2 中 `/system/run_context` 的 revision，以及同一 topic/header stamp/frame 和 ID/index，逐条重建 evidence 到 run 的归属；仅凭 Topic 名、到达墙钟或之后的 current run 不足以通过。

#### 场景控制参数

Gateway 对一次场景请求原子设置四个标准 ROS 参数：`command_id`（UUID string）、`scenario_id`（稳定配置 string）、`scenario_action`（`start`、`trigger` 或 `reset`）、`scenario_parameters_json`（UTF-8、对象型 JSON 的 RFC 8785 canonical serialization）。`scenario_manager` 只接受配置中对该场景列入 allowlist 的参数名与范围；唯一 `command_id` 使重复的相同参数提交只执行一次。

## 4. `substation_interfaces` 自定义定义

包的直接接口依赖固定为 `builtin_interfaces`、`std_msgs`、`geometry_msgs` 和 `rosidl_default_generators`。下列代码块是未来文件的完整 schema 1 内容，可直接写入对应 `.msg`、`.srv`、`.action` 文件；注释不是字段，不需要额外的隐式属性。

### 4.1 消息

`msg/RunContext.msg`

```text
uint32 SCHEMA_VERSION=1
uint8 LIFECYCLE_IDLE=0
uint8 LIFECYCLE_STARTING=1
uint8 LIFECYCLE_ACTIVE=2
uint8 LIFECYCLE_ENDING=3
uint8 LIFECYCLE_ENDED=4

uint32 schema_version
std_msgs/Header header
uint64 context_revision
uint8 lifecycle
string run_id
builtin_interfaces/Time started_at
builtin_interfaces/Time ended_at
string transition_command_id
string reason_code
string reason
```

`header.frame_id` 必须为空，stamp 是该 lifecycle revision 生效的 ROS time。`context_revision` 是任务管理器持久化的全局单调 revision；IDLE 的 run_id/transition_command_id 为空且两个时间为零，STARTING/ACTIVE/ENDING 的 run_id 为 UUID、started_at 非零、ended_at 为零，ENDED 的 run_id 和两个时间均非零。由 REST 命令触发的转换必须携带对应 transition_command_id；自然结束/恢复转换可为空。reason_code 是稳定机器码，reason 最长 256 字符。

`msg/ManualVelocityCommand.msg`

```text
uint32 SCHEMA_VERSION=1

uint32 schema_version
std_msgs/Header header
string command_id
string run_id
uint64 context_revision
geometry_msgs/Twist twist
float32 duration_s
```

`header.frame_id="base_link"`，stamp 是 Gateway 发布命令时的 ROS time，但只用于审计、日志关联和 rosbag2 回放定位，不参与过期计算。`duration_s` 范围 `[0.05,0.25]`；command_id 是对应 REST 命令 UUID。Gateway 在发布前从同一份最新 ACTIVE RunContext 原子复制 run_id 和 context_revision；这两个字段由 Gateway 注入，REST 请求体不得提供或覆盖。

任务安全仲裁器收到消息的回调入口立即读取本进程 monotonic/steady clock 为 `t_received`。首次执行前必须验证 lifecycle=ACTIVE、消息 run_id 与当前 RunContext.run_id 逐字相等、消息 context_revision 与当前 RunContext.context_revision 精确相等；任一上下文条件不满足均以 `RUN_CONTEXT_MISMATCH` 拒绝。非 manual 模式、紧停锁存或 frame 错误分别使用 `MANUAL_MODE_REQUIRED`、`EMERGENCY_STOP_LATCHED` 或 `FRAME_ID_INVALID`。仲裁器按 command_id 去重，重复消息绝不再次执行；已存在 terminal 结果时可重发同一状态。

全部校验通过后唯一执行期限为 `t_deadline = t_received + duration_s`。仲裁器不得比较 ROS header stamp 与期限，不得使用 `/clock`、系统墙钟或 Gateway 发送时刻延长/缩短 duration；仿真时钟暂停、跳变或重置也不改变该期限。DDS `Q_CONTROL` lifespan 只可能在回调前丢弃陈旧运输样本，消息一旦被仲裁器接收就只由上述单调时钟期限管理。

`msg/ManualVelocityStatus.msg`

```text
uint32 SCHEMA_VERSION=1
uint8 STATE_ACCEPTED=0
uint8 STATE_APPLIED=1
uint8 STATE_REJECTED=2
uint8 STATE_EXPIRED=3
uint8 STATE_CANCELLED=4

uint32 schema_version
std_msgs/Header header
string command_id
uint8 state
string error_code
string error_message
```

`header.frame_id="base_link"`，stamp 是状态转换的 ROS time。每个 command 先至多发布一次 ACCEPTED，再恰好发布一个 terminal APPLIED/REJECTED/EXPIRED/CANCELLED；APPLIED 只能在该 twist 已被仲裁器选中并至少一次发布为最终 `/cmd_vel` 后发送。Gateway 只依据此 topic 终结手动速度 REST 命令。

REJECTED 的 `error_code` 使用具体稳定码（例如 `FRAME_ID_INVALID`、`RUN_CONTEXT_MISMATCH`、`MANUAL_MODE_REQUIRED` 或 `EMERGENCY_STOP_LATCHED`），没有更具体原因时使用 `MANUAL_COMMAND_REJECTED`；EXPIRED/CANCELLED 分别固定使用 `MANUAL_COMMAND_EXPIRED`/`MANUAL_COMMAND_CANCELLED`。APPLIED/ACCEPTED 的 error_code/error_message 为空。

`msg/AssetRisk.msg`

```text
uint32 SCHEMA_VERSION=1
uint8 LEVEL_NORMAL=0
uint8 LEVEL_ATTENTION=1
uint8 LEVEL_ALERT=2
uint8 LEVEL_EMERGENCY=3

uint32 schema_version
string asset_id
float32 score_0_100
uint8 level
float32 visual_0_1
float32 temperature_0_1
float32 smoke_0_1
float32 gas_0_1
float32 context_0_1
uint32 confirmation_frames
builtin_interfaces/Time last_observed
string[] evidence_ids
```

`score_0_100` 必须按项目计划公式 `100 × (0.30V + 0.25T + 0.20S + 0.10G + 0.15C)` 计算，权重来自 `risk_weights.yaml` 而不是消息或代码常量。等级边界固定为 0～29、30～59、60～79、80～100；实现比较时使用连续分数区间 `[0,30)`、`[30,60)`、`[60,80)`、`[80,100]`。`evidence_ids` 去重并按证据时间升序。

`msg/AssetRiskArray.msg`

```text
uint32 SCHEMA_VERSION=1

uint32 schema_version
std_msgs/Header header
string run_id
uint64 risk_revision
substation_interfaces/AssetRisk[] assets
```

`header.frame_id` 固定为 `map`；`risk_revision` 在同一 ACTIVE `run_id` 内每次原子风险提交加一。`assets` 按 `asset_id` 字典序排列，且不得重复。IDLE 时只允许完整空快照 `run_id=""`、`risk_revision=0`、assets 为空。

`msg/RiskAlert.msg`

```text
uint32 SCHEMA_VERSION=1
uint8 EVENT_OPENED=0
uint8 EVENT_LEVEL_CHANGED=1
uint8 EVENT_CLEARED=2
uint8 LEVEL_NORMAL=0
uint8 LEVEL_ATTENTION=1
uint8 LEVEL_ALERT=2
uint8 LEVEL_EMERGENCY=3

uint32 schema_version
std_msgs/Header header
string alert_id
string run_id
string asset_id
uint8 event_type
uint8 previous_level
uint8 current_level
float32 score_0_100
string summary
string[] evidence_ids
```

达到 60 分首次发 `EVENT_OPENED`；告警仍打开时跨等级发 `EVENT_LEVEL_CHANGED`；经滑动平均和回落滞回降到关闭阈值后发 `EVENT_CLEARED`。`summary` 仅用于显示，自动行为必须读取枚举和分数。

`msg/AlertAcknowledgement.msg`

```text
uint32 SCHEMA_VERSION=1

uint32 schema_version
std_msgs/Header header
string command_id
string run_id
string alert_id
uint64 risk_revision
uint64 alert_revision
string note
```

`header.frame_id` 必须为空，stamp 是确认提交的 ROS time。确认不会清除、降级或抑制风险；它只记录哪个 alert 在哪个风险/告警 revision 被操作员阅读。`alert_revision` 是风险模块跨 run 持久化的单调 revision，每次告警 open、level change、clear 或 acknowledgement 都严格增加。重复同 command_id 的相同请求返回同一记录；同一 `alert_id` 的另一次确认可以产生新 revision。Web 必须将两个 revision 作为第 2.5.1 节十进制字符串发送。

`msg/InspectionTask.msg`

```text
uint32 SCHEMA_VERSION=1
uint8 TYPE_INSPECT_ASSET=0
uint8 TYPE_NAVIGATION_GOAL=1
uint8 TYPE_RETURN_HOME=2
uint8 STATE_QUEUED=0
uint8 STATE_ACTIVE=1
uint8 STATE_SUCCEEDED=2
uint8 STATE_SKIPPED=3
uint8 STATE_FAILED=4
uint8 STATE_CANCELLED=5

uint32 schema_version
string task_id
string command_id
string mission_id
string asset_id
uint8 task_type
uint8 state
int32 base_priority
float32 risk_score_0_100
float32 risk_gain
float32 path_length_m
float32 distance_penalty
float32 computed_priority
geometry_msgs/PoseStamped goal
float32 safety_standoff_m
uint32 attempt
string last_error_code
```

`computed_priority = base_priority + risk_gain × risk_score_0_100 - distance_penalty × path_length_m`。所有 goal 的 `header.frame_id` 为 `map`。由 navigation.goal 或 return-home REST 命令创建的任务携带对应 command_id；配置路线或风险自动生成任务的 command_id 为空。`TYPE_NAVIGATION_GOAL` 的 `asset_id` 为空；另外两类必须引用配置资产或 `home` 资产。紧急资产目标使用配置中的安全观察点，`safety_standoff_m > 0`，不得位于资产碰撞体内。

任务管理器只从版本控制的 `configs/mission_ordering.yaml` 读取以下 schema 1 默认值，不能把它们写死在 ROS message、Gateway 或 Nav2：`risk_gain: 1.00`、`distance_penalty: 0.25`、`minimum_active_hold_s: 5.0`、`normal_replan_cooldown_s: 10.0`、`emergency_score_0_100: 80.0`。排序键依次为 `computed_priority` 降序、`task_id` 字典序升序；相同输入必须得到相同完整队列。当前 ACTIVE 任务开始后的 5.0 s 内，normal/attention/alert 风险、操作员优先或显式 replan 只能更新后续队列，不能取消该任务；任一非紧急重排距离上一次已应用非紧急重排不足 10.0 s 时只合并为下一次待处理重排。新样本分数达到或跨越 80.0 emergency 时绕过 hold/cooldown，立即取消普通 Nav2 goal、插入配置安全观察点并发起替代 Action goal。动态障碍仍只由 Nav2 costmap 局部避让；它不会改变该任务排序规则。所有 hold/cooldown 用任务管理器 monotonic clock，接受的实际参数、排序前后队列和 bypass 原因均写入任务 revision、rosbag2 和报告。

`msg/InspectionTaskArray.msg`

```text
uint32 SCHEMA_VERSION=1
uint8 MISSION_IDLE=0
uint8 MISSION_READY=1
uint8 MISSION_RUNNING=2
uint8 MISSION_PAUSED=3
uint8 MISSION_STOPPING=4
uint8 MISSION_SUCCEEDED=5
uint8 MISSION_FAILED=6
uint8 MISSION_STOPPED=7
uint8 MODE_AUTONOMOUS=0
uint8 MODE_MANUAL=1
uint8 MODE_ESTOP=2

uint32 schema_version
std_msgs/Header header
string run_id
string mission_id
string route_id
uint64 state_revision
uint64 queue_revision
uint8 mission_state
uint8 robot_mode
bool emergency_stop_latched
uint64 emergency_stop_latch_revision
string transition_command_id
string transition_reason_code
string transition_reason
string active_task_id
uint32 completed_tasks
uint32 total_tasks
float32 progress_0_1
substation_interfaces/InspectionTask[] tasks
```

`header.frame_id="map"`，stamp 是该 state_revision 生效的 ROS time。`tasks` 是当前排序后的完整队列，按执行顺序排列；重排原子地增加 `queue_revision`。`state_revision` 是任务管理器跨 run 持久化的全局单调 revision，对 mission state、route、mode、锁存、active task、进度或队列的任何原子变化加一，并与该完整快照一起持久化；Gateway 重启后使用该 revision 丢弃旧样本。REST 命令导致的提交携带 transition_command_id，自动风险/导航反馈提交可为空；transition_reason_code 是稳定机器码，transition_reason 是最长 256 字符的人读原因。ACTIVE run 中 route_id 必须是启动时的配置 route。IDLE/no-run 快照的 run_id、mission_id、route_id、active_task_id 为空，queue_revision 为 0、mission_state=IDLE、tasks 为空；但 state_revision、robot_mode、emergency_stop_latched、emergency_stop_latch_revision 和安全命令产生的 transition 字段仍必须保留，以便无 run 紧停/复位后的 Gateway 重启恢复。`progress_0_1` 在一次 mission 内不得倒退，队列新增高风险任务时以“已完成数/当前总数”重新计算可能违反该条件，因此实现必须保存任务模块发布的单调任务进度，并另由 `completed_tasks/total_tasks` 表示即时比例。

### 4.2 Service

`srv/ManageMission.srv`

```text
uint32 SCHEMA_VERSION=1
uint8 ACTION_START=0
uint8 ACTION_PAUSE=1
uint8 ACTION_RESUME=2
uint8 ACTION_STOP=3
uint8 ACTION_RETURN_HOME=4

uint32 schema_version
string command_id
string mission_id
uint8 action
string route_id
string reason
---
uint32 schema_version
bool accepted
string run_id
string mission_id
uint64 run_context_revision
uint64 state_revision
uint64 queue_revision
string error_code
string error_message
```

`ACTION_START` 的 `mission_id` 为空且 `route_id` 必填；任务管理器原子生成 run UUID 和 mission UUID，并在响应及 RunContext/mission state 中返回。其他 action 的 `mission_id` 必填且 `route_id` 为空，任务管理器从当前上下文解析 run_id，Gateway 不得传入。`reason` 长度 1～256。Service 的 accepted 只表示任务模块接管命令；响应 revision 是已安排的最小权威 revision，最终状态由 RunContext、Action/任务 Topic 和第 9.4 节终态条件决定。

`srv/QueueNavigationGoal.srv`

```text
uint32 SCHEMA_VERSION=1

uint32 schema_version
string command_id
string mission_id
geometry_msgs/PoseStamped goal
---
uint32 schema_version
bool accepted
string task_id
uint64 state_revision
uint64 queue_revision
string error_code
string error_message
```

任务模块验证 `goal.header.frame_id == "map"`、四元数、占据栅格、资产碰撞体和危险区后才创建 `TYPE_NAVIGATION_GOAL`。Gateway 不能绕过该 Service 直接调用 Nav2。

`srv/EmergencyStop.srv`

```text
uint32 SCHEMA_VERSION=1

uint32 schema_version
string command_id
string reason
---
uint32 schema_version
bool accepted
bool latched
uint64 latch_revision
uint64 state_revision
string error_code
string error_message
```

该 Service 必须先锁存再返回：取消所有可见 Nav2 goal、阻止新任务、选择零速度并发布 `/cmd_vel`。已锁存时再次调用是成功的幂等操作，返回当前 `latch_revision`。

`srv/ResetEmergencyStop.srv`

```text
uint32 SCHEMA_VERSION=1

uint32 schema_version
string command_id
uint64 observed_latch_revision
bool confirm
string reason
---
uint32 schema_version
bool accepted
bool latched
uint64 latch_revision
uint64 state_revision
string error_code
string error_message
```

复位要求 `confirm=true`、观察到的 revision 与当前锁存 revision 相同、机器人线/角速度连续 0.5 s 为零、无活动 Nav2 goal、任务安全仲裁器和持久化审计可用。成功只释放锁存并将模式置为 `MANUAL`；不会恢复、重发或继续紧停前的 mission。

`srv/SetRobotMode.srv`

```text
uint32 SCHEMA_VERSION=1
uint8 MODE_AUTONOMOUS=0
uint8 MODE_MANUAL=1

uint32 schema_version
string command_id
string mission_id
uint8 target_mode
uint64 observed_state_revision
uint64 observed_latch_revision
string reason
---
uint32 schema_version
bool accepted
uint8 robot_mode
uint64 state_revision
uint64 latch_revision
string error_code
string error_message
```

`target_mode` 不接受 ESTOP（只允许 EmergencyStop）；两个 observed revision 是 compare-and-set，必须精确等于当前 `InspectionTaskArray`。切入 MANUAL 前必须取消 Nav2 goal、仲裁器选中零速度并确认 0.5 s；切入 AUTONOMOUS 前必须非紧停、mission 为 READY/RUNNING/PAUSED、map/TF/Nav2 与报告审计 readiness 都有效，且不存在未确认零速度。任何 e-stop、状态/revision 不匹配、无效目标、导航/审计/安全链不可用都拒绝，不得部分切换。

`srv/PrioritizeAsset.srv`、`srv/ReplanMission.srv` 与 `srv/RequestReinspection.srv`

```text
# PrioritizeAsset.srv
uint32 SCHEMA_VERSION=1
uint32 schema_version
string command_id
string mission_id
string asset_id
uint64 observed_queue_revision
string reason
---
uint32 schema_version
bool accepted
string task_id
uint64 state_revision
uint64 queue_revision
string error_code
string error_message

# ReplanMission.srv
uint32 SCHEMA_VERSION=1
uint32 schema_version
string command_id
string mission_id
uint64 observed_queue_revision
string reason
---
uint32 schema_version
bool accepted
uint64 state_revision
uint64 queue_revision
string error_code
string error_message

# RequestReinspection.srv
uint32 SCHEMA_VERSION=1
uint32 schema_version
string command_id
string mission_id
string asset_id
uint64 observed_queue_revision
string reason
---
uint32 schema_version
bool accepted
string task_id
uint64 state_revision
uint64 queue_revision
string error_code
string error_message
```

三者仅在当前 mission、非紧停和精确 `observed_queue_revision` 下受理。优先巡检只提升或创建可达的 `TYPE_INSPECT_ASSET` 安全观察任务；复检总是创建新的任务 UUID，不得重置或改写已 terminal task；显式重规划只重新计算已排队任务，遵守 `minimum_active_hold_s`/`normal_replan_cooldown_s`，除 emergency bypass 外不能取消当前 active task。未知资产、terminal mission、旧 revision、不可达观察点或安全约束失败分别使用 `ASSET_NOT_FOUND`、`INVALID_STATE_TRANSITION`、`QUEUE_REVISION_MISMATCH`、`GOAL_*` 或 `NAVIGATION_UNAVAILABLE`。

`srv/EditInspectionTask.srv`

```text
uint32 SCHEMA_VERSION=1

uint32 schema_version
string command_id
string mission_id
string task_id
uint64 observed_queue_revision
bool replace_goal
geometry_msgs/PoseStamped goal
bool replace_base_priority
int32 base_priority
string reason
---
uint32 schema_version
bool accepted
uint64 state_revision
uint64 queue_revision
string error_code
string error_message
```

请求至少一个 `replace_*` 为 true；没有替换的字段仍必须使用 ROS 默认值但不得读取。只能编辑 QUEUED、非 emergency 自动任务，且 `goal` 必须通过与 `QueueNavigationGoal` 相同的 frame、四元数、occupancy、资产碰撞体、危险区与安全距离验证。编辑不得修改 task_id、command_id、asset_id、type、attempt 或已记录风险；`base_priority` 范围为配置声明的 `[-1000,1000]`。active、terminal、emergency 或 stale queue 依次返回 `TASK_NOT_EDITABLE`、`TASK_TERMINAL`、`EMERGENCY_TASK_PROTECTED` 或 `QUEUE_REVISION_MISMATCH`。

`srv/AcknowledgeAlert.srv`

```text
uint32 SCHEMA_VERSION=1

uint32 schema_version
string command_id
string alert_id
uint64 observed_risk_revision
uint64 observed_alert_revision
string note
---
uint32 schema_version
bool accepted
uint64 risk_revision
uint64 alert_revision
string error_code
string error_message
```

确认仅接受当前或已归档、属于当前/已结束 run 的 alert，两个 observed revision 必须精确匹配；note 长度 1～256。它不改变风险分数、级别、队列或 e-stop。不存在 alert、旧 revision 或存储不可写分别返回 `ALERT_NOT_FOUND`、`ALERT_REVISION_MISMATCH`、`AUDIT_STORAGE_UNAVAILABLE`。

`srv/ReconnectNoncriticalService.srv`

```text
uint32 SCHEMA_VERSION=1

uint32 schema_version
string command_id
string service_name
string reason
---
uint32 schema_version
bool accepted
string service_name
string health_state
string error_code
string error_message
```

allowlist 逐字固定为 `perception_safety`、`perception_equipment`、`perception_fault`、`meter_reader`、`report_generator`。它只能要求 maintenance supervisor 重连/重启该受限非关键服务，绝不重启 mission、risk、Nav2、Gazebo、Gateway、Nginx、evidence_store、DDS 或 e-stop 路径。名单外返回 `SERVICE_RECONNECT_FORBIDDEN`，服务不存在返回 `SERVICE_NOT_FOUND`，健康检查未恢复返回 `SERVICE_RECONNECT_FAILED`。

`srv/RecordRunTimeMapping.srv` 与 `srv/QueryRunTimeMapping.srv`

```text
# RecordRunTimeMapping.srv
uint32 SCHEMA_VERSION=1
uint32 schema_version
string run_id
uint64 context_revision
int32 anchor_ros_sec
uint32 anchor_ros_nanosec
string anchor_utc
---
uint32 schema_version
bool accepted
string error_code
string error_message

# QueryRunTimeMapping.srv
uint32 SCHEMA_VERSION=1
uint32 schema_version
string run_id
---
uint32 schema_version
bool found
uint64 context_revision
int32 anchor_ros_sec
uint32 anchor_ros_nanosec
string anchor_utc
string error_code
string error_message
```

`anchor_utc` 必须是 canonical six-place RFC 3339 UTC；record 只接受 ACTIVE RunContext 的精确 run/revision。evidence store 是唯一写入者，Gateway 只调用 Service；相同记录幂等，不同记录固定失败 `TIME_MAPPING_CONFLICT`。

`srv/StoreEvidence.srv`、`srv/FreezeEvidence.srv`、`srv/QueryEvidence.srv` 与 `srv/ReadEvidenceChunk.srv`

```text
# StoreEvidence.srv
uint32 SCHEMA_VERSION=1
uint32 schema_version
string evidence_id
string run_id
uint64 context_revision
string media_type
string content_sha256
string metadata_canonical_json
string source_topic
int32 source_ros_sec
uint32 source_ros_nanosec
string source_frame_id
string source_message_type
uint32 source_index
uint8[] content
---
uint32 schema_version
bool accepted
uint64 evidence_revision
string error_code
string error_message

# FreezeEvidence.srv
uint32 SCHEMA_VERSION=1
uint32 schema_version
string evidence_id
string run_id
uint64 context_revision
string source_topic
int32 source_ros_sec
uint32 source_ros_nanosec
string source_frame_id
string content_sha256
string metadata_canonical_json
uint8[] jpeg
---
uint32 schema_version
bool accepted
uint64 evidence_revision
string error_code
string error_message

# QueryEvidence.srv
uint32 SCHEMA_VERSION=1
uint32 schema_version
string evidence_id
---
uint32 schema_version
bool found
string run_id
uint64 context_revision
uint64 evidence_revision
string media_type
string content_sha256
uint64 size_bytes
string metadata_canonical_json
string error_code
string error_message

# ReadEvidenceChunk.srv
uint32 SCHEMA_VERSION=1
uint32 schema_version
string evidence_id
uint64 offset_bytes
uint32 max_bytes
---
uint32 schema_version
bool found
uint64 size_bytes
string content_sha256
uint8[] content
bool eof
string error_code
string error_message
```

`media_type` 只允许 `image/jpeg`、`application/json`、`application/pdf`、`application/zip`、`text/html`；其中 `text/html` 只用于 report generator 提交 `GenerateReport.formats` 中的 HTML 报告，不能用于任意 Web 内容。`content_sha256` 是 64 个小写十六进制字符，metadata 必须是 RFC 8785 canonical object JSON，`max_bytes` 范围 1～1048576。Store/Freeze 必须原子校验内容摘要、标准消息归属字段和 RunContext 后写入内容与 metadata；只有 `substation_reporting/evidence_store` 写对象、`evidence.sqlite3` 或最终目录。`FreezeEvidence` 只接受 JPEG SOI/EOI、camera topic 和当前 Gateway 已验的 frame；相同 evidence_id/内容/metadata 幂等，不同值为 `EVIDENCE_ID_CONFLICT`。Query/Read 从不泄露文件路径；Gateway 仅用它们实现只读 metadata 和 Range 下载。

`srv/GetReportingReadiness.srv`、`srv/GenerateReport.srv` 与 `srv/GenerateDiagnosticBundle.srv`

```text
# GetReportingReadiness.srv
uint32 SCHEMA_VERSION=1
uint32 schema_version
---
uint32 schema_version
bool evidence_store_writable
bool report_generator_ready
bool time_mapping_ready
string error_code
string error_message

# GenerateReport.srv
uint32 SCHEMA_VERSION=1
uint32 schema_version
string command_id
string run_id
string mission_id
string[] formats
---
uint32 schema_version
bool accepted
string report_id
string error_code
string error_message

# GenerateDiagnosticBundle.srv
uint32 SCHEMA_VERSION=1
uint32 schema_version
string command_id
string run_id
string reason
---
uint32 schema_version
bool accepted
string diagnostic_id
string error_code
string error_message
```

formats 只能为非空、去重并按字典序的 `html`、`pdf`、`evidence`。report_generator 只在自己的工作目录生成内容，evidence store 校验摘要并原子发布/index；两进程和 Gateway 不能写同一 SQLite 表。readiness 的任一 false 使 start/resume、freeze、报告或诊断生成拒绝 `AUDIT_STORAGE_UNAVAILABLE` 或 `REPORTING_UNAVAILABLE`；已存在文件仍可由 Query/Read 下载。诊断 bundle 必含运行日志索引、服务状态、Git/manifest/模型摘要、rosbag2 引用和 SHA-256，不得包含 token、私钥或原始数据库写入口。

### 4.3 Action

`action/ExecuteInspection.action`

```text
uint32 SCHEMA_VERSION=1

uint32 schema_version
std_msgs/Header header
string command_id
string run_id
string mission_id
string route_id
uint64 state_revision
uint64 queue_revision
substation_interfaces/InspectionTask[] tasks
bool continue_on_unreachable
---
uint8 RESULT_SUCCEEDED=0
uint8 RESULT_STOPPED=1
uint8 RESULT_FAILED=2
uint8 RESULT_CANCELLED=3

uint32 schema_version
string command_id
string mission_id
uint8 result_state
uint32 completed_tasks
uint32 skipped_tasks
string error_code
string error_message
---
uint8 MISSION_RUNNING=2
uint8 MISSION_PAUSED=3
uint8 MISSION_STOPPING=4

uint32 schema_version
builtin_interfaces/Time stamp
string command_id
string mission_id
uint8 mission_state
string active_task_id
float32 progress_0_1
uint64 state_revision
uint64 queue_revision
```

Gateway 的 `start` 请求只调用 `ManageMission`；任务管理器建立队列后，把完整任务快照作为此 Action goal 发给同包的巡检执行器。goal `header.frame_id="map"`、stamp 是 state_revision/queue_revision 快照形成的 ROS time，route/run/mission/revision 和 tasks 必须与同 revision 的 `InspectionTaskArray` 一致。风险变化导致后续顺序改变时，任务管理器取消旧的内部 Action goal，并以相同 run_id/mission_id、最新 header/revision/task 快照发送替代 goal；这不产生新的操作员 command。巡检执行器对每个任务调用标准 `/navigate_to_pose` `nav2_msgs/action/NavigateToPose`。暂停取消当前 Nav2 goal 但保留队列；停止取消内部 Action；返航创建最高优先级 `TYPE_RETURN_HOME` 任务。Nav2 的局部避障职责不变。

## 5. TF 契约

### 5.1 树、所有者与语义

```text
map                                      (SLAM 或 AMCL，二选一)
├── odom                                 (定位融合节点；动态)
│   └── base_footprint                   (底盘平面里程计；动态)
│       └── base_link                    (robot_state_publisher；静态 z/roll/pitch 偏移)
│           ├── camera_link              (robot_state_publisher；静态)
│           │   └── camera_optical_frame (robot_state_publisher；静态 REP-103 optical)
│           └── laser_frame              (robot_state_publisher；静态)
└── asset/<asset_id>                     (资产静态广播器；按已配置资产重复该模式)
```

| 变换 | 唯一所有者 | 约束 |
|---|---|---|
| `map -> odom` | SLAM 运行时由 SLAM 拥有；预建地图运行时由 AMCL/定位拥有，不能同时广播 | 允许全局定位修正跳变；10 Hz 或每次修正立即发。 |
| `odom -> base_footprint` | 底盘里程计/定位融合节点 | 必须连续、不得因全局定位跳变重置；30 Hz。`base_footprint` 的 z、roll、pitch 为 0。 |
| `base_footprint -> base_link` | `robot_state_publisher` | 来自 URDF/Xacro 的静态底盘高度与姿态。 |
| `base_link -> camera_link` | `robot_state_publisher` | 来自 URDF/Xacro 标定，运行中不得由感知节点改写。 |
| `camera_link -> camera_optical_frame` | `robot_state_publisher` | 遵循 REP-103：optical frame 的 z 向前、x 向右、y 向下。 |
| `base_link -> laser_frame` | `robot_state_publisher` | 来自 URDF/Xacro 标定。LaserScan 使用该 frame。 |
| `map -> asset/<asset_id>` | `substation_description` 配置驱动的资产静态广播器 | pose 唯一来源是版本控制配置，frame 名中的 asset_id 必须已注册。 |

每个 child frame 在一个运行模式中只能有一个广播者。禁止 `map -> base_link` 捷径、`odom -> asset/*`、以视觉观测移动静态资产 frame、以 `Time(0)` 代替有证据时间的精确查询，或让 Gateway/前端广播 TF。

### 5.2 时间容差与失败行为

- 传感/检测关联必须查询消息 stamp 的 TF。相机、检测、环境和资产观测允许使用不早于消息 0.1 s 的最近变换；LiDAR、里程计和导航安全校验允许的最大过去外推为 0.05 s。任何业务链均不得使用超过消息时间 0.02 s 的未来变换。
- 静态变换不受年龄限制。动态变换超过上述容差、TF 树断开或 frame 不匹配时，该样本标记为 STALE/无效并从风险新增证据中排除；不得静默改用最新 pose。
- Gateway 对外 pose 的 source stamp 必须是成功组成 `map -> base_link` 时的 ROS 时间。若最近一份可用 pose 已老于 0.5 s，`robot.state.stale=true`，停止接受普通移动命令；紧急停止仍必须可用。
- `/digital_twin/assets` 和资产 REST pose 永远在 `map`。资产 pose 由描述配置创作和评审；运行时数字孪生只更新状态、风险和证据引用，不更新几何真值。

## 6. HTTP 通用契约

### 6.1 传输与媒体类型

产品 API 基础路径固定为 `/api/v1`，由 Nginx 同源代理到只监听 `127.0.0.1` 的 Gateway。JSON 请求必须是 UTF-8 `application/json`，JSON 成功响应是 `application/json`，错误是 `application/problem+json`。未知 JSON 字段在 schema 1 中返回 422，防止拼写错误被忽略。请求体上限 64 KiB；超限返回 413 `REQUEST_TOO_LARGE`，错误媒体类型返回 415 `UNSUPPORTED_MEDIA_TYPE`。报告下载不受此请求体限制。

列表分页使用 `limit` 和 `cursor`；`limit` 默认为 50、范围 1～100，`cursor` 是服务器生成的 opaque base64url 字符串，客户端不得解析。所有字符串去除首尾空白后验证；原因/备注最长 256 个 Unicode code point。所有控制响应和错误返回 `Cache-Control: no-store`；快照响应返回 ETag，报告文件返回内容 SHA-256 ETag。

### 6.2 快照成功外壳

除 health/readiness、命令查询和二进制下载外，所有 GET 快照使用：

```json
{
  "schema_version": "1.0",
  "run_id": "f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f",
  "snapshot_revision": "1842",
  "generated_at": "2026-07-22T14:03:05.123456Z",
  "data": {}
}
```

系统未开始 run 时 `run_id` 为 `null`、revision 仍为当前 Gateway 进程的系统快照 revision；进入 run 后按第 2.5 节规则重置为 1。数组顺序在各 endpoint 中明确，不允许依赖数据库偶然顺序。

### 6.3 控制受理、幂等与命令查询

所有 POST 控制请求必须携带 `Idempotency-Key`，值为客户端生成的规范 UUID 字符串。Gateway 严格按以下 gate 顺序处理：

1. Content-Type、64 KiB 上限和 JSON 语法；失败分别返回 415、413 或 400 `BAD_REQUEST`。
2. Idempotency-Key 存在且是规范 UUID；缺失/非法返回 400 `IDEMPOTENCY_KEY_REQUIRED`/`INVALID_IDEMPOTENCY_KEY`。
3. 对象 schema 与 unknown-field 校验前，计算 RFC 8785 canonical JSON SHA-256，并查询 `(HTTP method, 规范化 route, Idempotency-Key)`。

第 1～2 步失败时 `command_id=null`，不得创建命令记录、幂等记录或 rejected 状态；只允许无请求体的访问日志/trace_id。第 3 步发现相同 key 已绑定不同摘要时返回 409 `IDEMPOTENCY_KEY_REUSED`、`command_id=null`，保留原记录且不创建新命令。相同 key、method、route 和摘要在 24 小时内返回完全相同的原始状态码和响应体，并加 `Idempotent-Replayed: true`；对象 key 顺序和无意义空白不影响摘要，也不重复调用 ROS。

只有三个 gate 全部通过且 key 未占用时，Gateway 才原子生成 `command_id`、预留幂等记录并执行字段/状态/安全校验。合法请求返回 202；此后的业务校验失败返回带 command_id 的 RFC 7807，并保存 terminal `rejected`，以便同 key 重放和命令查询。Idempotency 持久化不可用时，除紧急停止外返回 503 `AUDIT_STORAGE_UNAVAILABLE`、`command_id=null` 且不调用 ROS；紧急停止改用进程内幂等表生成 command_id 并继续走优先安全路径，同时产生系统降级事件。

202 响应体固定为：

```json
{
  "schema_version": "1.0",
  "command_id": "3181ea52-0d8b-4ab0-b2d0-c1c845ac33d2",
  "status": "accepted",
  "accepted_at": "2026-07-22T14:03:05.123456Z",
  "status_url": "/api/v1/commands/3181ea52-0d8b-4ab0-b2d0-c1c845ac33d2"
}
```

#### `GET /api/v1/commands/{command_id}` — `commands.lookup`

无请求体；path 参数必须是规范 UUID，否则返回 422 `VALIDATION_FAILED`。存在时返回 200：

```json
{
  "schema_version": "1.0",
  "command_id": "3181ea52-0d8b-4ab0-b2d0-c1c845ac33d2",
  "run_id": "f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f",
  "kind": "navigation.goal",
  "status": "executing",
  "created_at": "2026-07-22T14:03:05.100000Z",
  "accepted_at": "2026-07-22T14:03:05.123456Z",
  "started_at": "2026-07-22T14:03:05.180000Z",
  "completed_at": null,
  "result": null,
  "error": null
}
```

`run_id` 在活动 run 中为 UUID，在 run 建立前的紧急停止可为 null。`kind` 固定为 `mission.start|mission.pause|mission.resume|mission.stop|mission.return_home|mission.task_edit|mission.replan|navigation.goal|robot.mode|robot.manual_velocity|robot.emergency_stop|robot.emergency_stop_reset|asset.prioritize|asset.reinspect|alert.acknowledge|evidence.freeze|service.reconnect|simulation.scenario|diagnostic.generate` 之一；path 中的 `return-home` 在 kind 中规范化为 `return_home`。只有在 path action 本身无法映射时，被拒绝记录的 kind 为 `unknown`。`status` 只能是 `accepted`、`executing`、`succeeded`、`failed`、`timed_out`、`cancelled` 或 `rejected`。尚未发生的 `accepted_at`、`started_at`、`completed_at` 为 null。不存在返回 404 `COMMAND_NOT_FOUND`。命令记录至少保存到所属 run 的报告和证据保留期结束；无 run 的安全命令按系统审计保留策略保存。

### 6.4 RFC 7807 错误

所有非 2xx/304 错误使用 RFC 7807：

```json
{
  "type": "http://ros-server/problems/goal-in-hazard-zone",
  "title": "Navigation goal is inside a hazard zone",
  "status": 422,
  "detail": "Goal intersects hazard zone hz-transformer-01.",
  "instance": "/api/v1/navigation/goal",
  "code": "GOAL_IN_HAZARD_ZONE",
  "trace_id": "75d1a54e-bb49-48e1-a74a-74d6b576de45",
  "command_id": "1ebfdb5b-fcf6-4075-80c6-8cf6cc86d4c7",
  "violations": [
    {"field": "position", "reason": "hazard_zone", "value": {"x_m": 4.2, "y_m": 1.1}}
  ]
}
```

`code` 是第 10 节稳定机器码；`title/detail` 只用于人读。GET/握手错误，以及第 6.3 节 gate 阶段错误没有命令记录，因此 `command_id` 必须为 `null`。`violations` 无字段级错误时为空数组。响应不得暴露 traceback、主机路径、SQL 或 ROS 内部对象。

## 7. REST endpoint

下列 endpoint 除各自列出的错误外，都可能返回第 6 节通用的 400、413、415、422、500；所有 POST 还可能返回幂等键相关 400/409 和审计存储 503。除非 endpoint 明确例外，成功 GET 为 200、成功控制受理为 202。

### 7.1 健康与系统状态

#### `GET /healthz` — 存活

无参数。Gateway HTTP 事件循环可响应即返回 200：

```json
{"schema_version":"1.0","status":"alive","checked_at":"2026-07-22T14:03:05.123456Z"}
```

该 endpoint 不检查 ROS、SQLite、Gazebo 或模型，不能用作巡检就绪判据。

#### `GET /readyz` — 就绪

无参数。核心 ROS 图、数字孪生、风险、任务、Nav2、审计存储和当前模式所需的 Gazebo 均可用时返回 200：

```json
{
  "schema_version": "1.0",
  "status": "ready",
  "checked_at": "2026-07-22T14:03:05.123456Z",
  "dependencies": {"ros":true,"run_context":true,"gazebo":true,"nav2":true,"storage":true,"reporting":true,"time_mapping":true,"risk":true,"mission":true}
}
```

任一强制依赖不可用返回 503 RFC 7807 `NOT_READY`，并在 `violations` 列出依赖；`storage/reporting/time_mapping` 分别来自 `/reporting/readiness` 与已持久化当前 run mapping，不能由 Gateway SQLite 代替。紧急停止本身仍不得依赖该 readiness 成功。

#### `GET /api/v1/system/status` — `system.status`

无参数；200 快照的 `data`：

```json
{
  "simulation_mode": true,
  "overall": "ready",
  "emergency_stop_latched": false,
  "run_context": {
    "lifecycle": "active",
    "context_revision": "17",
    "started_at": "2026-07-22T14:00:00.000000Z",
    "ended_at": null,
    "transition_command_id": "88973acc-85b4-4d9f-9377-0c2b0c376a04",
    "reason_code": "MISSION_STARTED",
    "reason": "operator start"
  },
  "components": [
    {
      "name": "substation_risk",
      "kind": "ros_node",
      "status": "ok",
      "message": "",
      "last_seen_at": "2026-07-22T14:03:05.000000Z"
    }
  ],
  "gpu": {"status":"ok","utilization_percent":37.0,"memory_used_bytes":2252341248,"temperature_celsius":58.0},
  "storage": {"status":"ok","free_bytes":128849018880,"audit_writable":true},
  "websocket": {"telemetry":"ok","events":"ok","camera":"ok"}
}
```

`overall` 与组件 status 只能是 `ready|degraded|unavailable` 和 `ok|degraded|error|stale`；RunContext lifecycle 为 `idle|starting|active|ending|ended`。components 按 name 排序。仅采集失败的 GPU 可空字段必须为 `null`，不能伪造 0。失败码：503 `DEPENDENCY_UNAVAILABLE` 仅在 Gateway 无法组成任何一致快照时使用；单组件故障仍返回 200 并在 data 标降级。

### 7.2 机器人、资产与任务快照

#### `GET /api/v1/robot/state` — `robot.state`

无参数；200 快照的 `data`：

```json
{
  "frame_id": "map",
  "pose": {"x_m":1.2,"y_m":2.3,"z_m":0.0,"qx":0.0,"qy":0.0,"qz":0.1,"qw":0.994987},
  "twist": {"linear_x_m_s":0.1,"linear_y_m_s":0.0,"angular_z_rad_s":0.0},
  "battery_percent": 87.0,
  "mode": "autonomous",
  "stale": false,
  "emergency_stop": {"latched":false,"latch_revision":"12"},
  "current_mission_id": "0c5efce1-655b-413d-9847-da203fb5ca5e",
  "current_task_id": "63b3e775-75cd-4443-a4a3-cc1b97ec4b3c",
  "source_ros_time": {"sec":123,"nanosec":450000000}
}
```

`mode` 为 `autonomous|manual|estop`；无当前 mission/task 时相应值为 `null`。pose 超过第 5.2 节时限仍返回最后值但 `stale=true`。失败码：503 `ROBOT_STATE_UNAVAILABLE`（从未取得合法 TF/odom）。

#### `GET /api/v1/map` — `map.snapshot`

无参数。Gateway 只消费标准 `/map` `nav_msgs/msg/OccupancyGrid` 和 `/map_updates` `map_msgs/msg/OccupancyGridUpdate`，不创建地图专有 ROS 载荷。完整快照的 `data` 为：

```json
{
  "map_revision":"143",
  "frame_id":"map",
  "source_ros_time":{"sec":123,"nanosec":450000000},
  "resolution_m":0.05,
  "width_cells":400,
  "height_cells":300,
  "origin":{"x_m":-10.0,"y_m":-7.5,"yaw_rad":0.0},
  "data_encoding":"base64-int8-row-major-v1",
  "data":"AAH/..."
}
```

`data` 解码后长度必须严格等于 `width_cells * height_cells`，每个 int8 只允许 `-1` 或 `[0,100]`，行优先顺序与 ROS `OccupancyGrid.data` 完全一致；Gateway 不得重采样、反转坐标或将 unknown 变成 free。每次完整图或已验证连续增量提交使 `map_revision` 增加，值按第 2.5.1 节作为字符串。没有完整基图、frame 不为 map、长度不符或 update 越界时返回/保持 503 `MAP_UNAVAILABLE`，不得输出猜测地图。成功响应使用一般快照外壳、ETag 与 `map_revision`；客户端以 REST 取得基图后才可接受 `map.update`。

#### `GET /api/v1/evidence/{evidence_id}` — `evidence.metadata`

path 必须为 UUID；Gateway 调用 `/reporting/query_evidence`，成功 `data` 至少为：

```json
{
  "evidence_id":"ea6992e2-4398-414d-a587-ce8b33932266",
  "run_id":"f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f",
  "context_revision":"17",
  "evidence_revision":"41",
  "media_type":"image/jpeg",
  "size_bytes":"203844",
  "content_sha256":"4f5c9f3ea8071fba9f0a663c0f0e7650e72b88d447441e4a680f49b594f894dd",
  "metadata":{"source_topic":"/perception/annotated_image","source_ros_time":{"sec":123,"nanosec":400000000},"source_frame_id":"camera_optical_frame"},
  "download_url":"/api/v1/evidence/ea6992e2-4398-414d-a587-ce8b33932266/download"
}
```

`size_bytes` 是 uint64 decimal string；metadata 是 evidence store 保存的 canonical metadata 反序列化结果，不能由 Gateway 添加或替换。不存在为 404 `EVIDENCE_NOT_FOUND`，reporting 查询不可用为 503 `EVIDENCE_STORAGE_UNAVAILABLE`。

#### `GET /api/v1/evidence/{evidence_id}/download` — `evidence.download`

此 endpoint 以 `/reporting/read_evidence_chunk` 实现第 7.7 报告下载完全相同的单 range、ETag、`X-Content-SHA256`、200/206/304/400/416 行为；filename 固定为 `evidence-<evidence_id>.<ext>`，ext 从 media type 唯一映射 `jpg|json|pdf|zip`。不存在为 `EVIDENCE_NOT_FOUND`，摘要/读取不一致或 reporting 不可用为 `EVIDENCE_STORAGE_UNAVAILABLE`。Gateway 从不打开 evidence 文件路径或 SQL 表。

#### `GET /api/v1/assets` — `assets.list`

查询参数：`risk_level` 可重复且只能为 `normal|attention|alert|emergency`；`category` 使用配置字符串；`limit/cursor` 按第 6.1 节。200 `data`：

```json
{
  "items": [
    {
      "asset_id": "transformer-01",
      "category": "transformer",
      "state": "attention",
      "pose": {"frame_id":"map","x_m":4.0,"y_m":2.0,"z_m":0.0,"qx":0.0,"qy":0.0,"qz":0.0,"qw":1.0},
      "measurements": {"temperature_celsius":72.4,"smoke_0_1":0.05,"gas_ppm":8.0,"meter_reading":null,"meter_unit":null},
      "risk": {"score_0_100":48.2,"level":"attention","visual_0_1":0.2,"temperature_0_1":0.7,"smoke_0_1":0.05,"gas_0_1":0.08,"context_0_1":0.3},
      "latest_evidence_id": "ea6992e2-4398-414d-a587-ce8b33932266",
      "observed_at": "2026-07-22T14:03:04.900000Z",
      "stale": false
    }
  ],
  "next_cursor": null
}
```

按 `asset_id` 升序后分页；未知 category/risk_level 返回 422 `VALIDATION_FAILED`，cursor 失效返回 400 `INVALID_CURSOR`。

#### `GET /api/v1/missions/current` — `mission.current`

无参数；没有 mission 也返回 200，`data.mission_id=null`、`route_id=null`、state=`idle`、`queue_revision="0"`、tasks 为空数组。`state_revision` 和 transition 字段仍映射权威 `InspectionTaskArray`，模式与紧停锁存分别由 `/api/v1/robot/state` 暴露；从未发生独立安全转换时 transition_command_id 为 null、transition_reason_code=`NO_ACTIVE_RUN`。活动时 `data`：

```json
{
  "mission_id": "0c5efce1-655b-413d-9847-da203fb5ca5e",
  "route_id": "default-route",
  "state": "running",
  "state_revision": "63",
  "queue_revision": "42",
  "transition_command_id": "e1e1925a-6f51-4a24-b249-fc35ed5a53c0",
  "transition_reason_code": "TASK_STARTED",
  "transition_reason": "inspection task entered active state",
  "active_task_id": "63b3e775-75cd-4443-a4a3-cc1b97ec4b3c",
  "completed_tasks": 3,
  "total_tasks": 8,
  "progress_0_1": 0.375,
  "tasks": [
    {
      "task_id":"63b3e775-75cd-4443-a4a3-cc1b97ec4b3c",
      "command_id":null,
      "asset_id":"transformer-01",
      "type":"inspect_asset",
      "state":"active",
      "computed_priority":78.2,
      "risk_score_0_100":72.0,
      "goal":{"frame_id":"map","x_m":3.0,"y_m":2.0,"yaw_rad":0.0},
      "attempt":1,
      "last_error_code":null
    }
  ]
}
```

state 为 `idle|ready|running|paused|stopping|succeeded|failed|stopped`，任务顺序等于 ROS 完整队列。该 REST 对象逐字段映射权威 `InspectionTaskArray`，Gateway 不得从旧命令推导 route/state/reason；Gateway 重启后只有在 RunContext 与 mission 快照 run_id 一致且 revisions 已装载时才返回 200，否则返回 503 `MISSION_STATE_UNAVAILABLE`。

### 7.3 Mission 控制

#### `POST /api/v1/missions/{action}` — `mission.<action>`

`action` 只允许 `start|pause|resume|stop|return-home`，必须带 Idempotency-Key。请求体和同步前置条件：

| action | 请求 JSON | 同步验证 | 命令超时 |
|---|---|---|---:|
| `start` | `{"route_id":"default-route","reason":"operator start"}` | route 存在；当前 state 为 idle/ready/succeeded/failed/stopped；非紧停；数字孪生、风险、Nav2 与审计就绪 | 30 s |
| `pause` | `{"mission_id":"<uuid>","reason":"operator pause"}` | 指定 mission 是当前 mission 且 state=running | 10 s |
| `resume` | `{"mission_id":"<uuid>","reason":"operator resume"}` | state=paused；非紧停；所需依赖与审计恢复 | 10 s |
| `stop` | `{"mission_id":"<uuid>","reason":"operator stop"}` | state=ready/running/paused/stopping；重复 stop 由 Idempotency-Key 合并 | 10 s |
| `return-home` | `{"mission_id":"<uuid>","reason":"operator return"}` | 当前 mission 存在；非紧停；home 安全目标可用；state=running/paused | 300 s |

成功统一返回 202 命令受理体；最终由 `/ws/events` `command.status` 和命令查询给出。失败码：400 `INVALID_ACTION`；404 `MISSION_NOT_FOUND`/`ROUTE_NOT_FOUND`；409 `INVALID_STATE_TRANSITION`、`EMERGENCY_STOP_LATCHED`、`COMMAND_CONFLICT`；503 `NAVIGATION_UNAVAILABLE`、`AUDIT_STORAGE_UNAVAILABLE`、`DEPENDENCY_UNAVAILABLE`。

#### `POST /api/v1/robot/mode` — `robot.mode`

请求为 `{"mission_id":"<uuid-or-null>","target_mode":"manual|autonomous","observed_state_revision":"63","observed_latch_revision":"12","reason":"operator handoff"}`；两个 revision 必须按第 2.5.1 节编码并精确匹配当前快照，不能用过期页面切换模式。Gateway 仅调用 `/mission/set_robot_mode`。MANUAL 终结前必须由任务模块取消 Nav2、选择并确认 0.5 s 零速度；AUTONOMOUS 终结前必须验证非紧停、mission/地图/TF/Nav2/reporting readiness。不得通过这个 endpoint 进入或解除 ESTOP。成功受理 202，超时 10 s；失败码为 409 `STATE_REVISION_MISMATCH`、`LATCH_REVISION_MISMATCH`、`EMERGENCY_STOP_LATCHED`、`INVALID_STATE_TRANSITION`，422 `MODE_INVALID`，503 `NAVIGATION_UNAVAILABLE`、`ROBOT_STATE_UNAVAILABLE`、`AUDIT_STORAGE_UNAVAILABLE`。

#### `POST /api/v1/evidence/freeze` — `evidence.freeze`

请求为 `{"source":"camera","reason":"operator freeze"}`；只允许 source=`camera`、ACTIVE run、当前 frame 通过 JPEG/RunContext/time-mapping 校验且 reporting readiness 完整。Gateway 生成 evidence_id，并将当前带框帧、source topic/header/frame、摘要与 canonical metadata 调用 `/reporting/freeze_evidence`；它不得写 SQLite 或文件。成功受理 202、超时 10 s，最终返回/事件 result 含 evidence_id、evidence_revision 和 content_sha256。失败码：409 `RUN_CONTEXT_MISMATCH`、`CAMERA_FRAME_UNAVAILABLE`，422 `EVIDENCE_SOURCE_INVALID`，503 `TIME_MAPPING_UNAVAILABLE`、`EVIDENCE_STORAGE_UNAVAILABLE`、`AUDIT_STORAGE_UNAVAILABLE`。

#### `POST /api/v1/assets/{asset_id}/prioritize` — `asset.prioritize`

请求 `{"mission_id":"<uuid>","observed_queue_revision":"42","reason":"inspect transformer first"}`。Gateway 调 `/mission/prioritize_asset`，只允许当前 running/paused mission、非紧停和配置资产。成功受理 202、超时 10 s；最终需要 matching command_id 的完整队列含返回 task_id 且其 computed priority 已按排序契约应用。失败码：404 `ASSET_NOT_FOUND`/`MISSION_NOT_FOUND`，409 `QUEUE_REVISION_MISMATCH`、`EMERGENCY_STOP_LATCHED`、`INVALID_STATE_TRANSITION`，422 `ASSET_NOT_INSPECTABLE`，503 `NAVIGATION_UNAVAILABLE`。

#### `POST /api/v1/missions/{mission_id}/tasks/{task_id}/edit` — `mission.task_edit`

请求含 `observed_queue_revision`、至少一个 `replace_goal`/`replace_base_priority` 与 `reason`；replace_goal 为 true 时 goal 精确使用 navigation.goal 的 `frame_id`、position/yaw schema，replace_base_priority 为 true 时给出整数 `base_priority`。Gateway 调 `/mission/edit_inspection_task`；成功 202、超时 10 s，最终 matching task 的同一 task_id 具有返回的 revision 和请求字段。失败码：404 `MISSION_NOT_FOUND`/`TASK_NOT_FOUND`，409 `QUEUE_REVISION_MISMATCH`、`TASK_NOT_EDITABLE`、`TASK_TERMINAL`、`EMERGENCY_TASK_PROTECTED`，422 `TASK_EDIT_EMPTY`、`GOAL_*`、`INVALID_ORIENTATION`、`PRIORITY_OUT_OF_RANGE`，503 `NAVIGATION_UNAVAILABLE`。

#### `POST /api/v1/missions/{mission_id}/replan` — `mission.replan`

请求为 `{"observed_queue_revision":"42","reason":"operator route replan"}`。Gateway 调 `/mission/replan`，任务模块按第 4.1 节 hold/cooldown 合并或应用。成功受理 202、超时 10 s；若冷却尚未结束，matching command 只能在冷却届满且 revision/queue 真实变化后 succeeded，不能把“已排队”误报成功。失败码：404 `MISSION_NOT_FOUND`，409 `QUEUE_REVISION_MISMATCH`、`EMERGENCY_STOP_LATCHED`、`INVALID_STATE_TRANSITION`，503 `NAVIGATION_UNAVAILABLE`。

#### `POST /api/v1/alerts/{alert_id}/acknowledge` — `alert.acknowledge`

请求 `{"observed_risk_revision":"72","observed_alert_revision":"9","note":"operator reviewed"}`。Gateway 调 `/risk/acknowledge_alert`；成功受理 202、超时 10 s，终态须是 matching `/risk/alert_acknowledgements` event 与递增 alert_revision。确认不解除告警、不改变风险或停止既有安全动作。失败码：404 `ALERT_NOT_FOUND`，409 `RISK_REVISION_MISMATCH`、`ALERT_REVISION_MISMATCH`，422 `ALERT_NOTE_INVALID`，503 `AUDIT_STORAGE_UNAVAILABLE`。

#### `POST /api/v1/assets/{asset_id}/reinspect` — `asset.reinspect`

请求 `{"mission_id":"<uuid>","observed_queue_revision":"42","reason":"confirm after alert"}`。Gateway 调 `/mission/request_reinspection`；成功受理 202、超时 300 s，终态是新 task_id（不得复用先前 terminal task）在 matching queue 中完成 SUCCEEDED。失败码同 asset.prioritize，外加 409 `COMMAND_CONFLICT`；失败/取消沿 task terminal 状态归类。

#### `POST /api/v1/services/{service_name}/reconnect` — `service.reconnect`

请求 `{"reason":"operator maintenance reconnect"}`。仅 allowlist `perception_safety|perception_equipment|perception_fault|meter_reader|report_generator` 可受理，Gateway 只能调 `/maintenance/reconnect_noncritical_service`。成功受理 202、超时 30 s；最终需要 matching command_id 的 `/diagnostics` health 为 ok 且 Gateway 取得该组件的新 ready observation。失败码：403 `SERVICE_RECONNECT_FORBIDDEN`，404 `SERVICE_NOT_FOUND`，409 `SERVICE_RECONNECT_IN_PROGRESS`，503 `SERVICE_RECONNECT_FAILED`。本 endpoint 永不重启任何安全关键组件或 Foxglove。

### 7.4 导航与手动速度

#### `POST /api/v1/navigation/goal` — `navigation.goal`

请求：

```json
{
  "mission_id": "0c5efce1-655b-413d-9847-da203fb5ca5e",
  "frame_id": "map",
  "position": {"x_m": 3.4, "y_m": 5.6},
  "yaw_rad": 1.570796,
  "reason": "operator map click"
}
```

必须带 Idempotency-Key；frame 只能是 `map`，坐标有限，yaw 在规范范围；mission 必须是当前 mission 且 state 为 running/paused，模式为 autonomous，未紧停。任务模块再验证地图边界、可通行栅格、膨胀后资产碰撞体、危险区域和预设安全距离。成功 202，超时 300 s；Gateway 调 `/mission/queue_navigation_goal`，绝不直调 NavigateToPose。失败码：404 `MISSION_NOT_FOUND`；409 `MANUAL_MODE_ACTIVE`、`EMERGENCY_STOP_LATCHED`、`INVALID_STATE_TRANSITION`；422 `GOAL_OUTSIDE_MAP`、`GOAL_OCCUPIED`、`GOAL_IN_ASSET_COLLISION`、`GOAL_IN_HAZARD_ZONE`、`INVALID_ORIENTATION`；503 `NAVIGATION_UNAVAILABLE`。

#### `POST /api/v1/robot/manual-velocity` — `robot.manual_velocity`

请求：

```json
{
  "linear_x_m_s": 0.2,
  "angular_z_rad_s": -0.3,
  "deadman": true,
  "duration_s": 0.15
}
```

必须带 Idempotency-Key；只在 `mode=manual`、ACTIVE RunContext、非紧停、robot state 非 stale 时接受。`linear_x_m_s` 范围 `[-0.4,0.4]`，`angular_z_rad_s` 范围 `[-0.8,0.8]`，`duration_s` 为有限数且范围 `[0.05,0.25]`，非零速度要求 `deadman=true`。每个浏览器会话最高 10 请求/s；命令 1 s 超时。Gateway 在发布瞬间从同一最新 ACTIVE RunContext 复制 run_id/context_revision，与同一 command_id 一起写入 `ManualVelocityCommand` 并发布到 `/cmd_vel_manual`，不得发布裸 `Twist`；若上下文在仲裁器接收前变化，仲裁器必须拒绝而不能把命令归入新 run。

仲裁器以收到消息时的进程 monotonic/steady clock 加 duration_s 形成唯一执行 deadline。校验通过且 twist 至少一次成为最终 `/cmd_vel` 时发布 APPLIED；deadline 到达后立即选择零速度，若此前从未 APPLIED 则发布 EXPIRED，已经 APPLIED 则只自动归零且不创建新 command。松键、浏览器失焦、WebSocket 心跳丢失、进程断线、紧停或模式切换会更早取消尚未 APPLIED 的请求并发布 CANCELLED。Gateway 收到 `/mission/manual_velocity_status` 后才按第 9.4 节终结 REST 命令。成功受理为 202；失败码：409 `MANUAL_MODE_REQUIRED`、`EMERGENCY_STOP_LATCHED`、`RUN_CONTEXT_MISMATCH`；422 `VELOCITY_LIMIT_EXCEEDED`、`DEADMAN_REQUIRED`；429 `MANUAL_COMMAND_RATE_EXCEEDED`；503 `ROBOT_STATE_UNAVAILABLE`。

### 7.5 紧急停止与复位

#### `POST /api/v1/robot/emergency-stop` — `robot.emergency_stop`

请求 `{"reason":"operator emergency stop"}`，reason 必填。必须带 Idempotency-Key，但该路径不要求 readiness、当前 mission、Nav2 或 SQLite 可用；Gateway 优先调用 ROS 安全 Service。成功 202，命令超时 2 s。重复调用在任务模块侧保持已锁存并成功返回。若 ROS 确认超时，命令为 `timed_out`，UI 必须继续显示“紧停状态未知/按已锁存处理”，禁用普通控制，直到 REST/ROS 状态明确；不能因超时推断机器人未停止。失败仅限 422 `VALIDATION_FAILED` 或 503 `EMERGENCY_STOP_PATH_UNAVAILABLE`。

#### `POST /api/v1/robot/emergency-stop/reset` — `robot.emergency_stop_reset`

请求：

```json
{
  "observed_latch_revision": "13",
  "confirm": true,
  "reason": "area verified clear"
}
```

必须带 Idempotency-Key；reason 必填，revision 必须等于最新 `/api/v1/robot/state`，confirm 必须为 true。Gateway/任务模块执行第 4.2 节全部安全前置条件。成功受理为 202，命令超时 5 s；成功后模式为 manual、旧 mission 不自动恢复。失败码：409 `EMERGENCY_STOP_NOT_LATCHED`、`LATCH_REVISION_MISMATCH`、`EMERGENCY_STOP_RESET_UNSAFE`；422 `RESET_CONFIRMATION_REQUIRED`；503 `AUDIT_STORAGE_UNAVAILABLE`、`EMERGENCY_STOP_PATH_UNAVAILABLE`。

### 7.6 仿真场景

#### `POST /api/v1/simulation/scenario` — `simulation.scenario`

请求：

```json
{
  "scenario_id": "gas-high",
  "action": "trigger",
  "parameters": {"asset_id":"transformer-01","value_ppm":180.0},
  "reason": "acceptance scenario 5"
}
```

必须带 Idempotency-Key；只在 `simulation_mode=true` 且 RunContext ACTIVE 时显示和接受。action 为 `start|trigger|reset`；scenario_id 必须存在；parameters 必须是该场景配置 allowlist 内的标量键值，不能传文件路径、ROS 名称或任意代码。Gateway 使用第 3.4 节标准参数服务，成功受理为 202、命令超时 30 s；最终以 `/simulation/scenario_state` 的 matching command_id 确认。失败码：403 `SIMULATION_MODE_REQUIRED`；404 `SCENARIO_NOT_FOUND`；409 `SCENARIO_CONFLICT`、`RUN_CONTEXT_MISMATCH`；422 `SCENARIO_ACTION_INVALID`、`SCENARIO_PARAMETER_INVALID`；503 `GAZEBO_UNAVAILABLE`。

### 7.7 报告

#### `GET /api/v1/reports` — `reports.list`

查询参数：`run_id`、`mission_id` 为可选 UUID；`status` 为 `generating|ready|failed`；`from`/`to` 为 RFC 3339 UTC 且 from≤to；`limit/cursor` 按通用规则。200 `data`：

```json
{
  "items": [
    {
      "report_id":"74727656-b320-4fe8-9a14-6de3c0094f08",
      "run_id":"f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f",
      "mission_id":"0c5efce1-655b-413d-9847-da203fb5ca5e",
      "status":"ready",
      "created_at":"2026-07-22T14:20:00.000000Z",
      "completed_at":"2026-07-22T14:20:02.000000Z",
      "formats":["html","pdf","evidence"],
      "download_urls": {
        "html":"/api/v1/reports/74727656-b320-4fe8-9a14-6de3c0094f08/download?format=html",
        "pdf":"/api/v1/reports/74727656-b320-4fe8-9a14-6de3c0094f08/download?format=pdf",
        "evidence":"/api/v1/reports/74727656-b320-4fe8-9a14-6de3c0094f08/download?format=evidence"
      },
      "sha256": {"html":"4f5c9f3ea8071fba9f0a663c0f0e7650e72b88d447441e4a680f49b594f894dd","pdf":"6d3557f4b074d722734ae44a9d8e659df33404d3bce13cdb679780aed44d8788","evidence":"591025894a28dc42b2d4f0293fe7e1cc6ae64128ee753186c96223e21fb99c6c"}
    }
  ],
  "next_cursor": null
}
```

排序固定为 `created_at` 降序、report_id 升序。失败码：400 `INVALID_CURSOR`；422 `VALIDATION_FAILED`；503 `REPORT_INDEX_UNAVAILABLE`。

#### `GET /api/v1/reports/{report_id}/download` — `reports.download`

`format` 必填且为 `html|pdf|evidence`。ready 文件的媒体类型分别为 HTML `text/html; charset=utf-8`、PDF `application/pdf`、证据包 `application/zip`；digest 必须匹配 `^[0-9a-f]{64}$`。所有成功文件响应都含 `Accept-Ranges: bytes`、`Content-Disposition: attachment; filename="inspection-<report_id>.<ext>"`、强 ETag `"sha256:<digest>"` 和 `X-Content-SHA256: <digest>`：

- 无 Range（或 `If-Range` 与当前 ETag 不匹配）返回 200 完整文件，`Content-Length=<total>`，不得发送 `Content-Range`。匹配的 `If-None-Match` 且无 Range 返回 304、无 body。
- 只支持一个 `bytes=start-end`、`bytes=start-` 或 `bytes=-suffix_length`。语法合法、可满足，且 If-Range 缺失或匹配当前 ETag时返回 206；`Content-Range: bytes <actual_start>-<actual_end>/<total>`，`Content-Length=<actual_end-actual_start+1>`，body 只含该区间。
- malformed、负数、end<start 或多 range 返回 400 RFC 7807 `INVALID_RANGE`，不发送文件字节。
- 语法合法但 start≥total 或 suffix_length=0 返回 416 RFC 7807 `RANGE_NOT_SATISFIABLE`，必须含 `Accept-Ranges: bytes` 和 `Content-Range: bytes */<total>`；`Content-Type`/`Content-Length` 描述 problem JSON，不得描述文件或返回部分文件。

其他失败码：404 `REPORT_NOT_FOUND`/`REPORT_FORMAT_NOT_FOUND`；409 `REPORT_NOT_READY`；503 `REPORT_STORAGE_UNAVAILABLE`。下载错误始终用 RFC 7807，不返回部分 HTML 错误页。

### 7.8 诊断包

#### `POST /api/v1/diagnostics/bundles` — `diagnostic.generate`

请求 `{"reason":"operator support bundle"}`，只在 reporting readiness 完整时受理。Gateway 调 `/reporting/generate_diagnostic_bundle`；report_generator 在受控 work 目录生成，evidence_store 验证摘要并原子发布。成功 202、超时 60 s，终态 result 至少含 `diagnostic_id`、`run_id`、`content_sha256` 与 size_bytes（uint64 decimal string）；仅 service accepted 不得成功。失败码：409 `DIAGNOSTIC_ALREADY_GENERATING`，422 `DIAGNOSTIC_REASON_INVALID`，503 `REPORTING_UNAVAILABLE`、`EVIDENCE_STORAGE_UNAVAILABLE`。

#### `GET /api/v1/diagnostics/{diagnostic_id}/download` — `diagnostic.download`

diagnostic_id 是 UUID。已 ready 的 bundle 以 `application/zip`、`Content-Disposition: attachment; filename="diagnostic-<diagnostic_id>.zip"`、强 ETag 和 `X-Content-SHA256` 下载，并使用第 7.7 的单 Range 完整语义；Gateway 通过 `/reporting/read_evidence_chunk` 或 reporting 的同一只读抽象读取。错误码为 404 `DIAGNOSTIC_NOT_FOUND`、409 `DIAGNOSTIC_NOT_READY`、503 `EVIDENCE_STORAGE_UNAVAILABLE`。包及 metadata 不得暴露 token、私钥、未脱敏连接串或任意宿主机文件。

## 8. WebSocket 契约

### 8.1 握手、公共 JSON 外壳与心跳

产品流固定为 `WS /ws/telemetry`、`WS /ws/events`、`WS /ws/camera`，必须协商子协议 `substation.v1`。Gateway 只接受同源 Host/Origin；握手前依赖不可用时返回对应 RFC 7807 HTTP 错误。每次连接生成 UUIDv4 `connection_id`；Gateway 每次进程启动生成 UUIDv4 `stream_epoch`。每个 endpoint 在该 epoch 内维护一个全局 sequence，逻辑消息分配序号后再向所有连接 fan-out，因此所有客户端看到相同数据序号。连接私有的 `stream.open` 使用 sequence=`"0"`，不进入连续性/replay 判断；其后每个数据消息和全局心跳占用一个 sequence。达到 uint64 最大值 `18446744073709551615` 前 Gateway 必须滚动到新 stream_epoch 并从 `"1"` 重新开始；文本编码始终遵守第 2.5.1 节。

三个流的所有服务器文本消息均使用：

```json
{
  "schema_version": "1.0",
  "stream": "telemetry",
  "stream_epoch": "f72b21de-d178-4cf9-8819-29f07c824adb",
  "connection_id": "57d8cf69-ff22-4c0e-bc47-24d1b9eaf539",
  "run_id": "f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f",
  "sequence": "8124",
  "snapshot_revision": "1842",
  "timestamp": "2026-07-22T14:03:05.123456Z",
  "type": "robot.state",
  "payload": {}
}
```

顶层时间字段名称必须恰好是 `timestamp`，不得使用 `sent_at`、`time` 或其他别名；值是 Gateway 发送该 envelope 的 RFC 3339 UTC。`stream` 为 `telemetry|events|camera`，`run_id` 为权威当前 run UUID、未进入 run 时为 null，`sequence` 是第 2.5.1 节的 uint64 十进制字符串。连接建立后的第一条消息 type=`stream.open`，payload 为 `{"heartbeat_interval_s":1.0,"connection_timeout_s":5.0,"replay_available":bool}`。仅 events replay 消息可增加可选顶层字段 `replayed:true`，正常消息省略该字段。服务器每 1 s 为每个 endpoint 生成一条全局 type=`heartbeat` 并 fan-out，payload 为：

```json
{
  "server_time":"2026-07-22T14:03:05.123456Z",
  "latest_data_sequence":"8123",
  "ready":true
}
```

Gateway 另外每 2 s 发送 WebSocket protocol Ping，浏览器自动 Pong。浏览器超过 5 s 未收到任何合法应用消息必须进入“连接中断”、立即发送/选择零手动速度、禁用除紧急停止外的普通控制并开始重连；服务器超过 10 s 未收到 Pong 关闭连接，close code 1001。畸形 JSON/未知主版本关闭 1003；消息过大关闭 1009；服务重启关闭 1012。紧急停止 HTTP 按钮不得依赖 WebSocket 可用。

### 8.2 `WS /ws/telemetry`

这是可丢弃的最新状态流，不是历史日志。类型、payload 和最大发送率：

| type | payload | 最大率 |
|---|---|---:|
| `robot.state` | 与 `GET /api/v1/robot/state` 的 `data` 相同 | 10 Hz |
| `map.update` | `{"base_map_revision":"143","map_revision":"144","x_cells":20,"y_cells":10,"width_cells":8,"height_cells":4,"data_encoding":"base64-int8-row-major-v1","data":"...","source_ros_time":{"sec":123,"nanosec":500000000}}`；逐字映射标准 `/map_updates`，解码长度严格等于 width×height，坐标必须位于当前 REST 基图内 | 5 Hz |
| `navigation.paths` | `{"frame_id":"map","global":[{"x_m":1.0,"y_m":2.0}],"local":[{"x_m":1.1,"y_m":2.1}],"goal":{"x_m":3.0,"y_m":4.0,"yaw_rad":0.0}}`；无 goal 时为 null | 5 Hz |
| `environment.state` | `{"assets":[{"asset_id":"transformer-01","temperature_celsius":72.4,"smoke_0_1":0.05,"gas_ppm":8.0,"observed_at":"2026-07-22T14:03:04.900000Z","stale":false}]}`；可空测量为 null，按 asset_id 排序 | 5 Hz |
| `risk.assets` | `{"risk_revision":"42","assets":[{"asset_id":"transformer-01","score_0_100":72.0,"level":"alert","visual_0_1":0.4,"temperature_0_1":0.9,"smoke_0_1":0.2,"gas_0_1":0.1,"context_0_1":0.5}]}`；按 score 降序、asset_id 升序 | 5 Hz |
| `mission.state` | 与 `GET /api/v1/missions/current` 的 `data` 相同 | 10 Hz |
| `system.health` | `GET /api/v1/system/status` 中 overall/run_context/components/websocket 子集 | 1 Hz |

Gateway 在积压时只保留每个 type 最新一条，绝不延迟堆积旧遥测。`map.update` 的 base_map_revision 必须等于客户端最后已应用 revision；任何 map revision 跳跃、decode/长度/边界失败都要求客户端先 GET `/api/v1/map`，不得拼接猜测增量。客户端检测到同一 epoch 中 `sequence` 不连续、run_id 改变或 snapshot_revision 倒退时，标记 UI stale，关闭当前连接，依次 GET `/api/v1/system/status`、`/api/v1/robot/state`、`/api/v1/assets`、`/api/v1/missions/current`、`/api/v1/map` 快照，再建立新连接。telemetry 不提供 replay，不能用 `after_sequence` 猜补差量。

### 8.3 `WS /ws/events`

事件类型固定为：

| type | payload 必需字段 |
|---|---|
| `risk.alert` | `alert_id`、`run_id`、`asset_id`、`event`（`opened`、`level_changed`、`cleared`）、`previous_level`、`current_level`、`score_0_100`、`evidence_ids` |
| `risk.alert_acknowledged` | `command_id`、`run_id`、`alert_id`、`risk_revision`、`alert_revision`、`note`；两个 revision 为 uint64 decimal string |
| `command.status` | 第 6.3 节命令对象完整字段；每次状态转换一条 |
| `mission.changed` | `mission_id`、`state`、`queue_revision`、`active_task_id`、`reason_code` |
| `evidence.frozen` | `command_id`、`evidence_id`、`run_id`、`context_revision`、`evidence_revision`、`content_sha256` |
| `diagnostic.ready` | `command_id`、`diagnostic_id`、`run_id`、`content_sha256`、`size_bytes` |
| `system.event` | `severity`（`info`、`warning`、`error`、`critical`）、`code`、`message`、`component`、`evidence_id`（可空） |
| `resync.required` | `code="WS_RESYNC_REQUIRED"`、`oldest_available_sequence`、`latest_sequence`、`snapshot_revision` |

Gateway 将事件先持久化再发送，并保留至少最近 10,000 条事件流消息（包括其间心跳）且不少于 10 分钟的内存 replay 窗口。客户端在首次/完整 REST 恢复后不带 query 连接并从 `stream.open` 后的实时消息开始；需要补缺口时使用 `/ws/events?stream_epoch=<uuid>&after_sequence=<uint64-decimal-string>`。两个 query 必须同时出现，epoch 为 UUID、sequence 为 1～18446744073709551615 且遵守第 2.5.1 节文本语法；否则握手返回 422 `VALIDATION_FAILED`：

- epoch 相同且 `after_sequence` 仍在窗口内：先按原 sequence 重放之后事件，再发实时事件；重放外壳增加 `replayed:true`。
- 带 query 时 epoch 不同或 sequence 超出窗口：服务器在 `stream.open` 后发 `resync.required`，再以 private close code 4009 关闭；客户端读取 `/api/v1/system/status`、`/api/v1/robot/state`、`/api/v1/assets`、`/api/v1/missions/current` 四个 REST 快照，并不带 query 重连。
- 客户端在实时流发现缺口时先以最后连续 sequence 重连一次；若收到 `resync.required`，执行 REST 恢复。不得跳过 command/alert 事件后继续把 UI 当作一致。

### 8.4 `WS /ws/camera` 二进制 framing

相机连接发送两类 WebSocket message：第 8.1 节 JSON 文本 `stream.open`/`heartbeat`/`resync.required`，以及一条完整 JPEG 对应的一条二进制 message。目标帧率 15 FPS；拥塞时只保留最新帧并降低帧率，绝不让视频积压影响事件、紧急停止或基础任务控制。

每个二进制 message 为固定 64-byte header、UTF-8 metadata JSON、JPEG 三段连续拼接。多字节整数使用 network byte order（big-endian）：

| Offset | 长度 | 字段 | 约束 |
|---:|---:|---|---|
| 0 | 4 | magic | ASCII `SSCF` (`0x53 0x53 0x43 0x46`) |
| 4 | 1 | framing_version | `1` |
| 5 | 1 | flags | bit 0=`annotated`; bits 1～7 必须为 0 |
| 6 | 2 | header_length | uint16，固定 64 |
| 8 | 8 | sequence | uint64，与 camera 流 JSON 消息共享序号空间 |
| 16 | 8 | snapshot_revision | uint64 |
| 24 | 4 | metadata_length | uint32，1～16384 |
| 28 | 4 | jpeg_length | uint32，1～2097152 |
| 32 | 4 | width | uint32，必须与 JPEG SOF 一致 |
| 36 | 4 | height | uint32，必须与 JPEG SOF 一致 |
| 40 | 16 | stream_epoch | UUID 的 16 个 raw bytes，等于文本外壳 UUID |
| 56 | 8 | reserved | 全 0；schema 1 客户端拒绝非 0 |

metadata 是以下 schema，未知字段按同主版本可忽略：

```json
{
  "schema_version":"1.0",
  "connection_id":"57d8cf69-ff22-4c0e-bc47-24d1b9eaf539",
  "run_id":"f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f",
  "captured_at":"2026-07-22T14:03:05.100000Z",
  "source_ros_time":{"sec":123,"nanosec":400000000},
  "ros_frame_id":"camera_optical_frame",
  "encoding":"jpeg",
  "annotated":true,
  "detections_sequence":"7712",
  "evidence_id":null
}
```

JPEG 必须以 SOI `FFD8` 开始、EOI `FFD9` 结束，且二进制 message 总长度严格等于 `64 + metadata_length + jpeg_length`。`captured_at` 是 canonical RFC 3339 UTC；header 不使用非 RFC 3339 业务时间。`detections_sequence` 是 Gateway 在当前 stream_epoch 内为其消费的 `/perception/detections` 样本分配的单调序号，必须对应生成该 annotated frame 的检测样本。操作者冻结时 Gateway 先分配 UUIDv4 evidence_id，再请求证据存储按该 ID 幂等持久化；持久化确认后 metadata 暴露同一 UUID，未冻结或持久化失败时为 null。

相机是易失流：检测到 sequence 缺口时丢弃不完整帧并显示 dropped-frame 计数，继续等待下一完整帧；重连或 stream_epoch 变化后从新帧恢复，不 replay 视频。若客户端还需要一致状态，按 telemetry 规则读取 REST 快照。metadata/JPEG 不合法时丢弃该帧；连续 3 帧不合法则关闭 1003 并产生 `CAMERA_FRAME_INVALID` system event。

## 9. 命令状态机与安全语义

### 9.1 通用状态机

```text
媒体类型/大小/JSON/Idempotency-Key gate 失败 ──> HTTP 错误（无 command）
合法 gate 后的字段/状态/安全校验失败 ───────> rejected

accepted ──ROS 调用开始──> executing ──完成──────> succeeded
    │                         ├─确定失败──────────> failed
    │                         ├─到 endpoint 时限──> timed_out
    │                         └─紧停/stop/替代────> cancelled
    ├─紧停/stop 在执行前─────────────────────────> cancelled
    └─到 endpoint 时限───────────────────────────> timed_out
```

gate 失败不进入命令状态机，也不能伪造 rejected 记录。terminal 状态为 succeeded/failed/timed_out/cancelled/rejected，不能再转换。每次转换必须在 SQLite 命令记录提交后，才发送 `command.status`；WebSocket 发送失败不回滚命令。`result` 是 endpoint 特定 JSON，例如 mission_id/task_id/latch_revision/scenario_revision；失败对象固定为 `{"code":str,"message":str,"retryable":bool}`。

Gateway 接受请求不等于 ROS 操作成功。Service 的 `accepted=true`、Action goal accepted、`ManualVelocityStatus.ACCEPTED` 和 HTTP 202 都只能使命令进入或保持 executing；只有第 9.4 节的 endpoint 专用权威终态条件全部满足后才可 succeeded。到时限后 timed_out，即使底层随后成功也不改 terminal 状态，而是记录 `LATE_RESULT_IGNORED` system event 并通过新快照反映真实状态。客户端不得仅凭 202 或 ROS 受理回复改变业务真值。

### 9.2 任务与导航冲突

- 同一时刻只允许一个活动 mission 和一个 Nav2 goal。新的风险重排仅改变后续任务；若风险达到紧急等级，任务模块取消当前普通 Nav2 goal、把安全观察任务置于队首并重新调用 Nav2。
- `pause`、`stop`、`return-home` 和紧停可取消 Nav2；取消原因写入旧命令/任务。普通 navigation goal 不得抢占紧急任务，返回 `COMMAND_CONFLICT`。
- 手动模式只消费 `/cmd_vel_manual`；autonomous 模式只消费 `/cmd_vel_nav`；estop 模式只输出零。模式选择在任务安全仲裁器内完成，不允许浏览器或 Nav2 直接控制最终 `/cmd_vel`。
- 手动速度的 HTTP command succeeded 只表示收到 matching `ManualVelocityStatus.APPLIED`：该 twist 已被安全仲裁器选中并至少一次发布为最终 `/cmd_vel`，不保证物理位移已发生。duration 从仲裁器 monotonic/steady clock 的接收时刻开始；到期不创建新 command，而是安全仲裁器自动归零，ROS header stamp 不参与该期限。

### 9.3 紧急停止锁存与复位

紧急停止拥有最高优先级，并且即使数字孪生、风险、Nav2、SQLite、视频或 WebSocket 故障也必须尝试执行。锁存转换的顺序固定为：

1. 原子设置 `emergency_stop_latched=true` 并增加 `latch_revision`；
2. 安全仲裁器选择零速度，立即发布 `/cmd_vel` 零值；
3. 拒绝新普通任务/目标/速度并取消所有可见 Nav2 goal；
4. 取消受影响命令，错误码为 `EMERGENCY_STOP_ACTIVATED`；
5. 持久化可用时记录证据，向 REST/ROS/WS 暴露锁存状态。

复位是单独 endpoint 和 ROS Service，不能由 mission resume、场景 reset、Gateway 重启或重复 start 隐式完成。它使用 compare-and-set 的 `observed_latch_revision` 防止操作者依据旧页面复位。复位成功后不恢复先前速度、goal 或任务，机器人保持零速度和 manual 模式；操作者必须重新明确选择后续动作。

### 9.4 Endpoint 专用权威终态

令 `C` 为当前 command_id，`Rctx/Rstate/Rqueue/Rlatch` 为对应 ROS Service 受理响应返回的最小 revision。Gateway 必须观察到下表全部条件，再原子持久化 succeeded 和 result；任一 Service `accepted=true` 都不能单独满足条件。“Nav2 已清空”表示取得成功/取消结果且任务管理器已清除 goal handle；“零速度已确认”表示任务安全仲裁器在该转换开始后至少一次选中并发布全零最终 `/cmd_vel`。任务管理器只能在这些内部 barrier 完成后发布表中的匹配终态快照，因此 Gateway 不得根据时序或当前速度近似推断 barrier。

| 命令 kind | succeeded 的全部必要条件 | result 至少包含 |
|---|---|---|
| `mission.start` | matching `RunContext`：lifecycle=ACTIVE、transition_command_id=`C`、context_revision≥Rctx；matching `InspectionTaskArray`：同一 run_id/mission_id、route_id 等于请求值、mission_state=RUNNING、transition_command_id=`C`、state_revision≥Rstate、queue_revision≥Rqueue；对应 `ExecuteInspection` goal 已被 executor 受理并处于活动状态。 | `run_id`、`mission_id`、`route_id`、`run_context_revision`、`state_revision`、`queue_revision` |
| `mission.pause` | matching mission/run 快照的 mission_state=PAUSED、transition_command_id=`C`、state_revision≥Rstate、queue_revision≥Rqueue；matching `RunContext` 仍为同一 ACTIVE run 且 context_revision≥Rctx；Nav2 已清空且零速度已确认。 | `run_id`、`mission_id`、`run_context_revision`、`state_revision`、`queue_revision` |
| `mission.resume` | matching mission/run 快照的 mission_state=RUNNING、transition_command_id=`C`、state_revision≥Rstate、queue_revision≥Rqueue；matching `RunContext` 仍为同一 ACTIVE run 且 context_revision≥Rctx；当前 `ExecuteInspection` goal 已由 executor 受理且处于活动状态。 | `run_id`、`mission_id`、`run_context_revision`、`state_revision`、`queue_revision` |
| `mission.stop` | matching mission/run 快照的 mission_state=STOPPED、transition_command_id=`C`、state_revision≥Rstate、queue_revision≥Rqueue；Nav2 已清空且零速度已确认；matching `RunContext` 保留同一 run_id、lifecycle=ENDED、transition_command_id=`C`、context_revision≥Rctx。 | `run_id`、`mission_id`、`run_context_revision`、`state_revision`、`queue_revision` |
| `mission.return_home` | 在同一 run/mission 完整快照中存在唯一 `command_id=C`、task_type=RETURN_HOME 的任务，且该任务 state=SUCCEEDED；快照 state_revision≥Rstate、queue_revision≥Rqueue，matching `RunContext` 仍为同一 ACTIVE run 且 context_revision≥Rctx。 | `run_id`、`mission_id`、`task_id`、`run_context_revision`、`state_revision`、`queue_revision` |
| `navigation.goal` | 在同一 run/mission 完整快照中，Service 返回的 task_id 与 `command_id=C`、task_type=NAVIGATION_GOAL 同时匹配，且该任务 state=SUCCEEDED；快照 state_revision≥Rstate、queue_revision≥Rqueue。 | `run_id`、`mission_id`、`task_id`、`state_revision`、`queue_revision` |
| `robot.manual_velocity` | `/mission/manual_velocity_status` 出现 matching `command_id=C` 的 terminal state=APPLIED；仲裁器此前已验证命令 run_id/context_revision 精确匹配接收时的 ACTIVE RunContext。ACCEPTED 不终结命令。 | `run_id`、`context_revision`、`applied_at`、`duration_s` |
| `robot.emergency_stop` | matching `InspectionTaskArray` 的 transition_command_id=`C`、robot_mode=ESTOP、emergency_stop_latched=true、emergency_stop_latch_revision≥Rlatch、state_revision≥Rstate；Nav2 已清空且零速度已确认。无 run 时使用第 4.1 节的 IDLE/no-run 安全快照，不伪造 run_id。 | `run_id`（可空）、`latch_revision`、`state_revision` |
| `robot.emergency_stop_reset` | matching `InspectionTaskArray` 的 transition_command_id=`C`、robot_mode=MANUAL、emergency_stop_latched=false、emergency_stop_latch_revision≥Rlatch、state_revision≥Rstate；Nav2 仍已清空、零速度已确认，mission state/active task 与复位前锁存快照相同，不得自动 resume。 | `run_id`（可空）、`latch_revision`、`state_revision`、`mode="manual"` |
| `robot.mode` | matching `InspectionTaskArray` 的 transition_command_id=`C`、robot_mode 等于请求 target、state_revision≥Rstate、emergency_stop_latch_revision≥Rlatch；MANUAL 另需 Nav2 已清空与 0.5 s 零速度确认，AUTONOMOUS 另需对应 readiness 无降级。 | `run_id`、`mode`、`state_revision`、`latch_revision` |
| `asset.prioritize` | matching 完整队列含 `command_id=C` 的 INSPECT_ASSET task，asset_id 等于 path，queue_revision≥Rqueue，且其排序符合第 4.1 节；若 cooldown 生效，必须等到实际提交而非 Service accepted。 | `run_id`、`mission_id`、`task_id`、`state_revision`、`queue_revision` |
| `mission.task_edit` | matching task_id 的 QUEUED task 与请求的可编辑字段一致，任务身份不变，queue_revision≥Rqueue、state_revision≥Rstate、transition_command_id=`C`。 | `run_id`、`mission_id`、`task_id`、`state_revision`、`queue_revision` |
| `mission.replan` | matching 队列的 transition_command_id=`C`、queue_revision 严格大于受理前值、state_revision≥Rstate，并已依 hold/cooldown 或 emergency bypass 应用。 | `run_id`、`mission_id`、`state_revision`、`queue_revision` |
| `asset.reinspect` | matching queue 中唯一 command_id=`C` 的新 INSPECT_ASSET task 处于 SUCCEEDED，task_id 与先前 terminal task 均不同，queue_revision≥Rqueue。 | `run_id`、`mission_id`、`task_id`、`state_revision`、`queue_revision` |
| `alert.acknowledge` | matching `/risk/alert_acknowledgements` 含 command_id=`C`、alert_id 等于 path 且 alert_revision≥Ralert；风险级别、分数和 e-stop 不因确认而改变。 | `run_id`、`alert_id`、`risk_revision`、`alert_revision` |
| `evidence.freeze` | QueryEvidence 返回 Gateway 生成的 evidence_id，content_sha256/metadata/run/context 与 matching FreezeEvidence 记录一致，evidence_revision≥Revidence。 | `run_id`、`evidence_id`、`context_revision`、`evidence_revision`、`content_sha256` |
| `service.reconnect` | matching `/diagnostics` 对 allowlisted service 显示 ok，且 health observation 时间晚于 command accepted_at；不得有关键服务重启事件。 | `service_name`、`health_state="ok"` |
| `simulation.scenario` | `/simulation/scenario_state` 中 `name=scenario_id` 的 matching status 具有：run_id 等于受理时 RunContext、command_id=`C`、action 等于请求值、status=`applied`、scenario_revision=受理前观察 revision+1；`start` 或 `trigger` 要求 active=true，`reset` 要求 active=false。 | `run_id`、`scenario_id`、`action`、`scenario_revision`、`active` |
| `diagnostic.generate` | evidence store 的诊断索引含 command_id=`C`、ready status、bundle SHA-256 与 size；report_generator work artifact 必须已由 evidence store 原子发布。 | `diagnostic_id`、`run_id`、`content_sha256`、`size_bytes` |

负向终态也必须由 matching command 证据确定：Service `accepted=false` 或 matching transition 的稳定失败 error_code 使命令 failed；return-home/navigation/reinspection 任务 FAILED 使命令 failed、CANCELLED 使命令 cancelled；ManualVelocityStatus REJECTED/EXPIRED/CANCELLED 分别映射 failed/timed_out/cancelled；scenario status=`failed`、reporting index 的 failed 状态或 reconnect 的 failed health 分别使命令 failed。紧停、stop 或合法替代命令取消在途命令时为 cancelled；在 endpoint 时限前既无匹配正向也无负向证据时才为 timed_out。所有新命令的固定 timeout 分别为 robot.mode/asset.prioritize/task_edit/replan/alert.acknowledge/evidence.freeze 10 s、asset.reinspect 300 s、service.reconnect 30 s、diagnostic.generate 60 s。不匹配 command_id、低于 Service 最小 revision、旧 run 或旧 task 的状态一律只用于快照恢复/审计，不得终结当前命令。

### 9.5 项目计划功能覆盖矩阵

下表把项目计划第 7 章和第 12 章要求的产品操作固定到本文的 ROS、REST/WS 和验收入口。实现时任一行缺少 ROS 合同、Web 合同、命令终态或端到端验收，都不能宣布对应功能完成。

| 项目计划功能 | 权威 ROS 合同 | REST/WS 合同 | 命令终态 | 端到端验收 |
|---|---|---|---|---|
| 巡检 start/pause/resume/stop | `/mission/inspection_tasks`、`/system/run_context`、`ExecuteInspection` | `POST /api/v1/missions/{action}`、`GET /api/v1/missions/current`、`mission.state`、`command.status` | `mission.start`、`mission.pause`、`mission.resume`、`mission.stop` | 第 10、11、12、17 节验证完整 mission 生命周期、900 seconds 完成界限和报告证据 |
| 返航和地图设点 | `/mission/queue_navigation_goal`、`/navigate_to_pose`、`/map`、`/map_updates`、`/plan` | `POST /api/v1/missions/return-home`、`POST /api/v1/navigation/goal`、`GET /api/v1/map`、`map.update`、`navigation.paths` | `mission.return_home`、`navigation.goal` | 第 8、10、11、12 节验证目标合法性、地图 revision、路径和安全边界 |
| 手动/自动切换和手动速度 | `/mission/set_robot_mode`、`/cmd_vel_manual`、`/mission/manual_velocity_status`、`/cmd_vel` | `POST /api/v1/robot/mode`、`POST /api/v1/robot/manual-velocity`、`robot.state` | `robot.mode`、`robot.manual_velocity` | 第 7、9、11 节验证模式 barrier、0.5 s 零速度、deadman、限速和断线禁控 |
| 紧急停止和显式复位 | `/mission/emergency_stop`、`/mission/emergency_stop_reset`、`/cmd_vel`、`/mission/inspection_tasks` | `POST /api/v1/robot/emergency-stop`、`POST /api/v1/robot/emergency-stop/reset`、`robot.state`、`command.status` | `robot.emergency_stop`、`robot.emergency_stop_reset` | 第 7、9、11、12 节验证锁存、复位 CAS、Nav2 清空和断连时仍可触发紧停 |
| 风险驱动优先级、编辑、重规划和复检 | `/risk/assets`、`/risk/alerts`、`/mission/prioritize_asset`、`/mission/edit_inspection_task`、`/mission/replan`、`/mission/request_reinspection` | `POST /api/v1/assets/{asset_id}/prioritize`、`POST /api/v1/missions/{mission_id}/tasks/{task_id}/edit`、`POST /api/v1/missions/{mission_id}/replan`、`POST /api/v1/assets/{asset_id}/reinspect`、`risk.assets`、`mission.changed` | `asset.prioritize`、`mission.task_edit`、`mission.replan`、`asset.reinspect` | 第 10、11、12 节验证 `risk_gain`、hold/cooldown、emergency bypass、combined-risk-obstacle 和稳定排序 |
| 告警确认 | `/risk/acknowledge_alert`、`/risk/alert_acknowledgements`、`/risk/alerts` | `POST /api/v1/alerts/{alert_id}/acknowledge`、`risk.alert_acknowledged` | `alert.acknowledge` | 第 10、11、12、16 节验证确认不降低风险、不解除告警且进入报告 |
| 证据冻结、查询和下载 | `/reporting/freeze_evidence`、`/reporting/query_evidence`、`/reporting/read_evidence_chunk`、`/reporting/store_evidence` | `POST /api/v1/evidence/freeze`、`GET /api/v1/evidence/{evidence_id}`、`GET /api/v1/evidence/{evidence_id}/download`、`evidence.frozen` | `evidence.freeze` | 第 8、11、16、17 节验证 run/time mapping、Range、SHA-256、不可变 ID 和报告反查 |
| 场景触发 | `/scenario_manager/set_parameters_atomically`、`/simulation/scenario_state`、`/simulation/scenario_truth` | `POST /api/v1/simulation/scenario`、`command.status` | `simulation.scenario` | 第 10、11、12 节验证 smoke/gas/meter/unreachable/combined-risk-obstacle 场景必须经 Gateway |
| 报告与诊断包 | `/reporting/readiness`、`/reporting/generate_report`、`/reporting/generate_diagnostic_bundle`、`/reporting/read_evidence_chunk` | `GET /api/v1/reports`、`GET /api/v1/reports/{report_id}/download`、`POST /api/v1/diagnostics/bundles`、`GET /api/v1/diagnostics/{diagnostic_id}/download`、`diagnostic.ready` | `diagnostic.generate`；报告由 mission/reporting readiness 驱动 | 第 11、16、17 节验证 HTML/PDF/evidence ZIP、diagnostic ZIP、ETag、Range 和摘要 |
| 系统状态和非关键服务重连 | `/diagnostics`、`/maintenance/reconnect_noncritical_service` | `GET /api/v1/system/status`、`POST /api/v1/services/{service_name}/reconnect`、`system.health`、`system.event` | `service.reconnect` | 第 11、12、15 节验证 allowlist、关键服务禁重启、健康恢复和降级显示 |

## 10. 稳定错误代码

HTTP status 是协议分类，`code` 是客户端逻辑依据。下表代码在 schema 1 中不得改义；ROS 自定义响应的 `error_code` 使用同一集合，成功时为空字符串。

| HTTP | code | 含义 / 典型恢复 |
|---:|---|---|
| 400 | `BAD_REQUEST` | JSON 语法或请求结构无法读取。 |
| 400 | `INVALID_CURSOR` | 列表 cursor 无效/过期；从第一页重取。 |
| 400 | `INVALID_ACTION` | path action 不在固定集合。 |
| 400 | `INVALID_RANGE` | Range 语法错误、负数、end<start 或包含多个 range。 |
| 400 | `IDEMPOTENCY_KEY_REQUIRED` | 控制请求缺少 header。 |
| 400 | `INVALID_IDEMPOTENCY_KEY` | header 不是规范 UUID。 |
| 403 | `SIMULATION_MODE_REQUIRED` | 真实模式禁止场景控制。 |
| 404 | `COMMAND_NOT_FOUND` | command_id 不存在或不再保留。 |
| 404 | `MISSION_NOT_FOUND` | mission UUID 不存在/不是当前 mission。 |
| 404 | `ROUTE_NOT_FOUND` | route_id 未配置。 |
| 404 | `SCENARIO_NOT_FOUND` | scenario_id 未配置。 |
| 404 | `REPORT_NOT_FOUND` | report_id 不存在。 |
| 404 | `REPORT_FORMAT_NOT_FOUND` | 该报告没有指定格式。 |
| 404 | `EVIDENCE_NOT_FOUND` | evidence_id 不存在。 |
| 404 | `TASK_NOT_FOUND` | task_id 不属于当前 mission。 |
| 404 | `ALERT_NOT_FOUND` | alert_id 不存在。 |
| 404 | `DIAGNOSTIC_NOT_FOUND` | diagnostic_id 不存在。 |
| 404 | `SERVICE_NOT_FOUND` | allowlisted service 尚未配置。 |
| 409 | `IDEMPOTENCY_KEY_REUSED` | 同 key 对应不同请求体。 |
| 409 | `INVALID_STATE_TRANSITION` | 当前 mission/command 状态不允许该动作。 |
| 409 | `COMMAND_CONFLICT` | 与活动紧急/导航/任务命令冲突。 |
| 409 | `MANUAL_MODE_ACTIVE` | 自动目标在 manual 模式被拒绝。 |
| 409 | `MANUAL_MODE_REQUIRED` | 手动速度在非 manual 模式被拒绝。 |
| 409 | `EMERGENCY_STOP_LATCHED` | 锁存期间拒绝普通控制。 |
| 409 | `EMERGENCY_STOP_NOT_LATCHED` | 无锁存可复位。 |
| 409 | `LATCH_REVISION_MISMATCH` | 页面观察 revision 已旧；刷新状态。 |
| 409 | `EMERGENCY_STOP_RESET_UNSAFE` | 速度、Nav2、仲裁器或审计前置条件不安全。 |
| 409 | `SCENARIO_CONFLICT` | 场景状态不允许该切换。 |
| 409 | `STATE_REVISION_MISMATCH` | 机器人模式的 observed state revision 已旧。 |
| 409 | `QUEUE_REVISION_MISMATCH` | 队列操作依据的 revision 已旧；读取 current mission 后重试。 |
| 409 | `RISK_REVISION_MISMATCH` | alert 确认依据的 risk revision 已旧。 |
| 409 | `ALERT_REVISION_MISMATCH` | alert 确认依据的 alert revision 已旧。 |
| 409 | `TASK_NOT_EDITABLE` | task 非 queued 或当前任务不允许人工改写。 |
| 409 | `TASK_TERMINAL` | terminal task 不可编辑。 |
| 409 | `EMERGENCY_TASK_PROTECTED` | emergency 自动安全任务不可编辑。 |
| 409 | `DIAGNOSTIC_ALREADY_GENERATING` | 同一 run 已有诊断包生成中。 |
| 409 | `SERVICE_RECONNECT_IN_PROGRESS` | allowlisted service 已有一次重连在途。 |
| 409 | `REPORT_NOT_READY` | 报告仍生成或已失败。 |
| 409 | `RUN_CONTEXT_MISMATCH` | run_id/生命周期与任务管理器当前 RunContext 不一致；刷新权威快照。 |
| 409 | `EVIDENCE_ID_CONFLICT` | 同一 evidence_id 已绑定不同内容、媒体类型或 canonical metadata；保留原对象。 |
| 413 | `REQUEST_TOO_LARGE` | 请求体超过 64 KiB。 |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | JSON 请求不是 UTF-8 `application/json`。 |
| 416 | `RANGE_NOT_SATISFIABLE` | Range 语法合法但起点超出文件或 suffix_length=0。 |
| 422 | `VALIDATION_FAILED` | 通用字段/范围/未知字段错误。 |
| 422 | `FRAME_ID_INVALID` | ROS/Web frame_id 不符合第 3.4 节固定坐标约定。 |
| 422 | `INVALID_ORIENTATION` | yaw/quaternion 不合法。 |
| 422 | `GOAL_OUTSIDE_MAP` | 目标超出地图。 |
| 422 | `GOAL_OCCUPIED` | 目标栅格不可通行。 |
| 422 | `GOAL_IN_ASSET_COLLISION` | 目标落入膨胀资产碰撞体。 |
| 422 | `GOAL_IN_HAZARD_ZONE` | 目标落入危险区。 |
| 422 | `VELOCITY_LIMIT_EXCEEDED` | 手动速度超限。 |
| 422 | `DEADMAN_REQUIRED` | 非零手动速度缺少 deadman。 |
| 422 | `RESET_CONFIRMATION_REQUIRED` | 紧停复位未显式 confirm。 |
| 422 | `SCENARIO_ACTION_INVALID` | 场景 action 非法。 |
| 422 | `SCENARIO_PARAMETER_INVALID` | 参数不在 allowlist/范围。 |
| 422 | `MODE_INVALID` | mode 不是 manual/autonomous，或试图用 mode endpoint 进入 ESTOP。 |
| 422 | `TASK_EDIT_EMPTY` | edit 请求没有替换字段。 |
| 422 | `PRIORITY_OUT_OF_RANGE` | base priority 超出配置范围。 |
| 422 | `ASSET_NOT_INSPECTABLE` | 配置资产没有合法安全观察点。 |
| 422 | `ALERT_NOTE_INVALID` | 告警确认 note 为空或超过 256 字符。 |
| 422 | `EVIDENCE_SOURCE_INVALID` | freeze source、JPEG 或证据元数据不符合合同。 |
| 422 | `DIAGNOSTIC_REASON_INVALID` | 诊断原因为空或超过 256 字符。 |
| 426 | `WEBSOCKET_SUBPROTOCOL_REQUIRED` | 未协商 `substation.v1`。 |
| 429 | `MANUAL_COMMAND_RATE_EXCEEDED` | 超过 10 请求/s。 |
| 403 | `SERVICE_RECONNECT_FORBIDDEN` | 不在非关键重连 allowlist，或服务属安全关键路径。 |
| 500 | `INTERNAL_ERROR` | 未分类服务器错误；用 trace_id 排查。 |
| 500 | `INTERFACE_VERSION_UNSUPPORTED` | 收到不支持的 ROS/Web 主 schema。 |
| 500 | `CAMERA_FRAME_INVALID` | camera framing/JPEG 连续不合法。 |
| 503 | `NOT_READY` | `/readyz` 强制依赖未就绪。 |
| 503 | `DEPENDENCY_UNAVAILABLE` | 非专用依赖故障。 |
| 503 | `ROBOT_STATE_UNAVAILABLE` | 无合法 robot pose/odom。 |
| 503 | `MISSION_STATE_UNAVAILABLE` | 无一致任务快照。 |
| 503 | `NAVIGATION_UNAVAILABLE` | Nav2/map/TF 安全校验不可用。 |
| 503 | `GAZEBO_UNAVAILABLE` | 场景管理不可用。 |
| 503 | `AUDIT_STORAGE_UNAVAILABLE` | 需要审计的操作无法持久化。 |
| 503 | `REPORT_INDEX_UNAVAILABLE` | 报告索引不可读。 |
| 503 | `REPORT_STORAGE_UNAVAILABLE` | 报告文件不可读。 |
| 503 | `REPORTING_UNAVAILABLE` | reporting readiness 或 report generator 未就绪。 |
| 503 | `EVIDENCE_STORAGE_UNAVAILABLE` | evidence metadata/object 不可查询或读取。 |
| 503 | `TIME_MAPPING_UNAVAILABLE` | run 的已持久化 ROS-time→UTC 映射缺失或不可读。 |
| 503 | `MAP_UNAVAILABLE` | 无合法完整 map 或 map update 无法安全应用。 |
| 503 | `CAMERA_FRAME_UNAVAILABLE` | 无可冻结的当前有效 camera frame。 |
| 503 | `SERVICE_RECONNECT_FAILED` | maintenance supervisor 未能将 allowlisted service 恢复为健康。 |
| 503 | `EMERGENCY_STOP_PATH_UNAVAILABLE` | Gateway 到安全 Service 的优先路径不可用；UI 按危险状态处理。 |
| WS/4009 | `WS_RESYNC_REQUIRED` | replay 不可能；REST 快照后重连。 |
| 命令终态 | `TIMEOUT` | endpoint 时限到达。 |
| 命令终态 | `EMERGENCY_STOP_ACTIVATED` | 命令被紧停取消。 |
| 命令终态 | `MANUAL_COMMAND_REJECTED` | 仲裁器拒绝手动样本且无更专用的稳定 error_code。 |
| 命令终态 | `MANUAL_COMMAND_EXPIRED` | 手动样本在首次 APPLIED 前超过仲裁器 monotonic/steady 接收时刻加 duration_s 的期限。 |
| 命令终态 | `MANUAL_COMMAND_CANCELLED` | 手动样本在首次 APPLIED 前因松键、失焦、断线、紧停或模式变更取消。 |
| 系统事件 | `LATE_RESULT_IGNORED` | terminal 后到达的底层结果，仅审计。 |
| 服务 | `TIME_MAPPING_CONFLICT` | 尝试为同一 run 写入不同锚点映射。 |

## 11. 只读诊断例外

服务器 Foxglove Bridge 可订阅本文件 ROS Topic、TF、地图和图像，供开发者在 Foxglove Web 中只读排障；它不是 `REST /api/v1` 或 `WS /ws/*` 的一部分，不承诺产品 schema、频率、replay、命令状态或浏览器兼容性。部署必须关闭 Bridge 的发布、Service 调用和 Action goal 能力，浏览器只连接服务器 Bridge 而不直连 DDS。Foxglove 不可用不得影响产品 Web、任务、风险或证据链；Gateway/Nginx 不可用时也不得把 Foxglove 改造成控制替代路径。
